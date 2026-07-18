"""multi_ayanamsa.py — 多 Ayanamsa 交叉分析

在主用 Lahiri 的基础上，额外计算 Raman 和 KP 两种 Ayanamsa 下的行星星座，
标注哪些行星在三套体系中落座不同（"Ayanamsa 敏感"）。

D60（Shashtiamsa）对 Ayanamsa 最敏感：1° 差异即可换宫。
本模块重点标注 D1/D9/D60 在三套体系下的差异。

输出不修改主 chart 的 Lahiri 结论；仅提供"交叉参考"和"敏感度警告"。
"""
import swisseph as swe
from datetime import datetime
import pytz

SIGNS = ['Aries','Taurus','Gemini','Cancer','Leo','Virgo',
         'Libra','Scorpio','Sagittarius','Capricorn','Aquarius','Pisces']

AYANAMSA_MODES = {
    'Lahiri': swe.SIDM_LAHIRI,
    'Raman':  swe.SIDM_RAMAN,
    'KP':     swe.SIDM_KRISHNAMURTI,
}

PLANETS_SWE = {
    'Sun': swe.SUN, 'Moon': swe.MOON, 'Mars': swe.MARS,
    'Mercury': swe.MERCURY, 'Jupiter': swe.JUPITER,
    'Venus': swe.VENUS, 'Saturn': swe.SATURN
}


def _to_jd(year, month, day, hour, minute, tz_str):
    tz = pytz.timezone(tz_str)
    local_dt = tz.localize(datetime(year, month, day, hour, minute))
    utc_dt = local_dt.astimezone(pytz.utc)
    ut_hour = utc_dt.hour + utc_dt.minute/60.0 + utc_dt.second/3600.0
    return swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, ut_hour)


def _calc_sign(jd, planet_id, ayan_mode):
    """计算指定 Ayanamsa 下行星的黄道度和星座。"""
    swe.set_sid_mode(ayan_mode)
    flags = swe.FLG_SIDEREAL | swe.FLG_SPEED
    result = swe.calc_ut(jd, planet_id, flags)
    lon = result[0][0]
    return int(lon / 30), lon


def _calc_lagna(jd, lat, lon_deg, ayan_mode):
    swe.set_sid_mode(ayan_mode)
    flags = swe.FLG_SIDEREAL
    cusps, ascmc = swe.houses_ex(jd, lat, lon_deg, b'W', flags)
    asc_lon = ascmc[0]
    return int(asc_lon / 30), asc_lon


def _calc_navamsha_sign(longitude):
    """D9 星座（与 engine 公式完全相同）。"""
    nav_part = int((longitude % 30) / (30/9))
    sign_idx = int(longitude / 30)
    element_start = [0, 9, 6, 3]
    element = sign_idx % 4
    return (element_start[element] + nav_part) % 12


def _calc_d60_sign(longitude):
    """D60 星座（每星座60等分，每份 0.5°）。
    奇数星座：从 Aries 顺序数 part；偶数星座：从 Libra 顺序数 part。
    """
    part = int((longitude % 30) / 0.5)  # 0-59
    sign_idx = int(longitude / 30)
    if sign_idx % 2 == 0:   # 奇数星座（0-indexed 偶数）
        return (sign_idx + part // 5) % 12
    else:
        return (sign_idx + 6 + part // 5) % 12


def calculate_multi_ayanamsa(year, month, day, hour, minute,
                              lat, lon, tz_str='Asia/Shanghai'):
    """三套 Ayanamsa (Lahiri / Raman / KP) 交叉分析。

    Returns:
        {
          'ayanamsa_values': {'Lahiri': float, 'Raman': float, 'KP': float},
          'differences': {'Lahiri_vs_Raman': float, 'Lahiri_vs_KP': float},
          'planet_comparison': {
              planet_name: {
                  'Lahiri': sign_name,
                  'Raman':  sign_name,
                  'KP':     sign_name,
                  'sensitive': bool,   # True if any system disagrees
              }
          },
          'lagna_comparison': {'Lahiri': sign_name, 'Raman': ..., 'KP': ..., 'sensitive': bool},
          'd9_comparison': {planet: {'Lahiri': sign, 'Raman': sign, 'KP': sign, 'sensitive': bool}},
          'd60_comparison': {planet: {'Lahiri': sign, 'Raman': sign, 'KP': sign, 'sensitive': bool}},
          'sensitive_summary': [str],   # 有差异的简要说明
        }
    """
    jd = _to_jd(year, month, day, hour, minute, tz_str)

    # Ayanamsa 值
    ayan_vals = {}
    for name, mode in AYANAMSA_MODES.items():
        swe.set_sid_mode(mode)
        ayan_vals[name] = round(swe.get_ayanamsa_ut(jd), 6)

    # 行星 D1 星座
    planet_comp = {}
    d9_comp = {}
    d60_comp = {}
    for pname, pid in PLANETS_SWE.items():
        row = {}
        d9_row = {}
        d60_row = {}
        for ayan_name, mode in AYANAMSA_MODES.items():
            sidx, lon_val = _calc_sign(jd, pid, mode)
            row[ayan_name] = SIGNS[sidx]
            d9_row[ayan_name] = SIGNS[_calc_navamsha_sign(lon_val)]
            d60_row[ayan_name] = SIGNS[_calc_d60_sign(lon_val)]
        row['sensitive'] = len(set(row[n] for n in AYANAMSA_MODES)) > 1
        d9_row['sensitive'] = len(set(d9_row[n] for n in AYANAMSA_MODES)) > 1
        d60_row['sensitive'] = len(set(d60_row[n] for n in AYANAMSA_MODES)) > 1
        planet_comp[pname] = row
        d9_comp[pname] = d9_row
        d60_comp[pname] = d60_row

    # Rahu（Mean Node）
    for ayan_name, mode in AYANAMSA_MODES.items():
        swe.set_sid_mode(mode)
        flags = swe.FLG_SIDEREAL | swe.FLG_SPEED
        result = swe.calc_ut(jd, swe.MEAN_NODE, flags)
        rahu_lon = result[0][0]
        sidx = int(rahu_lon / 30)
        planet_comp.setdefault('Rahu', {})[ayan_name] = SIGNS[sidx]
        d9_comp.setdefault('Rahu', {})[ayan_name] = SIGNS[_calc_navamsha_sign(rahu_lon)]
        d60_comp.setdefault('Rahu', {})[ayan_name] = SIGNS[_calc_d60_sign(rahu_lon)]
        ketu_lon = (rahu_lon + 180) % 360
        ketu_sidx = int(ketu_lon / 30)
        planet_comp.setdefault('Ketu', {})[ayan_name] = SIGNS[ketu_sidx]
        d9_comp.setdefault('Ketu', {})[ayan_name] = SIGNS[_calc_navamsha_sign(ketu_lon)]
        d60_comp.setdefault('Ketu', {})[ayan_name] = SIGNS[_calc_d60_sign(ketu_lon)]
    planet_comp['Rahu']['sensitive'] = len(set(planet_comp['Rahu'][n] for n in AYANAMSA_MODES)) > 1
    planet_comp['Ketu']['sensitive'] = len(set(planet_comp['Ketu'][n] for n in AYANAMSA_MODES)) > 1
    d9_comp['Rahu']['sensitive'] = len(set(d9_comp['Rahu'][n] for n in AYANAMSA_MODES)) > 1
    d9_comp['Ketu']['sensitive'] = len(set(d9_comp['Ketu'][n] for n in AYANAMSA_MODES)) > 1
    d60_comp['Rahu']['sensitive'] = len(set(d60_comp['Rahu'][n] for n in AYANAMSA_MODES)) > 1
    d60_comp['Ketu']['sensitive'] = len(set(d60_comp['Ketu'][n] for n in AYANAMSA_MODES)) > 1

    # Lagna
    lagna_row = {}
    for ayan_name, mode in AYANAMSA_MODES.items():
        sidx, _ = _calc_lagna(jd, lat, lon, mode)
        lagna_row[ayan_name] = SIGNS[sidx]
    lagna_row['sensitive'] = len(set(lagna_row[n] for n in AYANAMSA_MODES)) > 1

    # 敏感总结
    summary = []
    if lagna_row['sensitive']:
        summary.append(f"Lagna: {lagna_row}")
    for p, row in planet_comp.items():
        if row['sensitive']:
            summary.append(f"D1 {p}: {row['Lahiri']} vs {row['Raman']}(Raman) vs {row['KP']}(KP)")
    for p, row in d9_comp.items():
        if row['sensitive']:
            summary.append(f"D9 {p}: {row['Lahiri']} vs {row['Raman']}(Raman) vs {row['KP']}(KP)")
    for p, row in d60_comp.items():
        if row['sensitive']:
            summary.append(f"D60 {p}: {row['Lahiri']} vs {row['Raman']}(Raman) vs {row['KP']}(KP)")

    # 恢复 Lahiri（不影响 engine 后续调用）
    swe.set_sid_mode(swe.SIDM_LAHIRI)

    return {
        'ayanamsa_values': ayan_vals,
        'differences': {
            'Lahiri_vs_Raman': round(ayan_vals['Lahiri'] - ayan_vals['Raman'], 4),
            'Lahiri_vs_KP':    round(ayan_vals['Lahiri'] - ayan_vals['KP'], 4),
        },
        'planet_comparison': planet_comp,
        'lagna_comparison': lagna_row,
        'd9_comparison': d9_comp,
        'd60_comparison': d60_comp,
        'sensitive_summary': summary,
    }


if __name__ == '__main__':
    import sys
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    r = calculate_multi_ayanamsa(2005,12,14,10,28,31.2304,121.4737)
    print('Ayanamsa 值:', r['ayanamsa_values'])
    print('差值:', r['differences'])
    print(f"Lagna: {'⚠️敏感' if r['lagna_comparison']['sensitive'] else '一致'} "
          f"Lahiri={r['lagna_comparison']['Lahiri']}")
    d1_sens = [p for p, v in r['planet_comparison'].items() if v['sensitive']]
    d9_sens = [p for p, v in r['d9_comparison'].items() if v['sensitive']]
    d60_sens = [p for p, v in r['d60_comparison'].items() if v['sensitive']]
    print(f"D1 敏感行星({len(d1_sens)}):", d1_sens)
    print(f"D9 敏感行星({len(d9_sens)}):", d9_sens)
    print(f"D60 敏感行星({len(d60_sens)}):", d60_sens)
    print(f"总体敏感点: {len(r['sensitive_summary'])}处")
    for s in r['sensitive_summary'][:5]:
        print(' ', s)
    print('=== 完成 ✅ ===')
