"""career_verdict.py — 事业确定性判定层

把 career.md 中原本由 AI 心算的 Phase 1-4 判断落地为代码，产出权威标签：
  - classify_niche   : 职场生态位（权威/竞争/商贸/隐形型）
  - monetization     : 变现路径（产品/流量/危机/资产型）
  - karakamsha       : AmK 事业内核（AmK 所在 D9 星座当 Lagna）
  - career_timing    : 事业大运吉凶（复用 verdict.dasha 判定，聚焦 L10/AmK/10宫住客）

career 的 AI 只负责把这些结构标签翻译成现代行业建议，不得擅自翻转。
所有输入来自 engine.calculate_full_chart() 返回的 chart dict。
"""

SIGNS = ['Aries','Taurus','Gemini','Cancer','Leo','Virgo',
         'Libra','Scorpio','Sagittarius','Capricorn','Aquarius','Pisces']

SIGN_LORDS = {
    0:'Mars', 1:'Venus', 2:'Mercury', 3:'Moon', 4:'Sun', 5:'Mercury',
    6:'Venus', 7:'Mars', 8:'Jupiter', 9:'Saturn', 10:'Saturn', 11:'Jupiter'
}

# 各行星/宫位对应的职场生态位倾向
AUTHORITY_PLANETS = {'Sun', 'Jupiter'}      # 权威/稳态
MARKET_PLANETS = {'Saturn', 'Mercury', 'Rahu'}  # 市场/竞争
DUSTHANA = {6, 8, 12}
KENDRA = {1, 4, 7, 10}


def _house(chart, planet):
    return chart['planets'][planet]['house']


def _sign_idx(chart, planet):
    return chart['planets'][planet]['sign_idx']


def _compound(chart, planet):
    return chart['dignity'].get(planet, {}).get('compound', 'neutral')


def _shadbala_pct(chart, planet):
    val = chart['shadbala'].get(planet)
    if isinstance(val, dict):
        return val.get('strength_pct')
    return None


def _sav_house(chart, house):
    return chart['sav_by_house'].get(house, {}).get('value', 0)


def _associated_planets(chart, target):
    """与 target 有相位/合相关系的行星集合（读引擎已算好的 aspects）"""
    assoc = set()
    for a in chart['aspects']:
        if a['p1'] == target:
            assoc.add(a['p2'])
        elif a['p2'] == target:
            assoc.add(a['p1'])
    return assoc


# ─────────────────────────────────────────────────────────────
# 1. 职场生态位
# ─────────────────────────────────────────────────────────────

def classify_niche(chart):
    """按 L10 落宫 + L10 关联行星 + 10宫住客 判定生态位（可复合）。"""
    house_lords = chart['house_lords']
    l10 = house_lords[10]['lord']
    l10_house = _house(chart, l10)
    l10_assoc = _associated_planets(chart, l10)

    # 10宫住客
    occupants = [p for p in ['Sun','Moon','Mars','Mercury','Jupiter','Venus','Saturn','Rahu','Ketu']
                 if _house(chart, p) == 10]

    niches = []
    reasons = []

    # 权威/稳态型：L10 或 10宫住客关联 太阳/木星/9宫
    if (l10 in AUTHORITY_PLANETS or l10_assoc & AUTHORITY_PLANETS
            or set(occupants) & AUTHORITY_PLANETS or l10_house == 9):
        niches.append('权威/稳态型')
        reasons.append('L10或10宫关联太阳/木星/9宫→制度、权威、专业声誉路线')

    # 市场/竞争型：L10 关联 土星/水星/罗睺，或 6宫能量强
    if (l10 in MARKET_PLANETS or l10_assoc & MARKET_PLANETS
            or set(occupants) & MARKET_PLANETS):
        niches.append('市场/竞争型')
        reasons.append('L10或10宫关联土星/水星/罗睺→竞争、市场、效率驱动')

    # 商贸/自由型：L10 落 7/3/5 宫，或关联这些宫的主
    if l10_house in (3, 5, 7):
        niches.append('商贸/自由型')
        reasons.append(f'L10落{l10_house}宫→交易、创造、伙伴关系驱动的自由路线')

    # 隐形/虚拟型：L10 落 8/12 宫，或关联 8/12 宫主
    if l10_house in DUSTHANA:
        niches.append('隐形/虚拟型')
        reasons.append(f'L10落{l10_house}宫→研究、幕后、跨境、非常规路径')

    # 兜底：L10 落 kendra 但无以上特征 → 执行/建设型
    if not niches:
        niches.append('执行/建设型')
        reasons.append(f'L10落{l10_house}宫，无特殊倾向→稳健执行、长期建设')

    return {
        'l10': l10,
        'l10_house': l10_house,
        'l10_dignity': _compound(chart, l10),
        'l10_shadbala': _shadbala_pct(chart, l10),
        'occupants_10h': occupants,
        'niches': niches,
        'reasons': reasons,
    }


# ─────────────────────────────────────────────────────────────
# 2. 变现路径
# ─────────────────────────────────────────────────────────────

def monetization(chart):
    """按强星（Shadbala≥120% 或 入旺/入庙/Yogakaraka）连接 2/8/11 宫判定变现路径。"""
    house_lords = chart['house_lords']
    roles = chart.get('roles', {})

    # 强星集合
    strong = set()
    for p in ['Sun','Moon','Mars','Mercury','Jupiter','Venus','Saturn']:
        pct = _shadbala_pct(chart, p)
        comp = _compound(chart, p)
        if (pct and pct >= 120) or comp in ('exalted', 'own_sign') or roles.get(p, {}).get('is_yogakaraka'):
            strong.add(p)

    l2 = house_lords[2]['lord']
    l11 = house_lords[11]['lord']
    l8 = house_lords[8]['lord']

    paths = []
    # 路径A：强星连接2宫（产品/资产型）
    if l2 in strong or any(_house(chart, s) == 2 for s in strong):
        paths.append(('产品/资产型', f'2宫主{l2}或强星入2宫→积累型财富(不动产/产品/存量)', _sav_house(chart, 2)))
    # 路径B：强星连接11宫（流量/服务型）
    if l11 in strong or any(_house(chart, s) == 11 for s in strong):
        paths.append(('流量/服务型', f'11宫主{l11}或强星入11宫→流量型收益(服务/社交/增长)', _sav_house(chart, 11)))
    # 路径C：强星连接8宫（危机/资源型）
    if l8 in strong or any(_house(chart, s) == 8 for s in strong):
        paths.append(('危机/资源型', f'8宫主{l8}或强星入8宫→他人资源(投资/继承/危机咨询)', _sav_house(chart, 8)))

    if not paths:
        paths.append(('常规工资型', '无强星连接2/8/11宫→以稳定收入为主，非爆发型', _sav_house(chart, 11)))

    return {
        'strong_planets': sorted(strong),
        'paths': [{'type': t, 'reason': r, 'sav': s} for t, r, s in paths],
    }


# ─────────────────────────────────────────────────────────────
# 3. Karakamsha（AmK 事业内核）
# ─────────────────────────────────────────────────────────────

def karakamsha(chart):
    """AmK（事业指示星）在 D9 的落座星座 = Karakamsha Lagna。
    Karakamsha 所在星座 + 其内/相关行星，揭示事业的灵魂驱动。
    """
    # AmK：8K 体系第 2 位
    amk = None
    for k, planet, deg in chart['karakas'].get('8k', []):
        if k == 'AmK':
            amk = planet
            break
    if amk is None:
        return {'available': False}

    # AmK 在 D9 的星座
    d9 = chart.get('d9', {})
    amk_d9 = d9.get(amk)
    if not amk_d9:
        return {'available': False, 'amk': amk}
    # d9 legacy 格式 (sign_name, sign_idx)
    if isinstance(amk_d9, tuple):
        k_sign, k_idx = amk_d9
    elif isinstance(amk_d9, dict):
        k_sign, k_idx = amk_d9.get('sign'), amk_d9.get('sign_idx')
    else:
        return {'available': False, 'amk': amk}

    # 落在 Karakamsha（第1宫）及其 10宫（从 Karakamsha 数）的 D9 行星
    def d9_house_from(planet_idx, lagna_idx):
        return ((planet_idx - lagna_idx) % 12) + 1

    ka_occupants = {'1宫': [], '10宫': []}
    for name in ['Sun','Moon','Mars','Mercury','Jupiter','Venus','Saturn','Rahu','Ketu']:
        pd9 = d9.get(name)
        if isinstance(pd9, tuple):
            pidx = pd9[1]
        elif isinstance(pd9, dict):
            pidx = pd9.get('sign_idx')
        else:
            continue
        h = d9_house_from(pidx, k_idx)
        if h == 1:
            ka_occupants['1宫'].append(name)
        elif h == 10:
            ka_occupants['10宫'].append(name)

    return {
        'available': True,
        'amk': amk,
        'karakamsha_sign': k_sign,
        'karakamsha_lord': SIGN_LORDS.get(k_idx),
        'in_karakamsha_1h': ka_occupants['1宫'],
        'in_karakamsha_10h': ka_occupants['10宫'],
    }


# ─────────────────────────────────────────────────────────────
# 4. D60 业力层对事业判定的补充
# ─────────────────────────────────────────────────────────────

def d60_career_supplement(chart):
    """读取 D60 判定结果，提取事业相关的业力信号。
    D60 10宫（从 D60 Lagna 数）= 业力层的职业天赋宫，强星/业力资产 = 前世职业积累。
    """
    karma = chart.get('d60_karma') or {}
    zones = chart.get('d60_zones') or {}
    if not karma:
        return {'available': False}
    # D60 10宫的行星
    d60_10h_planets = [p for p, z in zones.items() if z.get('house') == 10]
    # D60 业力资产中与事业相关的星
    career_assets = [p for p, k in karma.items()
                     if k.get('karma_type') == 'asset' and p in ['Mercury','Saturn','Sun','Jupiter','Mars']]
    career_debts = [p for p, k in karma.items()
                    if k.get('karma_type') in ('debt','heavy_debt') and p in ['Mercury','Saturn','Venus','Jupiter']]
    # D60×D1 交叉中"业力支撑"（今生弱但有前世底气）
    cross = chart.get('d60_cross') or {}
    supported_career = [p for p, c in cross.items()
                        if c.get('cross_type') == 'supported' and p in ['Mercury','Saturn','Venus','Sun','Jupiter']]
    return {
        'available': True,
        'd60_10h_planets': d60_10h_planets,   # D60 事业宫行星
        'karma_assets_career': career_assets,  # 前世职业积累的星
        'karma_debts_career': career_debts,    # 前世职业欠账的星
        'supported_career': supported_career,  # 今生弱但有业力支撑的星
    }


# ─────────────────────────────────────────────────────────────
# 总入口
# ─────────────────────────────────────────────────────────────

def compute_career_verdicts(chart):
    return {
        'career_niche': classify_niche(chart),
        'career_monetization': monetization(chart),
        'career_karakamsha': karakamsha(chart),
        'career_d60_supplement': d60_career_supplement(chart),
    }



