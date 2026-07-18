"""
rectifier_auto.py — 出生时间自动校准（Rectification 自动化闭环）
================================================================
整合现有的 time_scan.py（时间扫描）和 event_house_map.md（事件-宫位映射），
实现从"用户输入5个事件"到"最佳出生时间"的全自动评分闭环。

流程：
  Step 1: 接收出生信息（基准时间±范围）
  Step 2: 接收 1-10 个重大人生事件（事件类型 + 年份）
  Step 3: 对范围内每分钟的出生时间，计算对应的 Dasha/Antardasha
  Step 4: 对每个时间点，计算每个事件与对应大运的匹配分
  Step 5: 输出最高匹配分的前5个时间点 + 置信度

评分规则（来自 event_house_map.md）：
  强匹配（大运主星 = 事件宫主）      : +4分
  中匹配（落宫/照射/Karaka 匹配）    : +2分
  弱匹配（间接关联）                 : +1分
  不匹配                            : 0分

支持的事件类型（来自 event_house_map.md）：
  marriage, romance, breakup, promotion, job_start, job_quit,
  startup, exam_pass, relocation, buy_house, serious_illness,
  surgery, accident, father_death, mother_death, child_birth,
  windfall, big_loss, lawsuit, emigration, award
"""

import swisseph as swe
from datetime import datetime, timedelta
import pytz

from _pyjhora_base import build_jd_place, _silence_stdout, SIGNS

SIGN_LORDS = {
    0:'Mars', 1:'Venus', 2:'Mercury', 3:'Moon', 4:'Sun', 5:'Mercury',
    6:'Venus', 7:'Mars', 8:'Jupiter', 9:'Saturn', 10:'Saturn', 11:'Jupiter'
}

# ── 事件-宫位映射（来自 event_house_map.md）──
EVENT_HOUSE_MAP = {
    'marriage':       {'houses': [7], 'aux': [2], 'karakas': ['Venus'], 'planets': ['Venus']},
    'romance':        {'houses': [5], 'aux': [7], 'karakas': ['Venus'], 'planets': ['Venus']},
    'breakup':        {'houses': [6, 8], 'aux': [7], 'karakas': [], 'planets': ['Mars', 'Saturn']},
    'promotion':      {'houses': [10], 'aux': [11], 'karakas': ['Sun'], 'planets': ['Sun']},
    'job_start':      {'houses': [10], 'aux': [6, 11], 'karakas': [], 'planets': []},
    'job_quit':       {'houses': [10], 'aux': [12], 'karakas': [], 'planets': []},
    'startup':        {'houses': [10, 5], 'aux': [3], 'karakas': [], 'planets': ['Mars']},
    'exam_pass':      {'houses': [4, 5], 'aux': [], 'karakas': [], 'planets': ['Mercury', 'Jupiter']},
    'relocation':     {'houses': [4], 'aux': [3, 12], 'karakas': [], 'planets': ['Moon']},
    'buy_house':      {'houses': [4], 'aux': [], 'karakas': [], 'planets': ['Mars']},
    'serious_illness':{'houses': [6], 'aux': [8], 'karakas': [], 'planets': []},
    'surgery':        {'houses': [8], 'aux': [6], 'karakas': [], 'planets': ['Mars']},
    'accident':       {'houses': [8], 'aux': [], 'karakas': [], 'planets': ['Mars']},
    'father_death':   {'houses': [9], 'aux': [2], 'karakas': ['Sun'], 'planets': ['Sun']},
    'mother_death':   {'houses': [4], 'aux': [2], 'karakas': ['Moon'], 'planets': ['Moon']},
    'child_birth':    {'houses': [5], 'aux': [], 'karakas': ['Moon'], 'planets': ['Jupiter']},
    'windfall':       {'houses': [2, 11], 'aux': [], 'karakas': [], 'planets': ['Jupiter']},
    'big_loss':       {'houses': [12], 'aux': [8], 'karakas': [], 'planets': []},
    'lawsuit':        {'houses': [6], 'aux': [], 'karakas': [], 'planets': []},
    'emigration':     {'houses': [12], 'aux': [9], 'karakas': [], 'planets': ['Rahu']},
    'award':          {'houses': [10, 11], 'aux': [], 'karakas': [], 'planets': ['Sun', 'Jupiter']},
}

# 强匹配：大运主星管事件的核心宫位（是该宫的宫主）
# 中匹配：大运主星落在核心宫位 / 照射核心宫位 / 是事件的 Karaka
# 弱匹配：间接关联

NATURAL_BENEFICS = {'Jupiter', 'Venus', 'Mercury', 'Moon'}
PLANETS9 = ['Sun', 'Moon', 'Mars', 'Mercury', 'Jupiter', 'Venus', 'Saturn', 'Rahu', 'Ketu']

# Vimsottari 标准年数
DASHA_YEARS = {
    'Ketu': 7, 'Venus': 20, 'Sun': 6, 'Moon': 10, 'Mars': 7,
    'Rahu': 18, 'Jupiter': 16, 'Saturn': 19, 'Mercury': 17,
}
DASHA_ORDER = ['Ketu', 'Venus', 'Sun', 'Moon', 'Mars', 'Rahu', 'Jupiter', 'Saturn', 'Mercury']


def _get_dasha_at_date(birth_moon_lon, birth_dt, target_year):
    """给定出生时的月亮经度和出生时间，计算 target_year 时处于哪段大运/小运。
    返回 (mahadasha_planet, antardasha_planet) 或 (mahadasha_planet, None)
    """
    NAKSHATRAS = 27
    nak_span = 360 / NAKSHATRAS
    nak_idx = int(birth_moon_lon / nak_span)
    nak_elapsed = birth_moon_lon % nak_span
    remaining_frac = 1 - (nak_elapsed / nak_span)

    # 找月亮所在星宿的大运主星
    nak_lord_idx = {
        0: 'Ketu', 1: 'Venus', 2: 'Sun', 3: 'Moon', 4: 'Mars', 5: 'Rahu',
        6: 'Jupiter', 7: 'Saturn', 8: 'Mercury', 9: 'Ketu', 10: 'Venus',
        11: 'Sun', 12: 'Moon', 13: 'Mars', 14: 'Rahu', 15: 'Jupiter',
        16: 'Saturn', 17: 'Mercury', 18: 'Ketu', 19: 'Venus', 20: 'Sun',
        21: 'Moon', 22: 'Mars', 23: 'Rahu', 24: 'Jupiter', 25: 'Saturn', 26: 'Mercury',
    }
    start_planet = nak_lord_idx.get(nak_idx % 27, 'Ketu')
    start_idx = DASHA_ORDER.index(start_planet)

    # 计算大运起始时间
    first_years = DASHA_YEARS[start_planet]
    elapsed_years = first_years * (1 - remaining_frac)
    current_dt = birth_dt - timedelta(days=elapsed_years * 365.25)

    # 扫描大运
    target_dt = datetime(target_year, 7, 1)  # 用年份中间作为代表时间点
    for i in range(9):
        idx = (start_idx + i) % 9
        planet = DASHA_ORDER[idx]
        years = DASHA_YEARS[planet]
        end_dt = current_dt + timedelta(days=years * 365.25)
        if current_dt <= target_dt < end_dt:
            # 找小运
            ad_start = current_dt
            for j in range(9):
                ad_idx = (idx + j) % 9
                ad_planet = DASHA_ORDER[ad_idx]
                ad_years = years * DASHA_YEARS[ad_planet] / 120
                ad_end = ad_start + timedelta(days=ad_years * 365.25)
                if ad_start <= target_dt < ad_end:
                    return (planet, ad_planet)
                ad_start = ad_end
            return (planet, None)
        current_dt = end_dt
    return (DASHA_ORDER[start_idx], None)


def _score_event(event_type, year, house_lords, planet_positions, aspects, md, ad):
    """对单个事件打分，返回 0-6 的整数分。"""
    event_info = EVENT_HOUSE_MAP.get(event_type, {})
    if not event_info:
        return 0

    target_houses = event_info['houses']
    aux_houses = event_info.get('aux', [])
    karakas = event_info.get('karakas', [])
    event_planets = event_info.get('planets', [])

    score = 0
    for active_planet in [md, ad]:
        if not active_planet:
            continue
        owned = [h for h in range(1, 13) if house_lords.get(h) == active_planet]
        planet_house = planet_positions.get(active_planet, {}).get('house', 0)
        planet_aspects = [a['p2'] for a in aspects if a['p1'] == active_planet]

        # 强匹配：主星管核心宫位
        if set(owned) & set(target_houses):
            score = max(score, 4)
            continue
        # 中匹配：落在核心宫位
        if planet_house in target_houses:
            score = max(score, 2)
            continue
        # 中匹配：照射核心宫位（主星 p1 相位到核心宫的宫主）
        for th in target_houses:
            lord_of_th = house_lords.get(th, '')
            if lord_of_th in planet_aspects:
                score = max(score, 2)
        # 中匹配：是事件的 Karaka
        if active_planet in karakas or active_planet in event_planets:
            score = max(score, 2)
            continue
        # 弱匹配：管辅助宫位
        if set(owned) & set(aux_houses):
            score = max(score, 1)
        # 弱匹配：落在辅助宫位
        if planet_house in aux_houses:
            score = max(score, 1)

    return score


def _moon_longitude_at_birth(year, month, day, hour, minute, tz_str):
    """计算指定出生时间的月亮黄道经度（恒星黄道 Lahiri）。"""
    tz = pytz.timezone(tz_str)
    local_dt = tz.localize(datetime(year, month, day, hour, minute))
    utc_dt = local_dt.astimezone(pytz.utc)
    ut_h = utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0
    jd = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, ut_h)
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    flags = swe.FLG_SIDEREAL | swe.FLG_SPEED
    result = swe.calc_ut(jd, swe.MOON, flags)
    return result[0][0]


def auto_rectify(
        year, month, day, hour, minute, lat, lon, tz_str,
        events: list,
        scan_range_minutes: int = 60,
        top_n: int = 5
):
    """自动校准出生时间。

    Parameters
    ----------
    year, month, day, hour, minute : 基准出生时间
    lat, lon, tz_str : 出生地点
    events : list of {'type': str, 'year': int}
        type: 见 EVENT_HOUSE_MAP 键名
        year: 事件发生年份
    scan_range_minutes : 在基准时间 ±N 分钟内扫描
    top_n : 返回得分最高的前 N 个时间点

    Returns
    -------
    {
        'base_time': 'HH:MM',
        'scan_range': '±Nmin',
        'events': [...],
        'results': [
            {'time': 'HH:MM', 'score': int, 'max_score': int, 'pct': float,
             'confidence': str, 'event_scores': {...}},
            ...
        ],
        'recommendation': str,
    }
    """
    from engine import calculate_full_chart

    max_possible = len(events) * 6  # 每个事件最高6分
    base_dt = datetime(year, month, day, hour, minute)

    candidate_scores = []

    for delta in range(-scan_range_minutes, scan_range_minutes + 1):
        test_dt = base_dt + timedelta(minutes=delta)
        try:
            # 快速计算：只需月亮经度、宫主表、行星位置、大运
            moon_lon = _moon_longitude_at_birth(
                test_dt.year, test_dt.month, test_dt.day,
                test_dt.hour, test_dt.minute, tz_str)

            # 计算此时间点的星盘核心数据（不算所有分盘，只需宫主表和行星位置）
            chart = calculate_full_chart(
                test_dt.year, test_dt.month, test_dt.day,
                test_dt.hour, test_dt.minute, lat, lon, tz_str)
            house_lords = {h: chart['house_lords'][h]['lord'] for h in range(1, 13)}
            planet_positions = chart['planets']
            aspects = chart['aspects']

            birth_dt_naive = datetime(test_dt.year, test_dt.month, test_dt.day,
                                       test_dt.hour, test_dt.minute)

            # 对每个事件打分
            event_scores = {}
            total = 0
            for event in events:
                md, ad = _get_dasha_at_date(moon_lon, birth_dt_naive, event['year'])
                sc = _score_event(event['type'], event['year'],
                                   house_lords, planet_positions, aspects, md, ad)
                event_scores[f"{event['type']}({event['year']})"] = {
                    'score': sc, 'md': md, 'ad': ad
                }
                total += sc

            candidate_scores.append({
                'delta': delta,
                'time': test_dt.strftime('%H:%M'),
                'score': total,
                'event_scores': event_scores,
            })
        except Exception:
            candidate_scores.append({'delta': delta, 'time': test_dt.strftime('%H:%M'),
                                      'score': 0, 'event_scores': {}})

    # 排序取前 N
    candidate_scores.sort(key=lambda x: x['score'], reverse=True)
    top_results = []
    for c in candidate_scores[:top_n]:
        pct = round(c['score'] / max(max_possible, 1) * 100, 1)
        if pct >= 60:
            conf = 'high（建议采用）'
        elif pct >= 40:
            conf = 'medium（可参考）'
        else:
            conf = 'low（仍有较大不确定性）'
        top_results.append({
            'time': c['time'],
            'delta_min': c['delta'],
            'score': c['score'],
            'max_score': max_possible,
            'pct': pct,
            'confidence': conf,
            'event_scores': c['event_scores'],
        })

    best = top_results[0] if top_results else {}
    rec = (f"建议出生时间：{best.get('time','')} "
           f"（基准±{best.get('delta_min',0):+d}分钟，"
           f"匹配度 {best.get('pct',0)}%，{best.get('confidence','')}）"
           if best else "无足够数据给出建议")

    return {
        'base_time': f"{hour:02d}:{minute:02d}",
        'scan_range': f"±{scan_range_minutes}分钟",
        'events_count': len(events),
        'max_possible_score': max_possible,
        'results': top_results,
        'recommendation': rec,
    }


if __name__ == '__main__':
    import sys
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    # 测试：样本盘，提供3个事件（测试用，不是真实事件）
    events = [
        {'type': 'exam_pass', 'year': 2022},   # 高考/考试
        {'type': 'job_start', 'year': 2024},    # 开始工作/实习
        {'type': 'relocation', 'year': 2021},   # 搬家/上大学
    ]
    print('正在扫描出生时间（±30分钟）...')
    r = auto_rectify(2005, 12, 14, 10, 28, 31.2304, 121.4737, 'Asia/Shanghai',
                     events, scan_range_minutes=30, top_n=3)
    print(f"事件数: {r['events_count']}，最高可能分: {r['max_possible_score']}")
    for i, res in enumerate(r['results'], 1):
        print(f"#{i} 时间={res['time']} delta={res['delta_min']:+d}min "
              f"分={res['score']}/{res['max_score']} ({res['pct']}%) {res['confidence']}")
        for ek, ev in res['event_scores'].items():
            print(f"   {ek}: {ev['score']}分 MD={ev['md']} AD={ev['ad']}")
    print('建议:', r['recommendation'])
