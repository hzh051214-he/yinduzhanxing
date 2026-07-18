"""avastha.py — 行星状态（Avastha）计算

替代 engine.py P8 里粗糙的 5 段度数分法，实现 BPHS 标准的两套 Avastha：

## Baladi Avastha（五态，按度数）
  婴儿期(Bala)    0-6°   — 能力未展，需培育
  少年期(Kumara)  6-12°  — 成长中，学习型
  青壮期(Yuva)    12-18° — 最活跃，主动进取
  成熟期(Vriddha) 18-24° — 稳健，经验主导
  老年期(Mrityu)  24-30° — 辅助型，力量衰减

  奇偶宫规则（BPHS 第 45.1-5 章）：
    奇数星座（Ar/Ge/Le/Li/Sg/Aq = sign_idx 0,2,4,6,8,10）：正序排列（0→婴/6→少/…）
    偶数星座（Ta/Cn/Vi/Sc/Cp/Pi = sign_idx 1,3,5,7,9,11）：反序排列（0→老/6→成/12→青/18→少/24→婴）

## Jagradadi Avastha（三态，按星宿主关系）
  醒态(Jagrat)  — 星宿主是该行星的天然友方 → 清醒，全效发挥
  梦态(Swapna)  — 星宿主是中性关系 → 梦游，半效
  睡态(Sushupti)— 星宿主是天然敌方 → 沉睡，效率 ~25%

  数据来源：BPHS Graha Maitri（自然友敌表，不用 Panchadha 合成）
"""

NATURAL_FRIENDS = {
    'Sun':     {'Moon', 'Mars', 'Jupiter'},
    'Moon':    {'Sun', 'Mercury'},
    'Mars':    {'Sun', 'Moon', 'Jupiter'},
    'Mercury': {'Sun', 'Venus'},
    'Jupiter': {'Sun', 'Moon', 'Mars'},
    'Venus':   {'Mercury', 'Saturn'},
    'Saturn':  {'Mercury', 'Venus'},
}
NATURAL_ENEMIES = {
    'Sun':     {'Venus', 'Saturn'},
    'Moon':    set(),
    'Mars':    {'Mercury'},
    'Mercury': {'Moon'},
    'Jupiter': {'Mercury', 'Venus'},
    'Venus':   {'Sun', 'Moon'},
    'Saturn':  {'Sun', 'Moon', 'Mars'},
}
RAHU_KETU_FRIENDS = {'Venus', 'Saturn'}
RAHU_KETU_ENEMIES = {'Sun', 'Moon', 'Mars'}

# Baladi 阶段名称
BALADI_NAMES = ['婴儿(Bala)', '少年(Kumara)', '青壮(Yuva)', '成熟(Vriddha)', '老年(Mrityu)']
BALADI_KEYS  = ['bala', 'kumara', 'yuva', 'vriddha', 'mrityu']
BALADI_EFFECT = {
    'bala':    '潜力未展，需时间成熟',
    'kumara':  '成长型，学习中',
    'yuva':    '最活跃，主动进取，全效',
    'vriddha': '稳健成熟，经验主导',
    'mrityu':  '辅助型，力量衰减',
}

# Jagradadi 状态名称
JAGRADADI_NAMES = ['醒(Jagrat)', '梦(Swapna)', '睡(Sushupti)']
JAGRADADI_KEYS  = ['jagrat', 'swapna', 'sushupti']
JAGRADADI_EFFECT = {
    'jagrat':   '清醒，全效发挥（约100%）',
    'swapna':   '半醒，中效（约50%）',
    'sushupti': '沉睡，低效（约25%）',
}


def _baladi(planet_name, degree_in_sign, sign_idx):
    """返回 (baladi_key, baladi_name, effect)"""
    is_odd_sign = (sign_idx % 2 == 0)  # 0-indexed: 0=Ar(奇) 1=Ta(偶) ...
    buckets = [0, 6, 12, 18, 24, 30]  # 5 buckets
    bucket = min(int(degree_in_sign / 6), 4)  # 0-4
    if is_odd_sign:
        idx = bucket
    else:
        idx = 4 - bucket   # 反序
    key = BALADI_KEYS[idx]
    return key, BALADI_NAMES[idx], BALADI_EFFECT[key]


def _jagradadi(planet_name, nakshatra_lord):
    """返回 (jagradadi_key, jagradadi_name, effect)"""
    if planet_name in ('Rahu', 'Ketu'):
        friends = RAHU_KETU_FRIENDS
        enemies = RAHU_KETU_ENEMIES
    else:
        friends = NATURAL_FRIENDS.get(planet_name, set())
        enemies = NATURAL_ENEMIES.get(planet_name, set())

    if nakshatra_lord == planet_name:
        # 自己的 nakshatra → 醒态（同庙效果）
        key = 'jagrat'
    elif nakshatra_lord in friends:
        key = 'jagrat'
    elif nakshatra_lord in enemies:
        key = 'sushupti'
    else:
        key = 'swapna'

    idx = JAGRADADI_KEYS.index(key)
    return key, JAGRADADI_NAMES[idx], JAGRADADI_EFFECT[key]


def calculate_avastha(chart):
    """计算 9 颗行星的双层 Avastha。

    Returns:
        {planet_name: {
            'baladi':    {'key', 'name', 'effect'},
            'jagradadi': {'key', 'name', 'effect', 'nak_lord'},
        }}
    """
    planets = chart['planets']
    result = {}
    for name in ['Sun', 'Moon', 'Mars', 'Mercury', 'Jupiter',
                 'Venus', 'Saturn', 'Rahu', 'Ketu']:
        p = planets[name]
        degree = p['degree']
        sign_idx = p['sign_idx']
        nak_lord = p['nakshatra']['lord']

        b_key, b_name, b_eff = _baladi(name, degree, sign_idx)
        j_key, j_name, j_eff = _jagradadi(name, nak_lord)

        result[name] = {
            'baladi':    {'key': b_key, 'name': b_name, 'effect': b_eff, 'degree': round(degree, 2)},
            'jagradadi': {'key': j_key, 'name': j_name, 'effect': j_eff, 'nak_lord': nak_lord},
        }
    return result


if __name__ == '__main__':
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    from engine import calculate_full_chart
    chart = calculate_full_chart(2005, 12, 14, 10, 28, 31.2304, 121.4737, 'Asia/Shanghai')
    avs = calculate_avastha(chart)
    print('=== Avastha 行星状态 ===')
    print(f"{'行星':<10} {'度数':>6}  {'Baladi':<18}  {'Jagradadi':<15}  {'nak主'}")
    print('-' * 75)
    for name, av in avs.items():
        b = av['baladi']
        j = av['jagradadi']
        print(f"{name:<10} {b['degree']:>6.2f}°  {b['name']:<18}  {j['name']:<15}  {j['nak_lord']}")
    print('=== 完成 ✅ ===')
