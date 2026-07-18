"""
synastry_formatter.py — 合盘报告格式化器
==========================================
将 synastry_pyjhora.calculate_synastry() 的输出格式化为三个 Markdown 文件，
供 report_builder.py 打包进 HTML 合盘报告。

输出文件：
  synastry_overview.md  — 否决检查 + 总分 + 8项Koota明细
  synastry_jaimini.md   — Jaimini双盘交叉 + 深层信号
  synastry_advice.md    — 综合建议 + 时间轴 + 伦理声明

调用方式：
  python synastry_formatter.py \\
      --p1-name "甲方" --p1-dob 1990-01-15 --p1-time 10:30 --p1-place "Beijing" \\
      --p2-name "乙方" --p2-dob 1992-06-20 --p2-time 14:00 --p2-place "Shanghai" \\
      --output-dir /path/to/output
"""
import os
import sys
import argparse
from datetime import date


# ── Koota 权重说明（供报告内渲染） ────────────────────────────────────
KOOTA_TIER = {
    'Naadi':  ('🔴 最高', '否决', '健康与后代相容性'),
    'Bhakut': ('🟠 高',   '降权', '整体相容和生活品质'),
    'Gana':   ('🟡 中高', '降权', '气质/性情匹配'),
    'Maitri': ('🟢 中',   '—',    '月亮守护星友敌'),
    'Yoni':   ('🟢 中',   '—',    '本性/性格相容'),
    'Tara':   ('🔵 低',   '—',    '命运星宿距离'),
    'Vasiya': ('🔵 低',   '—',    '相互吸引力'),
    'Varna':  ('🔵 最低', '—',    '精神层次'),
}

NAADI_NAMES = {'aadi': 'Aadi（首）', 'madhya': 'Madhya（中）', 'antya': 'Antya（尾）'}


def _dosha_check(koota_scores):
    """按 synastry.md 否决规则，返回 (warnings, alerts) 两个列表。
    warnings = 有否决/降权风险的条目
    alerts   = 需要在总分前置显示的强警告
    """
    warnings = []
    alerts = []

    naadi = koota_scores.get('Naadi', {})
    bhakut = koota_scores.get('Bhakut', {})
    gana = koota_scores.get('Gana', {})

    # Naadi 否决
    if naadi.get('score', -1) == 0:
        alerts.append(
            '🚨 **Naadi Dosha**：双方 Naadi 相同（得 0/8 分）。'
            '传统视为对后代和健康有重大隐患。'
            '即使总分较高，此配对在 Naadi 层面存在否决条件，'
            '建议在充分了解风险后再做决策。'
        )
        warnings.append(('Naadi', 0, 8, '否决'))

    # Bhakut 降权
    if bhakut.get('score', -1) == 0:
        alerts.append(
            '⚠️ **Bhakut Dosha**：双方月亮形成凶象数字对（得 0/7 分）。'
            '影响整体相容和生活品质，建议参考 Jaimini 深层信号进行综合评估。'
        )
        warnings.append(('Bhakut', 0, 7, '降权'))

    # Gana 降权
    if gana.get('score', -1) == 0:
        alerts.append(
            '⚠️ **Gana 不合**：双方气质/性情存在根本性差异（得 0/6 分）。'
            '长期相处磨合成本较高，建议重点观察 Jaimini 层信号。'
        )
        warnings.append(('Gana', 0, 6, '降权'))

    return warnings, alerts


def _render_overview(result, p1_name, p2_name):
    """生成 synastry_overview.md 内容。"""
    lines = []

    ak = result.get('ashtakoota', {})
    ks = ak.get('koota_scores', {})
    total = ak.get('total_score', 0)
    grade = ak.get('grade', '—')
    pct = ak.get('percent', 0)

    p1_nak = result.get('person1_nakshatra', {})
    p2_nak = result.get('person2_nakshatra', {})

    lines.append(f"# 合盘相容性分析：{p1_name} × {p2_name}")
    lines.append("")
    lines.append(f"> **{p1_name}** 月亮星宿：{p1_nak.get('name', '—')} Pada {p1_nak.get('pada', '—')}")
    lines.append(f"> **{p2_name}** 月亮星宿：{p2_nak.get('name', '—')} Pada {p2_nak.get('pada', '—')}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── 否决条件（置顶） ──────────────────────────────────────────────
    _, alerts = _dosha_check(ks)
    if alerts:
        lines.append("## ⚠️ 否决/降权条件（优先级高于总分，请先阅读）")
        lines.append("")
        for a in alerts:
            lines.append(a)
            lines.append("")
        lines.append('> 传统说法"18分以上可接受"的前提是 **Naadi 和 Bhakut 均不为 0**。')
        lines.append("> 若两者任一为 0，此基准线失去参考意义，请以上方警告为主要参考。")
        lines.append("")
        lines.append("---")
        lines.append("")

    # ── 总分评级 ──────────────────────────────────────────────────────
    lines.append("## Ashtakoota 总分与评级")
    lines.append("")
    naadi_score = ks.get('Naadi', {}).get('score', '—')
    bhakut_score = ks.get('Bhakut', {}).get('score', '—')
    lines.append(f"| 项目 | 值 |")
    lines.append(f"|------|-----|")
    lines.append(f"| **总分** | **{total} / 36**（{pct:.0f}%）|")
    lines.append(f"| **评级** | {grade} |")
    lines.append(f"| Naadi（最高优先级）| {naadi_score} / 8 |")
    lines.append(f"| Bhakut（次优先级） | {bhakut_score} / 7 |")
    lines.append("")

    # 高总分陷阱提示
    if total >= 28 and (naadi_score == 0 or bhakut_score == 0):
        lines.append(f"> **⚠️ 高总分陷阱**：总分 {total}/36 表面优秀，")
        if naadi_score == 0 and bhakut_score == 0:
            lines.append("> 但 Naadi + Bhakut 均触发否决/降权，15 分关键项全部缺失，")
            lines.append(f"> 实际有效参考分仅 {total}/21（去除两项后的基准）。")
        elif naadi_score == 0:
            lines.append("> 但 Naadi Dosha 已触发否决条件，此分数具有误导性，")
            lines.append("> 建议以否决警告为主要参考。")
        else:
            lines.append(f"> 但 Bhakut 贡献 0 分（凶象数字对），去除后实际得分 {total}/29，")
            lines.append(f"> 相当于 {total/29*100:.0f}%，评级应降为【需谨慎】。")
        lines.append("")

    lines.append("---")
    lines.append("")

    # ── 8项Koota明细表 ────────────────────────────────────────────────
    lines.append("## 八大 Koota 明细")
    lines.append("")
    lines.append("| Koota | 得分 | 满分 | 优先级 | 否决/降权 | 核心含义 | 结果 |")
    lines.append("|:------|:----:|:----:|:------:|:--------:|:--------|:-----|")
    for k in ['Naadi', 'Bhakut', 'Gana', 'Maitri', 'Yoni', 'Tara', 'Vasiya', 'Varna']:
        entry = ks.get(k, {})
        score = entry.get('score', '—')
        mx = entry.get('max', '—')
        res = entry.get('result', '—')
        tier, veto, desc = KOOTA_TIER.get(k, ('—', '—', '—'))
        lines.append(f"| **{k}** | {score} | {mx} | {tier} | {veto} | {desc} | {res} |")
    lines.append("")

    return '\n'.join(lines)


def _render_jaimini(result, p1_name, p2_name):
    """生成 synastry_jaimini.md 内容。"""
    lines = []
    jc = result.get('jaimini_cross', {})
    signals = jc.get('compatibility_signals', [])
    manglik = jc.get('manglik_note', '')

    lines.append(f"# 深层相容性：Jaimini 双盘交叉")
    lines.append(f"> {p1_name} × {p2_name} — 灵魂层、关系结构、配偶指示星交叉分析")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── 关键指示星对照 ─────────────────────────────────────────────
    lines.append("## 关键指示星对照")
    lines.append("")
    lines.append(f"| 指标 | {p1_name} | {p2_name} |")
    lines.append(f"|:-----|:--------:|:--------:|")
    lines.append(f"| DK（配偶指示星） | {jc.get('dk_p1') or '—'} | {jc.get('dk_p2') or '—'} |")
    lines.append(f"| L7（7宫主） | {jc.get('l7_p1') or '—'} | {jc.get('l7_p2') or '—'} |")
    lines.append(f"| UL（伴侣宫上升） | {jc.get('ul_p1') or '—'} | {jc.get('ul_p2') or '—'} |")
    lines.append(f"| A7（Darapada） | {jc.get('a7_p1') or '—'} | {jc.get('a7_p2') or '—'} |")
    lines.append("")

    # ── 相容信号列表 ───────────────────────────────────────────────
    if signals:
        lines.append("## 双盘交叉信号")
        lines.append("")
        for s in signals:
            lines.append(f"- {s}")
        lines.append("")

    # ── Manglik 说明 ────────────────────────────────────────────────
    if manglik:
        lines.append("## Manglik 状态说明")
        lines.append("")
        lines.append(manglik)
        lines.append("")

    # ── 解读指引 ────────────────────────────────────────────────────
    lines.append("## 解读说明")
    lines.append("")
    lines.append("Jaimini 双盘交叉分析是 Ashtakoota 的**深层补充**，而非替代：")
    lines.append("")
    lines.append("- **✅ 信号**：两盘的 DK/UL/A7 形成正面连接，说明灵魂层和关系结构支持长期发展")
    lines.append("- **ℹ️ 信号**：中性信息，行星落宫但不在感情核心宫位，提供背景参考")
    lines.append("- **⚠️ 信号**：需要特别关注的配置，如 Manglik 单方有、或 DK 落凶宫")
    lines.append("")
    lines.append("> 当 Ashtakoota 总分一般但 Jaimini 信号强时，说明表层磨合有难度但深层契合度高——")
    lines.append("> 适合长期关系，前提是双方有足够耐心渡过初期磨合期。")
    lines.append('> 反之，Ashtakoota 高分但 Jaimini 信号弱，关系可能「相处容易但缺乏深度」。')

    return '\n'.join(lines)


def _render_advice(result, p1_name, p2_name):
    """生成 synastry_advice.md 内容。"""
    lines = []
    ak = result.get('ashtakoota', {})
    ks = ak.get('koota_scores', {})
    total = ak.get('total_score', 0)
    grade = ak.get('grade', '—')
    summary = result.get('summary', '')
    _, alerts = _dosha_check(ks)

    lines.append(f"# 综合建议：{p1_name} × {p2_name}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── 综合摘要 ───────────────────────────────────────────────────
    lines.append("## 综合评估摘要")
    lines.append("")
    if summary:
        lines.append(summary)
        lines.append("")

    lines.append(f"Ashtakoota 总分 **{total}/36**（{grade}），")
    if alerts:
        lines.append("但存在需特别关注的否决/降权条件（见概述报告）。")
    else:
        lines.append("三项核心 Koota（Naadi/Bhakut/Gana）均无否决/降权触发。")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── 优势与挑战 ─────────────────────────────────────────────────
    lines.append("## 相容优势与挑战")
    lines.append("")
    strong = [(k, v) for k, v in ks.items() if v.get('score', 0) == v.get('max', 0)]
    weak = [(k, v) for k, v in ks.items() if v.get('score', 0) == 0]

    if strong:
        lines.append("**优势项（满分 Koota）**：")
        lines.append("")
        for k, v in strong:
            _, _, desc = KOOTA_TIER.get(k, ('—', '—', k))
            lines.append(f"- ✅ **{k}**（满分 {v.get('max', '?')}）：{desc}")
        lines.append("")

    if weak:
        lines.append("**挑战项（0分 Koota）**：")
        lines.append("")
        for k, v in weak:
            _, veto, desc = KOOTA_TIER.get(k, ('—', '—', k))
            tag = f"[{veto}]" if veto != '—' else ''
            lines.append(f"- ❌ **{k}** {tag}：{desc}，需在关系中特别留意")
        lines.append("")

    lines.append("---")
    lines.append("")

    # ── 实践建议 ───────────────────────────────────────────────────
    lines.append("## 实践建议")
    lines.append("")
    lines.append("1. **优先参考 Jaimini 深层信号**（见双盘交叉报告）——")
    lines.append("   Ashtakoota 反映月亮层的即时相容，Jaimini 反映灵魂层的长期契合。")
    lines.append("   两套系统结论一致时，可信度最高。")
    lines.append("")
    lines.append("2. **Dosha 的正确看法**：")
    lines.append("   - Naadi Dosha = 生理/后代层面的根本不合，是**结构性问题**")
    lines.append("   - Bhakut/Gana Dosha = 相处模式和气质差异，可通过双方觉察和努力**部分缓解**")
    lines.append('   - 不存在能完全「化解」Naadi Dosha 的补救方法，了解风险比寻找补救更重要')
    lines.append("")
    lines.append("3. **时间轴参考**：")
    lines.append("   两人的 Mahadasha 共振期（双方都在正面大运期间）是关系发展的最佳窗口。")
    lines.append("   建议在单盘大运分析的基础上，找出双方正面大运重叠的时段。")
    lines.append("")

    # ── 伦理声明 ───────────────────────────────────────────────────
    lines.append("---")
    lines.append("")
    lines.append("## 说明")
    lines.append("")
    lines.append("> 本报告基于传统吠陀占星 Ashtakoota 八大 Koota 计算（KN Rao 体系）。")
    lines.append('> **不做绝对判断**：不说「你们绝对不合适」或「一定要分开」。')
    lines.append("> 占星提供参考视角，最终决定权在当事人。")

    return '\n'.join(lines)


def format_synastry_report(result, p1_name, p2_name, output_dir):
    """将 calculate_synastry() 的结果格式化为三个 MD 文件。

    Parameters
    ----------
    result     : calculate_synastry() 的返回值
    p1_name    : 甲方姓名（显示用）
    p2_name    : 乙方姓名（显示用）
    output_dir : 输出目录（三个 MD 文件写到这里）

    Returns
    -------
    dict: {'overview': path, 'jaimini': path, 'advice': path}
    """
    if 'error' in result:
        raise ValueError(f"synastry 计算结果包含错误：{result['error']}")

    os.makedirs(output_dir, exist_ok=True)

    overview_path = os.path.join(output_dir, 'synastry_overview.md')
    jaimini_path  = os.path.join(output_dir, 'synastry_jaimini.md')
    advice_path   = os.path.join(output_dir, 'synastry_advice.md')

    with open(overview_path, 'w', encoding='utf-8') as f:
        f.write(_render_overview(result, p1_name, p2_name))

    with open(jaimini_path, 'w', encoding='utf-8') as f:
        f.write(_render_jaimini(result, p1_name, p2_name))

    with open(advice_path, 'w', encoding='utf-8') as f:
        f.write(_render_advice(result, p1_name, p2_name))

    return {
        'overview': overview_path,
        'jaimini':  jaimini_path,
        'advice':   advice_path,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='合盘报告格式化器')
    parser.add_argument('--p1-name',    required=True,  help='甲方姓名')
    parser.add_argument('--p1-dob',     required=True,  help='甲方出生日期 YYYY-MM-DD')
    parser.add_argument('--p1-time',    required=True,  help='甲方出生时间 HH:MM')
    parser.add_argument('--p1-place',   required=True,  help='甲方出生地（城市名或"纬度,经度"）')
    parser.add_argument('--p2-name',    required=True,  help='乙方姓名')
    parser.add_argument('--p2-dob',     required=True,  help='乙方出生日期 YYYY-MM-DD')
    parser.add_argument('--p2-time',    required=True,  help='乙方出生时间 HH:MM')
    parser.add_argument('--p2-place',   required=True,  help='乙方出生地')
    parser.add_argument('--output-dir', default='.',    help='输出目录（默认当前目录）')
    parser.add_argument('--tz',         default='Asia/Shanghai', help='时区（默认 Asia/Shanghai）')
    args = parser.parse_args()

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        from synastry_pyjhora import calculate_synastry
        import pytz
        from datetime import datetime
    except ImportError as e:
        print(f"错误：缺少依赖 {e}，请先运行 setup_env.py")
        sys.exit(1)

    CITY_COORDS = {
        'beijing': (39.9042, 116.4074), 'shanghai': (31.2304, 121.4737),
        'guangzhou': (23.1291, 113.2644), 'shenzhen': (22.5431, 114.0579),
        'chengdu': (30.5728, 104.0668), 'hangzhou': (30.2741, 120.1551),
        'nanjing': (32.0603, 118.7969), 'wuhan': (30.5928, 114.3055),
        "xi'an": (34.3416, 108.9398), 'chongqing': (29.5630, 106.5516),
        'mumbai': (19.0760, 72.8777), 'delhi': (28.6139, 77.2090),
    }

    def _parse_person(dob_str, time_str, place_str, tz_str):
        y, m, d = map(int, dob_str.split('-'))
        hh, mm = map(int, time_str.split(':'))
        tz = pytz.timezone(tz_str)
        dt = tz.localize(datetime(y, m, d, hh, mm))
        tz_offset = dt.utcoffset().total_seconds() / 3600.0
        if ',' in place_str:
            lat, lon = map(float, place_str.split(','))
        else:
            key = place_str.lower().strip()
            if key not in CITY_COORDS:
                print(f"未知城市 '{place_str}'，请使用'纬度,经度'格式")
                sys.exit(1)
            lat, lon = CITY_COORDS[key]
        return {'year': y, 'month': m, 'day': d, 'hour': hh, 'minute': mm,
                'lat': lat, 'lon': lon, 'tz_offset': tz_offset}

    p1 = _parse_person(args.p1_dob, args.p1_time, args.p1_place, args.tz)
    p2 = _parse_person(args.p2_dob, args.p2_time, args.p2_place, args.tz)

    print(f"\n计算合盘：{args.p1_name} × {args.p2_name}")
    result = calculate_synastry(p1, p2)

    if 'error' in result:
        print(f"计算失败：{result['error']}")
        sys.exit(1)

    paths = format_synastry_report(result, args.p1_name, args.p2_name, args.output_dir)
    print("\n合盘报告已生成：")
    for k, p in paths.items():
        print(f"  {k}: {p}")
    print(f"\n打包 HTML：")
    print(f"  python report_builder.py {args.output_dir} --type synastry "
          f"--p1 \"{args.p1_name}\" --p2 \"{args.p2_name}\" --lang cn")
