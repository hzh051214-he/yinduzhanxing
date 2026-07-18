"""
timing_confluence.py — 多大运系统时机交叉扫描（含质量判断）
=============================================
扫描未来 N 个月内每个月的多系统共振分数，输出按主题分类的高概率时机窗口。

评分规则（基础分 × 质量系数）：

基础分：
  Vimsottari 小运激活目标宫位：+2分
  Chara 主运/小运对应目标宫位：+2分
  Narayana 主运/小运对应目标宫位：+2分
  Shoola 顺境（harsha）：+1分 | 逆境（shoola）：-1分

质量系数（对基础分加权，不影响 Shoola）：

  激活行星 D9 品质（兑现率）[权重40%]：
    exalted/own_sign → ×1.5（满状态兑现）
    great_friend/friend → ×1.2（友方位可靠）
    neutral → ×1.0（中性）
    enemy/great_enemy → ×0.6（敌方位打折）
    debilitated → ×0.5（落陷大幅打折）

  激活行星 Shadbala（执行力）[权重30%]：
    ≥130% BPHS达标 → ×1.3（有力真正兑现）
    100–129% → ×1.0（够用）
    85–99% → ×0.85（略弱）
    <85% BPHS不足 → ×0.7（执行力不足）
    Rahu/Ketu 无 Shadbala → ×1.0（节点默认中性）

  目标宫位 SAV 总分（环境支持）[权重30%]：
    ≥32 溢出 → ×1.3（环境充裕）
    28–31 充裕 → ×1.1
    24–27 平稳 → ×1.0
    20–23 高阻 → ×0.8
    <20 匮乏 → ×0.5（环境极差）

综合质量系数 = D9权重×D9分 + Shadbala权重×Shadbala分 + SAV权重×SAV分
最终得分 = 基础分 × 综合质量系数（Shoola 底色不受质量系数影响，直接叠加）

对外接口：
  scan_timing_confluence(chart, months=60, themes=None)
  → 返回按主题分类的时机窗口排行榜（含质量调整后的分数）
"""
from datetime import date, timedelta

SIGNS = ['Aries','Taurus','Gemini','Cancer','Leo','Virgo',
         'Libra','Scorpio','Sagittarius','Capricorn','Aquarius','Pisces']

THEME_HOUSES = {
    '感情': [5, 7],
    '事业': [10, 6],
    '财富': [2, 11],
    '灵性/运势': [9, 12],
    '家庭/根基': [4, 3],
}

# 功能角色交叉系数（MD×AD 组合修正 Vimsottari 评分）
# KN Rao 体系：三角宫主（L1/L5/L9）在任何大运底色下均加速激活；
# 凶宫主（L6/L8/L12）即使大运底色良好也会压制或延迟兑现。
#
# 表含义：(MD功能层, AD功能层) → 质量系数修正值（叠加到原有 _quality_factor 上）
# 原始质量系数范围约 0.5-1.5；修正值在此基础上乘以 cross_factor
_MD_AD_CROSS = {
    # MD 三角宫主（底色稳）× AD 三角宫主 → 双重加持，最强组合
    ('trikona', 'trikona'):  1.4,
    # MD 三角宫主 × AD 角宫主 → 稳固中推进，良好
    ('trikona', 'kendra'):   1.15,
    # MD 三角宫主 × AD 混合 → 有吉有阻，中性偏正
    ('trikona', 'mixed'):    1.0,
    # MD 三角宫主 × AD 凶宫主 → 底色好但小运施压，好事多磨
    ('trikona', 'dusthana'): 0.75,
    # MD 三角宫主 × AD 节点 → 节点有扩张力，但不稳定
    ('trikona', 'neutral'):  1.05,

    # MD 角宫主 × AD 三角宫主 → 执行力 × 吉力，不错
    ('kendra', 'trikona'):   1.2,
    ('kendra', 'kendra'):    1.0,
    ('kendra', 'mixed'):     0.95,
    ('kendra', 'dusthana'):  0.7,
    ('kendra', 'neutral'):   1.0,

    # MD 混合 × AD 三角宫主 → 吉力部分抵消混合负面
    ('mixed', 'trikona'):    1.1,
    ('mixed', 'kendra'):     1.0,
    ('mixed', 'mixed'):      0.9,
    ('mixed', 'dusthana'):   0.65,
    ('mixed', 'neutral'):    0.95,

    # MD 凶宫主 × AD 三角宫主 → VRY 大运里三角小运有翻盘潜力
    ('dusthana', 'trikona'): 1.05,   # VRY 期间的稀有增效
    ('dusthana', 'kendra'):  0.85,
    ('dusthana', 'mixed'):   0.7,
    ('dusthana', 'dusthana'): 0.5,   # 最差组合，双重凶叠加
    ('dusthana', 'neutral'): 0.8,

    # MD 节点（Rahu/Ketu） × AD 功能角色
    ('neutral', 'trikona'):  1.1,
    ('neutral', 'kendra'):   1.0,
    ('neutral', 'mixed'):    0.95,
    ('neutral', 'dusthana'): 0.75,
    ('neutral', 'neutral'):  1.0,
}

SHOOLA_QUALITY_MAP = {'harsha': +1, 'sama': 0, 'shoola': -1}

# D9 尊贵度 → 兑现率系数
D9_DIGNITY_FACTOR = {
    'exalted': 1.5, 'own_sign': 1.4, 'great_friend': 1.2, 'friend': 1.1,
    'neutral': 1.0, 'enemy': 0.6, 'great_enemy': 0.55, 'debilitated': 0.5,
    'node': 1.0,   # Rahu/Ketu
}

# BPHS 个星 Shadbala 达标线（Rupas）
_ISHTA_BALA_RUPAS = {
    'Sun': 6.5, 'Moon': 6.0, 'Mars': 5.0,
    'Mercury': 7.0, 'Jupiter': 6.5, 'Venus': 5.5, 'Saturn': 5.0,
}

_TRIKONA = {1, 5, 9}
_KENDRA  = {1, 4, 7, 10}
_DUSTHANA = {6, 8, 12}


def _func_role_tier(planet, house_lords):
    """timing_confluence 内部用：根据宫主表判断功能角色层级。
    返回 'trikona'/'kendra'/'mixed'/'dusthana'/'neutral'。
    """
    if planet in ('Rahu', 'Ketu'):
        return 'neutral'
    oh = set()
    for h in range(1, 13):
        if house_lords.get(h, {}).get('lord') == planet:
            oh.add(h)
    if not oh:
        return 'neutral'
    trik = oh & _TRIKONA
    kend = oh & _KENDRA
    dust = oh & _DUSTHANA
    pure_dust = dust - trik - kend
    if trik and not dust:
        return 'trikona'
    if trik and dust:
        return 'mixed'
    if kend and not dust:
        return 'kendra'
    if pure_dust:
        return 'dusthana'
    return 'neutral'


def _md_ad_cross_factor(md_planet, ad_planet, house_lords):
    """MD×AD 功能角色交叉系数，从 _MD_AD_CROSS 查表返回修正乘数。"""
    md_tier = _func_role_tier(md_planet, house_lords)
    ad_tier = _func_role_tier(ad_planet, house_lords)
    return _MD_AD_CROSS.get((md_tier, ad_tier), 1.0), md_tier, ad_tier


def _house_from_lagna(sign_idx, lagna_sign_idx):
    return ((sign_idx - lagna_sign_idx) % 12) + 1


def _month_iter(start_year, start_month, n_months):
    y, m = start_year, start_month
    for _ in range(n_months):
        yield y, m
        m += 1
        if m > 12:
            m = 1; y += 1


def _dasha_sign_at_month(dashas, year, month):
    target = date(year, month, 15)
    for d in dashas:
        try:
            start = date.fromisoformat(d.get('start', '1900-01') + '-01')
            end = date.fromisoformat(d.get('end', '2100-01') + '-01')
        except ValueError:
            continue
        if start <= target < end:
            md_idx = d.get('sign_idx')
            for ad in d.get('antardashas', []):
                try:
                    ad_start = date.fromisoformat(ad.get('start', '1900-01-01'))
                    ad_end = date.fromisoformat(ad.get('end', '2100-01-01'))
                except ValueError:
                    continue
                if ad_start <= target < ad_end:
                    return md_idx, ad.get('sign_idx')
            return md_idx, None
    return None, None


def _vimsottari_at_month(dashas, year, month):
    """返回 (md_planet, ad_planet, pad_planet) 三元组。
    pad_planet 来自当前小运下已计算好的 pratyantardashas；
    若三级运数据不存在或该月不在任何 PAD 时段内，则为 None。
    """
    target = date(year, month, 15)
    for d in dashas:
        try:
            start = date.fromisoformat(d.get('start', '1900-01') + '-01')
            end = date.fromisoformat(d.get('end', '2100-01') + '-01')
        except ValueError:
            continue
        if start <= target < end:
            md = d.get('planet')
            for ad in d.get('antardashas', []):
                try:
                    ad_start = date.fromisoformat(ad.get('start', '1900-01-01'))
                    ad_end = date.fromisoformat(ad.get('end', '2100-01-01'))
                except ValueError:
                    continue
                if ad_start <= target < ad_end:
                    # 查找 PAD（三级运）
                    pad = None
                    for prd in ad.get('pratyantardashas', []):
                        try:
                            p_start = date.fromisoformat(prd.get('start', '1900-01-01'))
                            p_end = date.fromisoformat(prd.get('end', '2100-01-01'))
                        except ValueError:
                            continue
                        if p_start <= target < p_end:
                            pad = prd.get('planet')
                            break
                    return md, ad.get('planet'), pad
            return md, None, None
    return None, None, None


def _d9_dignity_for_planet(planet, chart):
    """返回某行星在 D9 的尊贵度字符串。"""
    if planet in ('Rahu', 'Ketu'):
        return 'node'
    d9 = chart.get('d9', {})
    pd9 = d9.get(planet)
    if not pd9:
        return 'neutral'
    sign_idx = pd9[1] if isinstance(pd9, tuple) else pd9.get('sign_idx', 0)
    sign = SIGNS[sign_idx] if 0 <= sign_idx < 12 else ''

    EXALT = {'Sun':'Aries','Moon':'Taurus','Mars':'Capricorn','Mercury':'Virgo',
              'Jupiter':'Cancer','Venus':'Pisces','Saturn':'Libra'}
    DEBI  = {'Sun':'Libra','Moon':'Scorpio','Mars':'Cancer','Mercury':'Pisces',
              'Jupiter':'Capricorn','Venus':'Virgo','Saturn':'Aries'}
    OWN   = {'Sun':['Leo'],'Moon':['Cancer'],'Mars':['Aries','Scorpio'],
              'Mercury':['Gemini','Virgo'],'Jupiter':['Sagittarius','Pisces'],
              'Venus':['Taurus','Libra'],'Saturn':['Capricorn','Aquarius']}
    NATURAL_FRIENDS = {
        'Sun':{'Moon','Mars','Jupiter'},'Moon':{'Sun','Mercury'},
        'Mars':{'Sun','Moon','Jupiter'},'Mercury':{'Sun','Venus'},
        'Jupiter':{'Sun','Moon','Mars'},'Venus':{'Mercury','Saturn'},
        'Saturn':{'Mercury','Venus'},
    }
    NATURAL_ENEMIES = {
        'Sun':{'Venus','Saturn'},'Moon':set(),'Mars':{'Mercury'},
        'Mercury':{'Moon'},'Jupiter':{'Mercury','Venus'},
        'Venus':{'Sun','Moon'},'Saturn':{'Sun','Moon','Mars'},
    }
    SIGN_LORDS = {0:'Mars',1:'Venus',2:'Mercury',3:'Moon',4:'Sun',5:'Mercury',
                  6:'Venus',7:'Mars',8:'Jupiter',9:'Saturn',10:'Saturn',11:'Jupiter'}

    if EXALT.get(planet) == sign:
        return 'exalted'
    if DEBI.get(planet) == sign:
        return 'debilitated'
    if sign in OWN.get(planet, []):
        return 'own_sign'
    lord = SIGN_LORDS.get(sign_idx, '')
    if lord in NATURAL_FRIENDS.get(planet, set()):
        return 'friend'
    if lord in NATURAL_ENEMIES.get(planet, set()):
        return 'enemy'
    return 'neutral'


def _shadbala_factor(planet, chart):
    """返回 Shadbala 质量系数。"""
    if planet in ('Rahu', 'Ketu'):
        return 1.0
    sb = chart.get('shadbala', {}).get(planet)
    if not isinstance(sb, dict):
        return 1.0
    rupas = sb.get('total_rupas')
    if rupas is None:
        return 1.0
    threshold = _ISHTA_BALA_RUPAS.get(planet, 6.5)
    pct = rupas / threshold * 100
    if pct >= 130:
        return 1.3
    if pct >= 100:
        return 1.0
    if pct >= 85:
        return 0.85
    return 0.7


def _sav_factor(house, chart):
    """返回目标宫位 SAV 总分的质量系数。"""
    sav_val = chart.get('sav_by_house', {}).get(house, {})
    if not isinstance(sav_val, dict):
        return 1.0
    v = sav_val.get('value', 28)
    if v >= 32:
        return 1.3
    if v >= 28:
        return 1.1
    if v >= 24:
        return 1.0
    if v >= 20:
        return 0.8
    return 0.5


def _quality_factor(planet, target_house, chart):
    """综合质量系数 = D9(40%) + Shadbala(30%) + SAV(30%)。
    Rahu/Ketu 无 D9 尊贵度，按 neutral×1.0 处理。
    """
    d9f = D9_DIGNITY_FACTOR.get(_d9_dignity_for_planet(planet, chart), 1.0)
    sbf = _shadbala_factor(planet, chart)
    savf = _sav_factor(target_house, chart)
    return 0.4 * d9f + 0.3 * sbf + 0.3 * savf


def _jaimini_quality_factor(target_house, chart):
    """Chara/Narayana 没有激活行星，质量只看目标宫位 SAV。"""
    # D9 和 Shadbala 部分取中性值 1.0
    savf = _sav_factor(target_house, chart)
    return 0.4 * 1.0 + 0.3 * 1.0 + 0.3 * savf


def scan_timing_confluence(chart, months=60, themes=None):
    """扫描未来 months 个月的多系统时机共振（含质量判断）。

    Parameters
    ----------
    chart : dict  — calculate_full_chart() 的返回值
    months : int  — 扫描范围（月数）
    themes : list | None — 关注的主题列表，None = 全部

    Returns
    -------
    {
      theme: {
        'top_windows': [
          {'year': int, 'month': int, 'label': 'YYYY-MM',
           'score': float, 'quality_score': float,
           'signals': [str], 'quality_notes': [str], 'details': str},
          ...
        ],
        'timeline': [{'label': 'YYYY-MM', 'score': float, 'quality_score': float}]
      },
      'scan_params': {...}
    }
    """
    try:
        lagna_idx = chart['lagna']['sign_idx']
        house_lords = chart.get('house_lords', {})

        vimsottari = chart.get('dashas', [])
        chara = chart.get('chara_dasha', {}).get('dashas', [])
        narayana = chart.get('narayana_dasha', {}).get('dashas', [])
        shoola = chart.get('shoola_dasha', {}).get('dashas', [])

        def _vimsottari_houses(planet):
            return [h for h in range(1, 13)
                    if house_lords.get(h, {}).get('lord') == planet]

        today = date.today()
        start_y, start_m = today.year, today.month

        # 预建 Shoola 时间线
        shoola_timeline = {}
        for d in shoola:
            try:
                s_start = date.fromisoformat(d.get('start', '1900-01') + '-01')
                s_end = date.fromisoformat(d.get('end', '2100-01') + '-01')
                q = d.get('quality', 'sama')
                cur = date(s_start.year, s_start.month, 1)
                while cur < s_end:
                    shoola_timeline[(cur.year, cur.month)] = q
                    nm = cur.month + 1
                    ny = cur.year + (1 if nm > 12 else 0)
                    nm = nm if nm <= 12 else 1
                    cur = date(ny, nm, 1)
            except Exception:
                continue

        target_themes = themes or list(THEME_HOUSES.keys())
        results = {}

        for theme in target_themes:
            target_hs = THEME_HOUSES.get(theme, [])
            monthly_scores = []

            for y, m in _month_iter(start_y, start_m, months):
                base_score = 0.0       # 基础分（不含质量）
                quality_score = 0.0   # 质量调整后的分数
                signals = []
                quality_notes = []

                # ── Vimsottari（激活行星有D9+Shadbala，含MD×AD×PAD三层交叉）──
                vm_md, vm_ad, vm_pad = _vimsottari_at_month(vimsottari, y, m)

                # Step 1：MD×AD 功能角色交叉系数（整体修正，不依赖宫位匹配）
                _cross_factor = 1.0
                _cross_note = None
                if vm_md and vm_ad:
                    _cross_factor, _md_tier, _ad_tier = _md_ad_cross_factor(
                        vm_md, vm_ad, house_lords)
                    if _cross_factor != 1.0:
                        _cross_note = (f'MD×AD交叉:{vm_md}({_md_tier})'
                                       f'×{vm_ad}({_ad_tier})→×{_cross_factor:.2f}')

                # Step 2：逐层评分（MD、AD、PAD）
                for _layer, p in [('MD', vm_md), ('AD', vm_ad), ('PAD', vm_pad)]:
                    if not p:
                        continue
                    p_houses = _vimsottari_houses(p)
                    match_hs = [h for h in p_houses if h in target_hs]
                    if match_hs:
                        # PAD 层基础分降为 1.0（精度层，权重低于 MD/AD）
                        _base = 1.0 if _layer == 'PAD' else 2.0
                        base_score += _base
                        _qf = max(_quality_factor(p, h, chart) for h in match_hs)
                        # MD/AD 层叠加交叉系数；PAD 层不再叠加（避免三重放大）
                        _effective_qf = _qf * (_cross_factor if _layer != 'PAD' else 1.0)
                        quality_score += _base * _effective_qf
                        # 质量分解说明
                        _d9dig = _d9_dignity_for_planet(p, chart)
                        _d9f = D9_DIGNITY_FACTOR.get(_d9dig, 1.0)
                        _sbf = _shadbala_factor(p, chart)
                        _savf = max(_sav_factor(h, chart) for h in match_hs)
                        _tag = f'V[{_layer}]:{p}管{match_hs}'
                        signals.append(_tag)
                        _note = (f'V[{_layer}]:{p} D9={_d9dig}(×{_d9f:.1f})'
                                 f' SB(×{_sbf:.2f}) SAV(×{_savf:.1f})'
                                 f' base×{_effective_qf:.2f}')
                        quality_notes.append(_note)

                # Step 3：记录交叉系数说明
                if _cross_note:
                    quality_notes.append(_cross_note)
                    # 若交叉系数 < 0.7，额外在 signals 里加警告（对用户可见）
                    if _cross_factor <= 0.65:
                        signals.append(f'⚠️{vm_md}大运×{vm_ad}小运凶组合')
                    elif _cross_factor >= 1.3:
                        signals.append(f'✅{vm_md}大运×{vm_ad}小运吉组合')

                # ── Chara（激活宫位，质量只看 SAV）──
                ch_md, ch_ad = _dasha_sign_at_month(chara, y, m)
                _seen_ch = set()
                for sidx in [ch_md, ch_ad]:
                    if sidx is None:
                        continue
                    h = _house_from_lagna(sidx, lagna_idx)
                    if h in target_hs and h not in _seen_ch:
                        _seen_ch.add(h)
                        base_score += 2.0
                        _qf = _jaimini_quality_factor(h, chart)
                        quality_score += 2.0 * _qf
                        _savf = _sav_factor(h, chart)
                        signals.append(f'C:{SIGNS[sidx]}→{h}宫')
                        quality_notes.append(f'C:H{h} SAV(×{_savf:.1f}) →×{_qf:.2f}')

                # ── Narayana（同 Chara）──
                na_md, na_ad = _dasha_sign_at_month(narayana, y, m)
                _seen_na = set()
                for sidx in [na_md, na_ad]:
                    if sidx is None:
                        continue
                    h = _house_from_lagna(sidx, lagna_idx)
                    if h in target_hs and h not in _seen_na:
                        _seen_na.add(h)
                        base_score += 2.0
                        _qf = _jaimini_quality_factor(h, chart)
                        quality_score += 2.0 * _qf
                        _savf = _sav_factor(h, chart)
                        signals.append(f'N:{SIGNS[sidx]}→{h}宫')
                        quality_notes.append(f'N:H{h} SAV(×{_savf:.1f}) →×{_qf:.2f}')

                # ── Shoola 底色（直接叠加，不受质量系数影响）──
                sq = shoola_timeline.get((y, m), 'sama')
                s_delta = SHOOLA_QUALITY_MAP.get(sq, 0)
                base_score += s_delta
                quality_score += s_delta
                if sq == 'harsha':
                    signals.append('Shoola顺境+1')
                elif sq == 'shoola':
                    signals.append('Shoola逆境-1')

                label = f'{y:04d}-{m:02d}'
                monthly_scores.append({
                    'year': y, 'month': m, 'label': label,
                    'score': round(base_score, 1),
                    'quality_score': round(quality_score, 2),
                    'signals': signals,
                    'quality_notes': quality_notes,
                    'details': ' | '.join(signals) if signals else '无特殊激活',
                    'quality_details': ' | '.join(quality_notes) if quality_notes else '',
                })

            # 按质量调整后的分数排序
            top = sorted(monthly_scores, key=lambda x: x['quality_score'], reverse=True)[:12]
            results[theme] = {
                'top_windows': top,
                'timeline': [{'label': x['label'],
                              'score': x['score'],
                              'quality_score': x['quality_score']}
                             for x in monthly_scores],
            }

        end_y, end_m = start_y, start_m
        for _ in range(months):
            end_m += 1
            if end_m > 12:
                end_m = 1; end_y += 1

        return {
            **results,
            'scan_params': {
                'months': months,
                'from': f'{start_y:04d}-{start_m:02d}',
                'to': f'{end_y:04d}-{end_m:02d}',
                'lagna_sign': SIGNS[lagna_idx],
                'quality_weighting': 'D9(40%) + Shadbala(30%) + SAV(30%)',
                'cross_weighting': 'MD×AD功能角色交叉系数(0.5-1.4)叠加在质量系数上',
                'layers': 'Vimsottari MD+AD+PAD三层 | Chara MD+AD | Narayana MD+AD | Shoola底色',
            }
        }
    except Exception as e:
        return {'error': str(e)}


if __name__ == '__main__':
    import sys
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
    from engine import calculate_full_chart
    c = calculate_full_chart(2005, 12, 14, 10, 28, 31.2304, 121.4737, 'Asia/Shanghai',
                              time_precision_level=1, d60_consent=True, d60_trust_level='verified')
    r = scan_timing_confluence(c, months=60, themes=['感情', '事业'])
    if 'error' in r:
        print('ERROR:', r['error'])
    else:
        for theme in ['感情', '事业']:
            print(f'\n=== {theme} 未来60个月 Top 5（质量调整后）===')
            for w in r[theme]['top_windows'][:5]:
                qs = w.get('quality_score', 0)
                bs = w.get('score', 0)
                print(f'  {w["label"]}  基础={bs}  质量调整={qs:.2f}')
                print(f'    信号: {w["details"][:70]}')
                if w.get('quality_details'):
                    print(f'    质量: {w["quality_details"][:70]}')
