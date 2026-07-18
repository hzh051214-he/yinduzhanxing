"""Celery 任务 — 排盘计算 + structured_data 生成 + HTML 报告生成 + PDF 打印。"""
import os
import sys
import json
import traceback
from pathlib import Path
from datetime import datetime

# 主动加载 .env 文件（强制覆盖，确保每次重启都读到最新 key）
_env_file = Path(__file__).parent.parent.parent / ".env"
if _env_file.exists():
    with open(_env_file, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ[_k.strip()] = _v.strip()   # 强制覆盖

from celery import Celery
from celery.utils.log import get_task_logger

from app.core.config import get_settings

settings = get_settings()

# ── 确保 vedic scripts 目录在 sys.path 中（worker 进程需要 import engine/formatter/report_builder）
_vedic_scripts = settings.vedic_scripts_path or str(
    Path(__file__).parent.parent.parent.parent /
    "skills" / "vedic-astrology" / "vedic-astrology-redskill" / "scripts"
)
if _vedic_scripts not in sys.path:
    sys.path.insert(0, _vedic_scripts)
celery_app = Celery(
    "vedic_tasks",
    broker=settings.redis_url,
    backend=settings.redis_url,
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    worker_prefetch_multiplier=1,   # 每个 worker 一次只处理一个排盘（计算密集）
    task_acks_late=True,
)

logger = get_task_logger(__name__)


import redis as redis_lib

# 模块级连接池单例，所有 Celery task 共用，避免每次调用新建 TCP 连接
_redis_pool = None

def _get_redis():
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = redis_lib.ConnectionPool.from_url(settings.redis_url)
    return redis_lib.Redis(connection_pool=_redis_pool)


def _update_reading_status(reading_id: str, status: str, progress: int,
                           error_msg: str = None, report_id: str = None):
    """把状态写入 Redis（Pub/Sub 通知 WebSocket），并持久化到 hash 供轮询。"""
    r = _get_redis()

    payload = {
        "reading_id": reading_id,
        "status": status,
        "progress": progress,
    }
    if error_msg:
        payload["error_msg"] = error_msg
    if report_id:
        payload["report_id"] = report_id

    # Pub/Sub：WebSocket handler 订阅这个 channel
    r.publish(f"reading:{reading_id}:progress", json.dumps(payload))

    # 也写入 hash 供轮询
    r.hset(f"reading:{reading_id}", mapping={k: str(v) for k, v in payload.items()})
    r.expire(f"reading:{reading_id}", 3600)   # 1 小时后清理


@celery_app.task(bind=True, name="tasks.run_reading", max_retries=2)
def run_reading(self, reading_params: dict):
    """
    完整的排盘流水线任务。

    reading_params 包含：
      reading_id, year, month, day, hour, minute, lat, lon, tz_str,
      place_name, gender, relationship, time_precision_level,
      name, lang, modules, d60_consent, output_dir
    """
    reading_id = reading_params["reading_id"]
    output_dir = reading_params.get("output_dir") or str(
        Path(settings.reports_storage_path) / reading_id
    )
    os.makedirs(output_dir, exist_ok=True)

    try:
        # ── Step 1: 天文计算 ────────────────────────────────────
        _update_reading_status(reading_id, "calculating", 5)
        logger.info(f"[{reading_id}] 开始排盘计算")

        from app.services.vedic_engine import calculate_chart, format_structured_data

        chart = calculate_chart(
            year=reading_params["year"],
            month=reading_params["month"],
            day=reading_params["day"],
            hour=reading_params["hour"],
            minute=reading_params["minute"],
            lat=reading_params["lat"],
            lon=reading_params["lon"],
            tz_str=reading_params.get("tz_str", "Asia/Shanghai"),
            d60_consent=reading_params.get("d60_consent"),
            time_precision_level=reading_params.get("time_precision_level", 2),
        )
        _update_reading_status(reading_id, "calculating", 40)
        logger.info(f"[{reading_id}] 排盘计算完成，开始格式化")

        # ── Step 2: 格式化 structured_data.md ───────────────────
        dob = f"{reading_params['year']:04d}-{reading_params['month']:02d}-{reading_params['day']:02d}"
        time_str = f"{reading_params['hour']:02d}:{reading_params['minute']:02d}"
        meta = {
            "dob": dob,
            "time": time_str,
            "place": reading_params.get("place_name", ""),
            "lat": reading_params["lat"],
            "lon": reading_params["lon"],
            "time_precision": ["精确到分钟", "±5分钟内", "±15分钟或更大误差", "不确定"][
                min(reading_params.get("time_precision_level", 2) - 1, 3)
            ],
            "time_source": "用户提供",
            "effective_precision": "±分钟级",
        }
        user_info = {
            "gender": reading_params.get("gender", "未知"),
            "relationship": reading_params.get("relationship", "未知"),
        }
        structured_md = format_structured_data(chart, meta, user_info)
        structured_path = os.path.join(output_dir, "structured_data.md")
        with open(structured_path, "w", encoding="utf-8") as f:
            f.write(structured_md)

        _update_reading_status(reading_id, "formatting", 60)
        logger.info(f"[{reading_id}] structured_data.md 已写入 {structured_path}")

        # ── Step 3: 生成 HTML 报告（Phase 1 数据层）────────────────
        # Phase 1 只有 structured_data.md，直接用它生成一份数据层报告。
        # find_files() 找不到它（不在 SECTION_REGISTRY），所以这里手动构建 HTML。
        from report_builder import (
            build_cover, build_blind_review_note, build_toc,
            build_section, detect_package, CSS,
        )
        import markdown as _md_lib

        lagna_sign = chart.get("lagna", {}).get("sign", "—")
        lang = reading_params.get("lang", "cn")
        name = reading_params.get("name", "")

        # 把 structured_data.md 作为单独的"数据层"章节渲染
        sd_html = _md_lib.markdown(structured_md, extensions=["tables", "fenced_code"])
        section_title = "星盘数据（数据层）" if lang == "cn" else "Chart Data (Data Layer)"
        section_html = (
            '<div class="section">'
            f'<div class="section-header">'
            f'<div class="section-number">01</div>'
            f'<h2>{section_title}</h2>'
            f'</div>{sd_html}</div>'
        )

        pkg  = "核心数据" if lang == "cn" else "Core Data"
        desc = "星盘结构化数据（AI 分析进行中...）" if lang == "cn" else "Chart Data (AI analysis in progress...)"
        cover = build_cover(name, lagna_sign,
                            reading_params.get("gender", "—"),
                            reading_params.get("relationship", "—"),
                            pkg, desc, lang)
        blind = build_blind_review_note(lang)
        # Phase 1 目录只有一项
        toc_items = [f'<li class="toc-part"><span class="toc-num">01</span>{section_title}</li>']
        toc = f'<div class="toc"><h2>{"目录" if lang == "cn" else "Contents"}</h2><ul class="toc-list">{"".join(toc_items)}</ul></div>'
        footer_txt = ("本报告基于传统吠陀占星方法。仅供参考。&copy; Vedic Astrology"
                      if lang == "cn" else
                      "Generated using Vedic astrological methods. For reference only. &copy; Vedic Astrology")
        footer = f'<div class="footer-note">{footer_txt}</div>'

        html_lang = "zh-CN" if lang == "cn" else "en"
        html_content = (
            f'<!DOCTYPE html><html lang="{html_lang}"><head>'
            f'<meta charset="UTF-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1.0">'
            f'<title>吠陀占星 — {name}</title>'
            f'<style>{CSS}</style></head>'
            f'<body>{cover}{blind}{toc}{section_html}{footer}</body></html>'
        )

        html_path = os.path.join(output_dir, "report.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        _update_reading_status(reading_id, "pdf", 75)
        logger.info(f"[{reading_id}] HTML 报告已写入 {html_path}")

        # ── Step 4: 生成 PDF ─────────────────────────────────────
        pdf_path = os.path.join(output_dir, "report.pdf")
        try:
            from app.services.pdf_printer import html_to_pdf_sync
            html_to_pdf_sync(html_content, pdf_path)
            logger.info(f"[{reading_id}] PDF 已生成 {pdf_path}")
        except Exception as pdf_err:
            # PDF 失败不影响 HTML 报告的可用性
            logger.warning(f"[{reading_id}] PDF 生成失败（不影响 HTML）: {pdf_err}")
            pdf_path = None

        # ── 完成 Phase 1 ─────────────────────────────────────────────
        import uuid
        report_id = str(uuid.uuid4())

        # 写报告元数据
        meta_path = os.path.join(output_dir, "report_meta.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({
                "report_id": report_id,
                "reading_id": reading_id,
                "html_path": html_path,
                "pdf_path": pdf_path,
                "structured_md_path": structured_path,
                "lagna": lagna_sign,
                "created_at": datetime.utcnow().isoformat(),
                "phase": 1,
            }, f, ensure_ascii=False, indent=2)

        # 检查是否需要触发 Phase 2（AI 分析）
        # 条件：任意 AI key 已配置（Claude / Qwen / DeepSeek）
        import os as _os
        has_ai_key = bool(
            _os.getenv("ANTHROPIC_API_KEY") or
            _os.getenv("QWEN_API_KEY") or
            _os.getenv("DEEPSEEK_API_KEY")
        )
        if has_ai_key:
            # Phase 1 先报告"数据层报告已就绪"，Phase 2 继续在后台运行
            # 进度从 75 继续向前（不能倒退）
            _update_reading_status(reading_id, "analyzing", 80, report_id=report_id)
            logger.info(f"[{reading_id}] Phase 1 完成，触发 Phase 2 AI 分析")

            from app.tasks.ai_analysis_tasks import run_ai_analysis
            run_ai_analysis.apply_async(args=[{
                "reading_id":  reading_id,
                "output_dir":  output_dir,
                "modules":     reading_params.get("modules", "core"),
                "lang":        reading_params.get("lang", "cn"),
                "name":        reading_params.get("name", ""),
                "lagna":       lagna_sign,
                "gender":      reading_params.get("gender", "—"),
                "status":      reading_params.get("relationship", "—"),
                "d60_consent": reading_params.get("d60_consent"),
            }])
        else:
            # 没有 AI key，Phase 1 结果直接作为最终报告
            _update_reading_status(reading_id, "done", 100, report_id=report_id)
            logger.info(f"[{reading_id}] 流水线完成（仅 Phase 1 数据层），report_id={report_id}")

        return {"status": "analyzing" if has_ai_key else "done", "report_id": report_id}

    except Exception as exc:
        err_msg = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
        logger.error(f"[{reading_id}] 任务失败: {err_msg}")
        _update_reading_status(reading_id, "failed", 0, error_msg=str(exc))
        raise


# 在模块末尾导入 AI 任务，确保 worker 启动时自动注册
# （必须放在 celery_app 定义之后，避免循环导入）
try:
    import app.tasks.ai_analysis_tasks  # noqa: F401  — 注册副作用
except Exception:
    pass

try:
    import app.tasks.portrait_tasks  # noqa: F401  — 注册副作用
except Exception:
    pass

try:
    import app.tasks.synastry_tasks  # noqa: F401  — 注册副作用
except Exception:
    pass
