"""argala.py — Argala（干预链）计算

Argala（干预）：某宫位的 2/4/11 宫有行星 → 对该宫产生"正干预"，强化吉；
Virodhargala（反干预）：12/10/3 宫有行星 → 抵消对应干预。

Jaimini / Parashari 双派共识规则（KN Rao 标准）：
  正干预宫位：2宫（财富/关系）、4宫（舒适/家庭）、11宫（利益/收入）
  辅助干预：  5宫（少数流派承认；本实现标注但不计入净分）
  反干预宫位：12宫（对抗2宫）、10宫（对抗4宫）、3宫（对抗11宫）
  辅助反干预：9宫（对抗5宫辅助干预）

净效果判定：
  正干预行星数 > 反干预行星数 → argala_net = 'positive'
  正干预行星数 < 反干预行星数 → argala_net = 'blocked'
  相等 → 'neutral'
  无任何干预 → 'none'

用途：宫位诊断维度的补充——告诉 AI「谁在干预这个宫位」，
      从而判断该宫位的实际净吉凶，而非只看宫主和相位。
"""

PLANETS9 = ['Sun', 'Moon', 'Mars', 'Mercury', 'Jupiter', 'Venus', 'Saturn', 'Rahu', 'Ketu']

# Argala 宫位配对：{干预宫距: 反干预宫距}（从被分析宫位顺数）
ARGALA_PAIRS = {
    2: 12,   # 2宫干预 ↔ 12宫反干预
    4: 10,   # 4宫干预 ↔ 10宫反干预
    11: 3,   # 11宫干预 ↔ 3宫反干预
}
SECONDARY_ARGALA = 5    # 5宫辅助干预（不计净分，仅标注）
SECONDARY_VIRODHA = 9   # 9宫抵消5宫辅助干预


def _house_from(base_sign_idx, offset, lagna_sign_idx):
    """从 base_sign_idx 顺数 offset 宫后，计算从 lagna 数的宫位号（1-12）。"""
    target_sign = (base_sign_idx + offset - 1) % 12
    return target_sign, ((target_sign - lagna_sign_idx) % 12) + 1


def calculate_argala(chart):
    """计算所有 12 个宫位的 Argala（干预链）。

    Returns:
        {house_num(1-12): {
            'argala_planets':  {宫距: [行星列表]},  # 正干预
            'virodha_planets': {宫距: [行星列表]},  # 反干预
            'argala_net': 'positive' | 'blocked' | 'neutral' | 'none',
            'secondary_argala': [行星列表],          # 5宫辅助（仅标注）
            'secondary_virodha': [行星列表],         # 9宫辅助反干预
        }}
    """
    lagna_idx = chart['lagna']['sign_idx']
    planets = chart['planets']

    # 建立 sign_idx → 该宫行星列表 的映射
    sign_to_planets = {i: [] for i in range(12)}
    for name in PLANETS9:
        sign_to_planets[planets[name]['sign_idx']].append(name)

    result = {}
    for house in range(1, 13):
        # 该宫位的星座索引
        base_sign = (lagna_idx + house - 1) % 12

        argala = {}      # {距离: [行星]}
        virodha = {}     # {距离: [行星]}
        sec_argala = []
        sec_virodha = []

        for dist, opp_dist in ARGALA_PAIRS.items():
            a_sign = (base_sign + dist - 1) % 12
            v_sign = (base_sign + opp_dist - 1) % 12
            a_planets = sign_to_planets[a_sign]
            v_planets = sign_to_planets[v_sign]
            if a_planets:
                argala[dist] = a_planets
            if v_planets:
                virodha[opp_dist] = v_planets

        # 5/9 辅助
        s5_sign = (base_sign + 4) % 12
        s9_sign = (base_sign + 8) % 12
        sec_argala = sign_to_planets[s5_sign]
        sec_virodha = sign_to_planets[s9_sign]

        # 净效果：只计主干预对（2/12、4/10、11/3）
        a_count = sum(len(v) for v in argala.values())
        v_count = sum(len(v) for v in virodha.values())
        if a_count == 0 and v_count == 0:
            net = 'none'
        elif a_count > v_count:
            net = 'positive'
        elif v_count > a_count:
            net = 'blocked'
        else:
            net = 'neutral'

        result[house] = {
            'argala_planets': argala,
            'virodha_planets': virodha,
            'argala_net': net,
            'secondary_argala': sec_argala,
            'secondary_virodha': sec_virodha,
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
    result = calculate_argala(chart)
    print('=== Argala 干预链 ===')
    DOMAINS = {1:'自我',2:'财富',3:'兄弟',4:'家庭',5:'子女',6:'疾病',
               7:'婚姻',8:'变故',9:'运势',10:'事业',11:'收入',12:'损耗'}
    for h in range(1, 13):
        r = result[h]
        net = r['argala_net']
        a_str = '; '.join(f"{d}宫:{','.join(ps)}" for d, ps in r['argala_planets'].items())
        v_str = '; '.join(f"{d}宫:{','.join(ps)}" for d, ps in r['virodha_planets'].items())
        print(f"  {h:>2}宫({DOMAINS[h]:<4}) 净:{net:<9} 干预:{a_str or '无':<35} 反干预:{v_str or '无'}")
    print('=== 完成 ✅ ===')
