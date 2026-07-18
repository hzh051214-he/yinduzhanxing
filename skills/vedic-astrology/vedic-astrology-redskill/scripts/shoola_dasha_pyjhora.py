"""
shoola_dasha_pyjhora — Shoola Dasha PyJHora 包装
=================================================
对外接口：
    calculate_shoola_dasha(year, month, day, hour, minute, lat, lon, tz_offset)

返回：
    {
        'dashas': [
            {
                'sign_idx': int,        # 0-11
                'sign': str,            # 'Aries' 等
                'start': 'YYYY-MM',
                'end': 'YYYY-MM',
                'years': float,
                'is_current': bool,
                'quality': str,         # 'harsha' / 'sama' / 'shoola'
                'quality_cn': str,      # '顺境' / '平稳' / '逆境/考验'
            }, ...
        ],
        'current_sign': str,
        'current_quality': str,
    }

品质映射（传统规则，基于星座组别）：
  活动星座 1,4,7,10 (Aries/Cancer/Libra/Capricorn)  → 'harsha'  (顺境)
  固定星座 2,5,8,11 (Taurus/Leo/Scorpio/Aquarius)   → 'sama'    (平稳)
  双体星座 3,6,9,12 (Gemini/Virgo/Sagittarius/Pisces)→ 'shoola'  (逆境/考验)
注：sign_idx 0-indexed，上面序号是 1-indexed 传统数字。
"""
from datetime import date, timedelta

from _pyjhora_base import (
    build_jd_place, SIGNS, _silence_stdout,
)

# ── 品质映射 ──
# sign_idx 0-indexed: Aries=0, Taurus=1, ..., Pisces=11
# 活动(movable): 0,3,6,9  → harsha
# 固定(fixed):   1,4,7,10 → sama
# 双体(dual):    2,5,8,11 → shoola
_QUALITY_MAP = {}
for _i in range(12):
    _mod = _i % 3
    if _mod == 0:
        _QUALITY_MAP[_i] = 'harsha'
    elif _mod == 1:
        _QUALITY_MAP[_i] = 'sama'
    else:
        _QUALITY_MAP[_i] = 'shoola'

_QUALITY_CN = {
    'harsha': '顺境',
    'sama':   '平稳',
    'shoola': '逆境/考验',
}


def _add_years_to_date(y, m, d, h_float, duration_years):
    """从给定日期 + h_float（小时浮点）加上 duration_years * 365.25 天，返回 date。"""
    start = date(int(y), int(m), int(d))
    delta_days = duration_years * 365.25
    end = start + timedelta(days=delta_days)
    return end


def _ym(d):
    """date → 'YYYY-MM'"""
    return d.strftime('%Y-%m')


def calculate_shoola_dasha(year, month, day, hour, minute, lat, lon, tz_offset):
    """返回 Shoola Dasha 周期列表（逆境/挑战周期分析）。
    每个周期带有 'quality' 标签：harsha/sama/shoola（顺境/平稳/逆境考验）。
    """
    jd, place = build_jd_place(year, month, day, hour, minute, lat, lon, tz_offset)

    with _silence_stdout():
        from jhora.horoscope.dhasa.raasi import shoola
        result = shoola.get_dhasa_bhukthi(
            (year, month, day), (hour, minute, 0), place, dhasa_level_index=1
        )

    today = date.today()
    dashas = []
    current_sign = None
    current_quality = None

    for entry in result:
        # entry: ((sign_idx,), (y, m, d, h_float), duration_years)
        sign_tuple, start_tuple, duration_years = entry
        sign_idx = int(sign_tuple[0])
        sy, sm, sd, sh = start_tuple[0], start_tuple[1], start_tuple[2], start_tuple[3]

        start_date = date(int(sy), int(sm), int(sd))
        end_date = _add_years_to_date(sy, sm, sd, sh, duration_years)

        is_current = (start_date <= today < end_date)

        quality = _QUALITY_MAP[sign_idx]
        quality_cn = _QUALITY_CN[quality]

        dasha_entry = {
            'sign_idx': sign_idx,
            'sign': SIGNS[sign_idx],
            'start': _ym(start_date),
            'end': _ym(end_date),
            'years': round(float(duration_years), 4),
            'is_current': is_current,
            'quality': quality,
            'quality_cn': quality_cn,
        }
        dashas.append(dasha_entry)

        if is_current:
            current_sign = SIGNS[sign_idx]
            current_quality = quality

    return {
        'dashas': dashas,
        'current_sign': current_sign,
        'current_quality': current_quality,
    }


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    args = (2005, 12, 14, 10, 28, 31.2304, 121.4737, 8.0)
    r = calculate_shoola_dasha(*args)
    print('Current Dasha:', r['current_sign'], '|', r['current_quality'])
    print('All Dashas:')
    for d in r['dashas']:
        marker = ' << CURRENT' if d['is_current'] else ''
        print(
            f"  {d['sign']:<14} {d['start']} -> {d['end']}"
            f"  ({d['years']} yrs)  [{d['quality']} / {d['quality_cn']}]{marker}"
        )
