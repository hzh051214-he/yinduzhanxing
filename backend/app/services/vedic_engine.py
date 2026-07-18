"""封装现有 vedic 脚本的计算服务。

所有脚本调用都在这里集中，FastAPI 和 Celery 都通过这个模块调用计算引擎。
"""
import sys
import os
import hashlib
import json
import tempfile
import shutil
from pathlib import Path
from typing import Optional
import redis

from app.core.config import get_settings


def _ensure_vedic_path():
    """把 vedic scripts 目录加入 sys.path，确保可以 import engine 等模块。"""
    settings = get_settings()
    scripts_path = settings.vedic_scripts_path
    if not scripts_path:
        # 自动推断：backend/ 和 skills/ 在同一父目录下
        base = Path(__file__).parent.parent.parent.parent
        scripts_path = str(
            base / "skills" / "vedic-astrology" / "vedic-astrology-redskill" / "scripts"
        )
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)
    return scripts_path


def _chart_cache_key(year, month, day, hour, minute, lat, lon, tz_str,
                     d60_consent, time_precision_level):
    """根据出生参数生成唯一缓存键。"""
    raw = f"{year}-{month}-{day}-{hour}-{minute}-{lat:.4f}-{lon:.4f}-{tz_str}-{d60_consent}-{time_precision_level}"
    return "chart:" + hashlib.sha256(raw.encode()).hexdigest()


def calculate_chart(
    year: int, month: int, day: int,
    hour: int, minute: int,
    lat: float, lon: float,
    tz_str: str = "Asia/Shanghai",
    d60_consent: Optional[bool] = None,
    time_precision_level: int = 2,
) -> dict:
    """调用 engine.calculate_full_chart()，直接返回结果（暂不缓存）。"""
    _ensure_vedic_path()
    from engine import calculate_full_chart
    return calculate_full_chart(
        year, month, day, hour, minute,
        lat, lon,
        tz_str=tz_str,
        d60_consent=d60_consent,
        time_precision_level=time_precision_level,
        d60_trust_level="auto",
    )


def format_structured_data(chart: dict, meta: dict, user_info: dict) -> str:
    """
    调用 formatter.format_structured_data()，返回完整的 structured_data Markdown 字符串。

    meta 必需 key: dob, time, place, lat, lon
    user_info 必需 key: gender, relationship
    """
    _ensure_vedic_path()
    from formatter import format_structured_data as _fmt
    # formatter 期望的是 gochara_full（完整过运结构）
    # 对引擎实际返回的字段做兼容性补全，避免 formatter 触发 KeyError
    transit_data = _normalize_transit(chart)
    return _fmt(chart, transit_data, meta, user_info)


def _normalize_transit(chart: dict) -> dict:
    """把引擎的 gochara_full 标准化为 formatter 期望的结构。"""
    raw = chart.get("gochara_full") or {}
    if not raw:
        return None

    td = dict(raw)   # 浅拷贝，不修改原始 chart

    # formatter 期望 saturn_covers / jupiter_covers 为列表
    if "saturn_covers" not in td or td["saturn_covers"] is None:
        sat = raw.get("planets", {}).get("Saturn", {})
        td["saturn_covers"] = [sat.get("transit_house")] if sat.get("transit_house") else []
    if "jupiter_covers" not in td or td["jupiter_covers"] is None:
        jup = raw.get("planets", {}).get("Jupiter", {})
        td["jupiter_covers"] = [jup.get("transit_house")] if jup.get("transit_house") else []

    # formatter 期望 double_transit 为列表（引擎已提供，保持）
    if "double_transit" not in td:
        td["double_transit"] = []

    # formatter 访问 sade_sati['moon_sign'], ['saturn_sign'], ['position'], ['status']
    ss = td.get("sade_sati", {})
    if isinstance(ss, str):
        # 引擎有时返回字符串 "inactive"
        td["sade_sati"] = {
            "status":       ss,
            "phase":        "none",
            "moon_sign":    chart.get("planets", {}).get("Moon", {}).get("sign", "—"),
            "saturn_sign":  raw.get("planets", {}).get("Saturn", {}).get("current_sign", "—"),
            "position":     "非Sade Sati",
        }
    elif isinstance(ss, dict):
        td["sade_sati"] = {
            "moon_sign":   ss.get("moon_sign") or chart.get("planets", {}).get("Moon", {}).get("sign", "—"),
            "saturn_sign": ss.get("saturn_sign") or raw.get("planets", {}).get("Saturn", {}).get("current_sign", "—"),
            "position":    ss.get("position") or "非Sade Sati",
            "status":      ss.get("status", "inactive"),
            **ss,
        }

    # formatter 访问 planets[name]['sign'], ['house'], ['cycle']
    # 引擎 gochara_full.planets 有 current_sign / transit_house，但没有 cycle
    planets = td.get("planets", {})
    for name in ["Saturn", "Jupiter", "Rahu", "Ketu"]:
        if name in planets:
            p = dict(planets[name])
            if "sign" not in p:
                p["sign"] = p.get("current_sign", "—")
            if "house" not in p:
                p["house"] = p.get("transit_house", "—")
            if "cycle" not in p:
                # 过运周期说明
                cycles = {"Saturn": "约2.5年/星座", "Jupiter": "约1年/星座",
                          "Rahu": "约1.5年/星座", "Ketu": "约1.5年/星座"}
                p["cycle"] = cycles.get(name, "—")
            planets[name] = p
    td["planets"] = planets

    return td


def build_html_report(
    output_dir: str,
    name: str = "",
    lagna: str = "—",
    gender: str = "—",
    status: str = "—",
    lang: str = "cn",
    include: Optional[str] = None,
) -> str:
    """
    调用 report_builder 生成 HTML 报告，返回 HTML 字符串。

    output_dir 中应已有 structured_data.md 或 p2a_planets.md 等分析文件。
    返回 HTML 内容字符串（不写文件，由调用方决定如何存储）。
    """
    _ensure_vedic_path()
    import sys as _sys
    # report_builder 有顶层 import markdown，需要在正确 path 下
    _sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent /
                            "skills" / "vedic-astrology" / "vedic-astrology-redskill" / "scripts"))
    from report_builder import (
        find_files, detect_package, SECTION_REGISTRY,
        build_cover, build_blind_review_note, build_toc,
        build_section, CSS,
    )
    import markdown

    found = find_files(output_dir)
    if not found:
        raise ValueError(f"output_dir 中未找到任何 MD 报告文件: {output_dir}")

    # --include 过滤
    if include:
        include_set = set(include.lower().split(","))
        group_map = {
            "core": {"core", "planets", "planets_a", "planets_b", "planets_c", "planets_d",
                     "d9", "divisional", "d30_analysis", "d60_karma", "karma_dasha",
                     "d11_analysis", "houses", "houses_a", "life", "life2"},
            "career": {"career", "career1", "career2", "career3", "career4", "career5"},
            "love":   {"love", "love1", "love2", "love3"},
            "qa":     {"qa"},
        }
        allowed = set()
        for g in include_set:
            allowed |= group_map.get(g.strip(), set())
        if allowed:
            found = {k: v for k, v in found.items() if k in allowed}

    pkg, desc = detect_package(found, lang)

    ordered = []
    sec_num = 1
    for _priority, key, en_title, cn_title, _ in SECTION_REGISTRY:
        if key not in found or key.startswith("synastry_"):
            continue
        _p, et, ct, content = found[key]
        ordered.append((sec_num, key, en_title, cn_title, content))
        sec_num += 1

    cover        = build_cover(name, lagna, gender, status, pkg, desc, lang)
    blind_review = build_blind_review_note(lang)
    toc_raw      = build_toc(ordered, lang)

    sections_html = []
    for num, _key, en_title, cn_title, content in ordered:
        title = cn_title if lang == "cn" else en_title
        sec_html = build_section(f"{num:02d}", title, content)
        # 给每个 section 加 id，供目录锚点跳转使用
        sec_html = sec_html.replace('<div class="section">', f'<div class="section" id="sec-{num:02d}">', 1)
        sections_html.append(sec_html)

    # 给目录每项加 href 锚点，把 <li> 内容包进 <a>
    toc = toc_raw
    for num, *_ in ordered:
        num_str = f"{num:02d}"
        old = f'<li class="toc-part"><span class="toc-num">{num_str}</span>'
        new = f'<li class="toc-part"><a class="toc-link" href="#sec-{num_str}"><span class="toc-num">{num_str}</span>'
        toc = toc.replace(old, new, 1)
    toc = toc.replace('</li>', '</a></li>')

    if lang == "cn":
        footer = ('<div class="footer-note">本报告基于传统吠陀占星方法（Parashari Jyotish | KN Rao School）。'
                  '<br>每项结论均有量化行星指标支撑。仅供自我反思与战略思考参考。'
                  '<br>&copy; Data-Driven Vedic Astrology</div>')
    else:
        footer = ('<div class="footer-note">Generated using traditional Vedic astrological methods '
                  '(Parashari Jyotish | KN Rao School).<br>Every claim backed by quantified planetary metrics. '
                  'For self-reflection purposes only.<br>&copy; Data-Driven Vedic Astrology</div>')

    html_lang = "zh-CN" if lang == "cn" else "en"
    extra_css = """
<style>
html { scroll-behavior: smooth; }
.toc-link {
  display: block; text-decoration: none; color: inherit;
  padding: 2px 0; transition: color 0.2s;
}
.toc-link:hover { color: var(--gold, #b59540); }
</style>
"""
    html = (f'<!DOCTYPE html>\n<html lang="{html_lang}"><head><meta charset="UTF-8">\n'
            f'<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
            f'<title>Vedic Astrology Reading — {name}</title>\n'
            f'<style>{CSS}</style>{extra_css}</head>\n'
            f'<body>{cover}{blind_review}{toc}{"".join(sections_html)}{footer}</body></html>')
    return html
