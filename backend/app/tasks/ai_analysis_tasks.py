"""Phase 2 AI 分析任务。"""
import os
import sys
import json
import traceback
from pathlib import Path

# 主动加载 .env（强制覆盖，确保每次重启都读到最新 key）
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
from app.tasks.reading_tasks import celery_app, _update_reading_status
from app.services.ai_client import call_llm
from app.services.analysis_prompts import (
    planet_group_prompt, d9_audit_prompt, divisional_prompt,
    houses_prompt, life_boards_prompt, career_prompt,
    love_prompt, appendix_prompt,
    d60_karma_prompt, d11_analysis_prompt,
)

settings = get_settings()
logger = get_task_logger(__name__)


# ── 辅助函数 ──────────────────────────────────────────────────────────────

def _read_file(path: str) -> str:
    """安全读取文件，不存在则返回空字符串。"""
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def _write_md(output_dir: str, filename: str, content: str):
    """将 LLM 输出写入 MD 文件。"""
    path = os.path.join(output_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info(f"已写入 {filename} ({len(content)} 字符)")
    return path


def _call_with_log(name: str, system: str, user: str,
                   max_tokens: int = 2000) -> str:
    """调用 LLM 并记录日志。"""
    logger.info(f"[LLM] 开始生成 {name}…")
    result = call_llm(system, user, max_tokens=max_tokens)
    logger.info(f"[LLM] {name} 完成，{len(result)} 字符")
    return result


# ── 主任务 ────────────────────────────────────────────────────────────────

@celery_app.task(bind=True, name="tasks.run_ai_analysis", max_retries=1)
def run_ai_analysis(self, params: dict):
    """
    Phase 2 AI 分析总入口。

    params:
      reading_id: str
      output_dir:  str   (Phase 1 已写入 structured_data.md 的目录)
      modules:     str   逗号分隔: "core" | "core,career" | "core,career,love"
      lang:        str   "cn" | "en"
      name:        str
      lagna:       str
      gender:      str
      status:      str
    """
    reading_id = params["reading_id"]
    output_dir = params["output_dir"]
    modules    = params.get("modules", "core")
    lang       = params.get("lang", "cn")
    d60_consent = params.get("d60_consent")   # 只有 True 时才生成 D60

    structured_data_path = os.path.join(output_dir, "structured_data.md")
    if not os.path.exists(structured_data_path):
        _update_reading_status(reading_id, "failed", 0,
                                error_msg="structured_data.md 不存在，请先运行 Phase 1")
        return

    sd = _read_file(structured_data_path)
    module_list = [m.strip().lower() for m in modules.split(",")]

    try:
        import concurrent.futures

        # ── 行星审计（4组并行，节省约75%等待时间）──────────────────
        _update_reading_status(reading_id, "analyzing", 10)
        logger.info(f"[{reading_id}] 开始并行行星审计")

        planet_groups = [
            ("p2a_planets.md", "Sun/Moon",        ["Sun", "Moon"]),
            ("p2b_planets.md", "Mars/Mercury",     ["Mars", "Mercury"]),
            ("p2c_planets.md", "Jupiter/Venus",    ["Jupiter", "Venus"]),
            ("p2d_planets.md", "Saturn/Rahu/Ketu", ["Saturn", "Rahu", "Ketu"]),
        ]

        def _run_planet_group(args):
            filename, group_name, planets = args
            sys_p, usr_p = planet_group_prompt(group_name, planets, sd)
            content = _call_with_log(filename, sys_p, usr_p, max_tokens=2000)
            _write_md(output_dir, filename, content)
            return content

        planets_parts = ["", "", "", ""]
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(_run_planet_group, g): i
                       for i, g in enumerate(planet_groups)}
            for future in concurrent.futures.as_completed(futures):
                i = futures[future]
                try:
                    planets_parts[i] = future.result()
                except Exception as e:
                    logger.error(f"行星组 {i} 失败: {e}")
                    planets_parts[i] = ""

        planets_content = "\n\n".join(planets_parts)
        _update_reading_status(reading_id, "analyzing", 38)

        # ── D9 审计 + 分盘交叉（并行）────────────────────────────────
        def _run_d9():
            sys_p, usr_p = d9_audit_prompt(sd)
            return _call_with_log("p3a_d9.md", sys_p, usr_p, max_tokens=2000)

        def _run_divisional():
            sys_p, usr_p = divisional_prompt(sd)
            return _call_with_log("p3b_divisional.md", sys_p, usr_p, max_tokens=2000)

        def _run_d60():
            # 仅在用户知情同意且 structured_data 包含 D60 数据时生成
            if d60_consent is not True:
                logger.info("D60 知情同意未授权，跳过 d60_karma.md 生成")
                return None
            sys_p, usr_p = d60_karma_prompt(sd)
            return _call_with_log("d60_karma.md", sys_p, usr_p, max_tokens=2000)

        def _run_d11():
            sys_p, usr_p = d11_analysis_prompt(sd)
            return _call_with_log("d11_analysis.md", sys_p, usr_p, max_tokens=2000)

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            f_d9  = executor.submit(_run_d9)
            f_div = executor.submit(_run_divisional)
            f_d60 = executor.submit(_run_d60)
            f_d11 = executor.submit(_run_d11)

            d9_content = f_d9.result()
            _write_md(output_dir, "p3a_d9.md", d9_content)

            div_content = f_div.result()
            _write_md(output_dir, "p3b_divisional.md", div_content)

            try:
                d60_result = f_d60.result()
                if d60_result is not None:   # None 表示跳过（未授权）
                    _write_md(output_dir, "d60_karma.md", d60_result)
            except Exception as e:
                logger.warning(f"D60 生成失败（不影响主报告）: {e}")

            try:
                _write_md(output_dir, "d11_analysis.md", f_d11.result())
            except Exception as e:
                logger.warning(f"D11 生成失败（不影响主报告）: {e}")

        _update_reading_status(reading_id, "analyzing", 52)

        # ── 宫位诊断（两组并行）──────────────────────────────────────
        def _run_houses_a():
            sys_p, usr_p = houses_prompt("1-6", sd, planets_content)
            return _call_with_log("p4a_houses.md", sys_p, usr_p, max_tokens=2000)

        def _run_houses_b():
            sys_p, usr_p = houses_prompt("7-12", sd, planets_content)
            return _call_with_log("p4b_houses.md", sys_p, usr_p, max_tokens=2000)

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            fa = executor.submit(_run_houses_a)
            fb = executor.submit(_run_houses_b)
            houses_a = fa.result()
            houses_b = fb.result()

        _write_md(output_dir, "p4a_houses.md", houses_a)
        _write_md(output_dir, "p4b_houses.md", houses_b)
        _update_reading_status(reading_id, "analyzing", 65)

        # ── 十大板块（两组并行）+ 技术附录 ─────────────────────────
        all_core = planets_content + houses_a + houses_b

        def _run_life_a():
            sys_p, usr_p = life_boards_prompt("1-5", sd, planets_content, houses_a)
            return _call_with_log("p5a_life.md", sys_p, usr_p, max_tokens=2000)

        def _run_life_b():
            sys_p, usr_p = life_boards_prompt("6-10", sd, planets_content, houses_b)
            return _call_with_log("p5b_life.md", sys_p, usr_p, max_tokens=2000)

        def _run_appendix():
            sys_p, usr_p = appendix_prompt(sd)
            return _call_with_log("appendix.md", sys_p, usr_p, max_tokens=2000)

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            fl_a = executor.submit(_run_life_a)
            fl_b = executor.submit(_run_life_b)
            fa_x = executor.submit(_run_appendix)

            _write_md(output_dir, "p5a_life.md", fl_a.result())
            _write_md(output_dir, "p5b_life.md", fl_b.result())
            _write_md(output_dir, "appendix.md", fa_x.result())

        _update_reading_status(reading_id, "analyzing", 80)

        # ── 事业分析（可选）─────────────────────────────────────────
        if "career" in module_list:
            for phase, filename in [("1-2", "career_part1.md"),
                                     ("3",   "career_part2.md"),
                                     ("4",   "career_part3.md")]:
                sys_p, usr_p = career_prompt(phase, sd, all_core)
                content = _call_with_log(filename, sys_p, usr_p, max_tokens=2000)
                _write_md(output_dir, filename, content)
            _update_reading_status(reading_id, "analyzing", 88)

        # ── 感情分析（可选）─────────────────────────────────────────
        if "love" in module_list:
            for step, filename in [("1", "love_part1.md"),
                                    ("2", "love_part2.md"),
                                    ("3", "love_part3.md")]:
                sys_p, usr_p = love_prompt(step, sd, all_core)
                content = _call_with_log(filename, sys_p, usr_p, max_tokens=2000)
                _write_md(output_dir, filename, content)
            _update_reading_status(reading_id, "analyzing", 92)

        # ── 重新打包 HTML + PDF ──────────────────────────────────────
        _update_reading_status(reading_id, "pdf", 92)
        from app.services.vedic_engine import build_html_report

        html_content = build_html_report(
            output_dir=output_dir,
            name=params.get("name", ""),
            lagna=params.get("lagna", "—"),
            gender=params.get("gender", "—"),
            status=params.get("status", "—"),
            lang=lang,
        )
        html_path = os.path.join(output_dir, "report.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        pdf_path = os.path.join(output_dir, "report.pdf")
        try:
            from app.services.pdf_printer import html_to_pdf_sync
            html_to_pdf_sync(html_content, pdf_path)
        except Exception as pdf_err:
            logger.warning(f"PDF 生成失败（不影响 HTML）: {pdf_err}")
            pdf_path = None

        # 更新 report_meta.json
        meta_path = os.path.join(output_dir, "report_meta.json")
        final_report_id = None
        if os.path.exists(meta_path):
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
            final_report_id = meta.get("report_id")   # 先取出，避免后续变量覆盖
            meta["html_path"] = html_path
            meta["pdf_path"]  = pdf_path
            meta["modules"]   = modules
            meta["phase"]     = 2
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
            # 更新 Redis 索引，加速后续报告查询
            try:
                import redis as _r
                _rc = _r.from_url(settings.redis_url)
                _rc.setex(f"report_idx:{final_report_id}", 86400, meta_path)
            except Exception:
                pass

        # 若 report_id 丢失，暴露明确错误让前端可感知，而非静默卡死在进度页
        if not final_report_id:
            logger.error(f"[{reading_id}] report_meta.json 缺失或无 report_id，任务标记为 failed")
            _update_reading_status(reading_id, "failed", 0,
                                    error_msg="报告元数据丢失，请重新提交排盘")
            return

        _update_reading_status(reading_id, "done", 100,
                                report_id=final_report_id)
        logger.info(f"[{reading_id}] Phase 2 AI 分析完成")

    except Exception as exc:
        err_msg = f"{type(exc).__name__}: {exc}"
        logger.error(f"[{reading_id}] Phase 2 失败: {err_msg}\n{traceback.format_exc()}")
        _update_reading_status(reading_id, "failed", 0, error_msg=err_msg)
        raise
