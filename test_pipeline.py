"""
端到端联调测试脚本 — 不依赖 Redis/Celery，直接在当前进程内运行完整流水线。

测试内容：
  Phase 1: 排盘计算 → structured_data.md → HTML 报告
  Phase 2: AI 分析（通义千问）→ p2a_planets.md → 重建 HTML

用法：
  python test_pipeline.py
"""
import sys
import os
import json
import time
import tempfile

sys.stdout.reconfigure(encoding='utf-8')

# ── 设置路径 ──────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = SCRIPT_DIR   # test_pipeline.py 在项目根目录

VEDIC_SCRIPTS = os.path.join(
    PROJECT_ROOT, "skills", "vedic-astrology",
    "vedic-astrology-redskill", "scripts"
)

# 强制把 scripts 目录加到 sys.path 最前面
for p in [VEDIC_SCRIPTS, PROJECT_ROOT, os.path.join(PROJECT_ROOT, "backend")]:
    if p not in sys.path:
        sys.path.insert(0, p)

print(f"VEDIC_SCRIPTS = {VEDIC_SCRIPTS}")
print(f"scripts 目录存在: {os.path.isdir(VEDIC_SCRIPTS)}")
print(f"engine.py 存在: {os.path.isfile(os.path.join(VEDIC_SCRIPTS, 'engine.py'))}")

# 临时输出目录
OUTPUT_DIR = os.path.join(tempfile.gettempdir(), "vedic_test_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)
print(f"输出目录: {OUTPUT_DIR}\n")


def phase1_test():
    """Phase 1：排盘计算 + 格式化 + HTML 报告。"""
    print("=" * 60)
    print("Phase 1：排盘计算")
    print("=" * 60)

    # 使用样本盘：2005-12-14 10:28 上海 男
    t0 = time.time()
    print("  计算星盘（engine.calculate_full_chart）…")
    from engine import calculate_full_chart
    chart = calculate_full_chart(
        2005, 12, 14, 10, 28,
        31.2304, 121.4737,
        tz_str="Asia/Shanghai",
        d60_consent=True,
        time_precision_level=1,
    )
    t1 = time.time()
    print(f"  ✓ 排盘完成，耗时 {t1-t0:.1f}s")
    print(f"    上升：{chart['lagna']['sign']} {chart['lagna']['degree']:.2f}°")
    print(f"    行星数：{len(chart['planets'])}")

    # 格式化 structured_data.md
    print("\n  格式化 structured_data.md…")
    from formatter import format_structured_data
    meta = {
        "dob": "2005-12-14", "time": "10:28",
        "place": "上海", "lat": 31.2304, "lon": 121.4737,
        "time_precision": "精确到分钟", "time_source": "出生证明",
        "effective_precision": "±分钟级",
    }
    user_info = {"gender": "男", "relationship": "单身"}
    sd_text = format_structured_data(chart, None, meta, user_info)
    sd_path = os.path.join(OUTPUT_DIR, "structured_data.md")
    with open(sd_path, "w", encoding="utf-8") as f:
        f.write(sd_text)
    t2 = time.time()
    print(f"  ✓ structured_data.md 已生成 ({len(sd_text)//1024}KB)，耗时 {t2-t1:.1f}s")

    # 生成 HTML 报告（仅数据层）
    print("\n  生成 HTML 报告（数据层）…")
    from report_builder import (
        find_files, detect_package, SECTION_REGISTRY,
        build_cover, build_blind_review_note, build_toc, build_section, CSS,
    )
    import markdown as md_lib

    lagna_sign = chart["lagna"]["sign"]
    found = find_files(OUTPUT_DIR)
    pkg, desc = detect_package(found, "cn")
    ordered = []
    sec_num = 1
    for _p, key, en_t, cn_t, _ in SECTION_REGISTRY:
        if key in found and not key.startswith("synastry_"):
            _, et, ct, content = found[key]
            ordered.append((sec_num, key, en_t, cn_t, content))
            sec_num += 1

    cover = build_cover("测试用户", lagna_sign, "男", "单身", pkg, desc, "cn")
    blind = build_blind_review_note("cn")
    toc   = build_toc(ordered, "cn")
    sections = [build_section(f"{n:02d}", cnt if "cn" else ent, c)
                for n, _, ent, cnt, c in ordered]
    footer = '<div class="footer-note">测试报告 &copy; Vedic Astrology</div>'
    html = (f'<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">'
            f'<style>{CSS}</style></head>'
            f'<body>{cover}{blind}{toc}{"".join(sections)}{footer}</body></html>')

    html_path = os.path.join(OUTPUT_DIR, "report_phase1.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    t3 = time.time()
    print(f"  ✓ HTML 报告已生成 ({len(html)//1024}KB)，耗时 {t3-t2:.1f}s")
    print(f"  📄 {html_path}")

    return chart, sd_text


def phase2_test(sd_text: str):
    """Phase 2：AI 分析（仅测试第一组行星审计）。"""
    print("\n" + "=" * 60)
    print("Phase 2：AI 分析（Sun/Moon 行星审计测试）")
    print("=" * 60)

    api_key = os.getenv(
        "QWEN_API_KEY",
        "sk-ws-H.RXELRHH.wz3i.MEYCIQDUOkbSa0TqqoWsA78AQ1NZ8jsi4cO77HQSIHbaKv0zRQIhAPw2lqDIyA2TQfJ6mg1jKEuFHihPjkYZbbNMlBDLcq6r"
    )
    os.environ["QWEN_API_KEY"] = api_key

    backend_dir = os.path.join(PROJECT_ROOT, "backend")
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    from app.services.ai_client import call_llm
    from app.services.analysis_prompts import planet_group_prompt

    print("  调用通义千问：生成 p2a_planets.md（Sun/Moon 审计）…")
    t0 = time.time()
    sys_p, usr_p = planet_group_prompt("Sun/Moon", ["Sun", "Moon"], sd_text)
    result = call_llm(sys_p, usr_p, max_tokens=3000)
    t1 = time.time()

    p2a_path = os.path.join(OUTPUT_DIR, "p2a_planets.md")
    with open(p2a_path, "w", encoding="utf-8") as f:
        f.write(result)

    print(f"  ✓ p2a_planets.md 已生成 ({len(result)} 字符)，耗时 {t1-t0:.1f}s")
    print()
    # 打印前 600 字符预览
    print("─── 内容预览 ───")
    print(result[:600])
    if len(result) > 600:
        print(f"\n  … （共 {len(result)} 字符，已截断）")

    return result


def rebuild_html():
    """重建 HTML 报告（Phase 1 数据层 + Phase 2 AI 分析合并）。"""
    print("\n" + "=" * 60)
    print("重建 HTML 报告（含 AI 分析章节）")
    print("=" * 60)

    from report_builder import (
        find_files, detect_package, SECTION_REGISTRY,
        build_cover, build_blind_review_note, build_toc, build_section, CSS,
    )

    found = find_files(OUTPUT_DIR)
    print(f"  发现 {len(found)} 个报告章节：{list(found.keys())}")
    pkg, desc = detect_package(found, "cn")

    ordered = []
    sec_num = 1
    for _p, key, en_t, cn_t, _ in SECTION_REGISTRY:
        if key in found and not key.startswith("synastry_"):
            _, et, ct, content = found[key]
            ordered.append((sec_num, key, en_t, cn_t, content))
            sec_num += 1

    cover = build_cover("测试用户", "Capricorn", "男", "单身", pkg, desc, "cn")
    blind = build_blind_review_note("cn")
    toc   = build_toc(ordered, "cn")
    sections = [build_section(f"{n:02d}", cnt, c) for n, _, _e, cnt, c in ordered]
    footer = '<div class="footer-note">测试报告</div>'

    html = (f'<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">'
            f'<style>{CSS}</style></head>'
            f'<body>{cover}{blind}{toc}{"".join(sections)}{footer}</body></html>')

    html_path = os.path.join(OUTPUT_DIR, "report_final.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  ✓ 最终报告已生成 ({len(html)//1024}KB)")
    print(f"  📄 {html_path}")


if __name__ == "__main__":
    total_start = time.time()

    try:
        chart, sd_text = phase1_test()
        phase2_test(sd_text)
        rebuild_html()

        total = time.time() - total_start
        print(f"\n{'='*60}")
        print(f"✅ 完整流水线测试通过！总耗时 {total:.1f}s")
        print(f"📁 所有文件在：{OUTPUT_DIR}")
        print(f"{'='*60}")

    except Exception as e:
        import traceback
        print(f"\n❌ 测试失败: {e}")
        traceback.print_exc()
