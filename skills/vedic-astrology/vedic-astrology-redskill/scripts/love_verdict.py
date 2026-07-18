"""love_verdict.py — 感情确定性判定层

把 love.md 中原本由 AI 心算的判断落地为代码，产出权威标签：
  - spouse_triangle : 配偶画像三角（DK / UL / L7 交叉 + 一致性）
  - timing_signals  : 感情时机信号（AD 激活 5/7/9宫 或 Venus/Jupiter → 正缘/激情/社交）
  - relation_nature : 当前+未来窗口的关系性质（纯恋爱/落地/官宣）

love 的 AI 只负责翻译成人话，不得擅自翻转结构标签。
所有输入来自 engine.calculate_full_chart() 返回的 chart dict。
"""

SIGNS = ['Aries','Taurus','Gemini','Cancer','Leo','Virgo',
         'Libra','Scorpio','Sagittarius','Capricorn','Aquarius','Pisces']

SIGN_LORDS = {
    0:'Mars', 1:'Venus', 2:'Mercury', 3:'Moon', 4:'Sun', 5:'Mercury',
    6:'Venus', 7:'Mars', 8:'Jupiter', 9:'Saturn', 10:'Saturn', 11:'Jupiter'
}


def _house(chart, planet):
    return chart['planets'][planet]['house']


def _compound(chart, planet):
    return chart['dignity'].get(planet, {}).get('compound', 'neutral')


def _karaka(chart, key):
    """从 8K 体系取指定 karaka 的行星名"""
    for k, planet, deg in chart['karakas'].get('8k', []):
        if k == key:
            return planet
    return None


def _aspects_to_house(chart, house):
    """哪些行星相位某宫（读引擎 house_aspects）"""
    ha = chart.get('house_aspects', {})
    return ha.get('by_house', {}).get(house, [])


# ─────────────────────────────────────────────────────────────
# 1. 配偶画像三角（DK / UL / L7）
# ─────────────────────────────────────────────────────────────

def spouse_triangle(chart):
    """DK(配偶指示星) + UL(Upapada Lagna) + L7(7宫主) 三角交叉。
    三者指向一致→画像清晰；不一致→以 L7+7宫结构为主（DK 争议时弱化 DK）。
    """
    house_lords = chart['house_lords']
    l7 = house_lords[7]['lord']
    l7_house = _house(chart, l7)
    l7_sign = chart['planets'][l7]['sign']

    dk = _karaka(chart, 'DK')
    dk_consistent = chart['karakas'].get('dk_consistent', True)
    dk_house = _house(chart, dk) if dk else None
    dk_sign = chart['planets'][dk]['sign'] if dk else None

    sp = chart.get('special_points', {})
    ul = sp.get('UL', {})
    ul_sign = ul.get('sign')
    ul_house = ul.get('house')

    # 7宫住客 + 7宫被相位
    occupants_7h = [p for p in ['Sun','Moon','Mars','Mercury','Jupiter','Venus','Saturn','Rahu','Ketu']
                    if _house(chart, p) == 7]
    aspects_7h = _aspects_to_house(chart, 7)

    # 一致性：DK 争议时明确降权
    if dk_consistent:
        primary = f'DK({dk})+L7({l7})+UL 三源可交叉'
        weight = 'DK可用'
    else:
        primary = f'DK不一致(7K/8K冲突)→弱化DK，以L7({l7})+7宫结构为主'
        weight = 'DK降权'

    return {
        'l7': l7, 'l7_house': l7_house, 'l7_sign': l7_sign, 'l7_dignity': _compound(chart, l7),
        'dk': dk, 'dk_house': dk_house, 'dk_sign': dk_sign, 'dk_consistent': dk_consistent,
        'ul_sign': ul_sign, 'ul_house': ul_house,
        'occupants_7h': occupants_7h,
        'aspects_7h': aspects_7h,
        'weight_note': weight,
        'primary_source': primary,
    }


# ─────────────────────────────────────────────────────────────
# 2. 感情时机信号
# ─────────────────────────────────────────────────────────────

def _planet_relates_love(chart, planet):
    """某行星是否与感情系统相关：管5/7/9宫，或是 Venus/Jupiter，或是 PK/DK"""
    house_lords = chart['house_lords']
    owned = [h for h in range(1, 13) if house_lords[h]['lord'] == planet]
    tags = []
    if set(owned) & {5, 7, 9}:
        tags.append(f'管{",".join(str(h) for h in sorted(set(owned) & {5,7,9}))}宫')
    if planet == 'Venus':
        tags.append('Venus(恋爱/配偶指示)')
    if planet == 'Jupiter':
        tags.append('Jupiter(女盘夫星/福星)')
    if planet == _karaka(chart, 'PK'):
        tags.append('PK(子女/恋爱指示)')
    if planet == _karaka(chart, 'DK'):
        tags.append('DK(配偶指示)')
    if planet in ('Rahu', 'Ketu') and set(owned) == set():
        pass  # 节点单独在下方判激情/社交
    return tags


def _classify_love_signal(chart, planet):
    """把一个 Dasha 星归类为 正缘 / 激情 / 社交 / 弱信号"""
    house_lords = chart['house_lords']
    owned = [h for h in range(1, 13) if house_lords[h]['lord'] == planet]
    love_tags = _planet_relates_love(chart, planet)

    # 激情信号：Rahu 且与 Venus/5宫相关（Rahu 相位5宫 或 与 Venus 有相位）
    rahu_love = False
    if planet == 'Rahu':
        for a in chart['aspects']:
            if 'Rahu' in (a['p1'], a['p2']) and 'Venus' in (a['p1'], a['p2']):
                rahu_love = True
        if 5 in _aspects_to_planet_house(chart, 'Rahu'):
            rahu_love = True

    if love_tags:
        return ('正缘信号', '；'.join(love_tags))
    if rahu_love:
        return ('激情信号', 'Rahu激活且关联Venus/5宫→强烈迷恋，需辨别真伪')
    if set(owned) & {3, 11}:
        return ('社交信号', f'管{",".join(str(h) for h in sorted(set(owned) & {3,11}))}宫→暧昧/网恋/social')
    return ('弱信号', '与感情系统无直接连接')


def _aspects_to_planet_house(chart, planet):
    """某行星相位到的宫位列表（读 house_aspects by_planet）"""
    ha = chart.get('house_aspects', {})
    return ha.get('by_planet', {}).get(planet, [])


def timing_signals(chart):
    """扫描当前 + 下一大运的小运，标注每段的感情信号类型。"""
    dashas = chart.get('dashas', [])
    # 找当前大运 index
    idx_current = next((i for i, d in enumerate(dashas) if d.get('is_current')), None)
    focus = []
    if idx_current is not None:
        focus.append(dashas[idx_current])
        if idx_current + 1 < len(dashas):
            focus.append(dashas[idx_current + 1])

    windows = []
    for d in focus:
        md = d['planet']
        for ad in d.get('antardashas', []):
            adp = ad['planet']
            sig, reason = _classify_love_signal(chart, adp)
            if sig == '弱信号':
                # 弱信号也看大运星是否补足
                md_sig, _ = _classify_love_signal(chart, md)
                if md_sig != '弱信号':
                    sig = f'{sig}(大运{md}补:{md_sig})'
            windows.append({
                'period': f"{md}-{adp}",
                'start': ad['start'], 'end': ad['end'],
                'is_current': ad.get('is_current', False),
                'signal': sig, 'reason': reason,
            })
    return {'md_focus': [d['planet'] for d in focus], 'windows': windows}


# ─────────────────────────────────────────────────────────────
# 3. 关系性质（纯恋爱 / 落地 / 官宣）
# ─────────────────────────────────────────────────────────────

def relation_nature(chart):
    """结构性判断：谁在给 7宫/UL 供电，决定关系能否落地。"""
    aspects_7h = _aspects_to_house(chart, 7)
    sp = chart.get('special_points', {})
    ul_house = sp.get('UL', {}).get('house')
    aspects_ul = _aspects_to_house(chart, ul_house) if ul_house else []

    jupiter_on_7 = 'Jupiter' in aspects_7h or _house(chart, 'Jupiter') == 7
    saturn_on_7 = 'Saturn' in aspects_7h or _house(chart, 'Saturn') == 7
    jupiter_on_ul = 'Jupiter' in aspects_ul

    notes = []
    if saturn_on_7 and jupiter_on_7:
        nature = '落地型（土木同临7宫）'
        notes.append('土星给关系稳定性+木星给成长性→倾向长期落地关系')
    elif saturn_on_7:
        nature = '慢热稳定型（土星临7宫）'
        notes.append('土星临7宫→关系慢热、需时间验证，但一旦成立较稳固')
    elif jupiter_on_7:
        nature = '滋养成长型（木星临7宫）'
        notes.append('木星临7宫→关系带成长/保护色彩')
    else:
        nature = '结构中性（7宫无土木直接供电）'
        notes.append('7宫无土星/木星直接影响→关系性质更多由大运时机决定')

    if jupiter_on_ul:
        notes.append('木星照UL→有"官宣/公开化"的助力')

    return {
        'nature': nature,
        'aspects_7h': aspects_7h,
        'ul_house': ul_house,
        'aspects_ul': aspects_ul,
        'notes': notes,
    }


# ─────────────────────────────────────────────────────────────
# D60 业力层对感情判定的补充
# ─────────────────────────────────────────────────────────────

def d60_love_supplement(chart):
    """D60 第5宫（恋爱/创造）和第7宫（配偶）的行星及尊贵度 → 配偶业力品质修正。
    D60 5宫 = 前世恋爱业力；D60 7宫 = 前世配偶/合伙业力。
    """
    karma = chart.get('d60_karma') or {}
    zones = chart.get('d60_zones') or {}
    dignities = chart.get('d60_dignities') or {}
    cross = chart.get('d60_cross') or {}
    if not karma:
        return {'available': False}

    # D60 7宫行星（配偶业力宫）
    d60_7h = [p for p, z in zones.items() if z.get('house') == 7]
    # D60 5宫行星（恋爱业力宫）
    d60_5h = [p for p, z in zones.items() if z.get('house') == 5]

    # 配偶业力资产/欠账（7宫住客 or Venus/Moon 的 karma）
    spouse_assets = [p for p in ['Venus','Moon','Jupiter']
                     if karma.get(p, {}).get('karma_type') == 'asset']
    spouse_debts = [p for p in ['Venus','Moon','Jupiter']
                    if karma.get(p, {}).get('karma_type') in ('debt','heavy_debt')]

    # D60 7宫整体品质
    if d60_7h:
        h7_dignities = {p: dignities.get(p, 'neutral') for p in d60_7h}
        any_strong = any(d in ('exalted','own_sign','great_friend','friend')
                         for d in h7_dignities.values())
        any_weak = any(d in ('debilitated','great_enemy')
                       for d in h7_dignities.values())
        if any_strong and not any_weak:
            d60_7h_quality = '吉（D60配偶宫有强星）'
        elif any_weak:
            d60_7h_quality = '凶（D60配偶宫有受损星）'
        else:
            d60_7h_quality = '中性'
    else:
        d60_7h_quality = '空宫（无行星直接影响）'

    # Venus D60×D1 交叉
    venus_cross = cross.get('Venus', {}).get('cross_type', 'mixed')

    return {
        'available': True,
        'd60_7h_planets': d60_7h,
        'd60_5h_planets': d60_5h,
        'd60_7h_quality': d60_7h_quality,
        'spouse_karma_assets': spouse_assets,
        'spouse_karma_debts': spouse_debts,
        'venus_d60_d1_cross': venus_cross,
    }


# ─────────────────────────────────────────────────────────────
# 配偶外貌气质线索（用于真爱画像功能）
# ─────────────────────────────────────────────────────────────

# 12 星座 → 外貌气质关键词（基于 KN Rao 体系的行星/星座特质）
# 注：这是"气质风格"推断，非硬性长相预测；供 AI 撰写画像参考
_SIGN_APPEARANCE = {
    'Aries':       {'vibe': '锐利有朝气', 'style': '个性鲜明，轮廓立体或表情生动', 'energy': '主动'},
    'Taurus':      {'vibe': '温润饱满',   'style': '五官圆润，有美感，气质稳重',     'energy': '感性'},
    'Gemini':      {'vibe': '灵动多变',   'style': '眼神活泼，五官清秀，带机灵感',   'energy': '活跃'},
    'Cancer':      {'vibe': '柔和温婉',   'style': '面部圆润，眼神温柔，气质温暖',   'energy': '内敛'},
    'Leo':         {'vibe': '明艳大方',   'style': '气场强，五官有存在感，容易成为焦点', 'energy': '外放'},
    'Virgo':       {'vibe': '精致克制',   'style': '五官精巧，气质整洁，带知性感',   'energy': '细腻'},
    'Libra':       {'vibe': '匀称柔美',   'style': '五官平衡，气质温和，天然有亲和力', 'energy': '和谐'},
    'Scorpio':     {'vibe': '深邃神秘',   'style': '眼神深沉，气质有磁性，不易被看透', 'energy': '内敛'},
    'Sagittarius': {'vibe': '开朗爽朗',   'style': '轮廓舒展，笑容有感染力，朝气蓬勃', 'energy': '外放'},
    'Capricorn':   {'vibe': '稳重成熟',   'style': '气质端正，骨感突出，有岁月感',   'energy': '内敛'},
    'Aquarius':    {'vibe': '特立独行',   'style': '有独特的细节，气质难以归类，有吸引力', 'energy': '独特'},
    'Pisces':      {'vibe': '灵气飘逸',   'style': '眼神迷蒙，气质空灵，有梦幻感',   'energy': '感性'},
}

# 行星在 7 宫（住客/相位）→ 对外貌气质的修正标签
_PLANET_ON_7H_APPEARANCE = {
    'Sun':     '气质阳光或带领导感，五官有力量感，通常不会太内敛',
    'Moon':    '气质柔和，面部圆润或有流动感，情绪感强',
    'Mars':    '气质有活力或锐利感，五官有棱角或有运动感',
    'Mercury': '气质灵动，五官秀气，说话方式很有吸引力',
    'Jupiter': '气质温和开阔，体型可能偏丰润，带长者气息',
    'Venus':   '五官精致或有审美感，整体形象令人舒适，天然美感',
    'Saturn':  '气质沉稳成熟，可能偏纤细或有风骨，岁月感强',
    'Rahu':    '气质难以归类，可能有异域特征或独特的混搭风格',
    'Ketu':    '气质超脱，可能面容有特别之处，带古典或灵性感',
}

# 地域/族裔线索：哪些组合暗示可能非华人背景
# （结果仅是倾向，不是预言，AI 表述时须用模糊语气）
_OVERSEAS_INDICATORS = {
    'houses': {12, 9},     # UL 或 DK 在 9/12 宫 → 海外缘
    'signs':  {'Sagittarius', 'Pisces', 'Aquarius'},  # 12宫/木星星座 → 广域缘
    'planets': {'Rahu'},   # Rahu 主导 7 宫 → 异文化吸引
}


def spouse_appearance_hints(chart):
    """推导配偶外貌气质线索，用于生成真爱画像。

    推导链（按权重从高到低）：
      1. L7 星座 → 基础气质色调
      2. 7 宫住客行星 → 外貌特质修正
      3. 7 宫相位行星 → 补充修正
      4. D9 Venus 位置 → 灵魂层美感投射
      5. DK 星座 → 整体精致/朴素倾向
      6. UL/DK 宫位 + 星座 → 是否有海外/异文化线索

    返回结构供 love.md 的 AI 翻译成文字画像 + 绘画 prompt。
    """
    house_lords = chart['house_lords']
    l7_planet = house_lords[7]['lord']
    l7_sign = chart['planets'][l7_planet]['sign']

    # ── 1. L7 星座基础气质 ─────────────────────────────────────
    base = _SIGN_APPEARANCE.get(l7_sign, {'vibe': '气质多元', 'style': '风格不易定型', 'energy': '中性'})

    # ── 2/3. 7 宫住客 + 相位修正 ──────────────────────────────
    occupants_7h = [
        p for p in ['Sun','Moon','Mars','Mercury','Jupiter','Venus','Saturn','Rahu','Ketu']
        if chart['planets'][p]['house'] == 7
    ]
    aspects_7h = _aspects_to_house(chart, 7)
    all_7h_planets = list(dict.fromkeys(occupants_7h + aspects_7h))  # 去重，住客优先

    planet_modifiers = []
    for p in all_7h_planets[:3]:   # 最多取 3 颗，避免信息过载
        note = _PLANET_ON_7H_APPEARANCE.get(p)
        if note:
            role = '住客' if p in occupants_7h else '相位'
            planet_modifiers.append({'planet': p, 'role': role, 'note': note})

    # ── 4. D9 Venus → 灵魂层美感 ──────────────────────────────
    d9_venus_sign = None
    d9_venus_vibe = None
    d9 = chart.get('d9', {})
    venus_d9 = d9.get('Venus')
    if venus_d9:
        # d9 值可能是 (sign_str, sign_idx) 元组或 dict
        if isinstance(venus_d9, (list, tuple)):
            d9_venus_sign = venus_d9[0] if venus_d9 else None
        elif isinstance(venus_d9, dict):
            d9_venus_sign = venus_d9.get('sign')
    if d9_venus_sign:
        d9_app = _SIGN_APPEARANCE.get(d9_venus_sign, {})
        d9_venus_vibe = d9_app.get('vibe')

    # ── 5. DK 星座 → 精致度倾向 ───────────────────────────────
    dk_planet = _karaka(chart, 'DK')
    dk_sign = chart['planets'][dk_planet]['sign'] if dk_planet else None
    dk_compound = _compound(chart, dk_planet) if dk_planet else 'neutral'
    dk_quality = '精致/有品味' if dk_compound in ('exalted','own_sign','great_friend','friend') else \
                 '朴素/有个性'  if dk_compound in ('debilitated',)                              else \
                 '中性'

    # ── 6. 海外/异文化线索 ────────────────────────────────────
    sp = chart.get('special_points', {})
    ul_house = sp.get('UL', {}).get('house') or \
               (((SIGNS.index(sp.get('UL', {}).get('sign', 'Aries'))) -
                 chart['lagna']['sign_idx']) % 12 + 1 if sp.get('UL') else None)
    dk_house = chart['planets'][dk_planet]['house'] if dk_planet else None

    overseas_signals = []
    if ul_house in _OVERSEAS_INDICATORS['houses']:
        overseas_signals.append(f'UL在{ul_house}宫（海外/远方缘）')
    if dk_house in _OVERSEAS_INDICATORS['houses']:
        overseas_signals.append(f'DK在{dk_house}宫（异域相遇可能）')
    if l7_sign in _OVERSEAS_INDICATORS['signs']:
        overseas_signals.append(f'L7在{l7_sign}（广域/跨文化气质）')
    if any(p in _OVERSEAS_INDICATORS['planets'] for p in occupants_7h):
        rahu_in_7 = 'Rahu' in occupants_7h
        if rahu_in_7:
            overseas_signals.append('Rahu在7宫（异文化/非典型背景吸引）')

    has_overseas_hint = len(overseas_signals) >= 2  # 至少2个信号才标记

    # ── 整合输出 ───────────────────────────────────────────────
    return {
        # 基础气质层（L7星座）
        'base_vibe':       base['vibe'],
        'base_style':      base['style'],
        'base_energy':     base['energy'],
        'l7_planet':       l7_planet,
        'l7_sign':         l7_sign,

        # 外貌修正层（7宫行星）
        'planet_modifiers':   planet_modifiers,
        'occupants_7h':       occupants_7h,
        'aspects_7h':         aspects_7h,

        # 灵魂层美感（D9 Venus）
        'd9_venus_sign':   d9_venus_sign,
        'd9_venus_vibe':   d9_venus_vibe,

        # 品味倾向（DK）
        'dk_planet':       dk_planet,
        'dk_sign':         dk_sign,
        'dk_quality':      dk_quality,

        # 地域/背景线索
        'overseas_signals':   overseas_signals,
        'has_overseas_hint':  has_overseas_hint,
    }


# ─────────────────────────────────────────────────────────────
# 总入口
# ─────────────────────────────────────────────────────────────

def compute_love_verdicts(chart):
    return {
        'love_spouse_triangle':   spouse_triangle(chart),
        'love_timing_signals':    timing_signals(chart),
        'love_relation_nature':   relation_nature(chart),
        'love_d60_supplement':    d60_love_supplement(chart),
        'love_appearance_hints':  spouse_appearance_hints(chart),
    }



