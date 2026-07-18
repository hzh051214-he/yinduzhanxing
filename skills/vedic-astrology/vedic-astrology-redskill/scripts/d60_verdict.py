"""d60_verdict.py — D60 Shashtiamsa 客观化判定层

D60（六十分盘）是业力盘：把 D1 今生配置的"前世根源"代码化为权威标签。
五个模块：
  1. d60_dignity      : 每颗行星在 D60 的尊贵度（复用 D1 Panchadha Maitri 规则）
  2. d60_house_zone   : 每颗行星在 D60 的宫位安全区（金库/摩擦/有毒）
  3. karma_classify   : 业力资产/欠账四分类（Asset/Locked/Debt/HeavyDebt）
  4. d60_d1_cross     : D60 × D1 交叉（业力支撑/透支/双层巩固/惯性待破）
  5. d60_lagna_theme  : D60 Lagna + 住客 → 业力底色主题标签

接入规则：
  - D60 结论不覆盖 D1 结论，只提供"业力层"的修正权重（±1.0 分上限）
  - 仅在 d60_trust_level in ('verified', 'computed') 时参与确定性判定
  - 'uncertain'/'disabled' 时跳过所有判定，不影响 verdict/career/love 结论

输入来自 engine.calculate_full_chart() 返回的 chart dict（已含 d60 数据）。
"""

# ── 共享常量（与 engine.py 和 verdict.py 保持一致）──

SIGNS = ['Aries','Taurus','Gemini','Cancer','Leo','Virgo',
         'Libra','Scorpio','Sagittarius','Capricorn','Aquarius','Pisces']

SIGN_LORDS = {
    0:'Mars', 1:'Venus', 2:'Mercury', 3:'Moon', 4:'Sun', 5:'Mercury',
    6:'Venus', 7:'Mars', 8:'Jupiter', 9:'Saturn', 10:'Saturn', 11:'Jupiter'
}

EXALTATION   = {'Sun':'Aries','Moon':'Taurus','Mars':'Capricorn',
                'Mercury':'Virgo','Jupiter':'Cancer','Venus':'Pisces','Saturn':'Libra'}
DEBILITATION = {'Sun':'Libra','Moon':'Scorpio','Mars':'Cancer',
                'Mercury':'Pisces','Jupiter':'Capricorn','Venus':'Virgo','Saturn':'Aries'}
OWN_SIGNS    = {'Sun':['Leo'],'Moon':['Cancer'],'Mars':['Aries','Scorpio'],
                'Mercury':['Gemini','Virgo'],'Jupiter':['Sagittarius','Pisces'],
                'Venus':['Taurus','Libra'],'Saturn':['Capricorn','Aquarius']}

NATURAL_REL = {
    'Sun':     {'friend':{'Moon','Mars','Jupiter'}, 'enemy':{'Venus','Saturn'}, 'neutral':{'Mercury'}},
    'Moon':    {'friend':{'Sun','Mercury'}, 'enemy':set(), 'neutral':{'Mars','Jupiter','Venus','Saturn'}},
    'Mars':    {'friend':{'Sun','Moon','Jupiter'}, 'enemy':{'Mercury'}, 'neutral':{'Venus','Saturn'}},
    'Mercury': {'friend':{'Sun','Venus'}, 'enemy':{'Moon'}, 'neutral':{'Mars','Jupiter','Saturn'}},
    'Jupiter': {'friend':{'Sun','Moon','Mars'}, 'enemy':{'Mercury','Venus'}, 'neutral':{'Saturn'}},
    'Venus':   {'friend':{'Mercury','Saturn'}, 'enemy':{'Sun','Moon'}, 'neutral':{'Mars','Jupiter'}},
    'Saturn':  {'friend':{'Mercury','Venus'}, 'enemy':{'Sun','Moon','Mars'}, 'neutral':{'Jupiter'}},
}
COMPOUND_TABLE = {
    ('friend','temp_friend'):'great_friend', ('friend','temp_enemy'):'neutral',
    ('enemy','temp_friend'):'neutral',       ('enemy','temp_enemy'):'great_enemy',
    ('neutral','temp_friend'):'friend',      ('neutral','temp_enemy'):'enemy',
}

TRIKONA = {1, 5, 9}
KENDRA  = {1, 4, 7, 10}
DUSTHANA = {6, 8, 12}
GOOD_HOUSES = {1, 4, 5, 7, 9, 10}   # 金库区
FRICTION_HOUSES = {3, 6, 11}         # 摩擦区（增益但有代价）
TOXIC_HOUSES = {8, 12}               # 有毒区（得而复失）

PLANETS7 = ['Sun','Moon','Mars','Mercury','Jupiter','Venus','Saturn']
PLANETS9 = PLANETS7 + ['Rahu','Ketu']

DIGNITY_STRONG = {'exalted', 'own_sign', 'great_friend', 'friend'}
DIGNITY_WEAK   = {'great_enemy', 'debilitated'}


# ─────────────────────────────────────────────────────────────
# 模块1：D60 行星尊贵度
# ─────────────────────────────────────────────────────────────

def _d60_dignity(planet, sign_idx, d60_planets_sign_idx):
    """计算某行星在 D60 的 Panchadha Maitri 复合尊贵度。
    与 engine.py 的 dignity_data 计算逻辑完全一致，传入 D60 的 sign_idx 即可。
    Rahu/Ketu 无传统 dignity，返回 'node'。
    """
    if planet in ('Rahu', 'Ketu'):
        return 'node'
    sign = SIGNS[sign_idx]
    lord = SIGN_LORDS[sign_idx]
    if EXALTATION.get(planet) == sign:
        return 'exalted'
    if DEBILITATION.get(planet) == sign:
        return 'debilitated'
    if sign in OWN_SIGNS.get(planet, []):
        return 'own_sign'
    # Panchadha Maitri
    if lord == planet:
        return 'own_sign'
    rel = NATURAL_REL.get(planet, {})
    if lord in rel.get('friend', set()):
        natural = 'friend'
    elif lord in rel.get('enemy', set()):
        natural = 'enemy'
    else:
        natural = 'neutral'
    # 临时关系：座主落在行星的2/3/4/10/11/12宫（从行星所在sign_idx数）
    lord_sidx = d60_planets_sign_idx.get(lord, sign_idx)
    dist = (lord_sidx - sign_idx) % 12
    temporal = 'temp_friend' if dist in {1,2,3,9,10,11} else 'temp_enemy'
    return COMPOUND_TABLE.get((natural, temporal), 'neutral')


def calc_d60_dignities(chart):
    """返回 {planet: dignity_str} for all 9 planets."""
    d60 = chart.get('d60') or {}
    if not d60:
        return {}
    # 建立 D60 行星 → sign_idx 映射（用于临时关系计算）
    p_sidx = {p: d60[p][1] for p in PLANETS9 if p in d60}
    result = {}
    for p in PLANETS9:
        if p not in d60:
            continue
        _, sidx = d60[p]
        result[p] = _d60_dignity(p, sidx, p_sidx)
    return result


# ─────────────────────────────────────────────────────────────
# 模块2：D60 宫位安全区（从 D60 Lagna 数）
# ─────────────────────────────────────────────────────────────

def _d60_house(d60, planet):
    """从 D60 Lagna 数，返回行星的 D60 宫位号（1-12）。"""
    lagna_idx = d60['Lagna'][1]
    _, sidx = d60[planet]
    return ((sidx - lagna_idx) % 12) + 1


def calc_d60_house_zones(chart):
    """返回 {planet: {'house': int, 'zone': str}}。
    zone: 'asset'(金库区) / 'friction'(摩擦区) / 'toxic'(有毒区) / 'neutral'
    """
    d60 = chart.get('d60') or {}
    if not d60 or 'Lagna' not in d60:
        return {}
    result = {}
    for p in PLANETS9:
        if p not in d60:
            continue
        h = _d60_house(d60, p)
        if h in GOOD_HOUSES:
            zone = 'asset_zone'
        elif h in FRICTION_HOUSES:
            zone = 'friction_zone'
        elif h in TOXIC_HOUSES:
            zone = 'toxic_zone'
        else:
            zone = 'neutral_zone'
        result[p] = {'house': h, 'zone': zone}
    return result


# ─────────────────────────────────────────────────────────────
# 模块3：业力资产/欠账四分类
# ─────────────────────────────────────────────────────────────

# 分类标签（中英文）
KARMA_LABELS = {
    'asset':       ('业力资产', '前世积累，今生可直接提取'),
    'locked':      ('封印资产', '前世有积累但被凶宫封存，需特定条件解锁'),
    'debt':        ('业力欠账', '前世不足，今生需努力补足'),
    'heavy_debt':  ('重欠业力', '前世负积累，今生面临系统性阻力'),
    'node_asset':  ('节点资产', '轴线业力，Rahu扩展/Ketu释放'),
    'neutral':     ('中性业力', '平衡状态，无明显资产或欠账'),
}

def _karma_classify(dignity, zone):
    """四象限分类：dignity（强/弱）× zone（吉/凶）。"""
    if dignity == 'node':
        return 'node_asset'
    strong = dignity in DIGNITY_STRONG
    weak   = dignity in DIGNITY_WEAK
    good_z = zone in ('asset_zone', 'friction_zone')
    bad_z  = zone in ('toxic_zone',)
    if strong and good_z:
        return 'asset'
    if strong and bad_z:
        return 'locked'
    if weak and good_z:
        return 'debt'
    if weak and bad_z:
        return 'heavy_debt'
    return 'neutral'


def calc_karma_classification(d60_dignities, d60_zones):
    """返回 {planet: {'karma_type': str, 'label': str, 'desc': str}}。"""
    result = {}
    for p in PLANETS9:
        dig = d60_dignities.get(p, 'neutral')
        zone_info = d60_zones.get(p, {})
        zone = zone_info.get('zone', 'neutral_zone')
        karma = _karma_classify(dig, zone)
        label, desc = KARMA_LABELS.get(karma, ('未知', ''))
        result[p] = {
            'karma_type': karma,
            'label': label,
            'desc': desc,
            'd60_dignity': dig,
            'd60_house': zone_info.get('house'),
            'd60_zone': zone,
        }
    return result


# ─────────────────────────────────────────────────────────────
# 模块4：D60 × D1 交叉标注
# ─────────────────────────────────────────────────────────────

CROSS_LABELS = {
    'reinforced':    ('双层巩固', 'D1强+D60强：今生优势有业力根基，最稳固'),
    'supported':     ('业力支撑', 'D1弱+D60强：今生困难但有前世底气，能翻盘'),
    'overdrawn':     ('业力透支', 'D1强+D60弱：今生优势没有前世积累支撑，需防根基不稳'),
    'inertia':       ('惯性待破', 'D1弱+D60弱：两层均弱，今生需要主动打破业力惯性'),
    'mixed':         ('混合业力', 'D1中性或节点，需结合宫位具体判断'),
}

def _is_strong(dignity):
    return dignity in DIGNITY_STRONG or dignity == 'exalted' or dignity == 'own_sign'

def _is_weak(dignity):
    return dignity in DIGNITY_WEAK

def calc_d60_d1_cross(chart, d60_dignities):
    """D60 × D1 业力交叉分析。
    D1 dignity 从 chart['dignity'] 读取（Panchadha Maitri 已算好）。
    返回 {planet: {'cross_type': str, 'label': str, 'desc': str, 'd1_dignity': str, 'd60_dignity': str}}
    """
    d1_dignity = chart.get('dignity') or {}
    result = {}
    for p in PLANETS7:
        d1_dig = d1_dignity.get(p, {}).get('compound', 'neutral')
        d60_dig = d60_dignities.get(p, 'neutral')
        d1_strong = _is_strong(d1_dig)
        d1_weak   = _is_weak(d1_dig)
        d60_strong = _is_strong(d60_dig)
        d60_weak   = _is_weak(d60_dig)
        if d1_strong and d60_strong:
            cross = 'reinforced'
        elif not d1_strong and not d1_weak and d60_strong:
            cross = 'supported'
        elif d1_weak and d60_strong:
            cross = 'supported'
        elif d1_strong and d60_weak:
            cross = 'overdrawn'
        elif d1_weak and d60_weak:
            cross = 'inertia'
        else:
            cross = 'mixed'
        label, desc = CROSS_LABELS.get(cross, ('混合', ''))
        result[p] = {
            'cross_type': cross,
            'label': label,
            'desc': desc,
            'd1_dignity': d1_dig,
            'd60_dignity': d60_dig,
        }
    return result


# ─────────────────────────────────────────────────────────────
# 模块5：D60 Lagna 业力底色主题
# ─────────────────────────────────────────────────────────────

# D60 Lagna 星座 → 业力主题标签
LAGNA_KARMA_THEMES = {
    'Aries':       ('行动与突破', '带来行动力和先锋业力，课题是在限制中建设，习惯于用行动解决问题'),
    'Taurus':      ('稳固与积累', '带来物质积累和审美业力，课题是在安全感中寻求成长，易陷执著'),
    'Gemini':      ('连接与传递', '带来信息传递和社交业力，课题是深度与广度的平衡，易分散'),
    'Cancer':      ('情感与根源', '带来家庭和情感业力，课题是依恋与独立的张力，深层安全感议题'),
    'Leo':         ('荣耀与创造', '带来创造力和领导业力，课题是荣耀与谦逊，渴望被看见但需超越自我'),
    'Virgo':       ('完善与服务', '带来分析和服务业力，课题是完美主义和自我批评，技艺精进的执念'),
    'Libra':       ('平衡与关系', '带来合作和美学业力，课题是决策力和边界感，容易为了和谐而妥协'),
    'Scorpio':     ('深度与转化', '带来转化和洞察业力，课题是控制与放手，深度信任的建立'),
    'Sagittarius': ('追寻与智慧', '带来哲学和扩展业力，课题是承诺与自由的张力，将信念转化为行动'),
    'Capricorn':   ('责任与建设', '带来纪律和成就业力，课题是放下对成功的执着，允许脆弱'),
    'Aquarius':    ('革新与集体', '带来改革和人道主义业力，课题是个人与群体的张力，情感疏离倾向'),
    'Pisces':      ('消融与灵性', '带来灵性和共情业力，课题是边界感和自我保护，容易失去自我'),
}

def calc_d60_lagna_theme(chart):
    """D60 Lagna 业力主题 + 住客行星。"""
    d60 = chart.get('d60') or {}
    if not d60 or 'Lagna' not in d60:
        return {}
    lagna_sign, lagna_idx = d60['Lagna']
    theme_name, theme_desc = LAGNA_KARMA_THEMES.get(lagna_sign, ('未知', ''))
    # D60 Lagna 宫（1宫）住客
    occupants = [p for p in PLANETS9
                 if p in d60 and d60[p][1] == lagna_idx]
    return {
        'lagna_sign': lagna_sign,
        'theme_name': theme_name,
        'theme_desc': theme_desc,
        'lagna_occupants': occupants,
    }


# ─────────────────────────────────────────────────────────────
# D60 对 Dasha 判定的修正权重（接入 verdict.py）
# ─────────────────────────────────────────────────────────────

def d60_dasha_modifier(planet, karma_data, cross_data):
    """返回 D60 对某大运星的修正信号（正面/负面理由列表），供 verdict.py 使用。
    权重上限：正面 +1 条，负面 +1 条（不超过此量，避免 D60 主导 D1 结论）。
    仅在 karma_type 明确时产生信号，'neutral'/'mixed' 不干预。
    """
    pos, neg = [], []
    karma = karma_data.get(planet, {})
    cross = cross_data.get(planet, {})
    k_type = karma.get('karma_type', 'neutral')
    c_type = cross.get('cross_type', 'mixed')
    # 业力资产 → 正面信号
    if k_type == 'asset':
        pos.append(f'D60业力资产(前世积累，{karma.get("d60_dignity")}，{karma.get("d60_house")}宫)')
    elif k_type == 'locked':
        neg.append(f'D60封印资产(前世积累被凶宫封存，{karma.get("d60_house")}宫)')
    elif k_type == 'debt':
        neg.append(f'D60业力欠账(前世不足，{karma.get("d60_dignity")}，{karma.get("d60_house")}宫)')
    elif k_type == 'heavy_debt':
        neg.append(f'D60重欠业力(前世负积累，{karma.get("d60_house")}宫凶位)')
    # D1×D60 交叉补充（仅在 karma 中性时起作用，避免双重计分）
    if k_type == 'neutral':
        if c_type == 'reinforced':
            pos.append('D60×D1双层巩固(业力有根基)')
        elif c_type == 'supported':
            pos.append('D60业力支撑(前世有底气，今生困难可翻盘)')
        elif c_type == 'overdrawn':
            neg.append('D60业力透支(今生优势无前世积累，防根基不稳)')
        elif c_type == 'inertia':
            neg.append('D60惯性待破(两层均弱，需主动突破业力惯性)')
    return pos, neg


# ─────────────────────────────────────────────────────────────
# 总入口
# ─────────────────────────────────────────────────────────────

def compute_d60_verdicts(chart):
    """计算全部 D60 判定层，返回结构化结果。
    若 d60_trust_level 为 'uncertain' 或 'disabled'，跳过所有判定。
    """
    trust = chart.get('d60_trust_level', 'uncertain')
    if trust not in ('verified', 'computed'):
        return {
            'd60_verdicts_skipped': True,
            'd60_verdicts_skip_reason': f'd60_trust_level={trust}，不参与确定性判定',
        }
    d60 = chart.get('d60') or {}
    if not d60 or 'Lagna' not in d60:
        return {'d60_verdicts_skipped': True, 'd60_verdicts_skip_reason': 'D60数据缺失'}

    dignities   = calc_d60_dignities(chart)
    zones       = calc_d60_house_zones(chart)
    karma       = calc_karma_classification(dignities, zones)
    cross       = calc_d60_d1_cross(chart, dignities)
    lagna_theme = calc_d60_lagna_theme(chart)

    # 预计算每颗大运星的修正信号（verdict.py 可直接读取）
    dasha_modifiers = {}
    for p in PLANETS9:
        pos, neg = d60_dasha_modifier(p, karma, cross)
        if pos or neg:
            dasha_modifiers[p] = {'positive': pos, 'negative': neg}

    return {
        'd60_dignities':      dignities,
        'd60_zones':          zones,
        'd60_karma':          karma,
        'd60_cross':          cross,
        'd60_lagna_theme':    lagna_theme,
        'd60_dasha_modifiers': dasha_modifiers,
        'd60_verdicts_skipped': False,
    }
