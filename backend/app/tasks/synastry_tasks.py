"""合盘 Celery 任务。"""
import os
import sys
import json
import traceback
import concurrent.futures
from pathlib import Path

# 加载 .env
_env_file = Path(__file__).parent.parent.parent / ".env"
if _env_file.exists():
    with open(_env_file, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ[_k.strip()] = _v.strip()

from celery.utils.log import get_task_logger
from app.tasks.reading_tasks import celery_app, _get_redis
from app.services.ai_client import call_llm
from app.services.synastry_prompts import overview_prompt, jaimini_prompt, advice_prompt

logger = get_task_logger(__name__)


def _update_synastry_status(synastry_id: str, status: str, progress: int,
                             error_msg: str = None, result: dict = None):
    r = _get_redis()
    payload = {"synastry_id": synastry_id, "status": status, "progress": progress}
    if error_msg:
        payload["error_msg"] = error_msg
    if result:
        payload["result"] = json.dumps(result, ensure_ascii=False)

    r.publish(f"synastry:{synastry_id}:progress",
              json.dumps(payload, ensure_ascii=False))
    r.hset(f"synastry:{synastry_id}",
           mapping={k: str(v) for k, v in payload.items()})
    r.expire(f"synastry:{synastry_id}", 3600)


def _ensure_vedic_path():
    scripts = os.environ.get("VEDIC_SCRIPTS_PATH") or str(
        Path(__file__).parent.parent.parent.parent /
        "skills" / "vedic-astrology" / "vedic-astrology-redskill" / "scripts"
    )
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    return scripts


@celery_app.task(bind=True, name="tasks.run_synastry", max_retries=1)
def run_synastry(self, params: dict):
    """
    合盘流水线任务。

    params:
      synastry_id: str
      p1: {year,month,day,hour,minute,lat,lon,tz_str,gender,name,time_precision_level}
      p2: {同上}
      output_dir: str
      lang: str
    """
    synastry_id = params["synastry_id"]
    output_dir  = params["output_dir"]
    lang        = params.get("lang", "cn")
    p1_info     = params["p1"]
    p2_info     = params["p2"]
    p1_name     = p1_info.get("name") or "甲方"
    p2_name     = p2_info.get("name") or "乙方"

    os.makedirs(output_dir, exist_ok=True)

    try:
        _ensure_vedic_path()
        from engine import calculate_full_chart
        from synastry_pyjhora import calculate_synastry
        from synastry_formatter import format_synastry_report

        # ── Step 1: 并行计算两人星盘 ────────────────────────────
        _update_synastry_status(synastry_id, "calculating", 10)
        logger.info(f"[synastry:{synastry_id}] 开始双盘计算")

        def _calc(info):
            return calculate_full_chart(
                info["year"], info["month"], info["day"],
                info["hour"], info["minute"],
                info["lat"], info["lon"],
                tz_str=info.get("tz_str", "Asia/Shanghai"),
                d60_consent=None,
                time_precision_level=info.get("time_precision_level", 2),
                d60_trust_level="auto",
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            f1 = ex.submit(_calc, p1_info)
            f2 = ex.submit(_calc, p2_info)
            chart1 = f1.result()
            chart2 = f2.result()

        _update_synastry_status(synastry_id, "calculating", 35)

        # ── Step 2: 合盘计算 ────────────────────────────────────
        _update_synastry_status(synastry_id, "analyzing", 40)
        logger.info(f"[synastry:{synastry_id}] 合盘计算中")

        # 计算时区偏移
        import pytz
        from datetime import datetime
        def _tz_offset(tz_str):
            try:
                tz = pytz.timezone(tz_str)
                offset = tz.utcoffset(datetime.now()).total_seconds() / 3600
                return offset
            except Exception:
                return 8.0

        person1 = {
            "year": p1_info["year"], "month": p1_info["month"], "day": p1_info["day"],
            "hour": p1_info["hour"], "minute": p1_info["minute"],
            "lat": p1_info["lat"], "lon": p1_info["lon"],
            "tz_offset": _tz_offset(p1_info.get("tz_str", "Asia/Shanghai")),
            "gender": "M" if p1_info.get("gender") in ("男", "M") else "F",
            "chart": chart1,
        }
        person2 = {
            "year": p2_info["year"], "month": p2_info["month"], "day": p2_info["day"],
            "hour": p2_info["hour"], "minute": p2_info["minute"],
            "lat": p2_info["lat"], "lon": p2_info["lon"],
            "tz_offset": _tz_offset(p2_info.get("tz_str", "Asia/Shanghai")),
            "gender": "M" if p2_info.get("gender") in ("男", "M") else "F",
            "chart": chart2,
        }

        synastry_data = calculate_synastry(person1, person2)
        if "error" in synastry_data:
            raise ValueError(f"合盘计算失败：{synastry_data['error']}")

        _update_synastry_status(synastry_id, "analyzing", 50)

        # ── Step 3: 格式化 MD 报告（引擎层）────────────────────
        logger.info(f"[synastry:{synastry_id}] 格式化报告")
        md_paths = format_synastry_report(synastry_data, p1_name, p2_name, output_dir)
        _update_synastry_status(synastry_id, "analyzing", 58)

        # ── Step 4: AI 并行解读三章节 ────────────────────────
        logger.info(f"[synastry:{synastry_id}] AI 解读中")

        p1_gender = p1_info.get("gender", "男")
        p2_gender = p2_info.get("gender", "男")

        def _run_overview():
            sys_p, usr_p = overview_prompt(synastry_data, p1_name, p2_name, p1_gender, p2_gender)
            return call_llm(sys_p, usr_p, max_tokens=2000)

        def _run_jaimini():
            sys_p, usr_p = jaimini_prompt(synastry_data, p1_name, p2_name, p1_gender, p2_gender)
            return call_llm(sys_p, usr_p, max_tokens=1500)

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            fo = ex.submit(_run_overview)
            fj = ex.submit(_run_jaimini)
            overview_text = fo.result()
            jaimini_text  = fj.result()

        _update_synastry_status(synastry_id, "analyzing", 80)

        # 建议章节（依赖前两章结果）
        adv_sys, adv_usr = advice_prompt(
            synastry_data, p1_name, p2_name, p1_gender, p2_gender,
            overview_text, jaimini_text
        )
        advice_text = call_llm(adv_sys, adv_usr, max_tokens=1500)

        # 把 AI 文本追加写入对应 MD 文件
        _append_ai_text(md_paths.get("overview", ""), "\n\n---\n\n## AI 深度解读\n\n" + overview_text)
        _append_ai_text(md_paths.get("jaimini",  ""), "\n\n---\n\n## AI 深度解读\n\n" + jaimini_text)
        _append_ai_text(md_paths.get("advice",   ""), "\n\n---\n\n## AI 综合建议\n\n" + advice_text)

        _update_synastry_status(synastry_id, "pdf", 88)

        # ── Step 5: 打包 HTML ──────────────────────────────────
        from app.services.vedic_engine import _ensure_vedic_path as _evp
        _evp()
        from report_builder import (
            find_files, build_synastry_cover, build_toc, build_section,
            SECTION_REGISTRY, CSS,
        )
        import markdown as _md

        found = find_files(output_dir)
        # 只保留 synastry 相关章节
        synastry_keys = {"synastry_overview", "synastry_jaimini", "synastry_advice"}
        found = {k: v for k, v in found.items() if k in synastry_keys}

        if found:
            ordered = []
            sec_num = 1
            for _pri, key, en_title, cn_title, _ in SECTION_REGISTRY:
                if key not in found:
                    continue
                _p, et, ct, content = found[key]
                ordered.append((sec_num, key, en_title, cn_title, content))
                sec_num += 1

            ashtakoota = synastry_data.get("ashtakoota", {})
            cover = build_synastry_cover(
                p1_name, p2_name,
                ashtakoota.get("total_score", 0),
                ashtakoota.get("grade", ""),
                lang,
            )
            toc_raw = build_toc(ordered, lang)
            toc = toc_raw
            for num, *_ in ordered:
                num_str = f"{num:02d}"
                old = f'<li class="toc-part"><span class="toc-num">{num_str}</span>'
                new = f'<li class="toc-part"><a class="toc-link" href="#sec-{num_str}"><span class="toc-num">{num_str}</span>'
                toc = toc.replace(old, new, 1)
            toc = toc.replace('</li>', '</a></li>')

            sections_html = []
            for num, _key, en_title, cn_title, content in ordered:
                title = cn_title if lang == "cn" else en_title
                sec = build_section(f"{num:02d}", title, content)
                sec = sec.replace('<div class="section">', f'<div class="section" id="sec-{num:02d}">', 1)
                sections_html.append(sec)

            extra_css = "<style>html{scroll-behavior:smooth}.toc-link{display:block;text-decoration:none;color:inherit}.toc-link:hover{color:var(--gold,#b59540)}</style>"
            html = (f'<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">'
                    f'<meta name="viewport" content="width=device-width,initial-scale=1">'
                    f'<title>合盘分析 — {p1_name} × {p2_name}</title>'
                    f'<style>{CSS}</style>{extra_css}</head>'
                    f'<body>{cover}{toc}{"".join(sections_html)}</body></html>')
        else:
            html = f"<html><body><h1>合盘分析 — {p1_name} × {p2_name}</h1><p>数据生成中</p></body></html>"

        html_path = os.path.join(output_dir, "report.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)

        # 写元数据
        import uuid
        report_id  = str(uuid.uuid4())
        meta = {
            "synastry_id": synastry_id,
            "report_id":   report_id,
            "html_path":   html_path,
            "p1_name":     p1_name,
            "p2_name":     p2_name,
            "total_score": synastry_data.get("ashtakoota", {}).get("total_score", 0),
            "grade":       synastry_data.get("ashtakoota", {}).get("grade", ""),
        }
        with open(os.path.join(output_dir, "synastry_meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        # Redis 索引
        try:
            r = _get_redis()
            r.setex(f"synastry_idx:{report_id}", 86400, html_path)
        except Exception:
            pass

        _update_synastry_status(synastry_id, "done", 100, result={
            "report_id":   report_id,
            "p1_name":     p1_name,
            "p2_name":     p2_name,
            "total_score": meta["total_score"],
            "grade":       meta["grade"],
            "html_path":   html_path,
        })
        logger.info(f"[synastry:{synastry_id}] 完成")

    except Exception as exc:
        err_msg = f"{type(exc).__name__}: {exc}"
        logger.error(f"[synastry:{synastry_id}] 失败: {err_msg}\n{traceback.format_exc()}")
        _update_synastry_status(synastry_id, "failed", 0, error_msg=str(exc))
        raise


def _append_ai_text(path: str, text: str):
    if not path or not os.path.exists(path):
        return
    with open(path, "a", encoding="utf-8") as f:
        f.write(text)
