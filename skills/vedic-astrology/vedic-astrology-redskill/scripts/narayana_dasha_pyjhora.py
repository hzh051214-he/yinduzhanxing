"""
narayana_dasha_pyjhora — Narayana Dasha PyJHora 包装
=====================================================
Jaimini rasi/sign dasha system. Complements Vimsottari (psychological layer)
with environmental activation layer.

对外接口：
    calculate_narayana_dasha(year, month, day, hour, minute, lat, lon, tz_offset)

返回：
    {
        'dashas': [
            {
                'sign_idx': int,      # 0-11
                'sign': str,          # 'Aries' 等
                'start': 'YYYY-MM',
                'end': 'YYYY-MM',
                'years': float,
                'is_current': bool,
                'antardashas': [...],  # 仅 is_current=True 的条目包含此键
            }, ...
        ],
        'current_sign': str,
        'current_start': str,
        'current_end': str,
        'current_ad_sign': str,
        'current_ad_start': str,
        'current_ad_end': str,
    }
"""
from datetime import date, timedelta

from _pyjhora_base import (
    build_jd_place, SIGNS, _silence_stdout,
)


def _add_years_to_date(y, m, d, h_float, duration_years):
    """从给定日期 + h_float（小时浮点）加上 duration_years * 365.25 天，返回 date。"""
    start = date(int(y), int(m), int(d))
    delta_days = duration_years * 365.25
    end = start + timedelta(days=delta_days)
    return end


def _ymd(d):
    """date → 'YYYY-MM-DD'"""
    return d.strftime('%Y-%m-%d')


def _ym(d):
    """date → 'YYYY-MM'"""
    return d.strftime('%Y-%m')


def _parse_antardasha_level2(raw2, main_sign_idx, today):
    """
    从 level=2 的原始数据中过滤出属于 main_sign_idx 的子周期。

    raw2: list of ((md_sign_idx, ad_sign_idx), (y, m, d, h), duration_years)
    main_sign_idx: int, 当前主周期的星座索引 (0-11)

    返回：
        list of {'sign': str, 'sign_idx': int, 'start': 'YYYY-MM-DD',
                 'end': 'YYYY-MM-DD', 'is_current': bool}
    """
    sub_periods = []
    for entry in raw2:
        sign_tuple, start_tuple, duration_years = entry
        # level=2 returns (md_sign_idx, ad_sign_idx) as a tuple
        md_idx = int(sign_tuple[0])
        if md_idx != main_sign_idx:
            continue
        ad_idx = int(sign_tuple[1])
        sy, sm, sd, sh = start_tuple[0], start_tuple[1], start_tuple[2], start_tuple[3]
        start_date = date(int(sy), int(sm), int(sd))
        end_date = _add_years_to_date(sy, sm, sd, sh, duration_years)
        is_current = (start_date <= today < end_date)
        sub_periods.append({
            'sign_idx': ad_idx,
            'sign': SIGNS[ad_idx],
            'start': _ymd(start_date),
            'end': _ymd(end_date),
            'is_current': is_current,
        })
    return sub_periods


def calculate_narayana_dasha(year, month, day, hour, minute, lat, lon, tz_offset):
    """Returns Narayana Dasha periods (Jaimini rasi/sign dasha system).
    Complements Vimsottari (psychological layer) with environmental activation layer.
    Returns same structure as chara_dasha but using narayana system.
    Includes antardasha (sub-period) for the current main period.
    """
    jd, place = build_jd_place(year, month, day, hour, minute, lat, lon, tz_offset)

    with _silence_stdout():
        from jhora.horoscope.dhasa.raasi import narayana
        result = narayana.narayana_dhasa_for_rasi_chart(
            (year, month, day), (hour, minute, 0), place, dhasa_level_index=1
        )

    today = date.today()
    dashas = []
    current_sign = None
    current_start = None
    current_end = None
    current_main_sign_idx = None

    for entry in result:
        # narayana returns (sign_idx_int, (y, m, d, h_float), duration_years)
        sign_raw, start_tuple, duration_years = entry
        # handle both plain int and single-element tuple forms
        sign_idx = int(sign_raw[0]) if isinstance(sign_raw, (tuple, list)) else int(sign_raw)
        sy, sm, sd, sh = start_tuple[0], start_tuple[1], start_tuple[2], start_tuple[3]

        start_date = date(int(sy), int(sm), int(sd))
        end_date = _add_years_to_date(sy, sm, sd, sh, duration_years)

        is_current = (start_date <= today < end_date)

        dasha_entry = {
            'sign_idx': sign_idx,
            'sign': SIGNS[sign_idx],
            'start': _ym(start_date),
            'end': _ym(end_date),
            'years': round(float(duration_years), 4),
            'is_current': is_current,
        }
        dashas.append(dasha_entry)

        if is_current:
            current_sign = SIGNS[sign_idx]
            current_start = _ym(start_date)
            current_end = _ym(end_date)
            current_main_sign_idx = sign_idx

    # 计算当前主周期的子周期 (antardasha)
    current_ad_sign = None
    current_ad_start = None
    current_ad_end = None

    if current_main_sign_idx is not None:
        with _silence_stdout():
            from jhora.horoscope.dhasa.raasi import narayana
            raw2 = narayana.narayana_dhasa_for_rasi_chart(
                (year, month, day), (hour, minute, 0), place, dhasa_level_index=2
            )
        antardashas = _parse_antardasha_level2(raw2, current_main_sign_idx, today)

        # 将 antardashas 附加到当前主周期条目
        for dasha_entry in dashas:
            if dasha_entry['is_current']:
                dasha_entry['antardashas'] = antardashas
                break

        # 找到当前子周期
        for ad in antardashas:
            if ad['is_current']:
                current_ad_sign = ad['sign']
                current_ad_start = ad['start']
                current_ad_end = ad['end']
                break

    return {
        'dashas': dashas,
        'current_sign': current_sign,
        'current_start': current_start,
        'current_end': current_end,
        'current_ad_sign': current_ad_sign,
        'current_ad_start': current_ad_start,
        'current_ad_end': current_ad_end,
    }


if __name__ == '__main__':
    args = (2005, 12, 14, 10, 28, 31.2304, 121.4737, 8.0)
    r = calculate_narayana_dasha(*args)
    print('Current Dasha:', r['current_sign'], r['current_start'], '→', r['current_end'])
    print('Current Antardasha:', r['current_ad_sign'], r['current_ad_start'], '→', r['current_ad_end'])
    print('All Dashas:')
    for d in r['dashas']:
        marker = ' ◀ CURRENT' if d['is_current'] else ''
        print(f"  {d['sign']:<12} {d['start']} → {d['end']}  ({d['years']} yrs){marker}")
        if d['is_current'] and 'antardashas' in d:
            for ad in d['antardashas']:
                ad_marker = ' ◀ CURRENT AD' if ad['is_current'] else ''
                print(f"    {ad['sign']:<12} {ad['start']} → {ad['end']}{ad_marker}")
