"""
extras_pyjhora — Bhava Bala / Special Lagnas / Vargeeya Bala PyJHora 包装
========================================================================
对外接口（engine.py 在 try/except 中调用，缺失不致命）：
    calculate_bhava_bala(year, month, day, hour, minute, lat, lon, tz_offset)
        → {宫位(1-12): {'total_60ths','total_rupas','strength'}}
    calculate_special_lagnas(year, month, day, hour, minute, lat, lon, tz_offset)
        → {特殊上升点名: {'sign','sign_idx','longitude'}}
    calculate_vargeeya_bala(year, month, day, hour, minute, lat, lon, tz_offset)
        → {行星名: {'count','vargas','bala'}}  # Shodhasavarga(16 分盘) Vimsopaka Bala
"""
from _pyjhora_base import (
    strength, charts, drik,
    build_jd_place, PLANET_ID_TO_NAME, SIGNS, _silence_stdout,
)


def calculate_bhava_bala(year, month, day, hour, minute, lat, lon, tz_offset):
    """12 宫 Bhava Bala。strength.bhava_bala → [bb[12], bb_rupas[12], bb_strength[12]]。"""
    jd, place = build_jd_place(year, month, day, hour, minute, lat, lon, tz_offset)
    with _silence_stdout():
        bb, bb_rupas, bb_strength = strength.bhava_bala(jd, place)
    return {
        h + 1: {
            'total_60ths': round(bb[h], 2),
            'total_rupas': round(bb_rupas[h], 2),
            'strength': round(bb_strength[h], 2),
        }
        for h in range(12)
    }


# 特殊上升点 → drik 对应函数名
_SPECIAL_LAGNA_FUNCS = {
    'Bhava': 'bhava_lagna',
    'Hora': 'hora_lagna',
    'Ghati': 'ghati_lagna',
    'Vighati': 'vighati_lagna',
    'Pranapada': 'pranapada_lagna',
    'Indu': 'indu_lagna',
    'Sree': 'sree_lagna',
    'BhriguBindhu': 'bhrigu_bindhu_lagna',
}


def calculate_special_lagnas(year, month, day, hour, minute, lat, lon, tz_offset):
    """各特殊上升点。drik.<func>(jd, place, divisional_chart_factor=1) → [raasi_idx, long]。"""
    jd, place = build_jd_place(year, month, day, hour, minute, lat, lon, tz_offset)
    out = {}
    with _silence_stdout():
        for name, fname in _SPECIAL_LAGNA_FUNCS.items():
            func = getattr(drik, fname, None)
            if func is None:
                continue
            try:
                pos = func(jd, place, divisional_chart_factor=1)
                sidx = int(pos[0])
                out[name] = {
                    'sign': SIGNS[sidx],
                    'sign_idx': sidx,
                    'longitude': round(float(pos[1]), 2),
                }
            except Exception:
                continue
    return out


def calculate_vargeeya_bala(year, month, day, hour, minute, lat, lon, tz_offset):
    """Shodhasavarga（16 分盘）Vimsopaka Bala。
    charts.vimsopaka_shodhasavarga_of_planets → {pid: [count, 'D../D..', bala_float]}。"""
    jd, place = build_jd_place(year, month, day, hour, minute, lat, lon, tz_offset)
    with _silence_stdout():
        vb = charts.vimsopaka_shodhasavarga_of_planets(jd, place)
    out = {}
    for pid, name in PLANET_ID_TO_NAME.items():
        if pid not in vb:
            continue
        entry = vb[pid]
        # entry 形如 [count, 'D2/D4/...', bala]；做防御性解包
        count = entry[0] if len(entry) > 0 else None
        vargas = entry[1] if len(entry) > 1 else ''
        bala = entry[2] if len(entry) > 2 else None
        out[name] = {
            'count': count,
            'vargas': vargas,
            'bala': round(bala, 2) if isinstance(bala, (int, float)) else bala,
        }
    return out


if __name__ == '__main__':
    args = (2002, 12, 11, 20, 47, 25.4333, 119.0, 8.0)
    bb = calculate_bhava_bala(*args)
    print('Bhava Bala (rupas):', {h: bb[h]['total_rupas'] for h in range(1, 13)})
    sl = calculate_special_lagnas(*args)
    print('Special Lagnas:')
    for n, d in sl.items():
        print(f"  {n:<12} {d['sign']:<10} {d['longitude']}°")
    vb = calculate_vargeeya_bala(*args)
    print('Vargeeya (Shodhasavarga Vimsopaka) Bala:')
    for n, d in vb.items():
        print(f"  {n:<8} count={d['count']} bala={d['bala']}")
