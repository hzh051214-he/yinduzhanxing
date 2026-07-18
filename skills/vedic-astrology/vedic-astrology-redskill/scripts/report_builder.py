"""
Vedic Report Builder — Universal MD → HTML Pipeline
=====================================================
Supports ALL Vedic skill outputs: Core, Career, Love, Q&A

Usage:
  python report_builder.py <folder> [--name "Name"] [--lagna "Cancer"] [--lang cn]

The script auto-detects which MD files exist and builds accordingly.
It checks both the folder itself and a 'parts/' subfolder.

Supported file patterns:
  Core:    p2a_planets.md, p2b_planets.md, p2c_planets.md,
           p3_divisional.md, p4_houses.md, p5a_life.md, p5b_life.md,
           appendix.md
  Career:  career_part1.md, career_part2.md, career_part3.md
           OR 02_career.md, career_phase*.md, career.md
  Love:    love_part1.md, love_part2.md
           OR 03_love.md, love.md
  Q&A:     qa_*.md (any file starting with qa_)

Requirements:  pip install markdown
"""

import os
import sys
import re
import glob
import argparse

try:
    import markdown
except ImportError:
    print("Installing markdown...")
    os.system(f"{sys.executable} -m pip install markdown -q")
    import markdown

# ── CSS ──
CSS = """
/* 字体回退链：优先系统字体，无需外部网络请求，PDF 生成和离线场景均可用 */
/* Noto Serif SC / Crimson Pro / Inter 在系统安装时会生效；未安装时回退到通用字族 */
/* 如需完整字体显示，可在服务器部署时安装 fonts-noto-cjk 包 */

:root {
  --parchment: #f8f4ec; --parchment-deep: #f0eadb;
  --brown: #5a4636; --brown-light: #7a6652; --brown-muted: #9c8b7a;
  --gold: #b59540; --gold-soft: #d4c07a; --gold-line: #c9a94e;
  --text: #3d352c; --text-light: #5a4e42; --text-muted: #8a7d70;
  --border: #ddd3c2; --border-light: #e8e0d2;
  --table-head-bg: #ede6d8; --table-stripe: #f4efe5;
}
@page { size: A4; margin: 22mm 20mm 24mm 20mm; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, "PingFang SC", "Microsoft YaHei", "Hiragino Sans GB", "Noto Sans SC", sans-serif;
  font-size: 14px; line-height: 1.85; color: var(--text);
  background: #e8e0d0;
  max-width: 780px; margin: 0 auto; padding: 48px 56px;
  background: var(--parchment);
  box-shadow: 0 1px 30px rgba(74,55,40,0.1);
  -webkit-print-color-adjust: exact; print-color-adjust: exact;
}
@media print {
  body { background: var(--parchment); box-shadow: none; padding: 0; max-width: none; font-size: 10.5pt; }
  .no-print { display: none; }
  .section-header, thead th { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  table { font-size: 8pt !important; }
}

.cover {
  page-break-after: always; min-height: 100vh;
  display: flex; flex-direction: column; justify-content: center; align-items: center;
  position: relative; padding: 80px 20px 60px; text-align: center;
}
.cover-top {
  color: var(--gold); font-family: 'Inter', sans-serif;
  font-size: 10px; font-weight: 600;
  letter-spacing: 4px; text-transform: uppercase; margin-bottom: 40px;
}
.cover h1 {
  font-family: "Noto Serif SC", "Songti SC", serif;
  font-size: 52px; font-weight: 700;
  color: var(--brown); line-height: 1.3; margin-bottom: 6px;
  border-bottom: none; padding-bottom: 0;
}
.cover .cover-accent {
  font-family: "Noto Serif SC", serif;
  font-size: 28px; font-weight: 400; color: var(--gold);
  letter-spacing: 6px; margin-bottom: 12px;
}
.cover .cover-ornament {
  width: 60px; height: 1px; background: var(--gold-line); margin: 28px auto;
}
.cover .subtitle {
  font-size: 14px; color: var(--text-muted); font-weight: 400;
  letter-spacing: 1px; margin-bottom: 0;
}
.cover-meta {
  margin-top: auto; padding-top: 0; width: 100%; text-align: left;
  border-top: 1px solid var(--border-light); padding-top: 24px;
}
.cover-meta-grid {
  display: grid; grid-template-columns: 1fr 1fr; gap: 6px 40px;
  font-size: 12px; color: var(--text-muted);
}
.cover-meta-grid div { display: flex; gap: 8px; align-items: baseline; padding: 4px 0; }
.cover-meta-grid dt { font-weight: 500; color: var(--brown-muted); font-size: 11px; min-width: 55px; flex-shrink: 0; }
.cover-meta-grid dd { margin: 0; color: var(--text-light); }

.toc { page-break-after: always; padding: 40px 0; }
.toc h2 {
  font-family: "Noto Serif SC", serif; font-size: 22px; color: var(--brown);
  margin-bottom: 24px; padding-bottom: 10px; border-bottom: 1px solid var(--border);
  font-weight: 600;
}
.toc-list { list-style: none; }
.toc-list li {
  padding: 8px 0; border-bottom: 1px dashed var(--border-light);
  display: flex; align-items: center;
  font-size: 14px;
}
.toc-num {
  display: inline-block; min-width: 32px; margin-right: 12px;
  font-size: 11px; font-weight: 600; color: var(--gold);
  letter-spacing: 0.04em; flex-shrink: 0;
}
.toc-section { font-weight: 500; color: var(--brown); }
.toc-list li.toc-part {
  background: var(--parchment-deep); color: var(--brown); padding: 10px 16px;
  margin: 4px -16px; border-radius: 3px; border: none; border-bottom: none;
  font-weight: 600; font-size: 14px;
}

.section { page-break-before: always; }
.section:first-of-type { page-break-before: auto; }
.section-header {
  border-left: 3px solid var(--gold-line);
  color: var(--brown); padding: 12px 22px; margin: 0 0 28px;
}
.section-header .section-number {
  color: var(--gold); font-family: 'Inter', sans-serif;
  font-size: 10px; font-weight: 600; letter-spacing: 3px; text-transform: uppercase;
}
.section-header h2 {
  font-family: "Noto Serif SC", serif; font-size: 21px; font-weight: 700;
  margin-top: 2px; border: none; color: var(--brown) !important; padding-bottom: 0;
}

h1 {
  font-family: "Noto Serif SC", "Crimson Pro", serif; font-size: 22px; color: var(--brown);
  margin: 32px 0 14px; font-weight: 600;
}
h2 {
  font-family: "Noto Serif SC", "Crimson Pro", serif; font-size: 18px; color: var(--brown);
  margin: 28px 0 12px; font-weight: 600;
}
h3 {
  font-size: 15px; font-weight: 600; color: var(--brown);
  margin: 22px 0 8px; padding-left: 10px;
  border-left: 2px solid var(--gold-line);
}
h4 { font-size: 14px; font-weight: 600; color: var(--brown-light); margin: 16px 0 6px; }
p { margin: 0 0 12px; text-align: justify; }

table {
  width: 100%; border-collapse: collapse; margin: 10px 0 20px;
  font-size: 12px; line-height: 1.5;
}
thead th {
  background: var(--table-head-bg); color: var(--brown);
  padding: 7px 10px; text-align: left;
  font-weight: 600; font-size: 11px;
  border-bottom: 1.5px solid var(--gold-line);
}
tbody td { padding: 6px 10px; border-bottom: 1px solid var(--border-light); vertical-align: top; }
tbody tr:nth-child(even) { background: var(--table-stripe); }

table:has(th:nth-child(10)) { font-size: 10px; }
table:has(th:nth-child(10)) th,
table:has(th:nth-child(10)) td { padding: 4px 3px; text-align: center; white-space: nowrap; }
table:has(th:nth-child(10)) th:first-child,
table:has(th:nth-child(10)) td:first-child { text-align: left; font-weight: 600; }

blockquote {
  border-left: 2px solid var(--gold-line);
  background: var(--parchment-deep);
  padding: 10px 16px; margin: 14px 0; border-radius: 0 3px 3px 0;
  color: var(--text-light); font-size: 13px;
}
blockquote strong { color: var(--brown); font-style: normal; }

ul, ol { margin: 6px 0 14px 22px; }
li { margin-bottom: 3px; }

strong { color: var(--brown); }
code {
  background: var(--parchment-deep); padding: 1px 4px; border-radius: 2px;
  font-size: 12px; color: var(--brown-light);
  font-family: 'Inter', monospace;
}
pre {
  background: #3d352c; color: #ede6d8; padding: 14px 18px; border-radius: 4px;
  margin: 14px 0; font-size: 11px; line-height: 1.6; overflow-x: auto; white-space: pre-wrap;
}
pre code { background: transparent; border: none; color: inherit; padding: 0; }
hr { border: none; border-top: 1px dashed var(--border-light); margin: 24px 0; }

.page-break { page-break-before: always; }
.footer-note {
  margin-top: 30px; padding-top: 14px; border-top: 1px solid var(--border-light);
  font-size: 10px; color: var(--text-muted); text-align: center;
}

/* 盲审声明框 */
.blind-review {
  page-break-before: always; padding: 48px 40px;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  min-height: 60vh; text-align: center;
  border: 1.5px solid var(--gold-line);
  background: var(--parchment-deep);
}
.blind-review-icon { font-size: 28px; margin-bottom: 16px; opacity: 0.7; }
.blind-review-title {
  font-family: "Noto Serif SC", "Crimson Pro", serif;
  font-size: 18px; font-weight: 700; color: var(--brown);
  letter-spacing: 0.08em; margin-bottom: 20px;
}
.blind-review-body {
  max-width: 480px; font-size: 12.5px; color: var(--text-light);
  line-height: 1.9; margin-bottom: 24px;
}
.blind-review-body strong { color: var(--brown); }
.blind-review-rule {
  max-width: 480px; font-size: 11px; color: var(--text-muted);
  line-height: 1.7; border-top: 1px dashed var(--border); padding-top: 16px;
}
"""

# ── Section definitions ──
# Each entry: (priority, canonical_key, en_title, cn_title, filename_patterns)
# priority 决定报告章节顺序（数字越小越靠前）
# 文件名模式支持多个别名，按顺序匹配第一个存在的文件
SECTION_REGISTRY = [
    # ── 第一部分：核心审计总览 ──────────────────────────────────────
    (10, "core",      "Part I: Core Audit",                    "第一部分：核心审计",
     ["01_core.md", "p1_data.md", "p1_basics.md", "core.md"]),

    # ── 第二部分：行星审计（P1-P12，按信号等级逐颗分析） ──────────────
    (15, "planets_a", "Part II-A: Planets (Sun / Moon)",       "第二部分A：行星审计（日 / 月）",
     ["p2a_planets.md"]),
    (17, "planets_b", "Part II-B: Planets (Mars / Mercury)",   "第二部分B：行星审计（火 / 水）",
     ["p2b_planets.md"]),
    (19, "planets_c", "Part II-C: Planets (Jupiter / Venus)",  "第二部分C：行星审计（木 / 金）",
     ["p2c_planets.md"]),
    (21, "planets_d", "Part II-D: Planets (Saturn / Rahu / Ketu)", "第二部分D：行星审计（土 / 罗 / 计）",
     ["p2d_planets.md"]),
    # 兼容旧版单文件行星审计
    (20, "planets",   "Part II: Planetary Audit (P1-P12)",     "第二部分：行星审计（P1-P12）",
     ["02_planets.md", "p2_planets.md", "planets.md"]),

    # ── 第三部分：分盘交叉分析 ─────────────────────────────────────
    (28, "d9",        "Part III-A: D9 Navamsha",               "第三部分A：D9灵魂盘（婚姻 · 内核品质）",
     ["p3a_d9.md"]),
    (30, "divisional","Part III-B: Divisional Cross-Analysis", "第三部分B：D10 / D4 / D5 分盘交叉",
     ["p3b_divisional.md", "p3_divisional.md", "03_d9.md", "p3_d9.md", "d9.md"]),
    (33, "d30_analysis", "Part III-C: D30 Hardship Analysis",  "第三部分C：D30逆境盘",
     ["d30_analysis.md", "trimsamsa.md"]),
    (35, "d60_karma",    "Part III-D: D60 Karma Analysis",     "第三部分D：D60业力盘",
     ["d60_karma.md", "shashtiamsa.md", "karma.md"]),
    (37, "karma_dasha",  "Part III-E: Multi-System Timing",    "第三部分E：多系统大运共振",
     ["karma_dasha.md", "multi_dasha.md", "shoola_narayana.md"]),
    (39, "d11_analysis", "Part III-F: D11 Deep Transformation","第三部分F：D11深度转化盘",
     ["d11_analysis.md", "ekadasamsha.md"]),

    # ── 第四部分：宫位诊断（12宫逐宫分析） ─────────────────────────
    (42, "houses_a",  "Part IV-A: Houses 1–6",                 "第四部分A：宫位诊断（1–6宫）",
     ["p4a_houses.md"]),
    (44, "houses",    "Part IV-B: Houses 7–12",                "第四部分B：宫位诊断（7–12宫）",
     ["p4b_houses.md", "04_houses.md", "p4_houses.md", "houses.md"]),

    # ── 第五部分：人生架构十大板块 ──────────────────────────────────
    (50, "life",      "Part V: Life Architecture",             "第五部分：人生架构总结（板块 1–5）",
     ["05_life.md", "p5a_life.md", "p5_life.md", "life.md"]),
    (52, "life2",     "Part V (cont.): Life Architecture",     "第五部分（续）：人生架构总结（板块 6–10）",
     ["05b_life.md", "p5b_life.md", "life2.md"]),

    # ── 第六部分：事业深度分析 ─────────────────────────────────────
    # 支持两套命名：career_part*.md（新统一命名）和 career_phase*.md（旧命名）
    (60, "career1",   "Part VI: Career — Portrait & Narrative","第六部分：事业（一）画像与叙事",
     ["career_part1.md", "career_phase12.md", "career_phase1_2.md"]),
    (62, "career2",   "Part VI (cont.): Career — Strategy",   "第六部分（续）：事业（二）战略决策",
     ["career_part2.md", "career_phase3.md"]),
    (64, "career3",   "Part VI (cont.): Career — Risk",        "第六部分（续）：事业（三）风险与箴言",
     ["career_part3.md", "career_phase4a.md", "career_phase4.md"]),
    (66, "career4",   "Part VI (cont.): Career — Appendix",    "第六部分（续）：事业（四）关键数据",
     ["career_phase4b.md"]),
    (68, "career5",   "Part VI (cont.): Career — Finale",      "第六部分（续）：事业（五）箴言与终局",
     ["career_phase4c.md"]),
    # 兼容旧版单文件
    (70, "career",    "Part VI: Career Architecture",          "第六部分：事业架构",
     ["02_career.md", "06_career.md", "career.md"]),

    # ── 第七部分：感情深度分析 ─────────────────────────────────────
    # 支持两套命名：love_part*.md（新统一命名）和 love_step*.md（旧命名）
    (75, "love1",     "Part VII: Love — Body & Timeline",      "第七部分：感情（一）体质报告与时间轴",
     ["love_part1.md", "love_step1.md"]),
    (77, "love2",     "Part VII (cont.): Love — Advice",       "第七部分（续）：感情（二）建议与时机",
     ["love_part2.md", "love_step2.md"]),
    (79, "love3",     "Part VII (cont.): Love — Data",         "第七部分（续）：感情（三）关键数据",
     ["love_part3.md", "love_step3.md"]),
    # 兼容旧版单文件
    (82, "love",      "Part VII: Love & Marriage",             "第七部分：感情与婚姻",
     ["03_love.md", "07_love.md", "love.md"]),
    # 真爱画像（感情分析附加模块）
    (84, "true_love_portrait", "Part VII+: True Love Portrait", "第七部分+：真爱画像（正缘外貌气质 · AI绘图Prompt）",
     ["true_love_portrait.md"]),

    # ── 附录（必须在所有正文章节之后） ──────────────────────────────
    (95, "appendix",  "Technical Appendix",                   "技术附录（Dasha速查 · P1-P12参数表）",
     ["appendix.md"]),
    # Q&A 通过 glob 动态收集，priority 最高以确保最末
    (100, "qa",       "Appendix: Q&A",                        "附录：追问答疑",
     []),  # handled separately via glob

    # ── 合盘报告专属章节（--type synastry 模式下使用） ──────────────────
    (10,  "synastry_overview", "Part I: Compatibility Overview",     "第一部分：相容性总览（否决检查 · 总分 · Koota明细）",
     ["synastry_overview.md"]),
    (20,  "synastry_jaimini",  "Part II: Jaimini Cross-Analysis",    "第二部分：Jaimini双盘交叉（灵魂层 · 深层信号）",
     ["synastry_jaimini.md"]),
    (30,  "synastry_advice",   "Part III: Advice & Conclusion",      "第三部分：综合建议与结论",
     ["synastry_advice.md"]),
]


def find_files(folder):
    """Auto-detect MD files using flexible naming.
    
    Strategy:
      1. Try exact matches from SECTION_REGISTRY
      2. Dynamic scan: find any p*_*.md not yet matched, group by prefix
      3. Glob for qa_*.md
    """
    found = {}  # canonical_key -> (priority, en_title, cn_title, content)
    matched_files = set()  # track which files are already matched

    # Pass 1: exact matches from registry
    for priority, key, en_title, cn_title, patterns in SECTION_REGISTRY:
        if not patterns:
            continue
        for pat in patterns:
            path = os.path.join(folder, pat)
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    found[key] = (priority, en_title, cn_title, f.read())
                matched_files.add(pat)
                print(f"  + {pat} -> {key}")
                break

    # Pass 2: dynamic scan for p*_*.md files not yet matched
    # Groups: p1->core, p2->planets, p3->divisional, p4->houses, p5->life
    PREFIX_MAP = {
        "p2": (20, "planets",    "Part II: Planetary Audit",      "第二部分：行星审计"),
        "p3": (30, "divisional", "Part III: Divisional Analysis",  "第三部分：分盘分析"),
        "p4": (40, "houses",     "Part IV: House Diagnostics",     "第四部分：宫位诊断"),
        "p5": (50, "life",       "Part V: Life Architecture",      "第五部分：人生架构总结"),
    }
    prefix_files = {}  # prefix -> [(filename, content), ...]
    
    all_md = sorted(glob.glob(os.path.join(folder, "p*_*.md")))
    for path in all_md:
        fname = os.path.basename(path)
        if fname in matched_files:
            continue
        # Extract prefix: p2a_xxx.md -> "p2", p3b_yyy.md -> "p3"
        m = re.match(r"(p\d)", fname)
        if m:
            prefix = m.group(1)
            if prefix in PREFIX_MAP:
                if prefix not in prefix_files:
                    prefix_files[prefix] = []
                with open(path, "r", encoding="utf-8") as f:
                    prefix_files[prefix].append((fname, f.read()))
    
    # Merge prefix groups into found (combine multiple files of same prefix)
    for prefix, files in prefix_files.items():
        priority, base_key, en_title, cn_title = PREFIX_MAP[prefix]
        if len(files) == 1:
            fname, content = files[0]
            suffix = re.match(r"p\d(\w?)_", fname)
            key = f"{base_key}_{suffix.group(1)}" if suffix and suffix.group(1) else base_key
            if key not in found:
                sub_label = f" ({suffix.group(1).upper()})" if suffix and suffix.group(1) else ""
                found[key] = (priority, en_title + sub_label, cn_title + sub_label, content)
                print(f"  + {fname} -> {key} (dynamic)")
        else:
            for i, (fname, content) in enumerate(files):
                suffix = re.match(r"p\d(\w?)_", fname)
                sub = suffix.group(1).upper() if suffix and suffix.group(1) else chr(65 + i)
                key = f"{base_key}_{sub.lower()}"
                sub_priority = priority + i
                if key not in found:
                    found[key] = (sub_priority, f"{en_title} ({sub})", f"{cn_title} ({sub})", content)
                    print(f"  + {fname} -> {key} (dynamic)")

    # Pass 3: Q&A glob
    qa_files = sorted(glob.glob(os.path.join(folder, "qa_*.md")))
    if qa_files:
        combined = []
        for qf in qa_files:
            with open(qf, "r", encoding="utf-8") as f:
                combined.append(f"<!-- {os.path.basename(qf)} -->\n{f.read()}")
            print(f"  + {os.path.basename(qf)} -> qa")
        found["qa"] = (100, "Appendix: Q&A", "附录：追问答疑", "\n\n---\n\n".join(combined))

    return found



def detect_package(found, lang="cn"):
    has_core = any(k in found for k in ["core", "planets", "planets_a", "d9", "houses", "houses_a", "life"])
    has_career = any(k in found for k in ["career", "career1", "career2", "career3"])
    has_love = any(k in found for k in ["love", "love1", "love2"])
    has_qa = "qa" in found

    parts = []
    if has_core:    parts.append("Core" if lang == "en" else "核心")
    if has_career:  parts.append("Career" if lang == "en" else "事业")
    if has_love:    parts.append("Love" if lang == "en" else "感情")
    if has_qa:      parts.append("Q&A" if lang == "en" else "答疑")

    if lang == "cn":
        return " + ".join(parts), " + ".join(parts) + " 完整报告"
    return " + ".join(parts), " + ".join(parts) + " Complete Reading"


def build_cover(name, lagna, gender, status, pkg, desc, lang="cn"):
    top = "DATA-DRIVEN VEDIC ASTROLOGY" if lang == "en" else "数据驱动吠陀占星"
    title = "吠陀占星" if lang == "cn" else "Vedic Astrology"
    accent = "完 整 解 读" if lang == "cn" else "Complete Reading"
    L = {
        "cn": ["客户", "上升", "信息", "套餐", "体系", "软件", "大运", "量化"],
        "en": ["Client", "Lagna", "Profile", "Package", "System", "Software", "Dasha", "Metrics"],
    }[lang]
    return f"""
<div class="cover">
  <div class="cover-top">{top}</div>
  <h1>{title}</h1>
  <div class="cover-accent">{accent}</div>
  <div class="cover-ornament"></div>
  <div class="subtitle">{desc}</div>
  <div class="cover-meta"><div class="cover-meta-grid">
    <div><dt>{L[0]}</dt><dd>{name}</dd></div>
    <div><dt>{L[1]}</dt><dd>{lagna}</dd></div>
    <div><dt>{L[2]}</dt><dd>{gender} | {status}</dd></div>
    <div><dt>{L[3]}</dt><dd>{pkg}</dd></div>
    <div><dt>{L[4]}</dt><dd>Parashari Jyotish | KN Rao School</dd></div>
    <div><dt>{L[5]}</dt><dd>Jagannatha Hora v8.0 | Lahiri Ayanamsha</dd></div>
    <div><dt>{L[6]}</dt><dd>Vimsottari (Mahadasha + Antardasha)</dd></div>
    <div><dt>{L[7]}</dt><dd>Shadbala, Ashtakavarga (SAV/BAV), D9 Navamsha</dd></div>
  </div></div>
</div>"""


def build_synastry_cover(p1_name, p2_name, ashtakoota_score, grade, lang="cn"):
    """合盘报告专用封面。"""
    top = "DATA-DRIVEN VEDIC ASTROLOGY" if lang == "en" else "数据驱动吠陀占星"
    if lang == "cn":
        title   = "双盘合参"
        accent  = "相 容 性 分 析"
        desc    = "基于 Ashtakoota 八大 Koota + Jaimini 双盘交叉"
        score_label = "Ashtakoota 总分"
        sys_label   = "体系"
        method_label = "方法"
    else:
        title   = "Synastry Reading"
        accent  = "Compatibility Analysis"
        desc    = "Ashtakoota 8-Koota System + Jaimini Cross-Chart Analysis"
        score_label = "Ashtakoota Score"
        sys_label   = "System"
        method_label = "Method"

    return f"""
<div class="cover">
  <div class="cover-top">{top}</div>
  <h1>{title}</h1>
  <div class="cover-accent">{accent}</div>
  <div class="cover-ornament"></div>
  <div class="subtitle">{desc}</div>
  <div class="cover-meta"><div class="cover-meta-grid">
    <div><dt>Person 1</dt><dd>{p1_name}</dd></div>
    <div><dt>Person 2</dt><dd>{p2_name}</dd></div>
    <div><dt>{score_label}</dt><dd>{ashtakoota_score} / 36 &nbsp; {grade}</dd></div>
    <div><dt>{sys_label}</dt><dd>Parashari Jyotish | KN Rao School</dd></div>
    <div><dt>{method_label}</dt><dd>Ashtakoota (Moon Nakshatra) + Jaimini DK/UL/A7</dd></div>
  </div></div>
</div>"""


def build_blind_review_note(lang="cn"):
    """封面后、目录前的盲审声明页。"""
    if lang == "cn":
        title_txt  = "盲审声明"
        body_txt   = (
            "本报告的所有行星分析结论（行星宫位、尊贵度、Shadbala、大运吉凶、格局判定）"
            "均基于天文计算数据独立推导，<strong>在分析过程中不参考当事人提供的任何个人经历信息</strong>。<br><br>"
            "分析师在生成本报告的核心内容（P1–P12 行星审计、分盘交叉、宫位诊断）时，"
            "仅使用出生日期、时间、地点三项客观数据，以及由此计算得出的星盘参数。"
            "当事人的职业、感情经历、家庭背景等信息不作为推导依据。"
        )
        rule_txt   = (
            "&#9658; 此声明意味着：您可以独立判断报告结论是否符合您的真实经历，"
            "而无需担心分析被您告知的信息所「引导」。<br>"
            "&#9658; 若报告中有多项结论与您的经历相符，这是盘面独立指向的结果，"
            "而非基于您提供的背景信息做出的推断。"
        )
    else:
        title_txt  = "Blind Analysis Declaration"
        body_txt   = (
            "All analytical conclusions in this report &mdash; planetary positions, dignities, Shadbala, "
            "Dasha judgments, and Yoga identification &mdash; were derived solely from astronomical calculations, "
            "<strong>without reference to any personal history information provided by the subject</strong>.<br><br>"
            "The core analysis (P1&ndash;P12 planetary audit, divisional charts, house diagnostics) used only "
            "three objective inputs: birth date, time, and location. Career history, relationships, "
            "family background, and other biographical details were not used as analytical inputs."
        )
        rule_txt   = (
            "&#9658; This means you can evaluate whether the conclusions match your actual life independently, "
            "without concern that the analysis was shaped by information you disclosed.<br>"
            "&#9658; When multiple conclusions align with your experience, they reflect the chart&rsquo;s "
            "independent indications &mdash; not inferences drawn from your stated background."
        )
    return (
        '<div class="blind-review">'
        '<div class="blind-review-icon">&#9878;</div>'
        f'<div class="blind-review-title">{title_txt}</div>'
        f'<div class="blind-review-body">{body_txt}</div>'
        f'<div class="blind-review-rule">{rule_txt}</div>'
        '</div>'
    )


def build_toc(sections, lang="cn"):
    toc_title = "目录" if lang == "cn" else "Table of Contents"
    items = []
    for num, _, en_title, cn_title, _ in sections:
        title = cn_title if lang == "cn" else en_title
        num_str = f"{num:02d}"
        items.append(f'<li class="toc-part"><span class="toc-num">{num_str}</span>{title}</li>')
    return f'<div class="toc"><h2>{toc_title}</h2><ul class="toc-list">{"".join(items)}</ul></div>'



def build_section(num, title, md_text):
    body = markdown.markdown(md_text, extensions=["tables", "fenced_code"])
    return f"""
<div class="section">
  <div class="section-header">
    <div class="section-number">Section {num}</div>
    <h2>{title}</h2>
  </div>
  {body}
</div>"""


def main():
    parser = argparse.ArgumentParser(
        description="Vedic Astrology Report Builder — MD → HTML",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 单人完整报告
  python report_builder.py ./client_folder --name "李明" --lagna "摩羯" --lang cn

  # 单人指定模块
  python report_builder.py ./analysis --name "测试" --include core,career --lang cn

  # 合盘报告（先运行 synastry_formatter.py 生成 MD，再打包）
  python report_builder.py ./synastry_output --type synastry --p1 "甲方" --p2 "乙方" --lang cn
        """)
    parser.add_argument("folder",    help="包含 MD 文件的目录（自动检查 parts/ 子目录）")
    parser.add_argument("--name",    default="Client", help="当事人姓名（单人报告用）")
    parser.add_argument("--lagna",   default="—",      help="上升星座")
    parser.add_argument("--gender",  default="—",      help="性别")
    parser.add_argument("--status",  default="—",      help="当前状态")
    parser.add_argument("--lang",    default="cn",     choices=["cn", "en"], help="语言（默认 cn）")
    parser.add_argument("--output",  default=None,     help="输出 HTML 路径（默认 folder/report.html）")
    parser.add_argument("--include", default=None,
                        help="选择性包含：core,career,love,qa（默认全部）")
    # 合盘专用参数
    parser.add_argument("--type",    default="single", choices=["single", "synastry"],
                        help="报告类型：single（单人）或 synastry（合盘）")
    parser.add_argument("--p1",      default="Person 1", help="合盘甲方姓名（--type synastry 时用）")
    parser.add_argument("--p2",      default="Person 2", help="合盘乙方姓名（--type synastry 时用）")
    args = parser.parse_args()

    folder = args.folder.rstrip("/\\")
    if not os.path.isdir(folder):
        print(f"Error: {folder} is not a directory")
        sys.exit(1)

    # Check for 'parts/' subfolder
    parts_dir = os.path.join(folder, "parts")
    search_dir = parts_dir if os.path.isdir(parts_dir) else folder
    print(f"  Scanning: {search_dir}\n")

    found = find_files(search_dir)

    if not found:
        print(f"\nError: No MD files found in {search_dir}")
        print("  Expected files like: p1_basics.md, career_part1.md, love_part1.md, qa_*.md")
        sys.exit(1)

    # ── 合盘模式：只保留 synastry_* sections ──────────────────────
    is_synastry = (args.type == "synastry")
    if is_synastry:
        synastry_keys = {"synastry_overview", "synastry_jaimini", "synastry_advice"}
        found = {k: v for k, v in found.items() if k in synastry_keys}
        if not found:
            print("\nError: 合盘模式（--type synastry）未找到 synastry_*.md 文件。")
            print("  请先运行：python synastry_formatter.py --p1-name ... --p2-name ... --output-dir .")
            sys.exit(1)
        print(f"  合盘模式：找到 {len(found)} 个合盘章节")

    # ── 单人模式 --include 过滤 ────────────────────────────────────
    if not is_synastry and args.include:
        include_set = set(args.include.lower().split(","))
        group_map = {
            "core": {"core", "planets", "planets_a", "planets_b", "planets_c", "planets_d",
                     "d9", "divisional", "d30_analysis", "d60_karma", "karma_dasha", "d11_analysis",
                     "houses", "houses_a", "life", "life2"},
            "career": {"career", "career1", "career2", "career3", "career4", "career5"},
            "love":   {"love", "love1", "love2", "love3"},
            "qa":     {"qa"},
        }
        allowed_keys = set()
        for g in include_set:
            if g.strip() in group_map:
                allowed_keys |= group_map[g.strip()]
        if allowed_keys:
            found = {k: v for k, v in found.items() if k in allowed_keys}
            print(f"  Filter: --include {args.include} → {len(found)} sections")

    lang = args.lang
    pkg, desc = detect_package(found, lang)
    print(f"\n  Package: {pkg} | Language: {lang}")

    # ── Section 排序：合盘模式只用 synastry_* 定义，单人模式过滤掉 synastry_* ──
    ordered = []
    sec_num = 1
    for priority, key, en_title, cn_title, _ in SECTION_REGISTRY:
        if key not in found:
            continue
        if is_synastry and not key.startswith("synastry_"):
            continue
        if not is_synastry and key.startswith("synastry_"):
            continue
        p, et, ct, content = found[key]
        ordered.append((sec_num, key, en_title, cn_title, content))
        sec_num += 1

    # ── 封面：合盘模式用专用封面 ───────────────────────────────────
    if is_synastry:
        # 从 synastry_overview.md 提取总分（简单扫描）
        overview_content = found.get('synastry_overview', ('', '', '', ''))[3]
        import re
        m = re.search(r'\*\*总分\*\*.*?(\d+)\s*/\s*36', overview_content)
        score_str = m.group(1) if m else '—'
        m2 = re.search(r'\*\*评级\*\*.*?\|.*?([★☆一-鿿 ]+)', overview_content)
        grade_str = m2.group(1).strip() if m2 else '—'
        cover = build_synastry_cover(args.p1, args.p2, score_str, grade_str, lang)
        blind_review = ''   # 合盘报告不需要盲审声明
    else:
        cover = build_cover(args.name, args.lagna, args.gender, args.status, pkg, desc, lang)
        blind_review = build_blind_review_note(lang)

    toc = build_toc(ordered, lang)
    sections_html = []
    for num, key, en_title, cn_title, content in ordered:
        title = cn_title if lang == "cn" else en_title
        num_str = f"{num:02d}"
        sections_html.append(build_section(num_str, title, content))

    footer_cn = """<div class="footer-note">
  本报告基于传统吠陀占星方法（Parashari Jyotish | KN Rao School）。<br>
  每项结论均有量化行星指标支撑。仅供自我反思与战略思考参考。<br>
  &copy; Data-Driven Vedic Astrology</div>"""
    footer_en = """<div class="footer-note">
  Generated using traditional Vedic astrological methods (Parashari Jyotish | KN Rao School).<br>
  Every claim backed by quantified planetary metrics. For self-reflection purposes only.<br>
  &copy; Data-Driven Vedic Astrology</div>"""
    footer = footer_cn if lang == "cn" else footer_en

    html_lang = "zh-CN" if lang == "cn" else "en"
    html = f"""<!DOCTYPE html>
<html lang="{html_lang}"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Vedic Astrology Reading — {args.name}</title>
<style>{CSS}</style></head>
<body>{cover}{blind_review}{toc}{"".join(sections_html)}{footer}</body></html>"""

    out = args.output or os.path.join(folder, "report.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)

    size = os.path.getsize(out) / 1024
    print(f"\n  [OK] Output: {out} ({size:.0f} KB)")
    print(f"  -> Open in browser -> Ctrl+P -> Save as PDF")


if __name__ == "__main__":
    main()
