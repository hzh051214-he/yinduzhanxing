"""
special_planets_pyjhora — 特殊行星状态 + 灾象检测
四个模块：
1. Mrityu Bhaga（死亡度数）— 行星在特定度数时功能严重受损
2. Pushkara Navamsha — D9 里的特殊吉位，行星在此大幅提升
3. Marana Karaka Sthana（MKS）— 行星落在"致命弱点宫"
4. Dosha 检测 — Kala Sarpa / Manglik / Ganda Moola
"""
from _pyjhora_base import (
    charts, drik, utils, const,
    build_jd_place, PLANET_ID_TO_NAME, SIGNS, _silence_stdout,
)
with _silence_stdout():
    from jhora.horoscope.chart.dosha import kala_sarpa, manglik, ganda_moola
    from jhora.panchanga.drik import Date


def _planet_ids_to_names(id_list):
    """把 planet id 列表（可能含 'L'）转换为英文名列表。"""
    result = []
    for item in id_list:
        if isinstance(item, int) and item in PLANET_ID_TO_NAME:
            result.append(PLANET_ID_TO_NAME[item])
        elif item == 'L' or item == const._ascendant_symbol:
            result.append('Lagna')
        else:
            result.append(str(item))
    return result


def _moon_nakshatra(rasi_chart):
    """从 rasi_chart 中提取月亮的星宿序号 0-26（0=Ashwini）。"""
    for entry in rasi_chart:
        if entry[0] == 1:  # Moon
            sign_idx = int(entry[1][0])
            long_in_sign = float(entry[1][1])
            abs_long = sign_idx * 30.0 + long_in_sign
            return int(abs_long / (360.0 / 27))
    return 0


def calculate_special_planets(year, month, day, hour, minute, lat, lon, tz_offset):
    """Returns special planetary conditions: Mrityu Bhaga, Pushkara, MKS, and Doshas.

    Parameters
    ----------
    year, month, day : int
    hour, minute     : int
    lat, lon         : float  — birth latitude / longitude
    tz_offset        : float  — UTC offset in hours (e.g. 5.5 for IST)

    Returns
    -------
    dict with keys:
        mrityu_bhaga        : list[str]  — planets at danger degrees
        pushkara_navamsha   : list[str]  — planets in Pushkara Navamsha
                             (index 0) and/or Pushkara Bhaga (index 1)
        marana_karaka_sthana: list[str]  — planets in MKS houses
        kala_sarpa          : bool       — Kala Sarpa dosha present
        manglik             : bool       — Manglik dosha present
        manglik_exceptions  : bool       — exceptions apply (only if manglik True)
        ganda_moola         : bool       — Moon in Ganda Moola nakshatra
    """
    try:
        jd, place = build_jd_place(year, month, day, hour, minute, lat, lon, tz_offset)

        with _silence_stdout():
            rasi_chart = charts.rasi_chart(jd, place)

        # house_to_planet_list needed by kala_sarpa
        with _silence_stdout():
            h2p_list = utils.get_house_planet_list_from_planet_positions(rasi_chart)

        # ── 1. Mrityu Bhaga ──────────────────────────────────────────────
        # API: charts.planets_in_mrityu_bhaga(dob, tob, place, planet_positions)
        # dob must be jhora Date namedtuple, not plain tuple
        try:
            dob = Date(year, month, day)
            tob = (hour, minute, 0)
            with _silence_stdout():
                mb_raw = charts.planets_in_mrityu_bhaga(dob, tob, place, rasi_chart)
            # returns list of planet ids (ints); may include 'L'
            if mb_raw is None:
                mb_list = []
            elif isinstance(mb_raw, (list, tuple)):
                mb_list = _planet_ids_to_names(list(mb_raw))
            else:
                mb_list = [str(mb_raw)]
        except Exception as e:
            mb_list = [f'error: {e}']

        # ── 2. Pushkara Navamsha + Bhaga ─────────────────────────────────
        # API: charts.planets_in_pushkara_navamsa_bhaga(planet_positions)
        # Returns [list_of_pn_planet_ids, list_of_pb_planet_ids]
        try:
            with _silence_stdout():
                pn_raw = charts.planets_in_pushkara_navamsa_bhaga(rasi_chart)
            pn_list = []
            if isinstance(pn_raw, (list, tuple)) and len(pn_raw) >= 2:
                pn_navamsa = _planet_ids_to_names(list(pn_raw[0]))
                pn_bhaga = _planet_ids_to_names(list(pn_raw[1]))
                pn_list = {
                    'navamsha': pn_navamsa,
                    'bhaga': pn_bhaga,
                }
            elif isinstance(pn_raw, (list, tuple)):
                pn_list = {'navamsha': _planet_ids_to_names(list(pn_raw)), 'bhaga': []}
            else:
                pn_list = {'navamsha': [], 'bhaga': []}
        except Exception as e:
            pn_list = {'error': str(e)}

        # ── 3. Marana Karaka Sthana ───────────────────────────────────────
        # API: charts.get_planets_in_marana_karaka_sthana(planet_positions, ...)
        try:
            with _silence_stdout():
                mks_raw = charts.get_planets_in_marana_karaka_sthana(
                    rasi_chart, consider_ketu_4th_house=True
                )
            if mks_raw is None:
                mks_list = []
            elif isinstance(mks_raw, (list, tuple)):
                mks_list = _planet_ids_to_names(list(mks_raw))
            elif isinstance(mks_raw, dict):
                mks_list = _planet_ids_to_names(list(mks_raw.keys()))
            else:
                mks_list = [str(mks_raw)]
        except Exception as e:
            mks_list = [f'error: {e}']

        # ── 4. Kala Sarpa ─────────────────────────────────────────────────
        # API: kala_sarpa(house_to_planet_list) → bool
        try:
            ks_val = bool(kala_sarpa(h2p_list))
        except Exception as e:
            ks_val = f'error: {e}'

        # ── 5. Manglik ────────────────────────────────────────────────────
        # API: manglik(planet_positions, ...) → [bool, exception_bool, [indices]]
        try:
            mg_raw = manglik(rasi_chart)
            # mg_raw = [is_manglik, has_exception, [exception_indices]]
            mg_val = bool(mg_raw[0]) if isinstance(mg_raw, (list, tuple)) else bool(mg_raw)
            mg_exc = bool(mg_raw[1]) if isinstance(mg_raw, (list, tuple)) and len(mg_raw) > 1 else False
        except Exception as e:
            mg_val = f'error: {e}'
            mg_exc = False

        # ── 6. Ganda Moola ────────────────────────────────────────────────
        # API: ganda_moola(moon_star) → bool
        # moon_star = nakshatra index 0-26
        try:
            moon_nak = _moon_nakshatra(rasi_chart)
            # ganda_moola_stars are 1-indexed nakshatras; convert: nak idx 0 = Ashwini = star 1
            moon_star = moon_nak + 1
            gm_val = bool(ganda_moola(moon_star))
        except Exception as e:
            gm_val = f'error: {e}'

        return {
            'mrityu_bhaga': mb_list,
            'pushkara_navamsha': pn_list,
            'marana_karaka_sthana': mks_list,
            'kala_sarpa': ks_val,
            'manglik': mg_val,
            'manglik_exceptions': mg_exc,
            'ganda_moola': gm_val,
        }

    except Exception as e:
        return {'error': str(e)}


if __name__ == '__main__':
    import json

    # Gandhi chart
    gandhi = (1869, 10, 2, 7, 12, 21.6417, 69.6293, 5.5)
    print('=== Gandhi (1869-10-02 07:12 IST) ===')
    r1 = calculate_special_planets(*gandhi)
    print(json.dumps(r1, default=str, indent=2))

    print()

    # Sample chart
    sample = (2005, 12, 14, 10, 28, 31.2304, 121.4737, 8.0)
    print('=== Sample (2005-12-14 10:28 CST) ===')
    r2 = calculate_special_planets(*sample)
    print(json.dumps(r2, default=str, indent=2))
