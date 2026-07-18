"""verdict.py — 确定性判定层（#6）

把原本由 AI 散文心算的判断落地成代码，产出权威标签：
  - classify_roles : P1 角色身份 + 功能吉凶
  - judge_dashas   : 大运/小运吉凶四分类（house_framework.md:134-171）
  - detect_yogas   : 格局识别 + 破格/孤立 + 激活窗口（yogas.md）

不反向 import engine（仅本地常量），避免循环依赖。
所有输入来自 engine.calculate_full_chart() 返回的 chart dict。
"""

from datetime import date, timedelta

SIGNS = ['Aries','Taurus','Gemini','Cancer','Leo','Virgo',
         'Libra','Scorpio','Sagittarius','Capricorn','Aquarius','Pisces']

SIGN_LORDS = {
    0:'Mars', 1:'Venus', 2:'Mercury', 3:'Moon', 4:'Sun', 5:'Mercury',
    6:'Venus', 7:'Mars', 8:'Jupiter', 9:'Saturn', 10:'Saturn', 11:'Jupiter'
}

SIGN_IDX = {s: i for i, s in enumerate(SIGNS)}

DEBILITATION = {
    'Sun': 'Libra', 'Moon': 'Scorpio', 'Mars': 'Cancer',
    'Mercury': 'Pisces', 'Jupiter': 'Capricorn', 'Venus': 'Virgo', 'Saturn': 'Aries'
}

EXALTATION_SIGN = {
    'Sun': 'Aries', 'Moon': 'Taurus', 'Mars': 'Capricorn',
    'Mercury': 'Virgo', 'Jupiter': 'Cancer', 'Venus': 'Pisces', 'Saturn': 'Libra'
}

PLANETS7 = ['Sun','Moon','Mars','Mercury','Jupiter','Venus','Saturn']
PLANETS9 = PLANETS7 + ['Rahu','Ketu']
NATURAL_MALEFICS = {'Mars','Saturn','Rahu','Ketu','Sun'}

TRIKONA = {1, 5, 9}
KENDRA = {1, 4, 7, 10}
DUSTHANA = {6, 8, 12}
GOOD_HOUSES = {1, 4, 5, 7, 9, 10}

# 复合尊贵度 ≥ 友方
DIGNITY_FRIENDLY = {'exalted', 'own_sign', 'great_friend', 'friend'}
DIGNITY_DAMAGED = {'debilitated'}

# Dig Bala 最强宫位（行星落此宫获方向力量）
DIGBALA_HOUSE = {'Jupiter':1, 'Mercury':1, 'Moon':4, 'Venus':4,
                 'Saturn':7, 'Sun':10, 'Mars':10}

# Shadbala 必需 Rupa（Requisite Strength）基准值
# ★ 依据：BPHS（Brihat Parashara Hora Shastra）第 27 章
#         与 B.V. Raman《Hindu Predictive Astrology》第 10 章引用值完全一致
# ★ 与 shadbala_pyjhora.py 的 _REQUIRED_RUPAS_BPHS 保持同步
# ⚠️ PyJHora const.shad_bala_factors 里 Sun = 5.0（非标准），本文件不采用
_ISHTA_BALA_RUPAS = {
    'Sun': 6.5, 'Moon': 6.0, 'Mars': 5.0,
    'Mercury': 7.0, 'Jupiter': 6.5, 'Venus': 5.5, 'Saturn': 5.0,
}


# ─────────────────────────────────────────────────────────────
# 基础工具
# ─────────────────────────────────────────────────────────────

def _owned_houses(house_lords):
    """planet -> [它担任宫主的宫位号...]"""
    owned = {}
    for h in range(1, 13):
        lord = house_lords[h]['lord']
        owned.setdefault(lord, []).append(h)
    return owned


def _sign_idx(chart, planet):
    return chart['planets'][planet]['sign_idx']


def _house(chart, planet):
    return chart['planets'][planet]['house']


def _compound(chart, planet):
    return chart['dignity'].get(planet, {}).get('compound', 'neutral')


def _shadbala_pct(chart, planet):
    """7 颗主星返回百分比；Rahu/Ketu 无 Shadbala 返回 None"""
    val = chart['shadbala'].get(planet)
    if isinstance(val, dict):
        return val.get('strength_pct')
    return None


def _is_combust(chart, planet):
    return planet in (chart.get('combustion') or {})


def _war_losers(chart):
    """行星战争败者集合：同星座且 <1°，经度大者败（Sun/Moon/Rahu/Ketu 除外）"""
    losers = set()
    contenders = ['Mars','Mercury','Jupiter','Venus','Saturn']
    for i in range(len(contenders)):
        for j in range(i+1, len(contenders)):
            a, b = contenders[i], contenders[j]
            pa, pb = chart['planets'][a], chart['planets'][b]
            if pa['sign_idx'] != pb['sign_idx']:
                continue
            if abs(pa['degree'] - pb['degree']) < 1.0:
                loser = a if pa['longitude'] > pb['longitude'] else b
                losers.add(loser)
    return losers


def _aspects_directed(chart):
    """构建有向相位集合 {(发出, 接收)} 与合相对 {(a,b)}"""
    directed = set()
    conj = set()
    for a in chart['aspects']:
        if a['type'] == '合相':
            conj.add(frozenset((a['p1'], a['p2'])))
        else:
            directed.add((a['p1'], a['p2']))
    return directed, conj


def _parivartana(chart, a, b):
    """互溶：a 落在 b 守护的星座，且 b 落在 a 守护的星座"""
    sa, sb = _sign_idx(chart, a), _sign_idx(chart, b)
    return SIGN_LORDS[sa] == b and SIGN_LORDS[sb] == a


def _associated(chart, a, b, directed, conj):
    """格局结合关系：合相 / 互视 / 单向相位 / 互溶"""
    if frozenset((a, b)) in conj:
        return True
    if (a, b) in directed or (b, a) in directed:
        return True
    if _parivartana(chart, a, b):
        return True
    return False


# ─────────────────────────────────────────────────────────────
# 1. 角色分类
# ─────────────────────────────────────────────────────────────

def classify_roles(chart):
    house_lords = chart['house_lords']
    owned = _owned_houses(house_lords)
    roles = {}
    for planet in PLANETS9:
        oh = owned.get(planet, [])
        r = []
        if 1 in oh:
            r.append('Core-Driver')
        if oh and (set(oh) & {5, 9}):
            r.append('Faithful')
        if set(oh) & {2, 4, 7, 10}:
            r.append('Trader')
        if set(oh) & {3, 6, 11}:
            r.append('Growth-Hacker')
        if set(oh) & {8, 12}:
            r.append('Destroyer')
        trik = set(oh) & TRIKONA
        kend = set(oh) & KENDRA
        is_yk = bool(trik) and bool(kend) and len(set(oh)) >= 2
        # 功能凶角色：Destroyer 管 8/12 或 GH 管 6
        malefic_role = bool(set(oh) & {6, 8, 12})
        # 功能吉角色：Core-Driver / Yogakaraka / Faithful
        benefic_role = (1 in oh) or is_yk or bool(set(oh) & {5, 9})
        roles[planet] = {
            'houses_owned': oh,
            'roles': r if r else (['Node'] if planet in ('Rahu', 'Ketu') else []),
            'is_yogakaraka': is_yk,
            'benefic_role': benefic_role,
            'malefic_role': malefic_role,
        }
    return roles


def _vry_planets(chart, roles):
    """落在 6/8/12 的 dusthana 宫主 = VRY 受益星集合"""
    owned = {p: roles[p]['houses_owned'] for p in roles}
    vry = set()
    for planet, oh in owned.items():
        if set(oh) & DUSTHANA and _house(chart, planet) in DUSTHANA:
            vry.add(planet)
    return vry


# ─────────────────────────────────────────────────────────────
# 2. 大运吉凶
# ─────────────────────────────────────────────────────────────

def _planet_dasha_signals(chart, planet, roles, vry, war_losers, conj_pairs):
    """返回 (positive[理由], negative[理由])，严格按 house_framework.md:134-160"""
    pos, neg = [], []
    role = roles.get(planet, {})
    oh = role.get('houses_owned', [])
    house = _house(chart, planet)
    comp = _compound(chart, planet)
    pct = _shadbala_pct(chart, planet)

    # 所管宫位 SAV 均值（nodes 无 owned → 跳过该条）
    owned_sav = None
    if oh:
        vals = [chart['sav_by_house'][h]['value'] for h in oh]
        owned_sav = sum(vals) / len(vals)

    # ── 正面条件 ──
    if role.get('benefic_role'):
        pos.append('P1吉角色')
    if comp in DIGNITY_FRIENDLY:
        pos.append('P7≥友方')
    if pct is not None:
        _rupas_val = chart.get('shadbala', {}).get(planet, {})
        _rupas_val = _rupas_val.get('total_rupas') if isinstance(_rupas_val, dict) else None
        if _rupas_val is not None:
            _threshold = _ISHTA_BALA_RUPAS.get(planet, 6.5)
            _pct_ishta = round(_rupas_val / _threshold * 100, 1)
            if _pct_ishta >= 130:
                pos.append(f'Shadbala {_pct_ishta:.0f}%≥BPHS达标130%')
        elif pct >= 120:
            pos.append(f'Shadbala {pct:.0f}%≥120')
    if house in GOOD_HOUSES:
        pos.append(f'落{house}宫(吉路)')
    if owned_sav is not None and owned_sav >= 28:
        pos.append(f'所管宫SAV {owned_sav:.0f}≥28')
    if chart['vargottama'].get(planet) or DIGBALA_HOUSE.get(planet) == house:
        pos.append('Vargottama/DigBala')

    # ── 负面条件 ──
    if role.get('malefic_role'):
        neg.append('P1凶角色')
    if _is_combust(chart, planet) or comp in DIGNITY_DAMAGED or planet in war_losers:
        neg.append('P2受损(燃烧/落陷/战败)')
    if house in DUSTHANA and planet not in vry:
        neg.append(f'落{house}宫(凶路)无VRY')
    if pct is not None:
        _rupas_v2 = chart.get('shadbala', {}).get(planet, {})
        _rupas_v2 = _rupas_v2.get('total_rupas') if isinstance(_rupas_v2, dict) else None
        if _rupas_v2 is not None:
            _threshold2 = _ISHTA_BALA_RUPAS.get(planet, 6.5)
            _pct_i2 = round(_rupas_v2 / _threshold2 * 100, 1)
            if _pct_i2 < 85:
                neg.append(f'Shadbala {_pct_i2:.0f}%<BPHS最低85%')
        elif pct < 100:
            neg.append(f'Shadbala {pct:.0f}%<100')
    if owned_sav is not None and owned_sav < 25:
        neg.append(f'所管宫SAV {owned_sav:.0f}<25')
    # 与凶星紧密合相 <5°
    for other in conj_pairs.get(planet, []):
        if other in NATURAL_MALEFICS and other != planet:
            neg.append(f'与凶星{other}紧密合相')
            break

    # Mrityu Bhaga + Avastha + MKS 三层叠加受损检测
    # 一颗星同时满足 ≥2 条受损指标 → 质变为额外负面信号（权重比单层更重）
    sp = chart.get('special_planets') or {}
    av_chart = chart.get('avastha') or {}
    damage_layers = []
    if planet in (sp.get('mrityu_bhaga') or []):
        damage_layers.append('Mrityu Bhaga(死亡度数)')
    if planet in (sp.get('marana_karaka_sthana') or []):
        damage_layers.append('MKS(致命弱点宫)')
    p_av = av_chart.get(planet, {})
    if p_av.get('baladi', {}).get('key') in ('mrityu', 'vriddha'):
        damage_layers.append(f'Baladi{p_av["baladi"]["key"]}(年老/行将)')
    if p_av.get('jagradadi', {}).get('key') == 'sushupti':
        damage_layers.append('Jagradadi睡(效率~25%)')
    if len(damage_layers) >= 2:
        neg.append(f'三层叠加受损({"＋".join(damage_layers)})')

    return pos, neg


def _verdict_from_counts(pos, neg):
    np_, nn = len(pos), len(neg)
    if np_ >= 2 and nn == 0:
        return '正面期'
    if np_ >= 2 and nn >= 1:
        return '混合期'
    if np_ < 2 and nn >= 1:
        return '困难期' if not (np_ == 0 and nn >= 2) else '危机期'
    if np_ == 0 and nn >= 2:
        return '危机期'
    return '平淡期'  # 信号极弱（多见于无主管的节点）


# ── 连续化打分权重 ──────────────────────────────────────────────
# 把每条信号理由映射到数值权重，使边界情形有更精细的置信度。
# 正面权重: 正值；负面权重: 负值。
_SIGNAL_WEIGHTS = {
    # 正面
    'P1吉角色':          2.0,
    'P7≥友方':           2.5,   # 入旺/入庙比友方更重
    'Vargottama/DigBala':1.5,
    'Shadbala':          0.0,   # 动态计算，见下文
    '落': 0.0,                  # 宫位类，动态计算
    '所管宫SAV':          0.0,   # 动态计算
    # 负面（在 neg 列表中）
    'P1凶角色':          -1.5,
    'P2受损':            -2.5,
    '凶路':              -1.5,
    'Shadbala弱':        -1.0,
    'SAV低':             -1.0,
    '紧密合相':          -1.0,
}

def _reason_weight(reason, is_positive):
    """把一条理由字符串映射到数值权重。"""
    if not is_positive:
        if 'P1凶' in reason: return -1.5
        if 'P2受损' in reason: return -2.5
        if '凶路' in reason or 'DUSTHANA' in reason.upper(): return -1.5
        if 'Shadbala' in reason: return -1.0
        if 'SAV' in reason: return -1.0
        if '合相' in reason: return -1.0
        return -0.8
    else:
        if 'P1吉角色' in reason: return 2.0
        if 'P7≥友方' in reason: return 2.5
        if 'Vargottama' in reason or 'DigBala' in reason: return 1.5
        if 'Shadbala' in reason:
            # 提取百分比给更精细权重
            try:
                pct = float(reason.split('%')[0].split()[-1])
                return min(3.0, (pct - 120) / 30 + 1.5)  # 120%→1.5, 150%→2.5, 200%→3.0
            except Exception:
                return 1.0
        if '吉路' in reason: return 1.0
        if 'SAV' in reason: return 0.8
        return 0.8


def _scored_verdict(pos, neg):
    """连续化打分版判定，返回 (verdict_str, score, confidence)。

    score: 净得分（正面信号权重之和 − 负面信号权重绝对值之和）
    confidence: 'high'(score方向明确≥2.5) / 'medium'(≥1.0) / 'low'(<1.0 或边界)
    verdict: 与 _verdict_from_counts 保持一致的字符串，确保向后兼容
    """
    pos_score = sum(_reason_weight(r, True)  for r in pos)
    neg_score = sum(_reason_weight(r, False) for r in neg)  # 负数
    net = round(pos_score + neg_score, 2)

    # 向后兼容：沿用原来的 verdict 字符串，加 score/confidence 作为增量信息
    verdict = _verdict_from_counts(pos, neg)

    abs_net = abs(net)
    if abs_net >= 3.0:
        confidence = 'high'
    elif abs_net >= 1.5:
        confidence = 'medium'
    else:
        confidence = 'low'      # 边界情形，两套信号互相抵消

    # 边界情形检测（原始计数在阈值±1内 → 特别标注）
    np_, nn = len(pos), len(neg)
    at_boundary = (np_ == 2 and nn == 1) or (np_ == 1 and nn == 1) or (np_ == 0 and nn == 1)

    return verdict, net, confidence, at_boundary


def _calc_sandhi(start_str, end_str, sandhi_days=180):
    """计算大运 Sandhi（过渡期）窗口。

    Dasha Sandhi：大运交接前后各约 180 天（6 个月）能量不稳定，
    旧大运力量消退、新大运力量尚未建立，是预测精度最低的区间。
    KN Rao 传统：交接前 6 个月 + 交接后 6 个月 = 共约 1 年过渡期。

    返回 dict：
      {
        'entering_sandhi': {'start': 'YYYY-MM-DD', 'end': 'YYYY-MM-DD'},  # 大运尾段
        'leaving_sandhi':  {'start': 'YYYY-MM-DD', 'end': 'YYYY-MM-DD'},  # 大运首段
        'in_entering_sandhi': bool,   # 今天是否在尾段 Sandhi 内
        'in_leaving_sandhi':  bool,   # 今天是否在首段 Sandhi 内
        'in_sandhi': bool,            # 两者取 OR
      }
    None 时间格式解析失败则返回 None。
    """
    try:
        start = date.fromisoformat(start_str[:10])   # 兼容 YYYY-MM 和 YYYY-MM-DD
        end   = date.fromisoformat(end_str[:10])
    except (ValueError, TypeError):
        return None

    today = date.today()
    delta = timedelta(days=sandhi_days)

    entering = {'start': str(end - delta), 'end': str(end)}          # 大运末尾 180 天
    leaving  = {'start': str(start), 'end': str(start + delta)}      # 大运开头 180 天

    in_entering = (end - delta) <= today < end
    in_leaving  = start <= today < (start + delta)

    return {
        'entering_sandhi': entering,
        'leaving_sandhi':  leaving,
        'in_entering_sandhi': in_entering,
        'in_leaving_sandhi':  in_leaving,
        'in_sandhi': in_entering or in_leaving,
    }


def _polarity(verdict):
    return '正' if verdict in ('正面期', '混合期', '平淡期') else '负'


def _func_role_tier(planet, roles):
    """返回行星的功能角色等级：
      'trikona'  — 纯三角宫主（L1/L5/L9，含 Yogakaraka）：最大增效层
      'kendra'   — 纯角宫主（L4/L7/L10，非 Yogakaraka）：中性偏正
      'mixed'    — 吉凶混合（如同管三角宫+凶宫）
      'dusthana' — 纯凶宫主（L6/L8/L12）：减效层
      'neutral'  — Rahu/Ketu 或无明确身份
    """
    r = roles.get(planet, {})
    oh = set(r.get('houses_owned', []))
    if not oh or planet in ('Rahu', 'Ketu'):
        return 'neutral'
    trik = oh & TRIKONA        # {1,5,9}
    kend = oh & KENDRA         # {1,4,7,10}（1 既是 trikona 也是 kendra）
    dust = oh & DUSTHANA       # {6,8,12}
    pure_dust = dust - trik - kend   # 纯凶（不兼管吉宫）
    if trik and not dust:
        return 'trikona'
    if trik and dust:
        return 'mixed'
    if kend and not dust:
        return 'kendra'
    if pure_dust:
        return 'dusthana'
    return 'neutral'


def _combine_md_ad(md_v, ad_v, md_planet=None, ad_planet=None, roles=None):
    """大运基调 × 小运功能角色交叉（house_framework.md:163-171 + KN Rao 增效规则）。

    在原来 2×2 极性矩阵基础上，叠加 AD 星功能角色对 MD 基调的修正：
      - AD 是 trikona 主（L1/L5/L9）→ 对"正面期"放大，对"困难期"减轻
      - AD 是 dusthana 主（L6/L8/L12）→ 对"正面期"抑制，对"困难期"加重
    返回 (combined_label, role_note) 二元组。
    """
    mp = _polarity(md_v)
    ap = _polarity(ad_v)

    # 基础 2×2 矩阵（向后兼容）
    base_table = {
        ('正', '正'): '该领域顺利',
        ('正', '负'): '好事多磨',
        ('负', '正'): '困境中有转机',
        ('负', '负'): '该领域面临危机',
    }
    base = base_table[(mp, ap)]
    role_note = None

    if roles and ad_planet:
        tier = _func_role_tier(ad_planet, roles)
        if tier == 'trikona':
            if mp == '正' and ap == '正':
                base = '该领域顺利（三角宫主小运，效力加强）'
                role_note = f'{ad_planet}=L1/L5/L9，正×正叠加'
            elif mp == '负' and ap == '正':
                base = '困境中有明显转机（三角宫主激活）'
                role_note = f'{ad_planet}=L1/L5/L9，减轻大运压力'
            elif mp == '正' and ap == '负':
                # 功能吉星判定为"负"，说明它本身受损（燃烧/落陷），特别标注
                base = '好事多磨（三角宫主自身受损，吉力打折）'
                role_note = f'{ad_planet}=L1/L5/L9 但自身受损'
        elif tier == 'dusthana':
            if mp == '正' and ap == '正':
                # 凶宫主判定为"正"，通常是 VRY（Viparita Raja Yoga）
                base = '该领域顺利（凶宫主小运，疑有 VRY 翻转效果）'
                role_note = f'{ad_planet}=L6/L8/L12 判定正，核查 VRY'
            elif mp == '正' and ap == '负':
                base = '好事多磨，需防小运凶宫触发意外事件'
                role_note = f'{ad_planet}=L6/L8/L12，正大运受阻'
            elif mp == '负' and ap == '负':
                base = '该领域面临危机（凶宫主小运加重逆境）'
                role_note = f'{ad_planet}=L6/L8/L12，双重凶叠加'
        elif tier == 'mixed':
            if mp == '正' and ap == '负':
                base = '好事多磨（吉凶混合小运，成果须在逆境后到来）'
                role_note = f'{ad_planet}=吉凶混合宫主'

    # 同样用 MD 星功能角色对 AD 做正向校验
    if roles and md_planet and role_note is None:
        md_tier = _func_role_tier(md_planet, roles)
        if md_tier == 'trikona' and mp == '正' and ap == '正':
            base = '该领域顺利（大运本身三角宫主，底色稳固）'
            role_note = f'{md_planet}=L1/L5/L9 大运底色稳'
        elif md_tier == 'dusthana' and mp == '负' and ap == '负':
            base = '该领域面临危机（大运凶宫主，底色持续施压）'
            role_note = f'{md_planet}=L6/L8/L12 大运持续施压'

    return base, role_note


def judge_dashas(chart, roles):
    vry = _vry_planets(chart, roles)
    war_losers = _war_losers(chart)
    # 每颗星的同星座近合相伙伴(<5°)
    conj_pairs = {}
    for a in chart['aspects']:
        if a['type'] == '合相' and a['degree_diff'] < 5:
            conj_pairs.setdefault(a['p1'], []).append(a['p2'])
            conj_pairs.setdefault(a['p2'], []).append(a['p1'])

    # D60 修正信号（若已算出则融合，否则静默跳过）
    d60_mods = chart.get('d60_dasha_modifiers') or {}

    # 先算每颗星的独立判定（小运叠加复用）
    planet_verdict = {}
    for p in PLANETS9:
        pos, neg = _planet_dasha_signals(chart, p, roles, vry, war_losers, conj_pairs)
        # 融合 D60 修正信号（业力层补充，上限各1条）
        d60mod = d60_mods.get(p, {})
        d60pos = d60mod.get('positive', [])
        d60neg = d60mod.get('negative', [])
        if d60pos:
            pos = pos + d60pos[:1]   # 最多追加1条D60正面
        if d60neg:
            neg = neg + d60neg[:1]   # 最多追加1条D60负面
        v, score, conf, boundary = _scored_verdict(pos, neg)
        planet_verdict[p] = {
            'positive': pos, 'negative': neg,
            'verdict': v,
            'score': score,
            'confidence': conf,
            'at_boundary': boundary,
            'd60_pos': d60pos,   # 记录D60贡献（供formatter展示）
            'd60_neg': d60neg,
        }

    results = []
    # Shoola Dasha 当前质地（作为当前大运的"底色"叠加）
    _shoola = chart.get('shoola_dasha') or {}
    _shoola_quality = _shoola.get('current_quality')  # 'harsha'/'sama'/'shoola'

    for d in chart['dashas']:
        md = d['planet']
        mdv = planet_verdict[md]
        _pos = list(mdv['positive'])
        _neg = list(mdv['negative'])
        _score = mdv.get('score', 0)
        _shoola_note = None
        # 仅对当前大运叠加 Shoola 底色（Shoola 是"当下"状态，不预测未来大运）
        if d.get('is_current') and _shoola_quality:
            if _shoola_quality == 'harsha':
                _pos = _pos + ['Shoola顺境底色(+0.5)']
                _score = round(_score + 0.5, 2)
                _shoola_note = 'harsha顺境'
            elif _shoola_quality == 'shoola':
                _neg = _neg + ['Shoola逆境底色(-0.5)']
                _score = round(_score - 0.5, 2)
                _shoola_note = 'shoola逆境/考验'
            elif _shoola_quality == 'sama':
                _shoola_note = 'sama平稳'

        # 仅对当前大运叠加 Narayana/Chara 宫位激活信号
        # 逻辑：Jaimini 环境层当前激活的宫位 × Vimsottari 大运星管辖宫位 = 共振判断
        _jaimini_notes = []
        if d.get('is_current'):
            # 当前 Narayana/Chara 激活的宫位（主运+小运，按 (系统, 宫位) 去重，只取最重要的一条）
            _jaimini_raw = {}   # (system_key, house) → (domain, level)
            for _jkey in ('narayana_dasha', 'chara_dasha'):
                _jd = chart.get(_jkey) or {}
                _jcurr = [x for x in _jd.get('dashas', []) if x.get('is_current')]
                if _jcurr:
                    h = _jcurr[0].get('house_from_lagna')
                    if h:
                        k = (_jkey, h)
                        if k not in _jaimini_raw:
                            _jaimini_raw[k] = (_jcurr[0].get('domain', ''), '主运')
                    for _ad in _jcurr[0].get('antardashas', []):
                        if _ad.get('is_current'):
                            ah = _ad.get('house_from_lagna')
                            if ah and ah != h:   # 小运与主运不同宫才算独立信号
                                k2 = (_jkey, ah)
                                if k2 not in _jaimini_raw:
                                    _jaimini_raw[k2] = (_ad.get('domain', ''), '小运')

            # Vimsottari 大运星管辖的宫位
            _md_houses = set(roles.get(md, {}).get('houses_owned', []))

            for (_jkey, _jh), (_jdomain, _jlevel) in _jaimini_raw.items():
                _sys = 'Narayana' if 'narayana' in _jkey else 'Chara'
                if _jh in GOOD_HOUSES:
                    if _md_houses & {_jh}:
                        _pos = _pos + [f'{_sys}{_jlevel}激活{_jh}宫({_jdomain})=大运星直管共振(+1.0)']
                        _score = round(_score + 1.0, 2)
                        _jaimini_notes.append(f'{_sys}{_jh}宫强共振')
                    else:
                        _pos = _pos + [f'{_sys}{_jlevel}激活{_jh}宫({_jdomain})=吉宫环境支持(+0.5)']
                        _score = round(_score + 0.5, 2)
                        _jaimini_notes.append(f'{_sys}{_jh}宫环境支持')
                elif _jh in DUSTHANA:
                    _neg = _neg + [f'{_sys}{_jlevel}激活{_jh}宫({_jdomain})=凶宫环境(-0.5)']
                    _score = round(_score - 0.5, 2)
                    _jaimini_notes.append(f'{_sys}{_jh}宫凶域')
        entry = {
            'planet': md, 'start': d['start'], 'end': d['end'],
            'is_current': d.get('is_current', False),
            'positive': _pos, 'negative': _neg,
            'verdict': mdv['verdict'],
            'score': _score,
            'confidence': mdv.get('confidence', 'medium'),
            'at_boundary': mdv.get('at_boundary', False),
            'shoola_overlay': _shoola_note,
            'jaimini_overlay': _jaimini_notes if _jaimini_notes else None,
            'sandhi': _calc_sandhi(d['start'], d['end']),  # Dasha Sandhi 过渡期窗口
            'antardashas': [],
        }
        # 当前/下一大运展开 AD 叠加
        for ad in d.get('antardashas', []):
            adp = ad['planet']
            adv = planet_verdict[adp]['verdict']
            ad_score = planet_verdict[adp].get('score', 0)
            combined_label, role_note = _combine_md_ad(
                mdv['verdict'], adv,
                md_planet=md, ad_planet=adp, roles=roles,
            )
            ad_entry = {
                'planet': adp, 'start': ad['start'], 'end': ad['end'],
                'is_current': ad.get('is_current', False),
                'ad_verdict': adv,
                'ad_score': ad_score,
                'combined': combined_label,
                'role_note': role_note,       # 功能角色交叉注释（None = 无特殊修正）
                'md_tier': _func_role_tier(md, roles),
                'ad_tier': _func_role_tier(adp, roles),
            }
            # PAD（三级运）：直接透传已计算好的数据
            if ad.get('pratyantardashas'):
                ad_entry['pratyantardashas'] = ad['pratyantardashas']
            entry['antardashas'].append(ad_entry)
        results.append(entry)
    return results


# ─────────────────────────────────────────────────────────────
# 3. 格局
# ─────────────────────────────────────────────────────────────

def _activation(chart, participants):
    """参与星的 Mahadasha 时段"""
    windows = []
    for d in chart['dashas']:
        if d['planet'] in participants:
            windows.append(f"{d['planet']} {d['start']}~{d['end']}")
    return windows


def _yoga_strength(chart, participants):
    """yogas.md:108-128 强度评估"""
    damaged = any(_is_combust(chart, p) or _compound(chart, p) in DIGNITY_DAMAGED
                  for p in participants if p in PLANETS7)
    if damaged:
        return '受损(×0.2)'
    pcts = [_shadbala_pct(chart, p) for p in participants]
    pcts = [x for x in pcts if x is not None]
    if pcts and all(x > 120 for x in pcts):
        return '高(强实现)'
    if pcts and any(x < 100 for x in pcts):
        return '低(需时机激活)'
    return '中'


def detect_yogas(chart, roles):
    directed, conj = _aspects_directed(chart)
    house_lords = chart['house_lords']
    lord = {h: house_lords[h]['lord'] for h in range(1, 13)}
    yogas = []

    def assoc(a, b):
        return a != b and _associated(chart, a, b, directed, conj)

    def add(name, present, participants, note=''):
        participants = list(dict.fromkeys(participants))  # 去重保序
        yogas.append({
            'name': name, 'present': present, 'participants': participants,
            'strength': _yoga_strength(chart, participants) if present and participants else '—',
            'note': note,
            'activation': _activation(chart, set(participants)) if present else [],
        })

    # Raja Yoga：三角主 + 角主 结合
    trik_lords = {lord[h] for h in (1, 5, 9)}
    kend_lords = {lord[h] for h in (1, 4, 7, 10)}
    raja_pairs = []
    for t in trik_lords:
        for k in kend_lords:
            if t != k and assoc(t, k):
                raja_pairs.append(tuple(sorted((t, k))))
    raja_pairs = sorted(set(raja_pairs))
    if raja_pairs:
        parts = [p for pair in raja_pairs for p in pair]
        add('Raja Yoga（王者格）', True, parts,
            note='；'.join('+'.join(p) for p in raja_pairs))
    else:
        # Yogakaraka 单星内含 raja
        yk = [p for p in roles if roles[p]['is_yogakaraka']]
        if yk:
            add('Raja Yoga（王者格）', True, yk, note=f'Yogakaraka单星：{",".join(yk)}')
        else:
            add('Raja Yoga（王者格）', False, [])

    # Dhana Yoga：2&11 结合 或 2/11主 与 1/5/9主 结合
    dhana_parts, dhana_notes = [], []
    if assoc(lord[2], lord[11]):
        dhana_parts += [lord[2], lord[11]]; dhana_notes.append('L2+L11')
    for wealth_h in (2, 11):
        for tri_h in (1, 5, 9):
            if lord[wealth_h] != lord[tri_h] and assoc(lord[wealth_h], lord[tri_h]):
                dhana_parts += [lord[wealth_h], lord[tri_h]]
                dhana_notes.append(f'L{wealth_h}+L{tri_h}')
    add('Dhana Yoga（财富格）', bool(dhana_parts), dhana_parts, note='；'.join(dhana_notes))

    # Dharma-Karma Yoga：9&10 结合
    add('Dharma-Karma Yoga（使命格）', assoc(lord[9], lord[10]),
        [lord[9], lord[10]] if assoc(lord[9], lord[10]) else [], note='L9+L10')

    # Viparita Raja Yoga：dusthana 主落 dusthana
    vry_names = {6: 'Harsha(6主)', 8: 'Sarala(8主)', 12: 'Vimala(12主)'}
    lagna_lord = lord[1]
    ll_pct = _shadbala_pct(chart, lagna_lord)
    benefic_lords_signs = {}  # 吉宫主(1/5/9/10)落座 → 用于孤立性
    for h in (1, 5, 9, 10):
        benefic_lords_signs.setdefault(lord[h], _sign_idx(chart, lord[h]))
    for dh in (6, 8, 12):
        dl = lord[dh]
        if _house(chart, dl) in DUSTHANA:
            # 孤立性：与吉宫主同星座的最近角距
            dl_deg = chart['planets'][dl]['degree']
            dl_sign = _sign_idx(chart, dl)
            isolation = 'VRY有效'
            for bl, bs in benefic_lords_signs.items():
                if bl == dl or bs != dl_sign:
                    continue
                gap = abs(chart['planets'][bl]['degree'] - dl_deg)
                if gap < 1:
                    isolation = f'VRY失效(与{bl}<1°)'
                elif gap < 5:
                    isolation = f'VRY稀释(与{bl}<5°)'
            strength_note = '逆境崛起' if (ll_pct and ll_pct >= 100) else '勉强求生(1宫主弱)'
            add(f'VRY {vry_names[dh]}', isolation == 'VRY有效', [dl],
                note=f'{dl}落{_house(chart, dl)}宫；{isolation}；{strength_note}')

    # Gajakesari：木月互为角宫(1/4/7/10)
    gk_dist = ((_sign_idx(chart, 'Jupiter') - _sign_idx(chart, 'Moon')) % 12) + 1
    add('Gajakesari Yoga（象王格）', gk_dist in (1, 4, 7, 10),
        ['Jupiter', 'Moon'] if gk_dist in (1, 4, 7, 10) else [],
        note=f'木月相距{gk_dist}宫')

    # Chandra-Mangala：月火合/互视
    add('Chandra-Mangala Yoga（月火格）', assoc('Moon', 'Mars'),
        ['Moon', 'Mars'] if assoc('Moon', 'Mars') else [])

    # Kemadruma：月 2/12 宫(从月数)无行星 + 解除条件
    moon_sign = _sign_idx(chart, 'Moon')
    s2 = (moon_sign + 1) % 12
    s12 = (moon_sign - 1) % 12
    occupied = set()
    for p in PLANETS7:
        if p == 'Moon':
            continue
        occupied.add(_sign_idx(chart, p))
    formed = (s2 not in occupied) and (s12 not in occupied)
    # 解除：月在角宫 / 有行星合月 / 木相位月
    moon_house = _house(chart, 'Moon')
    conj_moon = any(frozenset(('Moon', p)) in conj for p in PLANETS7 if p != 'Moon')
    jup_aspects_moon = ('Jupiter', 'Moon') in directed
    cancelled = moon_house in KENDRA or conj_moon or jup_aspects_moon
    if formed and not cancelled:
        add('Kemadruma Yoga（月孤格）', True, ['Moon'], note='月2/12宫空，孤独底色')
    elif formed and cancelled:
        add('Kemadruma Yoga（月孤格）', False, ['Moon'], note='形成但已解除(孤独感减弱)')
    else:
        add('Kemadruma Yoga（月孤格）', False, [])

    # Adhi Yoga: 吉星在月亮6/7/8宫
    # 条件：Jupiter/Venus/Mercury 中至少2颗分布在月亮的6宫、7宫或8宫（任意组合）
    moon_sidx = _sign_idx(chart, 'Moon')
    adhi_planets = []
    for p in ['Jupiter', 'Venus', 'Mercury']:
        p_sidx = _sign_idx(chart, p)
        dist = (p_sidx - moon_sidx) % 12 + 1
        if dist in (6, 7, 8):
            adhi_planets.append(p)
    add('Adhi Yoga（吉星格）', len(adhi_planets) >= 2, adhi_planets,
        note=f'月亮6/7/8宫有{len(adhi_planets)}颗吉星: {adhi_planets}')

    # Amala Yoga: 10宫有自然吉星（永久吉星：Jupiter/Venus/Mercury/盈月）
    NATURAL_BENEFICS = {'Jupiter', 'Venus', 'Mercury'}
    # 月亮盈亏判断
    is_waxing = chart.get('moon_phase', {}).get('waxing', False)
    amala_candidates = list(NATURAL_BENEFICS)
    if is_waxing:
        amala_candidates.append('Moon')
    amala_in_10 = [p for p in amala_candidates if _house(chart, p) == 10]
    add('Amala Yoga（纯洁格）', bool(amala_in_10), amala_in_10,
        note='10宫有自然吉星→事业清白声誉好' if amala_in_10 else '')

    # Kala Sarpa: 所有7颗主星是否全在罗计轴线同一侧
    rahu_sidx = _sign_idx(chart, 'Rahu')
    ketu_sidx = _sign_idx(chart, 'Ketu')  # = (rahu_sidx + 6) % 12
    # 检查每颗行星：从罗睺顺数到计都（0-6）= 罗侧；计都顺数到罗睺（7-11）= 计侧
    def dist_from_rahu(sidx):
        return (sidx - rahu_sidx) % 12
    rahu_side = [p for p in PLANETS7 if 0 < dist_from_rahu(_sign_idx(chart, p)) < 6]
    ketu_side = [p for p in PLANETS7 if 6 < dist_from_rahu(_sign_idx(chart, p)) < 12]
    all_rahu_side = len(rahu_side) == 7
    all_ketu_side = len(ketu_side) == 7
    ks_present = all_rahu_side or all_ketu_side
    add('Kala Sarpa（蛇格）', ks_present,
        rahu_side if all_rahu_side else ketu_side,
        note=('所有行星在罗侧(Rahu-Ketu方向)' if all_rahu_side
              else '所有行星在计侧(Ketu-Rahu方向)' if all_ketu_side
              else f'罗侧{len(rahu_side)}颗/计侧{len(ketu_side)}颗，未形成'))

    # Neecha Bhanga Raja Yoga
    debi_planets = [p for p in PLANETS7
                    if DEBILITATION.get(p) == chart['planets'][p]['sign']]
    nbry_planets = []
    nbry_notes = []
    for p in debi_planets:
        debi_sign = chart['planets'][p]['sign']
        debi_sign_idx = chart['planets'][p]['sign_idx']
        conditions_met = []

        # Condition 1: planet exalted in debilitation sign is in Kendra from Lagna
        for q, q_exalt in EXALTATION_SIGN.items():
            if q_exalt == debi_sign and q != p:
                q_house = _house(chart, q)
                if q_house in KENDRA:
                    conditions_met.append(f'C1:{q}在角宫({q_house}宫)入旺于{debi_sign}')

        # Condition 2: lord of debilitation sign is in Kendra from Lagna
        debi_sign_lord = SIGN_LORDS[debi_sign_idx]
        if _house(chart, debi_sign_lord) in KENDRA:
            conditions_met.append(f'C2:{debi_sign_lord}(落陷星座主)在角宫')

        # Condition 3: debilitated planet itself is in Kendra
        p_house = _house(chart, p)
        if p_house in KENDRA:
            conditions_met.append(f'C3:{p}(落陷星)自身在角宫({p_house}宫)')

        # Condition 4: debilitated planet aspected by its exaltation lord
        exalt_sign = EXALTATION_SIGN.get(p, '')
        if exalt_sign:
            exalt_sign_lord = SIGN_LORDS[SIGN_IDX[exalt_sign]]
            for asp in chart['aspects']:
                if asp['p1'] == exalt_sign_lord and asp['p2'] == p:
                    conditions_met.append(f'C4:{exalt_sign_lord}(旺星)相位{p}')

        if conditions_met:
            nbry_planets.append(p)
            nbry_notes.append(f'{p}落陷({debi_sign})但Neecha Bhanga: ' + '; '.join(conditions_met))

    if nbry_planets:
        add('Neecha Bhanga Raja Yoga（落陷消除格）', True, nbry_planets,
            note=' | '.join(nbry_notes))
    else:
        add('Neecha Bhanga Raja Yoga（落陷消除格）', False, [],
            note=f'无落陷行星' if not debi_planets else f'落陷行星{debi_planets}但无消除条件')

    # Pancha Mahapurusha：火/水/木/金/土 在角宫 + 旺/庙
    pmp = {'Mars': 'Ruchaka', 'Mercury': 'Bhadra', 'Jupiter': 'Hamsa',
           'Venus': 'Malavya', 'Saturn': 'Shasha'}
    for p, yname in pmp.items():
        in_kendra = _house(chart, p) in KENDRA
        strong = _compound(chart, p) in ('exalted', 'own_sign')
        present = in_kendra and strong
        add(f'{yname} Yoga（五大贤者）', present, [p] if present else [],
            note=(f'{p}在{_house(chart,p)}宫+{_compound(chart,p)}' if present else ''))

    # ── Jaimini 格局（基于 Chara Karaka，非宫位）──
    karakas_8k = chart.get('karakas', {}).get('8k', [])
    kara = {k: p for k, p, d in karakas_8k}
    ak = kara.get('AK'); amk = kara.get('AmK'); dk = kara.get('DK')

    def _d9_sign_idx(planet):
        d9 = chart.get('d9', {})
        pd = d9.get(planet)
        if isinstance(pd, tuple):
            return pd[1]
        if isinstance(pd, dict):
            return pd.get('sign_idx')
        return None

    # Jaimini Raja Yoga: AK 与 AmK 在 D9 互为 Kendra(1/4/7/10) 或 Trikona(1/5/9)
    if ak and amk and ak != amk:
        ak_d9 = _d9_sign_idx(ak); amk_d9 = _d9_sign_idx(amk)
        if ak_d9 is not None and amk_d9 is not None:
            dist = ((amk_d9 - ak_d9) % 12) + 1
            is_kendra = dist in (1, 4, 7, 10)
            is_trikona = dist in (1, 5, 9)
            present = is_kendra or is_trikona
            rel = '角宫' if is_kendra else ('三角' if is_trikona else '无关')
            add('Jaimini Raja Yoga（灵魂-事业格）', present,
                [ak, amk] if present else [],
                note=f'AK({ak})与AmK({amk})在D9成{rel}关系(距{dist})' if present
                     else f'AK({ak})与AmK({amk})在D9距{dist}，未成格')

    # Jaimini 婚姻格：DK 与 7宫主 在 D1 互为 Kendra/Trikona 或合相
    l7 = chart.get('house_lords', {}).get(7, {}).get('lord')
    if dk and l7:
        dk_sidx = _sign_idx(chart, dk); l7_sidx = _sign_idx(chart, l7)
        if dk == l7:
            add('Jaimini 婚姻格（DK=L7）', True, [dk],
                note=f'配偶指示星DK({dk})即7宫主，婚姻信号强化')
        else:
            dist = ((l7_sidx - dk_sidx) % 12) + 1
            present = dist in (1, 4, 5, 7, 9, 10)
            add('Jaimini 婚姻格（DK-L7关系）', present,
                [dk, l7] if present else [],
                note=f'DK({dk})与L7({l7})距{dist}宫，成吉相' if present
                     else f'DK({dk})与L7({l7})距{dist}宫，关系弱')

    # Atmakaraka 在角宫：灵魂目的与现实高度对齐
    if ak:
        ak_house = _house(chart, ak)
        add('AK 角宫格（灵魂-现实对齐）', ak_house in KENDRA,
            [ak] if ak_house in KENDRA else [],
            note=f'AK({ak})在{ak_house}宫(角宫)，灵魂目的直接现实化' if ak_house in KENDRA
                 else f'AK({ak})在{ak_house}宫，非角宫')

    return yogas


# ─────────────────────────────────────────────────────────────
# 总入口
# ─────────────────────────────────────────────────────────────

def compute_verdicts(chart):
    roles = classify_roles(chart)
    return {
        'roles': roles,
        'dasha_verdicts': judge_dashas(chart, roles),
        'yogas': detect_yogas(chart, roles),
    }


# ─────────────────────────────────────────────────────────────
# 自测
# ─────────────────────────────────────────────────────────────
if __name__ == '__main__':
    import sys, os
    try:
        sys.stdout.reconfigure(encoding='utf-8')  # Windows GBK 控制台兼容 emoji
    except Exception:
        pass
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from engine import calculate_full_chart

    # 甘地：1869-10-02 07:12 Porbandar
    chart = calculate_full_chart(1869, 10, 2, 7, 12, 21.6417, 69.6293, "Asia/Kolkata")
    v = compute_verdicts(chart)

    print("=== 角色身份 ===")
    for p in PLANETS9:
        r = v['roles'][p]
        print(f"  {p:<9} 管{r['houses_owned']} 角色={r['roles']} "
              f"YK={r['is_yogakaraka']} 吉角色={r['benefic_role']} 凶角色={r['malefic_role']}")

    print("\n=== 大运吉凶 ===")
    for d in v['dasha_verdicts']:
        cur = '→' if d['is_current'] else ' '
        print(f"  {cur}{d['planet']:<9} {d['start']}~{d['end']}  "
              f"正{len(d['positive'])}/负{len(d['negative'])} → {d['verdict']}")
        print(f"     +{d['positive']}  -{d['negative']}")

    print("\n=== 格局 ===")
    for y in v['yogas']:
        mark = '✅' if y['present'] else '❌'
        print(f"  {mark} {y['name']:<26} 参与={y['participants']} "
              f"强度={y['strength']} {y['note']}")

    # 四分类边界自测
    print("\n=== 判定四分类自测 ===")
    assert _verdict_from_counts(['a','b'], []) == '正面期'
    assert _verdict_from_counts(['a','b'], ['x']) == '混合期'
    assert _verdict_from_counts(['a'], ['x']) == '困难期'
    assert _verdict_from_counts([], ['x','y']) == '危机期'
    assert _combine_md_ad('正面期', '困难期') == '好事多磨'
    assert _combine_md_ad('危机期', '正面期') == '困境中有转机'
    print("  四分类 + 叠加 全部通过 ✅")
