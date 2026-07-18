"""
health_markers_pyjhora — 22nd Drekkana + 64th Navamsha 健康敏感点
================================================================
D11（深度转化盘）的配套工具：两个关键的"危机触发器"。

22nd Drekkana（第22个三分之一宫）：
  从出生月亮星座数第22个Drekkana（D3）分段，
  揭示健康的先天脆弱点。当过运行星经过此点时，
  是重大健康危机的高风险窗口之一。

64th Navamsha（第64个九分之一宫）：
  从出生月亮星座数第64个Navamsha（D9）分段，
  指向危机的主要触发器。精确到约0.33度的敏感点。

这两个数据点不做独立分析，而是作为Gochara过运的"热点坐标"：
当过运行星合相或接近这两个点时，标注为高风险过运。

实现说明
--------
PyJHora 的 charts.get_22nd_drekkana() / get_64th_navamsa() 返回
{planet_id: (sign_idx, lord_id)}，只给出敏感点所在星座（星座级）。
本模块取"月亮"（planet id=1）对应的敏感点星座，并从月亮在 D3/D9
分盘内的精确度数（longitude-in-sign）补齐 degree_in_sign，得到
可用于过运合相判断的绝对黄经点：
    22nd Drekkana sign == (月亮 D3 星座 + 7) % 12
    64th Navamsha sign == (月亮 D9 星座 + 3) % 12
degree_in_sign 沿用月亮在该分盘内的度数，从而把星座级敏感点
细化为精确黄经坐标供 ±3° 过运合相扫描。
"""
import datetime

import swisseph as swe

from _pyjhora_base import (
    charts, drik,
    build_jd_place, _silence_stdout,
)

PLANET_ID_TO_NAME = {
    0: 'Sun', 1: 'Moon', 2: 'Mars', 3: 'Mercury',
    4: 'Jupiter', 5: 'Venus', 6: 'Saturn', 7: 'Rahu', 8: 'Ketu',
}
SIGNS = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
         'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces']

# 凶星：过运接近敏感点时权重更高
_MALEFICS = {'Saturn', 'Mars', 'Rahu', 'Ketu'}

# 过运用 swisseph 天体号（Rahu 用平均交点 Mean Node，与 _pyjhora_base 一致）
_TRANSIT_SWE = {
    'Sun': swe.SUN, 'Moon': swe.MOON, 'Mars': swe.MARS,
    'Mercury': swe.MERCURY, 'Jupiter': swe.JUPITER, 'Venus': swe.VENUS,
    'Saturn': swe.SATURN, 'Rahu': swe.MEAN_NODE,  # Ketu = Rahu + 180
}

_ORB = 3.0  # ±3 度合相容许度


def _ang_sep(a, b):
    """两个黄经（度）之间的最短角距，0..180。"""
    d = abs((a - b) % 360.0)
    return d if d <= 180.0 else 360.0 - d


def _marker_from_moon(get_fn, div_chart):
    """取月亮（id=1）的敏感点星座 + 月亮在该分盘内的精确度数。

    @param get_fn: charts.get_22nd_drekkana 或 charts.get_64th_navamsa
    @param div_chart: 对应的 D3 / D9 分盘（[[pid,[sidx,long]],...]）
    @return: (marker_sign_idx, degree_in_sign, div_chart_dict)
    """
    with _silence_stdout():
        marker = get_fn(div_chart)  # {pid: (sign_idx, lord_id)}

    # 把分盘整理成 {pid: (sign_idx, long_in_sign)}
    dchart = {}
    for entry in div_chart:
        pid, pos = entry[0], entry[1]
        dchart[pid] = (int(pos[0]), float(pos[1]))

    marker_sign = int(marker[1][0])   # 月亮敏感点星座
    moon_deg = dchart[1][1]           # 月亮在该分盘内的度数
    return marker_sign, moon_deg, dchart


def _planets_in_sign(dchart, sign_idx):
    """分盘中与敏感点同星座的行星名列表（不含 Lagna）。"""
    out = []
    for pid, (sidx, _) in dchart.items():
        if pid == 'L':
            continue
        name = PLANET_ID_TO_NAME.get(pid)
        if name and sidx == sign_idx:
            out.append(name)
    return out


def _current_transit_longitudes():
    """当前时刻（UTC now）9 大行星的 Lahiri 恒星黄经（度，0..360）。"""
    swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
    now = datetime.datetime.utcnow()
    ut_hour = now.hour + now.minute / 60.0 + now.second / 3600.0
    jd_ut = swe.julday(now.year, now.month, now.day, ut_hour)
    flag = swe.FLG_SWIEPH | swe.FLG_SIDEREAL

    lons = {}
    for name, body in _TRANSIT_SWE.items():
        res = swe.calc_ut(jd_ut, body, flag)
        lon = res[0][0] if isinstance(res[0], (list, tuple)) else res[0]
        lons[name] = lon % 360.0
    # Ketu 与 Rahu 对冲
    if 'Rahu' in lons:
        lons['Ketu'] = (lons['Rahu'] + 180.0) % 360.0
    return lons


def _assess_risk(near_d22, near_d64, transit_lons, d22_lon, d64_lon):
    """按规则评估风险等级。

    high  : 任一敏感点附近有 2+ 行星；或某凶星落在 ±1 度内
    medium: 任一敏感点附近有 1 行星
    low   : 无行星接近
    """
    near_all = set(near_d22) | set(near_d64)

    # 凶星 ±1 度内 → high
    for name in near_all:
        if name not in _MALEFICS:
            continue
        lon = transit_lons.get(name)
        if lon is None:
            continue
        if _ang_sep(lon, d22_lon) <= 1.0 or _ang_sep(lon, d64_lon) <= 1.0:
            return 'high'

    if len(near_d22) >= 2 or len(near_d64) >= 2:
        return 'high'
    if len(near_all) >= 1:
        return 'medium'
    return 'low'


def calculate_health_markers(year, month, day, hour, minute, lat, lon, tz_offset):
    """计算22nd Drekkana和64th Navamsha健康敏感点。

    Returns:
    {
      'd22_drekkana': {...}, 'd64_navamsha': {...},
      'current_transits_near_markers': {...}
    }
    """
    try:
        with _silence_stdout():
            drik.set_ayanamsa_mode('LAHIRI')
        jd, place = build_jd_place(year, month, day, hour, minute, lat, lon, tz_offset)

        with _silence_stdout():
            d3 = charts.divisional_chart(jd, place, divisional_chart_factor=3)
            d9 = charts.divisional_chart(jd, place, divisional_chart_factor=9)

        d22_sign, d22_deg, d3chart = _marker_from_moon(charts.get_22nd_drekkana, d3)
        d64_sign, d64_deg, d9chart = _marker_from_moon(charts.get_64th_navamsa, d9)

        d22_lon = d22_sign * 30.0 + d22_deg
        d64_lon = d64_sign * 30.0 + d64_deg

        d22_same = _planets_in_sign(d3chart, d22_sign)
        d64_same = _planets_in_sign(d9chart, d64_sign)

        # 当前过运接近度检查
        transit_lons = _current_transit_longitudes()
        near_d22, near_d64 = [], []
        for name, tlon in transit_lons.items():
            if _ang_sep(tlon, d22_lon) <= _ORB:
                near_d22.append(name)
            if _ang_sep(tlon, d64_lon) <= _ORB:
                near_d64.append(name)

        risk = _assess_risk(near_d22, near_d64, transit_lons, d22_lon, d64_lon)

        return {
            'd22_drekkana': {
                'sign': SIGNS[d22_sign],
                'sign_idx': d22_sign,
                'degree_in_sign': round(d22_deg, 4),
                'planets_in_same_sign': d22_same,
                'interpretation': (
                    f"22nd Drekkana（先天健康脆弱点）位于{SIGNS[d22_sign]}"
                    f"{d22_deg:.2f}°。过运行星经过此点时为重大健康危机的"
                    f"高风险窗口之一。"
                    + (f"D3同宫行星：{'、'.join(d22_same)}。" if d22_same else "")
                ),
            },
            'd64_navamsha': {
                'sign': SIGNS[d64_sign],
                'sign_idx': d64_sign,
                'degree_in_sign': round(d64_deg, 4),
                'planets_in_same_sign': d64_same,
                'interpretation': (
                    f"64th Navamsha（危机主要触发器）位于{SIGNS[d64_sign]}"
                    f"{d64_deg:.2f}°，敏感点精确至约0.33°。过运行星合相此点"
                    f"标记为高风险健康窗口。"
                    + (f"D9同宫行星：{'、'.join(d64_same)}。" if d64_same else "")
                ),
            },
            'current_transits_near_markers': {
                'near_d22': near_d22,
                'near_d64': near_d64,
                'risk_level': risk,
            },
        }
    except Exception as e:
        return {'error': f'{type(e).__name__}: {e}'}


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    r = calculate_health_markers(2005, 12, 14, 10, 28, 31.2304, 121.4737, 8.0)
    print('error?', r.get('error', 'none'))
    d22 = r.get('d22_drekkana', {})
    d64 = r.get('d64_navamsha', {})
    print('22nd Drekkana:', d22.get('sign'), d22.get('degree_in_sign', '?'))
    print('64th Navamsha:', d64.get('sign'), d64.get('degree_in_sign', '?'))
    tr = r.get('current_transits_near_markers', {})
    print('near d22:', tr.get('near_d22'))
    print('near d64:', tr.get('near_d64'))
    print('risk_level:', tr.get('risk_level'))
