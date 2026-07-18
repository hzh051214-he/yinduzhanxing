"""
kalachakra_pyjhora — Kalachakra & Yogardha Dasha PyJHora 包装
=============================================================
对外接口：
    calculate_kalachakra_dasha(year, month, day, hour, minute, lat, lon, tz_offset)
    calculate_yogardha_dasha(year, month, day, hour, minute, lat, lon, tz_offset)

返回：
    {
        'dashas': [
            {
                'sign_or_planet': str,
                'start': 'YYYY-MM',
                'end': 'YYYY-MM',
                'years': float,
                'is_current': bool,
            }, ...
        ],
        'current': str,
        'current_start': str,
        'current_end': str,
    }
"""
from datetime import date, timedelta

from _pyjhora_base import (
    build_jd_place, PLANET_ID_TO_NAME, _silence_stdout,
)


# ── 辅助 ──────────────────────────────────────────────────────────────────────

def _to_dt(y, m, d, h_float):
    """把 PyJHora 返回的 (y, m, d, h_float) 转成 date 对象。"""
    return date(int(y), int(m), int(d))


def _add_years(start_date, duration_years):
    """start_date + duration_years * 365.25 天 → end date。"""
    return start_date + timedelta(days=duration_years * 365.25)


def _ym(d):
    """date → 'YYYY-MM'"""
    return d.strftime('%Y-%m')


def _planet_name(idx):
    return PLANET_ID_TO_NAME.get(int(idx), f'P{idx}')


# ── Kalachakra Dasha ──────────────────────────────────────────────────────────

def calculate_kalachakra_dasha(year, month, day, hour, minute, lat, lon, tz_offset):
    """返回结构化 Kalachakra Dasha 周期列表（按主大运分组）。"""
    try:
        jd, place = build_jd_place(year, month, day, hour, minute, lat, lon, tz_offset)

        with _silence_stdout():
            from jhora.horoscope.dhasa.raasi import kalachakra
            raw = kalachakra.get_dhasa_bhukthi(
                (year, month, day), (hour, minute, 0), place, dhasa_level_index=2
            )

        today = date.today()
        dashas = []
        current = None
        current_start = None
        current_end = None

        # group by md_idx — collect grouped major periods
        # raw entry: ((md_idx, ad_idx), (y, m, d, h), years)
        # We accumulate sub-periods per md_idx to derive major dasha span.
        from collections import OrderedDict
        groups = OrderedDict()
        for entry in raw:
            idx_tuple, start_tuple, duration_years = entry
            md_idx = idx_tuple[0]
            if md_idx not in groups:
                groups[md_idx] = []
            groups[md_idx].append((start_tuple, duration_years))

        for md_idx, entries in groups.items():
            # major dasha starts at first sub-period start
            first_start_tuple = entries[0][0]
            start_date = _to_dt(*first_start_tuple)

            # major dasha total years = sum of sub-period years
            total_years = sum(e[1] for e in entries)
            end_date = _add_years(start_date, total_years)

            is_current = (start_date <= today < end_date)

            name = _planet_name(md_idx)
            dasha_entry = {
                'sign_or_planet': name,
                'start': _ym(start_date),
                'end': _ym(end_date),
                'years': round(float(total_years), 4),
                'is_current': is_current,
            }
            dashas.append(dasha_entry)

            if is_current:
                current = name
                current_start = _ym(start_date)
                current_end = _ym(end_date)

        return {
            'dashas': dashas,
            'current': current,
            'current_sign': current,  # alias for consistency
            'current_start': current_start,
            'current_end': current_end,
        }

    except Exception as exc:
        return {'error': str(exc), 'dashas': [], 'current': None,
                'current_sign': None, 'current_start': None, 'current_end': None}


# ── Yogardha Dasha ────────────────────────────────────────────────────────────

def calculate_yogardha_dasha(year, month, day, hour, minute, lat, lon, tz_offset):
    """返回结构化 Yogardha Dasha 周期列表（按主大运分组）。"""
    try:
        jd, place = build_jd_place(year, month, day, hour, minute, lat, lon, tz_offset)

        with _silence_stdout():
            from jhora.horoscope.dhasa.raasi import yogardha
            raw = yogardha.get_dhasa_antardhasa(
                (year, month, day), (hour, minute, 0), place
            )

        today = date.today()
        dashas = []
        current = None
        current_start = None
        current_end = None

        from collections import OrderedDict
        groups = OrderedDict()
        for entry in raw:
            idx_tuple, start_tuple, duration_years = entry
            md_idx = idx_tuple[0]
            if md_idx not in groups:
                groups[md_idx] = []
            groups[md_idx].append((start_tuple, duration_years))

        for md_idx, entries in groups.items():
            first_start_tuple = entries[0][0]
            start_date = _to_dt(*first_start_tuple)

            total_years = sum(e[1] for e in entries)
            end_date = _add_years(start_date, total_years)

            is_current = (start_date <= today < end_date)

            name = _planet_name(md_idx)
            dasha_entry = {
                'sign_or_planet': name,
                'start': _ym(start_date),
                'end': _ym(end_date),
                'years': round(float(total_years), 4),
                'is_current': is_current,
            }
            dashas.append(dasha_entry)

            if is_current:
                current = name
                current_start = _ym(start_date)
                current_end = _ym(end_date)

        return {
            'dashas': dashas,
            'current': current,
            'current_sign': current,  # alias for consistency
            'current_start': current_start,
            'current_end': current_end,
        }

    except Exception as exc:
        return {'error': str(exc), 'dashas': [], 'current': None,
                'current_sign': None, 'current_start': None, 'current_end': None}


# ── CLI 自测 ──────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    args = (2005, 12, 14, 10, 28, 31.2304, 121.4737, 8.0)

    kc = calculate_kalachakra_dasha(*args)
    print('=== Kalachakra Dasha ===')
    if 'error' in kc:
        print('ERROR:', kc['error'])
    else:
        print('Current:', kc['current'], kc['current_start'], '->', kc['current_end'])
        for d in kc['dashas']:
            marker = ' <-- CURRENT' if d['is_current'] else ''
            print(f"  {d['sign_or_planet']:<12} {d['start']} -> {d['end']}  ({d['years']} yrs){marker}")

    yo = calculate_yogardha_dasha(*args)
    print('\n=== Yogardha Dasha ===')
    if 'error' in yo:
        print('ERROR:', yo['error'])
    else:
        print('Current:', yo['current'], yo['current_start'], '->', yo['current_end'])
        for d in yo['dashas']:
            marker = ' <-- CURRENT' if d['is_current'] else ''
            print(f"  {d['sign_or_planet']:<12} {d['start']} -> {d['end']}  ({d['years']} yrs){marker}")
