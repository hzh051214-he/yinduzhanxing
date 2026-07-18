"""
synastry_pyjhora — 双盘合参（配偶相容性分析）
=============================================
两层分析：

层一：Ashtakoota（八大 Koota，28分制 Guna Milan）
  传统南北印度双方 Nakshatra 相容性打分：
  Varna(1) + Vasiya(2) + Tara(3) + Yoni(4) +
  Maitri(5) + Gana(6) + Bhakut(7) + Naadi(8) = 共36分
  ≥28 = 极佳，≥21 = 合适，≥18 = 可接受，<18 = 需谨慎

层二：Jaimini/Parashari 双盘判定
  - 双方 DK（配偶指示星）的互相激活
  - 双方 UL（伴侣宫 Upapada Lagna）的交叉
  - 双方 7 宫主（L7）的相互激活宫位
  - 双方 A7（Darapada）的位置关系

对外接口：
  calculate_synastry(
      person1: dict,  # {year,month,day,hour,minute,lat,lon,tz_offset,gender}
      person2: dict,
  ) → 相容性分析结果

person gender: 'M' (男) / 'F' (女)
"""
from _pyjhora_base import build_jd_place, _silence_stdout, SIGNS

SIGN_LORDS = {
    0:'Mars', 1:'Venus', 2:'Mercury', 3:'Moon', 4:'Sun', 5:'Mercury',
    6:'Venus', 7:'Mars', 8:'Jupiter', 9:'Saturn', 10:'Saturn', 11:'Jupiter'
}

NAKSHATRA_NAMES = [
    'Ashwini', 'Bharani', 'Krittika', 'Rohini', 'Mrigashira', 'Ardra',
    'Punarvasu', 'Pushya', 'Ashlesha', 'Magha', 'Purva Phalguni', 'Uttara Phalguni',
    'Hasta', 'Chitra', 'Swati', 'Vishakha', 'Anuradha', 'Jyeshtha',
    'Moola', 'Purva Ashadha', 'Uttara Ashadha', 'Shravana', 'Dhanishta',
    'Shatabhisha', 'Purva Bhadrapada', 'Uttara Bhadrapada', 'Revati'
]

# Koota 最大分值
KOOTA_MAX = {
    'Varna': 1, 'Vasiya': 2, 'Tara': 3, 'Yoni': 4,
    'Maitri': 5, 'Gana': 6, 'Bhakut': 7, 'Naadi': 8,
}
KOOTA_MAX_TOTAL = 36

KOOTA_DESC = {
    'Varna': '社会地位/精神层次相容性',
    'Vasiya': '相互吸引力和控制力',
    'Tara': '命运相容性（出生星宿距离）',
    'Yoni': '性格/本性相容性',
    'Maitri': '双方月亮守护星的友敌关系',
    'Gana': '性情/气质相容（天/人/鬼属性）',
    'Bhakut': '整体相容性和健康',
    'Naadi': '健康和后代相容性（最重要）',
}

# 相容等级
def _compat_grade(score, total):
    pct = score / total * 100
    if pct >= 78:    return '极佳 ★★★★★'
    elif pct >= 67:  return '良好 ★★★★'
    elif pct >= 58:  return '合适 ★★★'
    elif pct >= 50:  return '可接受 ★★'
    elif pct >= 33:  return '需慎重 ★'
    else:             return '不建议 ☆'


def _get_nakshatra_pada(year, month, day, hour, minute, lat, lon, tz_offset):
    """获取某人的月亮星宿和 Pada。"""
    jd, place = build_jd_place(year, month, day, hour, minute, lat, lon, tz_offset)
    from jhora.panchanga import drik
    with _silence_stdout():
        na = drik.nakshatra(jd, place)
    return int(na[0]), int(na[1])  # (nakshatra_num 1-27, pada 1-4)


def _ashtakoota(na1, pa1, na2, pa2):
    """计算 Ashtakoota 8 个 Koota 的得分。
    Returns dict of {koota_name: {'score': int, 'max': int, 'result': str}}
    PyJHora Ashtakoota scores are computed by calling methods (not reading attrs).
    Each method returns (score, max_score) tuple.
    """
    from jhora.horoscope.match import compatibility
    with _silence_stdout():
        ak = compatibility.Ashtakoota(na1, pa1, na2, pa2)

    # Method names → max scores mapping
    method_map = [
        ('Varna',   'varna_porutham',    1),
        ('Vasiya',  'vasiya_porutham',   2),
        ('Tara',    'tara_porutham',     3),
        ('Yoni',    'yoni_porutham',     4),
        ('Maitri',  'raasi_adhipathi_porutham', 5),
        ('Gana',    'gana_porutham',     6),
        ('Bhakut',  'raasi_porutham',    7),
        ('Naadi',   'naadi_porutham',    8),
    ]
    results = {}
    total_score = 0
    for koota, method_name, max_score in method_map:
        try:
            method = getattr(ak, method_name, None)
            if method and callable(method):
                with _silence_stdout():
                    raw = method()
                # raw can be (score, max) tuple, bool, or int
                if isinstance(raw, (list, tuple)) and len(raw) >= 2:
                    score = int(raw[0])
                elif isinstance(raw, bool):
                    score = max_score if raw else 0
                elif isinstance(raw, (int, float)):
                    score = min(int(raw), max_score)
                else:
                    score = 0
            else:
                score = 0
            score = max(0, min(score, max_score))  # clamp
            result = '✅ 相容' if score == max_score else ('⚠️ 部分' if score > 0 else '❌ 不相容')
            results[koota] = {
                'score': score, 'max': max_score,
                'result': result,
                'desc': KOOTA_DESC.get(koota, '')
            }
            total_score += score
        except Exception as ex:
            results[koota] = {'score': 0, 'max': max_score, 'result': f'—({ex})', 'desc': KOOTA_DESC.get(koota, '')}

    grade = _compat_grade(total_score, KOOTA_MAX_TOTAL)
    return {
        'koota_scores': results,
        'total_score': total_score,
        'max_score': KOOTA_MAX_TOTAL,
        'grade': grade,
        'percent': round(total_score / KOOTA_MAX_TOTAL * 100, 1),
    }


def _jaimini_cross(chart1, chart2, gender1='M', gender2='F'):
    """Jaimini/Parashari 双盘交叉分析。
    gender: 'M' = 男, 'F' = 女
    """
    # DK（配偶指示星）双方互相激活
    dk1 = None; dk2 = None
    for k, p, d in chart1.get('karakas', {}).get('8k', []):
        if k == 'DK': dk1 = p
    for k, p, d in chart2.get('karakas', {}).get('8k', []):
        if k == 'DK': dk2 = p

    # UL（Upapada Lagna）
    ul1 = chart1.get('special_points', {}).get('UL', {})
    ul2 = chart2.get('special_points', {}).get('UL', {})

    # A7 (Darapada)
    a7_1 = chart1.get('arudha_padas', {}).get('A7', {})
    a7_2 = chart2.get('arudha_padas', {}).get('A7', {})

    # 7 宫主
    l7_1 = chart1.get('house_lords', {}).get(7, {}).get('lord', '?')
    l7_2 = chart2.get('house_lords', {}).get(7, {}).get('lord', '?')

    # 判断 Person2 的 DK 是否落在 Person1 的 7 宫（或相关宫位）
    signals = []

    # DK 激活：Person1 的 DK 行星 = Person2 的某颗关键星
    if dk1 and dk1 in [p for p in chart2.get('planets', {})]:
        dk1_house_in_p2 = chart2['planets'][dk1]['house']
        if dk1_house_in_p2 in (1, 7, 5, 9):
            signals.append(f"✅ P1的DK({dk1})在P2盘的{dk1_house_in_p2}宫（感情相关宫位）")
        else:
            signals.append(f"ℹ️ P1的DK({dk1})在P2盘的{dk1_house_in_p2}宫")

    if dk2 and dk2 in [p for p in chart1.get('planets', {})]:
        dk2_house_in_p1 = chart1['planets'][dk2]['house']
        if dk2_house_in_p1 in (1, 7, 5, 9):
            signals.append(f"✅ P2的DK({dk2})在P1盘的{dk2_house_in_p1}宫（感情相关宫位）")

    # UL 交叉：P1 的 UL 与 P2 的 7 宫 Lagna 的关系
    ul1_sign = ul1.get('sign', '')
    ul2_sign = ul2.get('sign', '')
    lagna2_sign = chart2.get('lagna', {}).get('sign', '')
    lagna1_sign = chart1.get('lagna', {}).get('sign', '')
    if ul1_sign and lagna2_sign:
        ul1_idx = SIGNS.index(ul1_sign) if ul1_sign in SIGNS else -1
        l2_idx = SIGNS.index(lagna2_sign) if lagna2_sign in SIGNS else -1
        dist = ((ul1_idx - l2_idx) % 12) + 1 if ul1_idx >= 0 and l2_idx >= 0 else 0
        if dist in (1, 7):
            signals.append(f"✅ P1的UL({ul1_sign})落在P2上升{dist}宫（婚姻信号强）")
        elif dist in (5, 9):
            signals.append(f"✅ P1的UL({ul1_sign})与P2上升形成三角（和谐信号）")

    # A7 交叉
    a7_1_sign = a7_1.get('sign', '')
    a7_2_sign = a7_2.get('sign', '')
    if a7_1_sign and a7_2_sign:
        a7_1_idx = SIGNS.index(a7_1_sign) if a7_1_sign in SIGNS else -1
        a7_2_idx = SIGNS.index(a7_2_sign) if a7_2_sign in SIGNS else -1
        if a7_1_idx >= 0 and a7_2_idx >= 0:
            a7_dist = abs(a7_1_idx - a7_2_idx)
            a7_dist = min(a7_dist, 12 - a7_dist)
            if a7_dist in (0, 6):
                signals.append(f"✅ 双方A7（实际伴侣宫）{('同宫' if a7_dist==0 else '对望')}({a7_1_sign}/{a7_2_sign})，强烈吸引信号")
            elif a7_dist in (2, 4):
                signals.append(f"ℹ️ 双方A7形成三角/六合({a7_1_sign}/{a7_2_sign})")

    # L7 互动
    if l7_1 and l7_2:
        l7_1_sign = chart1['planets'].get(l7_1, {}).get('sign', '')
        l7_2_sign = chart2['planets'].get(l7_2, {}).get('sign', '')
        signals.append(f"P1的L7({l7_1})在{l7_1_sign} | P2的L7({l7_2})在{l7_2_sign}")

    # Manglik check
    mg1 = chart1.get('special_planets', {}).get('manglik', False)
    mg1_ex = chart1.get('special_planets', {}).get('manglik_exceptions', False)
    mg2 = chart2.get('special_planets', {}).get('manglik', False)
    mg2_ex = chart2.get('special_planets', {}).get('manglik_exceptions', False)
    manglik_note = ''
    if mg1 and mg2:
        manglik_note = '双方均有Manglik → 相互抵消，感情磨砺但不单方受损'
    elif mg1 and not mg1_ex:
        manglik_note = '⚠️ P1有Manglik（无化解）→ 双方感情需要特别关注'
    elif mg2 and not mg2_ex:
        manglik_note = '⚠️ P2有Manglik（无化解）→ 双方感情需要特别关注'
    elif mg1 or mg2:
        manglik_note = 'Manglik存在但有化解条件，影响可控'

    return {
        'dk_p1': dk1, 'dk_p2': dk2,
        'ul_p1': ul1_sign, 'ul_p2': ul2_sign,
        'a7_p1': a7_1_sign, 'a7_p2': a7_2_sign,
        'l7_p1': l7_1, 'l7_p2': l7_2,
        'compatibility_signals': signals,
        'manglik_note': manglik_note,
    }


def calculate_synastry(person1: dict, person2: dict):
    """计算双方相容性。

    person1/person2 格式:
      {'year':int,'month':int,'day':int,'hour':int,'minute':int,
       'lat':float,'lon':float,'tz_offset':float,'gender':'M'/'F',
       'chart': dict}  # chart 是 calculate_full_chart() 的返回值
    chart 如果不传，会自动计算（但需要 tz_str 而非 tz_offset）
    """
    try:
        # 获取星宿和 Pada
        na1, pa1 = _get_nakshatra_pada(
            person1['year'], person1['month'], person1['day'],
            person1['hour'], person1['minute'],
            person1['lat'], person1['lon'], person1['tz_offset'])
        na2, pa2 = _get_nakshatra_pada(
            person2['year'], person2['month'], person2['day'],
            person2['hour'], person2['minute'],
            person2['lat'], person2['lon'], person2['tz_offset'])

        # 层一：Ashtakoota
        ashtakoota = _ashtakoota(na1, pa1, na2, pa2)

        # 层二：Jaimini/Parashari（如果 chart 数据已提供）
        chart1 = person1.get('chart')
        chart2 = person2.get('chart')
        jaimini = None
        if chart1 and chart2:
            jaimini = _jaimini_cross(chart1, chart2, person1.get('gender','M'), person2.get('gender','F'))

        return {
            'person1_nakshatra': {'number': na1, 'name': NAKSHATRA_NAMES[na1-1] if 1<=na1<=27 else '?', 'pada': pa1},
            'person2_nakshatra': {'number': na2, 'name': NAKSHATRA_NAMES[na2-1] if 1<=na2<=27 else '?', 'pada': pa2},
            'ashtakoota': ashtakoota,
            'jaimini_cross': jaimini,
            'summary': _summary(ashtakoota, jaimini),
        }
    except Exception as e:
        return {'error': str(e)}


def _summary(ashtakoota, jaimini):
    """生成综合评估摘要。"""
    score = ashtakoota['total_score']
    grade = ashtakoota['grade']
    parts = [f"Ashtakoota总分：{score}/{KOOTA_MAX_TOTAL}（{ashtakoota['percent']}%），{grade}"]
    if jaimini:
        sig_count = len([s for s in jaimini['compatibility_signals'] if '✅' in s])
        parts.append(f"Jaimini双盘交叉：{sig_count}个正向信号")
        if jaimini.get('manglik_note'):
            parts.append(f"Manglik说明：{jaimini['manglik_note']}")
    return ' | '.join(parts)


if __name__ == '__main__':
    import sys
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    # 测试：样本盘 vs 虚构伴侣
    r = calculate_synastry(
        {'year':2005,'month':12,'day':14,'hour':10,'minute':28,'lat':31.23,'lon':121.47,'tz_offset':8.0,'gender':'M'},
        {'year':2006,'month':3,'day':20,'hour':8,'minute':15,'lat':28.61,'lon':77.21,'tz_offset':5.5,'gender':'F'},
    )
    if 'error' in r:
        print('ERROR:', r['error'])
    else:
        print(f'P1星宿: {r["person1_nakshatra"]}')
        print(f'P2星宿: {r["person2_nakshatra"]}')
        ak = r['ashtakoota']
        total = ak["total_score"]; maxi = ak["max_score"]; grade = ak["grade"]
        print(f'Ashtakoota: {total}/{maxi} {grade}')
        for k, v in ak['koota_scores'].items():
            sc = v["score"]; mx = v["max"]; res = v["result"]
            print(f'  {k}: {sc}/{mx} {res}')
        print('摘要:', r['summary'])
