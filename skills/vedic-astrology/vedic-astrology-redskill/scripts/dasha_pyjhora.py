"""
dasha_pyjhora — Vimsottari 大运（Mahadasha + Antardasha + Pratyantardasha）PyJHora 包装
=====================================================================
对外接口：
    calculate_dasha_fixed(year, month, day, hour, minute, lat, lon, tz_offset)
返回 9×9 结构的大运/小运，且对当前小运展开第三层 Pratyantardasha（三级运）。

底层调用 PyJHora 4.8.6 vimsottari.get_vimsottari_dhasa_bhukthi。
"""
from datetime import datetime, timedelta

from _pyjhora_base import (
    vimsottari, const,
    build_jd_place, PLANET_ID_TO_NAME, _silence_stdout,
)

# PyJHora 内部星序（与 PLANET_ID_TO_NAME 一致）
_PY_ORDER = ['Sun','Moon','Mars','Mercury','Jupiter','Venus','Saturn','Rahu','Ketu']

# Vimsottari 各大运标准年数
_DASHA_YEARS = {
    'Ketu': 7, 'Venus': 20, 'Sun': 6, 'Moon': 10, 'Mars': 7,
    'Rahu': 18, 'Jupiter': 16, 'Saturn': 19, 'Mercury': 17,
}


def _to_dt(date_tuple):
    """PyJHora 日期元组 (year, month, day, fractional_hour) → datetime。"""
    y, m, d = int(date_tuple[0]), int(date_tuple[1]), int(date_tuple[2])
    frac_h = float(date_tuple[3]) if len(date_tuple) > 3 else 0.0
    return datetime(y, m, d) + timedelta(hours=frac_h)


def _calc_pratyantardashas(jd, place, md_name, ad_name):
    """计算指定大运+小运下的三级运（Pratyantardasha）列表。
    只在 compute_verdicts 之前被调用，数据量小（当前小运的81个条目中取9个）。
    """
    try:
        with _silence_stdout():
            _bal, entries3 = vimsottari.get_vimsottari_dhasa_bhukthi(
                jd, place, dhasa_level_index=3)
        md_idx = _PY_ORDER.index(md_name)
        ad_idx = _PY_ORDER.index(ad_name)
        now = datetime.now()
        prad = []
        for lords, date_tuple, years in entries3:
            if len(lords) < 3:
                continue
            if lords[0] != md_idx or lords[1] != ad_idx:
                continue
            pd_name = _PY_ORDER[lords[2]]
            start_dt = _to_dt(date_tuple)
            end_dt = start_dt + timedelta(days=float(years) * 365.25)
            prad.append({
                'planet': pd_name,
                'start': start_dt.strftime('%Y-%m-%d'),
                'end': end_dt.strftime('%Y-%m-%d'),
                'is_current': start_dt <= now < end_dt,
            })
        return prad
    except Exception:
        return []


def calculate_dasha_fixed(year, month, day, hour, minute, lat, lon, tz_offset,
                          reference_date=None):
    """reference_date: datetime | None. None → datetime.now() for is_current checks."""
    jd, place = build_jd_place(year, month, day, hour, minute, lat, lon, tz_offset)

    with _silence_stdout():
        _balance, entries = vimsottari.get_vimsottari_dhasa_bhukthi(
            jd, place, dhasa_level_index=2
        )

    parsed = []
    for lords, date_tuple, years in entries:
        maha_id, bhukti_id = lords[0], lords[1]
        parsed.append((maha_id, bhukti_id, _to_dt(date_tuple), float(years)))

    # reference_date 参数化：None → datetime.now()，否则用指定日期（转为 naive）
    _ref = reference_date if reference_date is not None else datetime.now()
    now = _ref.replace(tzinfo=None) if hasattr(_ref, 'tzinfo') and _ref.tzinfo else _ref

    groups = []
    for maha_id, bhukti_id, dt, years in parsed:
        if not groups or groups[-1][0] != maha_id:
            groups.append((maha_id, []))
        groups[-1][1].append((bhukti_id, dt, years))

    dashas = []
    for gi, (maha_id, bhuktis) in enumerate(groups):
        maha_name = PLANET_ID_TO_NAME[maha_id]
        maha_start = bhuktis[0][1]
        if gi + 1 < len(groups):
            maha_end = groups[gi + 1][1][0][1]
        else:
            maha_end = maha_start + timedelta(days=_DASHA_YEARS[maha_name] * 365.25)

        is_current_md = maha_start <= now < maha_end

        antardashas = []
        for bi, (bhukti_id, b_start, _b_years) in enumerate(bhuktis):
            if bi + 1 < len(bhuktis):
                b_end = bhuktis[bi + 1][1]
            else:
                b_end = maha_end
            is_current_ad = b_start <= now < b_end
            ad_entry = {
                'planet': PLANET_ID_TO_NAME[bhukti_id],
                'start': b_start.strftime('%Y-%m-%d'),
                'end': b_end.strftime('%Y-%m-%d'),
                'is_current': is_current_ad,
            }
            # 三级运：仅对当前大运的当前小运展开（数据量控制）
            if is_current_md and is_current_ad:
                ad_entry['pratyantardashas'] = _calc_pratyantardashas(
                    jd, place, maha_name, PLANET_ID_TO_NAME[bhukti_id])
            antardashas.append(ad_entry)

        dashas.append({
            'planet': maha_name,
            'start': maha_start.strftime('%Y-%m'),
            'end': maha_end.strftime('%Y-%m'),
            'years': round((maha_end - maha_start).days / 365.25, 1),
            'is_current': is_current_md,
            'antardashas': antardashas,
        })

    return dashas


if __name__ == '__main__':
    ds = calculate_dasha_fixed(2002, 12, 11, 20, 47, 25.4333, 119.0, 8.0)
    print(f"共 {len(ds)} 段大运")
    for d in ds:
        mark = '→当前' if d['is_current'] else '      '
        print(f"{mark} {d['planet']:<9} {d['start']} ~ {d['end']}  ({d['years']}yr)  "
              f"小运 {len(d['antardashas'])} 个")
        if d['is_current']:
            for ad in d['antardashas']:
                m = ' ←' if ad['is_current'] else ''
                print(f"        {d['planet']}-{ad['planet']:<8} {ad['start']} ~ {ad['end']}{m}")
