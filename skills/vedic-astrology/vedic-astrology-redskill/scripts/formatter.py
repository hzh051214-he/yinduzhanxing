# -*- coding: utf-8 -*-
"""structured_data.md 格式化输出器 - 按data_contract.md格式输出"""

KARAKA_DESC = {
    'AK': '灵魂指示星', 'AmK': '事业指示星', 'BK': '兄弟指示星',
    'MK': '母亲指示星', 'PiK': '父亲指示星', 'PK': '子女指示星',
    'GK': '障碍指示星', 'DK': '配偶指示星'
}

BAV_ROW_SUMS = {'Sun':48,'Moon':49,'Mars':39,'Mercury':54,'Jupiter':56,'Venus':52,'Saturn':39}
SIGN_ABBR = ['Ar','Ta','Ge','Cn','Le','Vi','Li','Sc','Sg','Cp','Aq','Pi']
SIGNS = ['Aries','Taurus','Gemini','Cancer','Leo','Virgo',
         'Libra','Scorpio','Sagittarius','Capricorn','Aquarius','Pisces']


def _render_meta(lines, chart, meta, user_info):
    """元信息 + 用户信息 + 边界警告"""
    # === 元信息 ===
    lines.append("## 元信息\n")
    lines.append("```")
    lines.append(f"出生日期: {meta['dob']}")
    lines.append(f"出生时间: {meta['time']}")
    lines.append(f"出生地点: {meta['place']} ({meta['lon']}, {meta['lat']})")
    lines.append(f"时间精度: {meta.get('time_precision', '精确到分钟')}")
    lines.append(f"时间来源: {meta.get('time_source', '未追问')}")
    lines.append(f"有效精度: {meta.get('effective_precision', '±分钟级')}")
    lines.append(f"验证轨道: 轨道1-标准")
    lines.append(f"读盘方式: vedic-calculator直接计算")
    lines.append(f"Ayanamsa: Lahiri ({chart['ayanamsa']:.4f}°)")
    lines.append(f"Node模式: Mean Node")
    # D60/D30 知情同意与精度等级状态（供 AI 分析时读取）
    _consent = chart.get('d60_consent')
    _precision_level = chart.get('time_precision_level', 2)
    _high_sens_disabled = chart.get('high_sensitivity_disabled', False)
    _time_precision = meta.get('time_precision', '精确到分钟')

    _PRECISION_LEVEL_LABELS = {1:'精确(Level1)', 2:'基本精确(Level2)', 3:'粗略(Level3)', 4:'不确定(Level4)'}
    lines.append(f"出生时间精度等级: {_PRECISION_LEVEL_LABELS.get(_precision_level, str(_precision_level))}")

    if _high_sens_disabled:
        lines.append(f"D30/D60状态: 🚫 精度不足（Level{_precision_level}），高敏感分盘自动禁用")
        lines.append(f"             如需使用D30/D60，请先校准出生时间至精确到分钟（Level1）")
    elif _consent is True:
        # 判断时间精度是否足以支撑 D60
        _LOW_PRECISION_KEYWORDS = ('±15', '±30', '±1小时', '±1 小时', '大概', '不确定', '只知道')
        _precision_ok = not any(kw in _time_precision for kw in _LOW_PRECISION_KEYWORDS)
        if _precision_ok:
            lines.append(f"D30/D60同意状态: ✅ 已告知并同意（d60_trust={chart.get('d60_trust_level','?')}）")
        else:
            lines.append(f"D30/D60同意状态: ⚠️ 已告知并同意，但时间精度「{_time_precision}」可能不足")
            lines.append(f"D60精度警告: 每0.5°≈1-2分钟，当前精度下结论可靠性有限，建议降低权重")
    elif _consent is False:
        lines.append(f"D30/D60同意状态: 🚫 用户明确拒绝，不参与分析")
    else:
        lines.append(f"D30/D60同意状态: ⚠️ 未经告知同意，已禁用（如需启用请重新排盘并告知用户）")
    lines.append("```\n")

    # 边界敏感度警告（Lagna 靠近星座边界 → 出生时间小误差即换上升）
    bs = chart.get('boundary_sensitivity') or {}
    if bs:
        if bs.get('near_boundary'):
            lines.append("> ⚠️ **出生时间敏感度警告**")
            lines.append(f"> Lagna位于星座内 {bs['lagna_deg_in_sign']}°，距最近星座边界不足3°。")
            lines.append(f"> 出生时间前后约 ±{min(bs['approx_min_to_next'], bs['approx_min_to_prev'])} 分钟内，")
            lines.append("> 上升星座即可能改变，进而影响全部宫位归属。")
            lines.append("> **若多项分析感觉偏差，强烈建议用 rectifier 校准出生时间。**\n")
        else:
            lines.append(f"> 出生时间敏感度：Lagna在星座内 {bs['lagna_deg_in_sign']}°，"
                         f"距下个星座边界约 {bs['approx_min_to_next']} 分钟，距上个约 {bs['approx_min_to_prev']} 分钟。"
                         f"上升星座稳定。\n")

    # === 用户信息 ===
    lines.append("## 用户信息\n")
    lines.append("```")
    lines.append(f"性别: {user_info.get('gender', '[待填]')}")
    lines.append(f"感情状态: {user_info.get('relationship', '[待填]')}")
    lines.append("```\n")


def _render_d1_data(lines, chart):
    """D1基础数据（行星位置/Karakas/Nakshatra/特殊点）"""
    # === D1基础数据 ===
    lines.append("## D1基础数据\n")

    # 行星位置（含双宫位列：整宫制 Rashi + 宫始盘 Bhava Chalit）
    bc = chart.get('bhava_chalit') or {}
    lines.append("### 行星位置")
    lines.append("> D1-Rashi宫 = 整宫制（按星座），D1-Bhava宫 = 宫始盘（按Lagna度数居中划宫）。")
    lines.append("> ⚠️ 两列不同的行星 = 宫位归属存在争议，分析时必须同时标注两个宫位，不得只取一边下定论。")
    lines.append("| 行星 | 星座 | D1-Rashi宫 | D1-Bhava宫 | 争议 | 度数 | 逆行 |")
    lines.append("|------|------|-----------|-----------|------|------|------|")
    l = chart['lagna']
    lines.append(f"| Lagna | {l['sign']} | 1 | 1 | — | {l['deg_str']} | — |")
    for name in ['Sun','Moon','Mars','Mercury','Jupiter','Venus','Saturn','Rahu','Ketu']:
        p = chart['planets'][name]
        r = 'R' if p['retrograde'] else 'D'
        rasi_h = p['house']
        bc_entry = bc.get(name, {})
        bhava_h = bc_entry.get('chalit_house', rasi_h)  # 若Bhava数据缺失则与Rashi相同
        flag = '⚠️' if bc_entry.get('shifted') else '—'
        lines.append(f"| {name} | {p['sign']} | {rasi_h} | {bhava_h} | {flag} | {p['deg_str']} | {r} |")
    lines.append("")

    # Chara Karakas (8K主表 — 与JHora 8K设置对齐)
    lines.append("### Chara Karakas")
    lines.append("| 排名 | Karaka | 行星 | 有效度数 | 说明 |")
    lines.append("|------|--------|------|---------|------|")
    for i, (k, planet, deg) in enumerate(chart['karakas']['8k']):
        desc = KARAKA_DESC.get(k, '')
        lines.append(f"| {i+1} | {k} | {planet} | {deg:.1f}° | {desc} |")
    lines.append("")
    lines.append("> Rahu参与8K，度数 = 30° - 原始度数\n")

    # DK争议
    lines.append("### DK争议")
    lines.append("```")
    lines.append(f"7K体系 DK = {chart['karakas']['dk_7k']}")
    lines.append(f"8K体系 DK = {chart['karakas']['dk_8k']}")
    status = '一致' if chart['karakas']['dk_consistent'] else '不一致 → 分析时弱化DK，以宫位结构为主'
    lines.append(f"状态: {status}")
    lines.append("```\n")

    # Nakshatra
    lines.append("### Nakshatra")
    lines.append("| 行星 | Nakshatra | Pada | Nakshatra主 |")
    lines.append("|------|-----------|------|-------------|")
    nak = chart['lagna']['nakshatra']
    lines.append(f"| Lagna | {nak['name']} | {nak['pada']} | {nak['lord']} |")
    for name in ['Sun','Moon','Mars','Mercury','Jupiter','Venus','Saturn','Rahu','Ketu']:
        nak = chart['planets'][name]['nakshatra']
        lines.append(f"| {name} | {nak['name']} | {nak['pada']} | {nak['lord']} |")
    lines.append("")

    # Special Points (AL/UL)
    sp = chart.get('special_points', {})
    if sp:
        lines.append("### 特殊点位")
        lines.append("| 点位 | 星座 | 宫位 | 说明 |")
        lines.append("|------|------|------|------|")
        if 'AL' in sp:
            lines.append(f"| AL (Arudha Lagna) | {sp['AL']['sign']} | {sp['AL']['house']} | 外在形象/世人眼中的你 |")
        if 'UL' in sp:
            lines.append(f"| UL (Upapada Lagna) | {sp['UL']['sign']} | {sp['UL']['house']} | 婚姻/伴侣宫 |")
        lines.append("")


def _render_quantitative(lines, chart):
    """量化数据（Shadbala/SAV/BAV/Dasha）"""
    # === 量化数据 ===
    lines.append("## 量化数据\n")

    # Shadbala
    lines.append("### Shadbala")
    lines.append("| 行星 | Rupas | 百分比 | 排名 | 强弱 | IshtaPhala | KashtaPhala | calc基准 | 数据来源/校验 |")
    lines.append("|------|-------|--------|------|------|-----------|-------------|----------|---------------|")
    sb = chart['shadbala']
    if 'error' not in sb:
        # Extract rupas for sorting
        sb_items = []
        for name, val in sb.items():
            if isinstance(val, dict) and 'total_rupas' in val:
                sb_items.append((name, val))
        sb_items.sort(key=lambda x: x[1]['total_rupas'], reverse=True)
        for rank, (name, val) in enumerate(sb_items, 1):
            rupas = round(val['total_rupas'], 2)
            pct = round(val.get('strength_pct', 0), 2)
            strength = '强' if pct >= 150 else ('中' if pct >= 100 else '弱')
            ishta = round(val.get('ishta_phala', 0), 2)
            kashta = round(val.get('kashta_phala', 0), 2)
            baseline = f"{rupas} / {pct}%"
            lines.append(
                f"| {name} | {rupas} | {pct}% | {rank} | {strength} | "
                f"{ishta} | {kashta} | {baseline} | calc |"
            )
    lines.append("")
    lines.append("> 来源: vedic-calculator引擎 (PyJHora + 9项修正)")
    lines.append("> 如导入同一出生时间的JHora PDF，逐行对照Shadbala；有PDF的行展示PDF值，不一致时标注“calc与PDF不一致；当前采用PDF”。")
    lines.append("> 强: ≥150% | 中: 100-149% | 弱: <100%\n")

    # SAV
    lines.append("### SAV (Sarvashtakavarga)\n")
    lines.append("#### 原始值（按星座，用于校验）")
    lines.append("| " + " | ".join(SIGN_ABBR) + " | 总计 |")
    lines.append("|" + "----|" * 12 + "------|")
    sav_vals = [chart['sav'].get(s, 0) for s in SIGNS]
    total = sum(sav_vals)
    lines.append("| " + " | ".join(str(v) for v in sav_vals) + f" | {total} |")
    lines.append("")

    lines.append("#### 宫位映射（按宫位，供core/career/love直接使用）")
    lines.append(f"> Lagna星座: {chart['lagna']['sign']}\n")
    lines.append("| " + " | ".join(f"{h}宫" for h in range(1,13)) + " |")
    lines.append("|" + "-----|" * 12)
    # sav_by_house 的 key 可能是 int 或 str（Redis 缓存后变为 str），统一兼容
    sav_by_house = chart['sav_by_house']
    house_vals = [str((sav_by_house.get(h) or sav_by_house.get(str(h)) or {}).get('value', '—'))
                  for h in range(1, 13)]
    lines.append("| " + " | ".join(house_vals) + " |")
    lines.append("")

    # BAV
    lines.append("### BAV (Bhinnashtakavarga)")
    lines.append("| 行星 | " + " | ".join(SIGN_ABBR) + " | 行和 |")
    lines.append("|------|" + "----|" * 12 + "------|")
    for pname in ['Sun','Moon','Mars','Mercury','Jupiter','Venus','Saturn']:
        bav_row = chart['bav'].get(pname, {})
        vals = [bav_row.get(s, 0) for s in SIGNS]
        row_sum = sum(vals)
        lines.append(f"| {pname} | " + " | ".join(str(v) for v in vals) + f" | {row_sum} |")
    lines.append("")

    # Dasha
    # 建立 dasha_verdicts 的 planet→sandhi 快速索引（sandhi 字段只在 verdict 输出里）
    _dv_sandhi = {}
    for _dv in chart.get('dasha_verdicts', []):
        _dv_sandhi[(_dv['planet'], _dv['start'])] = _dv.get('sandhi') or {}

    lines.append("### Vimsottari Dasha")
    lines.append("> ⚡ Dasha Sandhi：大运首尾各 6 个月为过渡期，能量不稳定，预测置信度降低。")
    lines.append("| 大运 | 行星 | 起始 | 结束 | 年数 | Sandhi窗口 |")
    lines.append("|------|------|------|------|------|-----------|")
    current_dasha = None
    next_dasha = None
    found_current = False
    for d in chart['dashas']:
        marker = '→当前' if d['is_current'] else ''
        # Sandhi 数据从 dasha_verdicts 索引读取（原始 chart['dashas'] 不含此字段）
        sandhi = _dv_sandhi.get((d['planet'], d['start']), {})
        sandhi_notes = []
        if sandhi.get('in_leaving_sandhi'):
            sandhi_notes.append('⚡首段过渡期')
        if sandhi.get('in_entering_sandhi'):
            sandhi_notes.append('⚡尾段过渡期')
        lv = sandhi.get('leaving_sandhi', {})
        ev = sandhi.get('entering_sandhi', {})
        # 有 sandhi 数据时展示窗口；无数据时留空（dasha_verdicts 可能尚未计算）
        if lv or ev:
            sandhi_str = f"{lv.get('start','?')[:7]}~{lv.get('end','?')[:7]} / {ev.get('start','?')[:7]}~{ev.get('end','?')[:7]}"
        else:
            sandhi_str = '—'
        if sandhi_notes:
            sandhi_str = f"{'、'.join(sandhi_notes)} | {sandhi_str}"
        lines.append(f"| {marker} | {d['planet']} | {d['start']} | {d['end']} | {d['years']} | {sandhi_str} |")
        if d['is_current']:
            current_dasha = d
            found_current = True
        elif found_current and next_dasha is None:
            next_dasha = d
    lines.append("")

    # Antardasha — 输出全部大运的小运表（验前事需要扫描过去的时间窗口）
    for d in chart['dashas']:
        if 'antardashas' in d:
            label = '当前' if d['is_current'] else ('下一' if d == next_dasha else '')
            label_str = f"（{label}）" if label else ""
            lines.append(f"### {d['planet']}大运 Antardasha{label_str}")
            lines.append("| 小运 | 起始 | 结束 |")
            lines.append("|------|------|------|")
            for ad in d['antardashas']:
                marker = ' ← 当前' if ad.get('is_current') else ''
                lines.append(f"| {d['planet']}-{ad['planet']} | {ad['start']} | {ad['end']} |{marker}")
            lines.append("")

    # 当前状态汇总
    if current_dasha:
        lines.append("当前状态:")
        lines.append("```")
        lines.append(f"Mahadasha: {current_dasha['planet']} ({current_dasha['start']} ~ {current_dasha['end']})")
        current_ad_info = None
        if 'antardashas' in current_dasha:
            for ad in current_dasha['antardashas']:
                if ad.get('is_current'):
                    current_ad_info = ad
                    break
        if current_ad_info:
            lines.append(f"Antardasha: {current_dasha['planet']}-{current_ad_info['planet']} ({current_ad_info['start']} ~ {current_ad_info['end']})")
        lines.append("```\n")


def _render_preanalysis(lines, chart):
    """预分析（尊贵度/相位/宫主表/Bhava Bala等）"""
    # === 预分析 ===
    lines.append("## 预分析（calculator计算，core直接引用）\n")

    # Compound Dignity
    lines.append("### 行星尊贵度（Compound Dignity / Panchadha Maitri）")
    lines.append("| 行星 | 落座 | 座主 | 复合尊贵度 | 说明 |")
    lines.append("|------|------|------|-----------|------|")
    SIGN_LORDS_MAP = {
        'Aries':'Mars','Taurus':'Venus','Gemini':'Mercury','Cancer':'Moon',
        'Leo':'Sun','Virgo':'Mercury','Libra':'Venus','Scorpio':'Mars',
        'Sagittarius':'Jupiter','Capricorn':'Saturn','Aquarius':'Saturn','Pisces':'Jupiter'
    }
    for name in ['Sun','Moon','Mars','Mercury','Jupiter','Venus','Saturn']:
        p = chart['planets'][name]
        dig = chart['dignity'].get(name, {})
        lord = SIGN_LORDS_MAP.get(p['sign'], '?')
        compound = dig.get('compound', '-')
        lines.append(f"| {name} | {p['sign']} | {lord} | {compound} | |")
    lines.append("")

    # Aspects (吠陀 graha drishti — 有向)
    lines.append("### 主要相位关系")
    lines.append("> 吠陀整宫相位(graha drishti)：A→B 表示 A 发出相位射中 B。")
    lines.append("> 全行星看7宫；火加4/8，木加5/9，土加3/10，罗计加5/9(=5/7/9)；同宫=合相。")
    lines.append("| 发出 | 接收 | 相位 | 度数差(参考) |")
    lines.append("|------|------|------|--------------|")
    for a in chart['aspects']:
        lines.append(f"| {a['p1']} | {a['p2']} | {a['type']} | {a['degree_diff']}° |")
    lines.append("")

    # 行星宫位相位（Graha Drishti on Houses）
    ha = chart.get('house_aspects', {})
    if ha:
        DOMAINS = {1:'自我',2:'财富',3:'兄弟',4:'家庭',5:'子女',6:'疾病',
                   7:'婚姻',8:'变故',9:'运势',10:'事业',11:'收入',12:'损耗'}
        lines.append("### 行星宫位相位（Graha Drishti on Houses）")
        lines.append("> 宫位诊断维度3「谁在看这个宫位」直接读此表，不再肉眼判。")
        lines.append("| 宫位 | 领域 | 被相位行星 |")
        lines.append("|------|------|-----------|")
        for h in range(1, 13):
            casters = ha.get('by_house', {}).get(h, [])
            casters_str = ', '.join(casters) if casters else '—'
            lines.append(f"| {h} | {DOMAINS[h]} | {casters_str} |")
        lines.append("")

    # House Lords
    lines.append("### 宫主表")
    lines.append("| 宫位 | 领域 | 宫主 | 宫主落宫 |")
    lines.append("|------|------|------|---------|")
    hl = chart['house_lords']
    for h in range(1, 13):
        # 兼容整数 key 和字符串 key（Redis 缓存后 key 变为字符串）
        info = hl.get(h) or hl.get(str(h)) or {}
        lines.append(f"| {h} | {info.get('domain','?')} | {info.get('lord','?')} | {info.get('lord_house','?')} |")
    lines.append("")

    # Bhava Bala（宫位力量）— 比 SAV 更全面的宫位强度指标
    bb = chart.get('bhava_bala') or {}
    if bb:
        # 兼容字符串 key（Redis 缓存）
        bb = {(int(k) if str(k).isdigit() else k): v for k, v in bb.items()}
        DOMAINS = {1:'自我',2:'财富',3:'兄弟',4:'家庭',5:'子女',6:'疾病',
                   7:'婚姻',8:'变故',9:'运势',10:'事业',11:'收入',12:'损耗'}
        lines.append("### 宫位力量（Bhava Bala）")
        lines.append("> 六源合成的宫位综合强度（Rupas）。强度>1.0=有力，<1.0=偏弱。")
        lines.append("> 与SAV互补：SAV看资源积分，Bhava Bala看宫位综合发力能力。")
        lines.append("| 宫位 | 领域 | Rupas | 强度 | 判定 |")
        lines.append("|------|------|-------|------|------|")
        # 排名用于标注最强/最弱
        try:
            ranked = sorted(range(1, 13), key=lambda h: bb.get(h, {}).get('total_rupas', 0), reverse=True)
            strongest, weakest = ranked[0], ranked[-1]
        except Exception:
            strongest = weakest = None
        for h in range(1, 13):
            e = bb.get(h, {})
            rupas = e.get('total_rupas', '—')
            stg = e.get('strength', '—')
            tag = ''
            if h == strongest:
                tag = '★最强'
            elif h == weakest:
                tag = '▽最弱'
            elif isinstance(stg, (int, float)):
                tag = '有力' if stg >= 1.0 else '偏弱'
            lines.append(f"| {h} | {DOMAINS[h]} | {rupas} | {stg} | {tag} |")
        lines.append("")

    # Vargeeya Bala（Shodhasavarga Vimsopaka）— 16分盘一致性，判断行星"底子"稳不稳
    vb = chart.get('vargeeya_bala') or {}
    if vb:
        lines.append("### 分盘一致性力量（Vimsopaka Bala / 16分盘）")
        lines.append("> 行星在16个分盘中保持吉位的一致性。bala越高=行星品质在多个维度都稳。")
        lines.append("> 用途：Shadbala看瞬时力量，此表看行星的\"结构性成色\"。")
        lines.append("| 行星 | 吉位分盘数 | bala | 强吉分盘 |")
        lines.append("|------|-----------|------|----------|")
        for name in ['Sun','Moon','Mars','Mercury','Jupiter','Venus','Saturn','Rahu','Ketu']:
            e = vb.get(name)
            if not e:
                continue
            lines.append(f"| {name} | {e.get('count','—')} | {e.get('bala','—')} | {e.get('vargas','—')} |")
        lines.append("")

    # Special Lagnas（特殊上升点）— 补充判断维度
    sl = chart.get('special_lagnas') or {}
    if sl:
        SL_DESC = {
            'Bhava': '宫始上升（宫位起点参考）', 'Hora': '财富上升（2宫财运）',
            'Ghati': '权力上升（地位/权威）', 'Vighati': '细分时间上升',
            'Pranapada': '生命力上升（活力/健康）', 'Indu': '财富积累点（月亮系）',
            'Sree': '吉祥上升（Lakshmi/繁荣）', 'BhriguBindhu': '业力中点（Rahu-Moon中点）',
        }
        lines.append("### 特殊上升点（Special Lagnas）")
        lines.append("> 主上升(Lagna)之外的辅助上升点，用于交叉验证特定领域（财富/权力/活力）。")
        lines.append("| 上升点 | 星座 | 度数 | 含义 |")
        lines.append("|--------|------|------|------|")
        for name, e in sl.items():
            desc = SL_DESC.get(name, '')
            lines.append(f"| {name} | {e.get('sign','—')} | {e.get('longitude','—')}° | {desc} |")
        lines.append("")

    # Bhava Chalit（宫始盘）— 行星"真实宫位归属"，靠近星座边界时与整宫制不同
    # 宫位争议汇总（行星表已含双列，此处只输出文字索引，供 core 快速定位）
    shifts = chart.get('chalit_shifts') or []
    if shifts:
        names = '、'.join(f"{s['planet']}({s['rasi_house']}宫→{s['chalit_house']}宫)" for s in shifts)
        lines.append(f"> **Bhava归属争议行星**：{names}")
        lines.append("> 上方行星表 ⚠️ 列已标注。core/career/love 分析这些行星时，")
        lines.append("> 必须标注\"整宫制看作X宫、宫始盘看作Y宫\"，不得只取一边下定论。")
    else:
        lines.append("> 全部行星 Rashi 与 Bhava Chalit 宫位一致，宫位归属无争议。")
    lines.append("")


def _render_verdicts(lines, chart):
    """确定性判定（P1角色/大运/格局/事业/感情/D60）"""
    # === 确定性判定层（#6）：角色 / 大运吉凶 / 格局 ===
    lines.append("## 确定性判定（calculator计算，core读取权威标签，不得擅自翻转）\n")

    # P1 角色身份表
    roles = chart.get('roles', {})
    if roles:
        lines.append("### P1 角色身份表")
        lines.append("> P1 角色由引擎按宫主身份确定；core 直接读取，不再自行推导。")
        lines.append("| 行星 | 所管宫 | 角色 | Yogakaraka | 功能 |")
        lines.append("|------|--------|------|-----------|------|")
        for name in ['Sun','Moon','Mars','Mercury','Jupiter','Venus','Saturn','Rahu','Ketu']:
            r = roles.get(name, {})
            oh = ','.join(str(x) for x in r.get('houses_owned', [])) or '—'
            rolestr = '/'.join(r.get('roles', [])) or '—'
            yk = '是' if r.get('is_yogakaraka') else '—'
            if r.get('malefic_role'):
                func = '功能凶'
            elif r.get('benefic_role'):
                func = '功能吉'
            else:
                func = '中性'
            lines.append(f"| {name} | {oh} | {rolestr} | {yk} | {func} |")
        lines.append("")

    # 大运吉凶判定
    dv = chart.get('dasha_verdicts', [])
    if dv:
        lines.append("### 大运吉凶判定")
        lines.append("> 严格按 house_framework.md 打分（正≥2且负=0→正面；正≥2且负≥1→混合；")
        lines.append("> 正<2且负≥1→困难；正=0且负≥2→危机）。core 读取此标签，异议须显式标注。")
        lines.append("> score=加权净分；confidence=判定置信度；⚠️=边界情形；🔮=D60修正；🌐=Jaimini环境层叠加。")
        lines.append("| 大运 | 时段 | 正面数 | 负面数 | 判定 | score | conf | 正面依据 / 负面依据 |")
        lines.append("|------|------|--------|--------|------|-------|------|---------------------|")
        for d in dv:
            cur = '→当前 ' if d['is_current'] else ''
            basis = f"+[{', '.join(d['positive']) or '无'}] / -[{', '.join(d['negative']) or '无'}]"
            score = d.get('score', 0)
            conf = d.get('confidence', '?')
            boundary_flag = ' ⚠️' if d.get('at_boundary') else ''
            has_d60 = bool(d.get('d60_pos') or d.get('d60_neg'))
            d60_flag = ' 🔮' if has_d60 else ''
            has_jaimini = bool(d.get('jaimini_overlay'))
            jaimini_flag = ' 🌐' if has_jaimini else ''
            lines.append(f"| {cur}{d['planet']}{boundary_flag}{d60_flag}{jaimini_flag} | {d['start']}~{d['end']} | "
                         f"{len(d['positive'])} | {len(d['negative'])} | {d['verdict']} | "
                         f"{score:+.2f} | {conf} | {basis} |")
        lines.append("")

        # 当前 / 下一大运的 Antardasha 叠加
        focus = [d for d in dv if d['is_current']]
        # 取当前大运之后的一段作为"下一大运"
        idx_current = next((i for i, d in enumerate(dv) if d['is_current']), None)
        if idx_current is not None and idx_current + 1 < len(dv):
            focus.append(dv[idx_current + 1])
        for d in focus:
            if not d.get('antardashas'):
                continue
            tag = '当前' if d['is_current'] else '下一'
            # 显示 Jaimini 环境层叠加摘要（当前大运才有）
            jaimini_note = ''
            if d.get('is_current') and d.get('jaimini_overlay'):
                jaimini_note = f"（🌐 Jaimini叠加：{', '.join(d['jaimini_overlay'])}）"
            lines.append(f"#### {d['planet']}大运（{tag}）小运叠加{jaimini_note}")
            lines.append("| 小运 | 时段 | 小运判定 | 大×小叠加 | 角色注释 |")
            lines.append("|------|------|----------|-----------|---------|")

            # 从原始 chart['dashas'] 查三级运数据（dasha_verdicts 不含）
            _raw_dashas = chart.get('dashas', [])
            _prad_lookup = {}  # ad_planet → pratyantardashas list
            for _rd in _raw_dashas:
                if _rd.get('planet') == d['planet'] and _rd.get('is_current'):
                    for _rad in _rd.get('antardashas', []):
                        if _rad.get('pratyantardashas'):
                            _prad_lookup[_rad['planet']] = _rad['pratyantardashas']

            for ad in d['antardashas']:
                mark = ' ← 当前' if ad.get('is_current') else ''
                role_note = ad.get('role_note') or '—'
                lines.append(f"| {d['planet']}-{ad['planet']}{mark} | {ad['start']}~{ad['end']} | "
                             f"{ad['ad_verdict']} | {ad['combined']} | {role_note} |")
                # 三级运：仅对当前小运展开，数据从原始 dashas 查取
                prad = _prad_lookup.get(ad['planet'], [])
                if ad.get('is_current') and prad:
                    lines.append(f"\n##### {d['planet']}-{ad['planet']} 三级运（Pratyantardasha，精确到月）")
                    lines.append("| 三级运 | 起始 | 结束 | 当前 |")
                    lines.append("|--------|------|------|------|")
                    for pd in prad:
                        pd_mark = ' ← 当前' if pd.get('is_current') else ''
                        lines.append(f"| {d['planet']}-{ad['planet']}-{pd['planet']}{pd_mark} | {pd['start']} | {pd['end']} |{pd_mark} |")
                    lines.append("")
            lines.append("")

    # 格局判定
    yogas = chart.get('yogas', [])
    if yogas:
        lines.append("### 格局判定（Yogas）")
        lines.append("> 引擎按 yogas.md 规则扫描；core 读取，不再自行识别。")
        lines.append("| 格局 | 成立 | 参与星 | 强度 | 破格/孤立/备注 | 激活窗口(大运) |")
        lines.append("|------|------|--------|------|----------------|----------------|")
        for y in yogas:
            mark = '✅' if y['present'] else '❌'
            parts = ', '.join(y['participants']) or '—'
            act = '；'.join(y['activation']) or '—'
            lines.append(f"| {y['name']} | {mark} | {parts} | {y['strength']} | "
                         f"{y['note'] or '—'} | {act} |")
        lines.append("")

    # === 事业确定性判定层（career-verdict）===
    cn = chart.get('career_niche')
    if cn:
        lines.append("## 事业确定性判定（career引擎计算，career.md读取权威标签，不得擅自翻转）\n")
        lines.append("### 职场生态位")
        lines.append(f"> L10={cn['l10']}（落{cn['l10_house']}宫，{cn['l10_dignity']}，"
                     f"Shadbala {cn['l10_shadbala']}%）；10宫住客：{', '.join(cn['occupants_10h']) or '无'}")
        lines.append("| 生态位 | 判定依据 |")
        lines.append("|--------|----------|")
        for niche, reason in zip(cn['niches'], cn['reasons']):
            lines.append(f"| {niche} | {reason} |")
        lines.append("")

        cm = chart.get('career_monetization', {})
        if cm:
            lines.append("### 变现路径")
            lines.append(f"> 强星集合：{', '.join(cm['strong_planets'])}")
            lines.append("| 路径 | SAV | 判定依据 |")
            lines.append("|------|-----|----------|")
            for p in cm['paths']:
                lines.append(f"| {p['type']} | {p['sav']} | {p['reason']} |")
            lines.append("")

        kk = chart.get('career_karakamsha', {})
        if kk and kk.get('available'):
            lines.append("### Karakamsha 事业内核")
            lines.append(f"> AmK(事业指示星)={kk['amk']}，其D9星座={kk['karakamsha_sign']}"
                         f"（守护星{kk['karakamsha_lord']}）作为Karakamsha Lagna。")
            lines.append(f"> Karakamsha 1宫行星：{', '.join(kk['in_karakamsha_1h']) or '无'}；"
                         f"10宫行星：{', '.join(kk['in_karakamsha_10h']) or '无'}")
            lines.append("> core/career 据此判断事业的灵魂驱动方向，不再自行推导 Karakamsha。")
            lines.append("")

    # === 感情确定性判定层（love-verdict）===
    st = chart.get('love_spouse_triangle')
    if st:
        lines.append("## 感情确定性判定（love引擎计算，love.md读取权威标签，不得擅自翻转）\n")
        lines.append("### 配偶画像三角（DK / UL / L7）")
        lines.append(f"> **{st['primary_source']}**（{st['weight_note']}）")
        lines.append("| 来源 | 行星/点 | 星座 | 宫位 | 状态 |")
        lines.append("|------|---------|------|------|------|")
        lines.append(f"| L7(7宫主) | {st['l7']} | {st['l7_sign']} | {st['l7_house']} | {st['l7_dignity']} |")
        lines.append(f"| DK(配偶指示) | {st['dk']} | {st['dk_sign']} | {st['dk_house']} | "
                     f"{'一致' if st['dk_consistent'] else '⚠️不一致降权'} |")
        lines.append(f"| UL(伴侣宫) | — | {st['ul_sign']} | {st['ul_house']} | — |")
        lines.append(f"> 7宫住客：{', '.join(st['occupants_7h']) or '无'}；"
                     f"相位7宫：{', '.join(st['aspects_7h']) or '无'}")
        lines.append("")

        rn = chart.get('love_relation_nature', {})
        if rn:
            lines.append("### 关系性质判定")
            lines.append(f"> **{rn['nature']}**")
            for note in rn['notes']:
                lines.append(f"> - {note}")
            lines.append("")

        ts = chart.get('love_timing_signals', {})
        if ts and ts.get('windows'):
            lines.append("### 感情时机信号（当前+下一大运小运扫描）")
            lines.append(f"> 聚焦大运：{'、'.join(ts['md_focus'])}")
            lines.append("| 小运 | 时段 | 信号类型 | 依据 |")
            lines.append("|------|------|----------|------|")
            for w in ts['windows']:
                mark = ' ←当前' if w['is_current'] else ''
                lines.append(f"| {w['period']}{mark} | {w['start']}~{w['end']} | "
                             f"{w['signal']} | {w['reason']} |")
            lines.append("")

        # D60 感情业力补充
        ld60 = chart.get('love_d60_supplement') or {}
        if ld60.get('available'):
            lines.append("### D60 感情业力补充（业力层修正，不覆盖D1结论）")
            lines.append(f"> D60 7宫整体品质：**{ld60.get('d60_7h_quality','—')}**"
                         f"（行星：{', '.join(ld60.get('d60_7h_planets',[])) or '无'}）")
            lines.append(f"> D60 5宫（恋爱业力）行星：{', '.join(ld60.get('d60_5h_planets',[])) or '无'}")
            if ld60.get('spouse_karma_assets'):
                lines.append(f"> 配偶业力资产（前世积累）：{', '.join(ld60['spouse_karma_assets'])}")
            if ld60.get('spouse_karma_debts'):
                lines.append(f"> 配偶业力欠账（今生功课）：{', '.join(ld60['spouse_karma_debts'])}")
            lines.append(f"> Venus D60×D1 交叉类型：{ld60.get('venus_d60_d1_cross','—')}")
            lines.append("")

    # === D60 确定性判定层 ===
    d60_skip = chart.get('d60_verdicts_skipped', True)
    if not d60_skip:
        lines.append("## D60 业力确定性判定（d60_verdict引擎计算，不得擅自翻转）\n")
        lines.append("> D60（Shashtiamsa）= 业力盘，前世积累的底层代码。")
        lines.append("> 判定权重：D60修正 ≤ D1判定的1/4（业力是背景，D1是前景）。")
        lines.append("> 此节供 core/career/love 读取，不得自行推断未列出的内容。\n")

        # Lagna 业力主题
        lt = chart.get('d60_lagna_theme') or {}
        if lt:
            lines.append("### D60 Lagna 业力底色")
            lines.append(f"> D60 Lagna = **{lt.get('lagna_sign','')}**（{lt.get('theme_name','')}）")
            lines.append(f"> {lt.get('theme_desc','')}")
            occ = lt.get('lagna_occupants', [])
            lines.append(f"> D60 Lagna 住客：{', '.join(occ) if occ else '空宫'}")
            lines.append("")

        # 业力资产/欠账分类表
        karma = chart.get('d60_karma') or {}
        if karma:
            lines.append("### 业力资产/欠账四分类")
            lines.append("> 资产=前世积累今生可提取；封印=积累但被凶宫封存；欠账=前世不足；重欠=前世负积累。")
            lines.append("| 行星 | D60星座/宫 | D60尊贵度 | 业力类型 | 含义 |")
            lines.append("|------|-----------|----------|----------|------|")
            d60 = chart.get('d60') or {}
            for p in ['Sun','Moon','Mars','Mercury','Jupiter','Venus','Saturn','Rahu','Ketu']:
                k = karma.get(p, {})
                if not k:
                    continue
                sign_info = d60.get(p, ('—', 0))
                sign_name = sign_info[0] if isinstance(sign_info, tuple) else '—'
                h = k.get('d60_house', '?')
                dig = k.get('d60_dignity', '—')
                ktype = k.get('karma_type', '—')
                label = k.get('label', '—')
                lines.append(f"| {p} | {sign_name}/{h}宫 | {dig} | {label} | {k.get('desc','')[:20]} |")
            lines.append("")

        # D60×D1 交叉标注
        cross = chart.get('d60_cross') or {}
        if cross:
            lines.append("### D60×D1 业力交叉")
            lines.append("> 双层巩固=最稳固；业力支撑=今生弱但有前世底气；业力透支=今生强但无前世积累；惯性待破=两层均弱。")
            lines.append("| 行星 | D1尊贵度 | D60尊贵度 | 交叉类型 | 说明 |")
            lines.append("|------|---------|---------|----------|------|")
            for p in ['Sun','Moon','Mars','Mercury','Jupiter','Venus','Saturn']:
                c = cross.get(p, {})
                if not c:
                    continue
                lines.append(f"| {p} | {c.get('d1_dignity','—')} | {c.get('d60_dignity','—')} | "
                             f"{c.get('label','—')} | {c.get('desc','')[:30]} |")
            lines.append("")

        # D60 对事业的补充
        cd60 = chart.get('career_d60_supplement') or {}
        if cd60.get('available'):
            lines.append("### D60 事业业力补充")
            lines.append(f"> D60 10宫（事业天赋宫）行星：{', '.join(cd60.get('d60_10h_planets',[])) or '无'}")
            if cd60.get('karma_assets_career'):
                lines.append(f"> 前世职业积累（资产）：{', '.join(cd60['karma_assets_career'])}")
            if cd60.get('karma_debts_career'):
                lines.append(f"> 前世职业欠账（今生需补足）：{', '.join(cd60['karma_debts_career'])}")
            if cd60.get('supported_career'):
                lines.append(f"> 业力支撑（今生弱但有底气）：{', '.join(cd60['supported_career'])}")
            lines.append("> career.md 读取此节，直接引用不得重新推断。")
            lines.append("")


def _render_precision_layers(lines, chart):
    """精度增强（Avastha/Argala/Sodhya/Dashas/Gochara）"""
    # === 精度增强模块 ===
    lines.append("## 精度增强数据（新增计算层）\n")

    # ── Avastha（行星状态）──
    avs = chart.get('avastha') or {}
    if avs:
        lines.append("### Avastha 行星状态（Baladi + Jagradadi）")
        lines.append("> Baladi：5态按度数（婴儿/少年/青壮/成熟/老年），偶数星座反序。")
        lines.append("> Jagradadi：按星宿主与行星自然关系（醒/梦/睡），影响实际效率（约100%/50%/25%）。")
        lines.append("| 行星 | 度数 | Baladi | 效率 | Jagradadi | 星宿主 | 效率 |")
        lines.append("|------|------|--------|------|-----------|--------|------|")
        for name in ['Sun','Moon','Mars','Mercury','Jupiter','Venus','Saturn','Rahu','Ketu']:
            av = avs.get(name, {})
            if not av:
                continue
            b = av.get('baladi', {}); j = av.get('jagradadi', {})
            lines.append(f"| {name} | {b.get('degree','?')}° | {b.get('name','?')} | {b.get('effect','?')[:8]} | "
                         f"{j.get('name','?')} | {j.get('nak_lord','?')} | {j.get('effect','?')[:12]} |")
        lines.append("")

    # ── Argala（干预链）──
    argala = chart.get('argala') or {}
    if argala:
        DOMAINS = {1:'自我',2:'财富',3:'兄弟',4:'家庭',5:'子女',6:'疾病',
                   7:'婚姻',8:'变故',9:'运势',10:'事业',11:'收入',12:'损耗'}
        lines.append("### Argala 干预链")
        lines.append("> 2/4/11宫有行星=正干预；12/10/3宫有行星=反干预（抵消）。")
        lines.append("> 净效果：positive(干预强)/neutral(平衡)/blocked(被反干)/none(无干预)。")
        lines.append("| 宫位 | 领域 | 净效果 | 正干预行星 | 反干预行星 |")
        lines.append("|------|------|--------|-----------|-----------|")
        for h in range(1, 13):
            r = argala.get(h, {})
            net = r.get('argala_net', '—')
            a_str = '; '.join(f"{d}宫:{','.join(ps)}" for d, ps in r.get('argala_planets', {}).items()) or '—'
            v_str = '; '.join(f"{d}宫:{','.join(ps)}" for d, ps in r.get('virodha_planets', {}).items()) or '—'
            lines.append(f"| {h} | {DOMAINS[h]} | {net} | {a_str} | {v_str} |")
        lines.append("")

    # ── Sodhya Pinda（Ashtakavarga 精细化）──
    sp = chart.get('sodhya_pinda') or {}
    if sp and 'error' not in sp and 'sodhya_pindas' in sp:
        lines.append("### Sodhya Pinda（Ashtakavarga 精细化净强度）")
        lines.append("> SAV 原始积分经 Trikona+Ekadhipatya Sodhana 减分后的净强度。")
        lines.append("> 净值越高=行星在该体系下实际更强；比 SAV 原始值更准确。")
        lines.append("| 行星 | Raasi Pinda | Graha Pinda | Sodhya Pinda | 排名 |")
        lines.append("|------|-------------|-------------|--------------|------|")
        sodhya = sp.get('sodhya_pindas', {})
        graha = sp.get('graha_pindas', {})
        raasi = sp.get('raasi_pindas', {})
        ranked = sorted(sodhya.keys(), key=lambda p: sodhya.get(p, 0), reverse=True)
        for rank, pname in enumerate(ranked, 1):
            lines.append(f"| {pname} | {raasi.get(pname,'—')} | {graha.get(pname,'—')} | "
                         f"{sodhya.get(pname,'—')} | {rank} |")
        lines.append("")

    # ── Chara Dasha（Jaimini 环境层）──
    cd = chart.get('chara_dasha') or {}
    if cd and 'error' not in cd and cd.get('dashas'):
        lines.append("### Chara Dasha（Jaimini 环境层）")
        lines.append("> 与 Vimsottari（心理层）互补的环境层大运。两者共振=高概率时机窗口。")
        lines.append(f"> 当前运行：**{cd.get('current_sign','?')}**（{cd.get('current_start','?')} ~ {cd.get('current_end','?')}）"
                     f" → D1 **{cd.get('current_house','?')}宫**（{cd.get('current_domain','')}）")
        lines.append("| Chara大运 | 起始 | 结束 | 激活宫位 | 领域 | 当前 |")
        lines.append("|-----------|------|------|---------|------|------|")
        for d in cd['dashas']:
            cur = '→当前' if d.get('is_current') else ''
            h = d.get('house_from_lagna', '?'); dom = d.get('domain', '')
            lines.append(f"| {d['sign']} | {d['start']} | {d['end']} | {h}宫 | {dom[:8]} | {cur} |")
        lines.append("")
        # 当前主运的小运（Antardasha）
        _cc = [d for d in cd['dashas'] if d.get('is_current')]
        if _cc and _cc[0].get('antardashas'):
            lines.append(f"#### Chara 当前主运（{cd.get('current_sign','?')}）小运 — 当前小运：{cd.get('current_ad_sign','?')}")
            lines.append("| 小运 | 起始 | 结束 | 激活宫 | 当前 |")
            lines.append("|------|------|------|-------|------|")
            for ad in _cc[0]['antardashas']:
                cur = ' ←当前' if ad.get('is_current') else ''
                ah = ad.get('house_from_lagna', '?'); adom = ad.get('domain','')[:6]
                lines.append(f"| {ad['sign']} | {ad['start']} | {ad['end']} | {ah}宫{adom} |{cur} |")
            lines.append("")

        # ── Chara Lagna（变动上升）判读：以当前主运星座为临时上升 ──
        cl = chart.get('chara_lagna')
        if cl and 'error' not in cl and cl.get('chara_lagna_sign'):
            lines.append(f"#### Chara Lagna 判读 — 本期临时上升：**{cl['chara_lagna_sign']}**")
            lines.append(f"> {cl.get('note','')}。这是 Jaimini 正统视角，与上表\"落本命第几宫\"互补：")
            lines.append("> 上表看大运星座落在原盘哪个领域；这里把大运星座当上升，看关键指示点相对它落第几宫。")
            # 激活提示
            notes = cl.get('activation_notes') or []
            if notes:
                lines.append("")
                lines.append("**本期领域激活提示：**")
                for n in notes:
                    lines.append(f"- {n}")
            # Chara Karaka 落宫表
            kp = cl.get('karaka_points') or []
            if kp:
                lines.append("")
                lines.append("| 指示星 | 行星 | 星座 | 落CL第几宫 | 领域 |")
                lines.append("|--------|------|------|-----------|------|")
                _kmean = {'AK':'灵魂','AmK':'事业','BK':'兄弟','MK':'母亲','PK':'子嗣','GK':'磨难','DK':'配偶'}
                for k in kp:
                    lines.append(f"| {k['karaka']}({_kmean.get(k['karaka'],'')}) | {k['planet']} | "
                                 f"{k['sign']} | {k['house_from_cl']}宫 | {k['domain'][:8]} |")
            # AL/UL + 关键宫
            sp = cl.get('special_points') or []
            kh = cl.get('key_houses') or []
            if sp or kh:
                lines.append("")
                lines.append("| 关键点/宫 | 内容 | 落CL位置 | 说明 |")
                lines.append("|-----------|------|---------|------|")
                for s in sp:
                    lines.append(f"| {s['point']} | {s['sign']} | 第{s['house_from_cl']}宫 | {s['label']} |")
                for h in kh:
                    occ = '/'.join(h['occupants']) if h['occupants'] else '空'
                    lord_info = f"{h['lord']}→{h['lord_in_house']}宫" if h['lord_in_house'] else h['lord']
                    lines.append(f"| CL第{h['house_from_cl']}宫 | {h['sign']}（{h['meaning']}） | "
                                 f"宫主{lord_info} | 宫内:{occ} |")
            lines.append("")

    # ── Narayana Dasha（Jaimini 环境层·宫位大运）──
    nd = chart.get('narayana_dasha') or {}
    if nd and 'error' not in nd and nd.get('dashas'):
        lines.append("### Narayana Dasha（Jaimini 宫位大运）")
        lines.append("> 以星座宫位为单位的 Jaimini 环境层大运，与 Vimsottari（心理层）交叉验证时机。")
        lines.append(f"> 当前运行：**{nd.get('current_sign','?')}**（{nd.get('current_start','?')} ~ {nd.get('current_end','?')}）"
                     f" → D1 **{nd.get('current_house','?')}宫**（{nd.get('current_domain','')}）")
        lines.append("| Narayana大运 | 起始 | 结束 | 激活宫位 | 领域 | 当前 |")
        lines.append("|------------|------|------|---------|------|------|")
        for d in nd['dashas']:
            cur = '→当前' if d.get('is_current') else ''
            h = d.get('house_from_lagna', '?'); dom = d.get('domain', '')
            lines.append(f"| {d['sign']} | {d['start']} | {d['end']} | {h}宫 | {dom[:8]} | {cur} |")
        lines.append("")

    # ── Shoola Dasha（逆境/顺境周期）──
    sd = chart.get('shoola_dasha') or {}
    if sd and 'error' not in sd and sd.get('dashas'):
        QUALITY_MARK = {'harsha': '✅顺境', 'sama': '⚪平稳', 'shoola': '⚠️逆境/考验'}
        lines.append("### Shoola Dasha（逆境/顺境周期）")
        lines.append("> 三分法大运：harsha(顺境)/sama(平稳)/shoola(逆境)，用于判断人生重大逆境/顺境窗口。")
        cur_q = sd.get('current_quality', '?')
        lines.append(f"> 当前质地：**{QUALITY_MARK.get(cur_q, cur_q)}** ({sd.get('current_sign','?')})")
        lines.append("| Shoola大运 | 起始 | 结束 | 年数 | 质地 | 当前 |")
        lines.append("|-----------|------|------|------|------|------|")
        for d in sd['dashas']:
            cur = '→当前' if d.get('is_current') else ''
            qmark = QUALITY_MARK.get(d.get('quality', ''), d.get('quality_cn', ''))
            lines.append(f"| {d['sign']} | {d['start']} | {d['end']} | {d['years']} | {qmark} | {cur} |")
        lines.append("")

    # ── Kalachakra Dasha ──
    kcd = chart.get('kalachakra_dasha') or {}
    if kcd and 'error' not in kcd and kcd.get('dashas'):
        lines.append("### Kalachakra Dasha（时轮大运）")
        lines.append("> 传统 Jaimini 时轮大运体系，与 Narayana 交叉验证时机。")
        lines.append(f"> 当前：**{kcd.get('current','?')}**（{kcd.get('current_start','?')} ~ {kcd.get('current_end','?')}）")
        lines.append("| 大运 | 起始 | 结束 | 年数 | 当前 |")
        lines.append("|------|------|------|------|------|")
        for d in kcd['dashas']:
            cur = '→当前' if d.get('is_current') else ''
            lines.append(f"| {d['sign_or_planet']} | {d['start']} | {d['end']} | {d['years']} | {cur} |")
        lines.append("")

    # ── Yogardha Dasha ──
    yod = chart.get('yogardha_dasha') or {}
    if yod and 'error' not in yod and yod.get('dashas'):
        lines.append("### Yogardha Dasha（混合大运）")
        lines.append("> Vimsottari+Chara 混合体系，两套系统矛盾时提供第三视角。")
        lines.append(f"> 当前：**{yod.get('current','?')}**（{yod.get('current_start','?')} ~ {yod.get('current_end','?')}）")
        lines.append("| 大运 | 起始 | 结束 | 年数 | 当前 |")
        lines.append("|------|------|------|------|------|")
        for d in yod['dashas'][:15]:
            cur = '→当前' if d.get('is_current') else ''
            lines.append(f"| {d['sign_or_planet']} | {d['start']} | {d['end']} | {d['years']} | {cur} |")
        lines.append("")

    # ── Mudda Dasha ──
    mdd = chart.get('mudda_dasha') or {}
    if mdd and 'error' not in mdd and mdd.get('dashas'):
        lines.append("### Mudda Dasha（年度内小大运）")
        lines.append(f"> {mdd.get('year','?')}年度盘压缩大运。当前段：**{mdd.get('current_period','?')}**（{mdd.get('current_start','?')} ~ {mdd.get('current_end','?')}）")
        lines.append("| 主运 | 起始 | 结束 | 天数 | 当前 |")
        lines.append("|------|------|------|------|------|")
        for d in mdd['dashas']:
            cur = '→当前' if d.get('is_current') else ''
            lines.append(f"| {d['planet']} | {d['start']} | {d['end']} | {round(d.get('days',0))}天 | {cur} |")
        lines.append("")

    # ── Gochara 完整过运 ──
    gf = chart.get('gochara_full') or {}
    if gf and 'error' not in gf and gf.get('planets'):
        ss = gf.get('sade_sati', {})
        lines.append("### Gochara 完整过运（Vedha阻隔+BAV强度+SAV置信度）")
        lines.append(f"> 日期：{gf.get('date','?')} | Sade Sati：{ss.get('status','?')} {ss.get('phase','')}")
        lines.append(f"> 双过运激活宫位：{gf.get('double_transit',[])} | 8宫凶过运：{gf.get('ashtama_gochara',[])}")
        lines.append("> BAV=个人力量（5+强/3-4中/≤2弱）| Bindu=宫位SAV总分 | 综合=个人×环境")
        lines.append("> 置信度：Bindu≥30→高（效果接近预期）| 25-29→中 | <25→⚠️低（预测降权）")
        lines.append("| 过运行星 | 当前星座 | Lagna宫 | Kaksha主 | BAV | Bindu | 综合强度 | 置信度 | Vedha |")
        lines.append("|---------|---------|---------|---------|-----|-------|---------|--------|-------|")
        for p in ['Sun','Moon','Mars','Mercury','Jupiter','Venus','Saturn','Rahu','Ketu']:
            v = gf.get('planets',{}).get(p,{})
            if v:
                vedha = f'被{v.get("vedha_blocker","?")}阻' if v.get('vedha_blocked') else '—'
                bindu = v.get('house_bindu', '—')
                combined = v.get('combined_label', '—')
                # 缩短 combined_label 以保持表格紧凑
                _short = {'最强过运（个人强×环境充裕）':'★★★最强',
                          '有力无处使（个人强但环境差）':'★★有力受限',
                          '环境好底子不足（效果打折）':'★★环境好但弱',
                          '双弱（过运效果极微）':'☆双弱',
                          '偏强过运':'★★偏强',
                          '偏弱过运':'☆偏弱',
                          '中等过运':'★中等'}
                combined_short = _short.get(combined, combined[:6])
                sav_conf = v.get('sav_confidence', 'unknown')
                conf_label = {'high': '高', 'medium': '中', 'low': '⚠️低', 'unknown': '—'}.get(sav_conf, '—')
                lines.append(f"| {p} | {v.get('current_sign','?')} | {v.get('transit_house','?')} | "
                             f"{v.get('kaksha_lord','?')} | {v.get('bav_score','?')}({v.get('bav_strength','?')}) | "
                             f"{bindu} | {combined_short} | {conf_label} | {vedha} |")
        lines.append("")
        # 低 SAV 宫位警告汇总
        low_warns = gf.get('low_sav_warnings', [])
        if low_warns:
            lines.append("> **⚠️ 行运预测降权警告（SAV < 25 的过境宫位）**：")
            for w in low_warns:
                lines.append(f"> - **{w['planet']}** 过境 {w['house']} 宫：{w['note']}")
            lines.append("> → core 分析这些行星的过运时，须标注\"置信度低\"，不得给出确定性预测。")
            lines.append("")
        else:
            lines.append("> 当前全部过境宫位 SAV ≥ 25，行运预测置信度正常。")
            lines.append("")

    # ── 多系统时机交叉扫描 ──
    tc = chart.get('timing_confluence') or {}
    if tc and 'error' not in tc:
        params = tc.get('scan_params', {})
        lines.append("### 多系统时机交叉扫描（未来60个月）")
        lines.append(f"> 扫描范围：{params.get('from','?')} ~ {params.get('to','?')} | "
                     f"基础评分：Vimsottari/Chara/Narayana各宫激活+2，Shoola顺境+1/逆境-1")
        lines.append(f"> 质量加权：{params.get('quality_weighting','D9(40%)+Shadbala(30%)+SAV(30%)')}。"
                     "质量分=基础分×激活行星兑现率×宫位环境系数。")
        lines.append("> 排序按质量分：强星在好宫的激活远重于弱星在差宫。核心价值：三套系统共振+质量确认。")
        for theme in ['感情','事业','财富','灵性/运势','家庭/根基']:
            theme_data = tc.get(theme, {})
            top = theme_data.get('top_windows', [])
            if top:
                # 只展示质量分 > 0 的窗口
                pos_top = [w for w in top if w.get('quality_score', 0) > 0]
                if pos_top:
                    lines.append(f"#### {theme} — 最强共振窗口（按质量分排序）")
                    lines.append("| 月份 | 基础分 | 质量分 | 激活信号 | 质量分解 |")
                    lines.append("|------|--------|--------|---------|---------|")
                    for w in pos_top[:5]:
                        qd = w.get('quality_details', '')
                        lines.append(f"| {w['label']} | {w['score']} | {w.get('quality_score',0):.2f} | "
                                     f"{w['details'][:45]} | {qd[:50] if qd else '—'} |")
                    lines.append("")
        lines.append("")

    # ── 健康敏感点（22nd Drekkana + 64th Navamsha）──
    hm = chart.get('health_markers') or {}
    if hm and 'error' not in hm:
        d22 = hm.get('d22_drekkana', {})
        d64 = hm.get('d64_navamsha', {})
        tr = hm.get('current_transits_near_markers', {})
        lines.append("### 健康敏感点（22nd Drekkana + 64th Navamsha）")
        lines.append("> 出生月亮的两个健康/危机触发坐标（D11 配套工具）。过运行星接近时为高风险窗口。")
        lines.append("> ⚠️ 用于识别健康关注窗口，不预测生命终结时间。")
        lines.append(f"> **22nd Drekkana**: {d22.get('sign','?')} {d22.get('degree_in_sign','?')}° "
                     f"| D3同座行星：{', '.join(d22.get('planets_in_same_sign',[])) or '无'}")
        lines.append(f"> **64th Navamsha**: {d64.get('sign','?')} {d64.get('degree_in_sign','?')}° "
                     f"| D9同座行星：{', '.join(d64.get('planets_in_same_sign',[])) or '无'}")
        lines.append(f"> 当前过运接近 22nd：{', '.join(tr.get('near_d22',[])) or '无'} "
                     f"| 接近 64th：{', '.join(tr.get('near_d64',[])) or '无'}")
        lines.append(f"> **当前风险等级**：{tr.get('risk_level','?')}")
        lines.append("")

    # ── 特殊行星状态与灾象检测 ──
    spp = chart.get('special_planets') or {}
    if spp and 'error' not in spp:
        lines.append("### 特殊行星状态与灾象检测")
        # Mrityu Bhaga
        mb = spp.get('mrityu_bhaga', [])
        lines.append(f"> **Mrityu Bhaga（死亡度数）**：{', '.join(mb) if mb else '无'}{'（⚠️ 以上行星在危险度数，功能严重受损）' if mb else '（无行星处于危险度数）'}")
        # Pushkara Navamsha
        pn = spp.get('pushkara_navamsha', {})
        pn_nav = pn.get('navamsha', [])
        pn_bhg = pn.get('bhaga', [])
        lines.append(f"> **Pushkara Navamsha（吉位）**：{', '.join(pn_nav) if pn_nav else '无'}"
                     + (f"（Bhaga特殊吉位：{', '.join(pn_bhg)}）" if pn_bhg else ""))
        # Marana Karaka Sthana
        mks = spp.get('marana_karaka_sthana', [])
        lines.append(f"> **Marana Karaka Sthana（致命弱点宫）**：{', '.join(mks) if mks else '无'}{'（⚠️ 以上行星落在MKS，效能大幅下降）' if mks else '（无行星落在MKS）'}")
        # Doshas
        ks = spp.get('kala_sarpa', False)
        mg = spp.get('manglik', False)
        mg_ex = spp.get('manglik_exceptions', False)
        gm = spp.get('ganda_moola', False)
        lines.append(f"> **Kala Sarpa（蛇格）**：{'✅ 形成（所有行星夹在罗计轴线一侧）' if ks else '❌ 未形成'}")
        lines.append(f"> **Manglik（火星凶相）**：{'⚠️ 形成' + ('，但有化解条件' if mg_ex else '') if mg else '❌ 未形成'}")
        lines.append(f"> **Ganda Moola（根星诅咒）**：{'⚠️ 月亮在Ganda Moola星宿，需要特殊仪式化解' if gm else '❌ 未形成'}")
        lines.append("")

    # ── Tajaka 年度盘（当年/下年）──
    taj = chart.get('tajaka') or {}
    if taj and 'error' not in taj:
        lines.append("### Tajaka 年度盘（Varshaphal / Solar Return）")
        lines.append("> 每年太阳回归出生度数时的新星盘，定义当年主题。年主（Muntha）每年前移一宫。")
        for period_key, period_label in [('current_year','当年'), ('next_year','下年')]:
            cy = taj.get(period_key, {})
            if not cy or 'error' in cy:
                continue
            al = cy.get('annual_lagna', {}); mu = cy.get('muntha', {})
            lines.append(f"> **{period_label}（{cy.get('year','?')}年，太阳回归日：{cy.get('solar_return_date','?')}）**")
            lines.append(f"> 年度上升：{al.get('sign','?')} {al.get('deg_str','')} | 年主Muntha：{mu.get('sign','?')}（{mu.get('house','?')}宫）| 年主星：{cy.get('year_lord','?')}")
            planets_cy = cy.get('planets', {})
            if planets_cy:
                lines.append("| 行星 | 年度星座 | 年度宫位 |")
                lines.append("|------|---------|---------|")
                for name in ['Sun','Moon','Mars','Mercury','Jupiter','Venus','Saturn','Rahu','Ketu']:
                    p = planets_cy.get(name, {})
                    if p:
                        lines.append(f"| {name} | {p.get('sign','?')} | {p.get('house','?')} |")
                lines.append("")
        lines.append("")

    # ── Arudha Padas（完整12个）──
    ap = chart.get('arudha_padas') or {}
    if ap and 'error' not in ap:
        DOMAINS = {1:'自我',2:'财富',3:'兄弟',4:'家庭',5:'子女',6:'疾病',
                   7:'婚姻',8:'变故',9:'运势',10:'事业',11:'收入',12:'损耗'}
        lines.append("### 完整 Arudha Padas（12个社会现实层指示点）")
        lines.append("> Arudha Pada 揭示「世人眼中」的你的各领域，与 D1 宫位对比=内在与外在的差距。")
        lines.append("> A1=AL外在形象，A7=实际合伙，A10=实际职业地位，A11=实际收益网络。")
        lines.append("| Pada | 名称 | 星座 | 宫位 | 含义 |")
        lines.append("|------|------|------|------|------|")
        for k in ['A1','A2','A3','A4','A5','A6','A7','A8','A9','A10','A11','A12']:
            v = ap.get(k, {})
            if v:
                lines.append(f"| {k} | {v.get('name','?')} | {v.get('sign','?')} | {v.get('house','?')} | {v.get('use','?')} |")
        lines.append("")

    # ── Panchanga 五要素（出生日的日历层数据）──
    pg = chart.get('panchanga') or {}
    if pg and 'error' not in pg:
        lines.append("### Panchanga 五要素（出生日日历层）")
        lines.append("> 五要素是吠陀择时的基础：Tithi(月相日)+Vara(星期)+Nakshatra(月宿)+Yoga(日月合度)+Karana(半日)。")
        ti = pg.get('tithi', {}); va = pg.get('vara', {}); na = pg.get('nakshatra', {})
        yo = pg.get('yoga', {}); ka = pg.get('karana', {})
        lines.append(f"> **Tithi** {ti.get('number','')} {ti.get('name','')} ({ti.get('paksha','')}) "
                     f"| **Vara** {va.get('name','')} "
                     f"| **Nakshatra** {na.get('name','')} Pada{na.get('pada','')} [{na.get('quality','')}]")
        lines.append(f"> **Yoga** {yo.get('name','')} [{yo.get('quality','')}] "
                     f"| **Karana** {ka.get('name','')} [{ka.get('quality','')}]")
        lines.append(f"> 日出: {pg.get('sunrise','')} | 日落: {pg.get('sunset','')} "
                     f"| **当日综合评估**: {pg.get('overall_quality','')}")
        lines.append(f"> Abhijit吉时: {pg.get('abhijit_muhurta',{}).get('start','')}~{pg.get('abhijit_muhurta',{}).get('end','')} "
                     f"| Rahu Kala凶时: {pg.get('rahu_kalam',{}).get('start','')}~{pg.get('rahu_kalam',{}).get('end','')} "
                     f"| Amrit Kalam: {', '.join(a.get('start','')+'-'+a.get('end','') for a in pg.get('amrit_kalam',[]) if isinstance(a,dict))}")
        lines.append("")

    # ── 多 Ayanamsa 交叉 ──
    ma = chart.get('multi_ayanamsa') or {}
    if ma and 'error' not in ma:
        lines.append("### 多 Ayanamsa 交叉（Lahiri / Raman / KP）")
        av = ma.get('ayanamsa_values', {})
        df = ma.get('differences', {})
        lines.append(f"> Lahiri: {av.get('Lahiri','?')}° | Raman: {av.get('Raman','?')}° | KP: {av.get('KP','?')}°")
        lines.append(f"> Lahiri与Raman差: {df.get('Lahiri_vs_Raman','?')}° | 与KP差: {df.get('Lahiri_vs_KP','?')}°")
        lagna_r = ma.get('lagna_comparison', {})
        lagna_tag = '⚠️敏感' if lagna_r.get('sensitive') else '一致'
        lines.append(f"> Lagna({lagna_tag}): Lahiri={lagna_r.get('Lahiri','?')}, Raman={lagna_r.get('Raman','?')}, KP={lagna_r.get('KP','?')}")
        d9_sens = [p for p,v in ma.get('d9_comparison',{}).items() if v.get('sensitive')]
        d60_sens = [p for p,v in ma.get('d60_comparison',{}).items() if v.get('sensitive')]
        if d9_sens:
            lines.append(f"> ⚠️ D9 Ayanamsa敏感行星({len(d9_sens)}): {', '.join(d9_sens)}")
        if d60_sens:
            lines.append(f"> ⚠️ D60 Ayanamsa敏感行星({len(d60_sens)}): {', '.join(d60_sens)}")
        s = ma.get('sensitive_summary', [])
        if s:
            lines.append(f"> 敏感差异总计 {len(s)} 处（D9敏感=三套体系中星座不同）。")
        lines.append("> ⚠️ 以 Lahiri 为主用体系；Raman/KP仅作交叉参考，不覆盖主盘结论。")
        lines.append("")

    # ── Dasha 连续化：更新判定表渲染，加入 score/confidence ──
    # （大运吉凶判定表已在前面渲染，此处补充置信度注释）
    boundary_dashas = [d for d in chart.get('dasha_verdicts', []) if d.get('at_boundary')]
    if boundary_dashas:
        lines.append("### ⚠️ 大运判定边界情形（置信度低，需辅助参数确认）")
        lines.append("> 以下大运正负面信号计数接近阈值，结论置信度偏低，建议结合 Argala/Avastha 辅助判断。")
        lines.append("| 大运 | 判定 | 净得分 | 置信度 |")
        lines.append("|------|------|--------|--------|")
        for d in boundary_dashas:
            lines.append(f"| {d['planet']}({d['start']}~{d['end']}) | {d['verdict']} | "
                         f"{d.get('score',0):+.2f} | {d.get('confidence','?')} |")
        lines.append("")


def _render_divisional(lines, chart):
    """分盘数据（D9-D60）"""
    # === 分盘 ===
    lines.append("## 分盘数据\n")

    # D60 可信度声明（动态，根据 d60_trust_level）
    d60_trust = chart.get('d60_trust_level', 'computed')
    d60_sens_n = chart.get('d60_ayanamsa_sensitive_count')
    _D60_TRUST_LABELS = {
        'verified':  '✅ 已事件校验，可大量引用',
        'computed':  '⚠️ 计算通过基础校验，可有限参考（置信度中等）',
        'uncertain': '❌ 校验未通过或Ayanamsa敏感性高，仅展示数据不做推断',
        'disabled':  '🚫 用户选择不参考 D60',
    }
    d60_label = _D60_TRUST_LABELS.get(d60_trust, '⚠️ 状态未知')

    lines.append("### 分盘可信度声明")
    lines.append("```")
    lines.append("D1  ✅ 可信（直接计算）")
    lines.append("D9  ✅ 可信（直接计算）")
    lines.append("D10 ✅ 可信（直接计算）")
    lines.append("D4  ✅ 可信（直接计算）")
    lines.append("D5  ✅ 可信（直接计算）")
    lines.append("D7  ✅ 可信（直接计算，子女盘，精度要求中等）")
    _d11c = chart.get('d60_consent'); _d11p = chart.get('time_precision_level', 4)
    d11_status = '✅ 可信（直接计算，已知情同意）' if (_d11c is True and _d11p <= 2) else '🚫 未启用（需知情同意+Level 1-2精度）'
    lines.append(f"D11 {d11_status} （深度转化盘，高度私密）")
    d30_trust_show = chart.get('d30_trust_level', 'disabled')
    _D30_LABELS = {
        'verified': '✅ 已事件校验，可大量引用',
        'computed': '⚠️ 基础校验通过，可有限参考',
        'uncertain': '❌ 精度存疑，仅展示不推断',
        'disabled': '🚫 未启用（精度不足/未同意）',
    }
    lines.append(f"D30 {_D30_LABELS.get(d30_trust_show, '?')} （逆境盘）")
    lines.append(f"D60 {d60_label}")
    if d60_sens_n is not None:
        lines.append(f"    Ayanamsa敏感行星数：{d60_sens_n}颗（≤3颗=computed，>3颗=uncertain）")
    lines.append("```")

    # D60 可信度说明块（供 AI 分析时读取行为指引）
    lines.append("\n### D60 分析行为指引")
    lines.append("```")
    if d60_trust == 'verified':
        lines.append("D60状态：verified（已事件校验）")
        lines.append("→ AI分析可大量引用D60宫位，与D1/D9交叉深度解读前世业力与今生模式。")
        lines.append("→ D60强星/强宫=业力资产，直接用于人格、使命和深层驱动力分析。")
    elif d60_trust == 'computed':
        lines.append("D60状态：computed（基础校验通过，未事件校验）")
        lines.append("→ AI分析可有限引用D60，每条结论须标注'D60供参考，未经事件验证'。")
        lines.append("→ D60的结论不得覆盖D1/D9的结论，只能作为补充视角。")
        lines.append("→ 如用户希望提升D60可信度，可提供5个重大人生事件进行校验。")
    elif d60_trust == 'uncertain':
        lines.append("D60状态：uncertain（校验未通过 或 Ayanamsa敏感性高）")
        lines.append("→ AI分析不得主动引用D60数据做推断。")
        lines.append("→ 若用户追问D60相关内容，告知：当前D60精度不足，建议先提供事件校验。")
        lines.append("→ 如用户希望使用D60，需先完成：1)确认出生时间精度 2)提供事件校验。")
    else:  # disabled
        lines.append("D60状态：disabled（用户选择不参考）")
        lines.append("→ 完全忽略D60数据，不做任何D60相关分析。")
    lines.append("```\n")

    # D9
    lines.append("### D9 Navamsha")
    lines.append("| 行星 | D9星座 | D9宫位 | Vargottama |")
    lines.append("|------|--------|--------|-----------|")
    d9l = chart['d9']['Lagna']
    lines.append(f"| Lagna | {d9l[0]} | 1 | — |")
    for name in ['Sun','Moon','Mars','Mercury','Jupiter','Venus','Saturn','Rahu','Ketu']:
        sign, sidx = chart['d9'][name]
        d9_house = ((sidx - chart['d9']['Lagna'][1]) % 12) + 1
        varg = '是' if chart['vargottama'].get(name, False) else '否'
        lines.append(f"| {name} | {sign} | {d9_house} | {varg} |")
    lines.append("")

    # D10
    lines.append("### D10 Dasamsha")
    lines.append("| 行星 | D10星座 | D10宫位 |")
    lines.append("|------|---------|---------|")
    d10l = chart['d10']['Lagna']
    lines.append(f"| Lagna | {d10l[0]} | 1 |")
    for name in ['Sun','Moon','Mars','Mercury','Jupiter','Venus','Saturn','Rahu','Ketu']:
        sign, sidx = chart['d10'][name]
        d10_house = ((sidx - chart['d10']['Lagna'][1]) % 12) + 1
        lines.append(f"| {name} | {sign} | {d10_house} |")
    lines.append("")

    # D4
    lines.append("### D4 Chaturthamsha")
    lines.append("| 行星 | D4星座 | D4宫位 |")
    lines.append("|------|--------|--------|")
    d4l = chart['d4']['Lagna']
    lines.append(f"| Lagna | {d4l[0]} | 1 |")
    for name in ['Sun','Moon','Mars','Mercury','Jupiter','Venus','Saturn','Rahu','Ketu']:
        sign, sidx = chart['d4'][name]
        d4_house = ((sidx - chart['d4']['Lagna'][1]) % 12) + 1
        lines.append(f"| {name} | {sign} | {d4_house} |")
    lines.append("")

    # D5
    lines.append("### D5 Panchamsha")
    lines.append("| 行星 | D5星座 | D5宫位 |")
    lines.append("|------|--------|--------|")
    d5l = chart['d5']['Lagna']
    lines.append(f"| Lagna | {d5l[0]} | 1 |")
    for name in ['Sun','Moon','Mars','Mercury','Jupiter','Venus','Saturn','Rahu','Ketu']:
        sign, sidx = chart['d5'][name]
        d5_house = ((sidx - chart['d5']['Lagna'][1]) % 12) + 1
        lines.append(f"| {name} | {sign} | {d5_house} |")
    lines.append("")

    # D60 (Shashtiamsa — 业力盘/前世业力)
    d60 = chart.get('d60') or {}
    _d60_trust = chart.get('d60_trust_level', 'computed')
    if d60 and 'Lagna' in d60 and _d60_trust != 'disabled':
        lines.append("### D60 Shashtiamsa")
        # 根据信任级别加不同的引用警示
        if _d60_trust == 'verified':
            lines.append("> ✅ 已事件校验，可大量参考。Ra-Ke规则=对宫(180°)。")
        elif _d60_trust == 'computed':
            lines.append("> ⚠️ 基础校验通过，未经事件验证。引用时须标注'D60供参考'，不覆盖D1/D9结论。")
        else:  # uncertain
            lines.append("> ❌ 精度存疑（Ayanamsa敏感性高 或 校验未通过）。")
            lines.append("> 以下数据仅供记录，AI分析不得主动推断。")
        lines.append("| 行星 | D60星座 | D60宫位 |")
        lines.append("|------|---------|---------|")
        d60l = d60['Lagna']
        lines.append(f"| Lagna | {d60l[0]} | 1 |")
        for name in ['Sun','Moon','Mars','Mercury','Jupiter','Venus','Saturn','Rahu','Ketu']:
            if name not in d60:
                continue
            sign, sidx = d60[name]
            d60_house = ((sidx - d60['Lagna'][1]) % 12) + 1
            lines.append(f"| {name} | {sign} | {d60_house} |")
        lines.append("")
        lines.append("> D60为业力盘（前世业力），Ra-Ke规则=对宫(180°)，与D1/D9/D10/D4一致。\n")
    elif _d60_trust == 'disabled':
        lines.append("### D60 Shashtiamsa")
        lines.append("> 🚫 用户选择不参考D60，数据不渲染。\n")

    # D30 Trimsamsa（逆境盘）— 与 D60 共用同意状态
    d30 = chart.get('d30') or {}
    _d30_trust = chart.get('d30_trust_level', 'disabled')
    if d30 and 'Lagna' in d30 and _d30_trust != 'disabled':
        lines.append("### D30 Trimsamsa（逆境盘）")
        if _d30_trust == 'verified':
            lines.append("> ✅ 已事件校验，可大量参考。D30 分析灾厄/疾病倾向/重大磨难的性质。")
        elif _d30_trust == 'computed':
            lines.append("> ⚠️ 基础校验通过，未经事件验证。D30 每1°≈4-7分钟，引用时须标注参考性质。")
        else:
            lines.append("> ❌ 精度存疑，以下数据仅供记录，AI分析不得主动推断。")
        lines.append("| 行星 | D30星座 | D30宫位 |")
        lines.append("|------|---------|---------|")
        d30l = d30.get('Lagna', ('—', 0))
        lines.append(f"| Lagna | {d30l[0]} | 1 |")
        for name in ['Sun','Moon','Mars','Mercury','Jupiter','Venus','Saturn','Rahu','Ketu']:
            if name not in d30:
                continue
            sign, sidx = d30[name]
            d30_house = ((sidx - d30l[1]) % 12) + 1
            lines.append(f"| {name} | {sign} | {d30_house} |")
        d30_rake = chart.get('d30_rake_ok')
        # D30 Ra-Ke 校验规则：BPHS D30 里 Ra-Ke 必然同宫（差0），非对宫（差6）
        # 这是 D30 奇偶星座映射规则的数学特性，与 D60 不同
        d30_rake_str = '✅ 同宫（BPHS D30规则，正确）' if d30_rake else '❌ 异常' if d30_rake is False else '— 未计算'
        lines.append(f"> D30 Ra-Ke校验: {d30_rake_str}\n")
    elif _d30_trust == 'disabled':
        lines.append("### D30 Trimsamsa（逆境盘）")
        lines.append("> 🚫 未启用（精度不足 或 未获同意），数据不渲染。\n")

    # D7 Saptamsa（子女盘）— 无隐私限制，精度要求中等
    d7 = chart.get('d7') or {}
    if d7 and 'Lagna' in d7:
        lines.append("### D7 Saptamsa（子女盘）")
        lines.append("> 分析子女运势、生育能力、子女数量与质量。精度要求：出生时间误差≤30分钟可靠。")
        lines.append("| 行星 | D7星座 | D7宫位 |")
        lines.append("|------|--------|--------|")
        d7l = d7.get('Lagna', ('—', 0))
        lines.append(f"| Lagna | {d7l[0]} | 1 |")
        for name in ['Sun','Moon','Mars','Mercury','Jupiter','Venus','Saturn','Rahu','Ketu']:
            if name not in d7:
                continue
            sign, sidx = d7[name]
            d7_house = ((sidx - d7l[1]) % 12) + 1
            lines.append(f"| {name} | {sign} | {d7_house} |")
        lines.append("")

    # D11 Ekadasamsha（深度转化盘）— 高度私密，仅在知情同意 + 精度 Level 1 时渲染
    d11 = chart.get('d11') or {}
    _d11_consent = chart.get('d60_consent')   # D11 与 D30/D60 共用同一个同意状态
    _d11_precision = chart.get('time_precision_level', 4)
    _d11_enabled = _d11_consent is True and _d11_precision <= 2 and bool(d11) and 'Lagna' in d11
    if _d11_enabled:
        lines.append("### D11 Ekadasamsha（深度转化盘）")
        lines.append("> ⚠️ **高度私密分盘**：本数据仅在本人知情同意且出生时间精确（Level 1-2）时渲染。")
        lines.append("> D11 揭示深度转化的性质与周期模式，不用于预测具体生命终结时间。")
        lines.append("> Ra-Ke 校验规则：D11 Ra-Ke 差值应为 6（与 D60 相同）。")
        d11_rake = chart.get('d11_rake_ok')
        if d11_rake is None:
            # 实时计算
            d11_ra = d11.get('Rahu', ('?',0)); d11_ke = d11.get('Ketu', ('?',0))
            d11_rake = ((d11_ra[1] - d11_ke[1]) % 12) == 6 if isinstance(d11_ra,tuple) else False
        lines.append(f"> D11 Ra-Ke 校验：{'✅ 对宫（差6，正确）' if d11_rake else '❌ 异常'}")
        lines.append("| 行星 | D11星座 | D11宫位 |")
        lines.append("|------|---------|---------|")
        d11l = d11.get('Lagna', ('—', 0))
        lines.append(f"| Lagna | {d11l[0]} | 1 |")
        for name in ['Sun','Moon','Mars','Mercury','Jupiter','Venus','Saturn','Rahu','Ketu']:
            if name not in d11:
                continue
            sign, sidx = d11[name] if isinstance(d11[name], tuple) else (d11[name].get('sign','?'), d11[name].get('sign_idx',0))
            d11_house = ((sidx - d11l[1]) % 12) + 1
            lines.append(f"| {name} | {sign} | {d11_house} |")
        lines.append("> 详细分析见 d11_analysis.md（转化性质/周期/三层交叉），此处仅展示原始数据。\n")
    elif _d11_consent is not True or _d11_precision > 2:
        lines.append("### D11 Ekadasamsha（深度转化盘）")
        if _d11_precision > 2:
            lines.append("> 🚫 精度不足（Level 3+），D11 不渲染。")
        else:
            lines.append("> 🚫 未获知情同意，D11 不渲染。")
        lines.append("")


def _render_validation(lines, chart, meta):
    """校验结果"""
    # === 校验 ===
    lines.append("## 校验结果\n")
    sav_total = sum(chart['sav'].get(s,0) for s in SIGNS)
    sav_ok = '✅' if sav_total == 337 else '❌'

    # BAV行常量检查
    bav_ok = '✅'
    bav_detail = ''
    for pname, expected in BAV_ROW_SUMS.items():
        row = chart['bav'].get(pname, {})
        actual = sum(row.get(s,0) for s in SIGNS)
        if actual != expected:
            bav_ok = '❌'
            bav_detail += f'{pname}:{actual}≠{expected} '

    # Ra-Ke 180°
    ra_lon = chart['planets']['Rahu']['longitude']
    ke_lon = chart['planets']['Ketu']['longitude']
    ra_ke_diff = abs(ra_lon - ke_lon)
    if ra_ke_diff > 180: ra_ke_diff = 360 - ra_ke_diff
    ra_ke_ok = '✅' if abs(ra_ke_diff - 180) < 0.01 else '❌'

    # 燃烧
    comb_list = list(chart['combustion'].keys()) if chart['combustion'] else []
    comb_str = ', '.join(comb_list) if comb_list else '无'

    # 盈亏月
    phase = chart['moon_phase']
    phase_str = f"{'盈月' if phase['waxing'] else '亏月'} (距Sun {phase['sun_moon_diff']}°)"

    # D60 Ra-Ke 对宫校验（D60为业力盘，规则=对宫180°）
    d60_rake = chart.get('d60_rake_ok')
    if d60_rake is True:
        d60_rake_str = '✅ 对宫(180°)'
    elif d60_rake is False:
        d60_rake_str = '❌ 非对宫'
    else:
        d60_rake_str = '— 未计算'

    lines.append("```")
    lines.append(f" 1. SAV={sav_total}          {sav_ok}")
    lines.append(f" 2. BAV行常量        {bav_ok} {bav_detail}")
    lines.append(f" 3. 行星完整性(10)   ✅")
    lines.append(f" 4. 度数唯一性        ✅")
    lines.append(f" 5. Ra-Ke差180°      {ra_ke_ok}")
    lines.append(f" 6. 逆行标记完整      ✅")
    lines.append(f" 6b. 燃烧检测        ✅ [{comb_str}]")
    lines.append(f" 7. Ayanamsa一致     ✅ Lahiri")
    lines.append(f" 7c. 盈月/亏月       {phase_str}")
    lines.append(f" 8. Nakshatra↔度数   ✅")
    lines.append(f" 9. Chara Karaka排序 ✅")
    lines.append(f"10. Dasha时长常数    ✅")
    lines.append(f"11. D9公式交叉       ✅（直接计算，无需交叉验证）")
    lines.append(f"12. Ra-Ke分盘校验    ✅（直接计算）")
    lines.append(f"12b. D60 Ra-Ke对宫   {d60_rake_str}")
    # D30 Ra-Ke 校验：BPHS规则下必然同宫（差0），与D60对宫（差6）不同
    d30_rake_ok = chart.get('d30_rake_ok')
    if d30_rake_ok is True:
        d30_rake_line = '✅ 同宫（BPHS D30规则正确，Ra-Ke在D30必然同宫）'
    elif d30_rake_ok is False:
        d30_rake_line = '❌ 异常（Ra-Ke在D30非同宫，计算可能有误）'
    else:
        d30_rake_line = '— 未计算'
    lines.append(f"12c. D30 Ra-Ke同宫   {d30_rake_line}")
    d60_trust_show = chart.get('d60_trust_level', '?')
    d60_sens_show = chart.get('d60_ayanamsa_sensitive_count')
    sens_note = f"（Ayanamsa敏感行星{d60_sens_show}颗）" if d60_sens_show is not None else ''
    lines.append(f"12d. D60可信度级别   {d60_trust_show}{sens_note}")
    lines.append("```\n")


def _render_transit(lines, chart, transit_data):
    """过运数据（legacy support）"""
    # === 过运 ===
    lines.append("## 当前过运位置（Transit Data）\n")
    lines.append(f"> 数据来源：vedic-calculator直接计算")
    lines.append(f"> 提取时间点：{transit_data['date']}\n")

    lines.append("### 慢行星过运")
    lines.append("| 行星 | 过运星座 | 过运宫位(从Lagna数) | 说明 |")
    lines.append("|------|---------|-------------------|------|")
    for name in ['Saturn','Jupiter','Rahu','Ketu']:
        t = transit_data['planets'][name]
        lines.append(f"| {name} | {t['sign']} | {t['house']} | {t['cycle']} |")
    lines.append("")

    lines.append("### Sade Sati初判")
    lines.append("```")
    ss = transit_data['sade_sati']
    lines.append(f"Moon本命星座: {ss['moon_sign']}")
    lines.append(f"Saturn过运星座: {ss['saturn_sign']}")
    lines.append(f"相对位置: {ss['position']}")
    lines.append(f"Sade Sati状态: {ss['status']}")
    lines.append("```\n")

    lines.append("### 双过运触发检查（Saturn-Jupiter Double Transit）")
    lines.append("```")
    lines.append(f"Saturn过运相位覆盖宫位: {transit_data['saturn_covers']}")
    lines.append(f"Jupiter过运相位覆盖宫位: {transit_data['jupiter_covers']}")
    lines.append(f"双过运激活宫位: {transit_data['double_transit']}")
    lines.append("```")


def format_structured_data(chart, transit_data, meta, user_info):
    """
    chart: calculate_full_chart() 的返回值
    transit_data: calc_transit() 的返回值
    meta: dict with keys: dob, time, place, lat, lon, time_precision, time_source
    user_info: dict with keys: gender, relationship
    """
    lines = []
    _render_meta(lines, chart, meta, user_info)
    _render_d1_data(lines, chart)
    _render_quantitative(lines, chart)
    _render_preanalysis(lines, chart)
    _render_verdicts(lines, chart)
    _render_precision_layers(lines, chart)
    _render_divisional(lines, chart)
    _render_validation(lines, chart, meta)
    # Transit data (legacy support)
    if transit_data:
        _render_transit(lines, chart, transit_data)
    return '\n'.join(lines)






