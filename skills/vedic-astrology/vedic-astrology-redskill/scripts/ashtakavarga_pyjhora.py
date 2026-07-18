"""
ashtakavarga_pyjhora — Ashtakavarga（SAV / BAV）PyJHora 包装
===========================================================
对外接口：
    calculate_ashtakavarga_fixed(year, month, day, hour, minute,
                                 lat, lon, tz_offset)
返回（engine.py 与 setup_env.py 的校验都依赖此结构）：
    {
        'sarvashtakavarga': {星座英文名: int},   # 12 项，合计 = 337
        'bhinnashtakavarga': {行星英文名: {星座英文名: int}},  # Sun..Saturn 7 行
    }

校验基准（calculator.md / setup_env.py）：
    2002-12-11 20:47, lat=25.4333 lon=119.0 tz=+8.0
    → SAV 合计 = 337
    BAV 行常量（吠陀固定值）：
      Sun 48, Moon 49, Mars 39, Mercury 54, Jupiter 56, Venus 52, Saturn 39
"""
from _pyjhora_base import (
    charts, ashtakavarga as av, utils,
    build_jd_place, SIGNS, SUN_TO_SATURN_NAMES, _silence_stdout,
)
# keep old alias so existing code in this file still works
ashtakavarga = av


def calculate_ashtakavarga_fixed(year, month, day, hour, minute, lat, lon, tz_offset):
    jd, place = build_jd_place(year, month, day, hour, minute, lat, lon, tz_offset)

    with _silence_stdout():
        # rasi_chart → [[planet/'L', (raasi_idx, long_in_sign)], ...]
        planet_positions = charts.rasi_chart(jd, place)
        # 转成 ashtakavarga 需要的 1-D house_to_planet_list（[0..11]）
        house_to_planet = utils.get_house_planet_list_from_planet_positions(planet_positions)
        # binna: [8][12] (0=Sun..6=Saturn, 7=Lagnam); samudhaya: [12] by raasi idx
        binna, samudhaya, _prastara = ashtakavarga.get_ashtaka_varga(house_to_planet)

    # SAV：raasi idx → 星座英文名
    sarvashtakavarga = {SIGNS[i]: int(samudhaya[i]) for i in range(12)}

    # BAV：binna 前 7 行 = Sun..Saturn（第 8 行是 Lagnam，不输出）
    bhinnashtakavarga = {}
    for pidx, pname in enumerate(SUN_TO_SATURN_NAMES):
        row = binna[pidx]
        bhinnashtakavarga[pname] = {SIGNS[i]: int(row[i]) for i in range(12)}

    return {
        'sarvashtakavarga': sarvashtakavarga,
        'bhinnashtakavarga': bhinnashtakavarga,
    }


def calculate_sodhya_pinda(year, month, day, hour, minute, lat, lon, tz_offset):
    """计算 Sodhya Pinda（Raasi Pinda / Graha Pinda / Sodhya Pinda）。

    返回：
        {
            'raasi_pindas':  {行星英文名: 数值, ...},  # 0-6 = Sun..Saturn
            'graha_pindas':  {行星英文名: 数值, ...},
            'sodhya_pindas': {行星英文名: 数值, ...},
        }
    或 {'error': str} 若计算失败。
    """
    try:
        jd, place = build_jd_place(year, month, day, hour, minute, lat, lon, tz_offset)

        with _silence_stdout():
            # rasi_chart → list of (planet_id_or_'L', (sign_idx, long_in_sign))
            planet_positions = charts.rasi_chart(jd, place)

            # 构造 house_to_planet_list：12 元素列表，index = sign 0-11
            # 每元素为该宫中行星 ID（或 'L'）用 '/' 连接的字符串，空则为 ''
            house_list = ['' for _ in range(12)]
            for item in planet_positions:
                pid, pos_tuple = item[0], item[1]
                sign_idx = int(pos_tuple[0])
                pid_str = 'L' if pid == 'L' else str(pid)
                if house_list[sign_idx] == '':
                    house_list[sign_idx] = pid_str
                else:
                    house_list[sign_idx] += '/' + pid_str

            bav_2d, sav_1d, prastara = av.get_ashtaka_varga(house_list)
            raasi_p, graha_p, sodhya_p = av.sodhaya_pindas(bav_2d, house_list)

        def _map_planets(pindas):
            out = {}
            for pidx, pname in enumerate(SUN_TO_SATURN_NAMES):
                val = pindas[pidx] if pidx < len(pindas) else None
                out[pname] = round(float(val), 4) if isinstance(val, (int, float)) else val
            return out

        return {
            'raasi_pindas': _map_planets(raasi_p),
            'graha_pindas': _map_planets(graha_p),
            'sodhya_pindas': _map_planets(sodhya_p),
        }
    except Exception as e:
        return {'error': str(e)}


if __name__ == '__main__':
    r = calculate_ashtakavarga_fixed(2002, 12, 11, 20, 47, 25.4333, 119.0, 8.0)
    sav_total = sum(r['sarvashtakavarga'].values())
    print('SAV total:', sav_total, '(expect 337)')
    for p in SUN_TO_SATURN_NAMES:
        print(f"  BAV {p:<8} row sum = {sum(r['bhinnashtakavarga'][p].values())}")
