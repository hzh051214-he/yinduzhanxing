"""
divisional_pyjhora — 分盘（Varga / Divisional Charts）PyJHora 包装
=================================================================
对外接口：
    calculate_divisional_charts(year, month, day, hour, minute, lat, lon, tz_offset)
返回（结构见 engine.py 的 _legacy_fmt 消费）：
    {
        'D1':  {行星名: {'sign': str, 'sign_idx': int, 'longitude': float}},
        'D9':  {...}, 'D10': {...}, 'D4': {...}, 'D5': {...}, ...
    }
    行星名 key 用 'Lagna' / 'Sun'..'Ketu'。engine 重点取 D9/D10/D4/D5。

底层调用 PyJHora 4.8.6 charts.divisional_chart(jd, place, divisional_chart_factor=N)，
返回 [['L',[raasi_idx, long_in_sign]], [planet_id,[raasi_idx, long]], ...]。
"""
from _pyjhora_base import (
    charts,
    build_jd_place, PLANET_ID_TO_NAME, SIGNS, _ASC, _silence_stdout,
)

# 标准分盘集合。engine 必用 D1/D4/D5/D9/D10。
# D11（Ekadasamsha）需用户知情同意后才分析（高度私密）。
_VARGA_FACTORS = {
    'D1': 1, 'D2': 2, 'D3': 3, 'D4': 4, 'D5': 5, 'D7': 7,
    'D9': 9, 'D10': 10, 'D11': 11, 'D12': 12, 'D16': 16, 'D20': 20,
    'D24': 24, 'D27': 27, 'D30': 30, 'D60': 60,
}


def _format_chart(planet_positions):
    """[['L',[sidx,long]], [pid,[sidx,long]], ...] → {name: {sign, sign_idx, longitude}}"""
    out = {}
    for entry in planet_positions:
        pid, pos = entry[0], entry[1]
        sidx = int(pos[0])
        long_in_sign = float(pos[1])
        name = 'Lagna' if pid == _ASC else PLANET_ID_TO_NAME.get(pid)
        if name is None:
            continue
        out[name] = {
            'sign': SIGNS[sidx],
            'sign_idx': sidx,
            'longitude': long_in_sign,
        }
    return out


def calculate_divisional_charts(year, month, day, hour, minute, lat, lon, tz_offset):
    jd, place = build_jd_place(year, month, day, hour, minute, lat, lon, tz_offset)

    charts_out = {}
    with _silence_stdout():
        for key, factor in _VARGA_FACTORS.items():
            try:
                pp = charts.divisional_chart(jd, place, divisional_chart_factor=factor)
                charts_out[key] = _format_chart(pp)
            except Exception as e:
                charts_out[key] = {'error': str(e)}
    return charts_out


if __name__ == '__main__':
    dc = calculate_divisional_charts(2002, 12, 11, 20, 47, 25.4333, 119.0, 8.0)
    print('分盘:', ', '.join(dc.keys()))
    for key in ['D1', 'D9', 'D10', 'D4', 'D5']:
        ch = dc[key]
        if 'error' in ch:
            print(f"  {key}: ERROR {ch['error']}")
            continue
        lag = ch['Lagna']
        sun = ch['Sun']
        print(f"  {key}: Lagna={lag['sign']:<10} Sun={sun['sign']}")
