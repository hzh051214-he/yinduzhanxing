"""
arudhas_pyjhora — PyJHora 完整 12 Arudha Pada 计算包装
=======================================================
接口：calculate_arudha_padas(year, month, day, hour, minute, lat, lon, tz_offset)
返回包含 A1-A12 完整信息的字典。
"""

from _pyjhora_base import (
    build_jd_place, _silence_stdout, charts, SIGNS
)


ARUDHA_NAMES = [
    'Arudha Lagna', 'Dhana Pada', 'Vikrama Pada', 'Matri Pada',
    'Putra Pada', 'Shhatru Pada', 'Darapada', 'Mrityu Pada',
    'Bhagya Pada', 'Karma Pada', 'Labha Pada', 'Vyaya Pada',
]

ARUDHA_USES = [
    '外在形象/世人眼中的你', '实际财富表现', '实际努力/兄弟运',
    '实际居所/母亲关系', '实际子女/投资', '实际竞争者/疾病',
    '实际合伙/配偶', '实际危机/变故', '实际运势/父亲',
    '实际职业/社会地位', '实际收益网络', '实际损耗/灵性',
]


def calculate_arudha_padas(year, month, day, hour, minute, lat, lon, tz_offset):
    """Complete 12 Arudha Padas.

    Returns {
      'A1': {'sign': str, 'sign_idx': int, 'house': int,
             'name': 'Arudha Lagna', 'use': '外在形象/世人眼中的你'},
      ...
      'A12': {'sign': str, 'sign_idx': int, 'house': int,
              'name': 'Vyaya Pada', 'use': '实际损耗/灵性'},
    }
    house is calculated from D1 Lagna:
      house = ((sign_idx - lagna_sign_idx) % 12) + 1
    """
    with _silence_stdout():
        try:
            from jhora.horoscope.chart.arudhas import bhava_arudhas_from_planet_positions

            jd, place = build_jd_place(year, month, day, hour, minute, lat, lon, tz_offset)

            # Build rasi chart
            rasi_chart = charts.rasi_chart(jd, place)

            # Extract lagna sign index from rasi_chart[0][1][0]
            # rasi_chart[0] = Lagna row: (planet_id, [sign_idx, ...])
            lagna_sign_idx = rasi_chart[0][1][0]

            # Get the 12 arudha sign indices
            arudhas = bhava_arudhas_from_planet_positions(rasi_chart)

            result = {}
            for i in range(12):
                key = f'A{i + 1}'
                sign_idx = arudhas[i]
                house = ((sign_idx - lagna_sign_idx) % 12) + 1
                result[key] = {
                    'sign': SIGNS[sign_idx],
                    'sign_idx': sign_idx,
                    'house': house,
                    'name': ARUDHA_NAMES[i],
                    'use': ARUDHA_USES[i],
                }
            return result

        except Exception as e:
            raise RuntimeError(f'calculate_arudha_padas failed: {e}') from e
