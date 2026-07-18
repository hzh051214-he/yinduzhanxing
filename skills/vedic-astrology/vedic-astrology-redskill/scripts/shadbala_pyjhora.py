"""
shadbala_pyjhora — Shadbala（六力）PyJHora 包装
===============================================
对外接口：
    calculate_shadbala_fixed(year, month, day, hour, minute, lat, lon, tz_offset)
返回（结构见 calculator.md「engine 返回数据结构」与 formatter.py 消费）：
    {
        '行星名': {
            'total_60ths': float,   # 六力合计（virupa / shashtiamsa，60 进制）
            'total_rupas': float,   # = total_60ths / 60
            'sthana': float, 'kaala': float, 'dig': float,
            'cheshta': float, 'naisargika': float, 'drik': float,
            'strength_pct': float,  # total_rupas / 必需 rupa × 100
            'classification': '强'/'中'/'弱',
            'ishta_phala': float,   # √(UcchaBala × CheshtaBala)
            'kashta_phala': float,  # √((60-Uccha) × (60-Cheshta))
        }, ...  # Sun..Saturn 共 7 颗（罗睺/计都不计 Shadbala）
    }

说明：底层调用 PyJHora 4.8.6 的 strength.shad_bala()。data_contract.md 已明确
PyJHora 的 Shadbala 与 JHora 有系统性偏差（分盘蝴蝶效应、aspect 插值、日出折射等），
平均每颗行星偏差 1-2 rupas——下游以「排序 + 强弱分级」为准，不引用具体数值。
"""
import math

from _pyjhora_base import (
    strength, charts, const,
    build_jd_place, SUN_TO_SATURN_NAMES, _silence_stdout,
)

# 各行星达到「满力」所需的最低 rupa（Requisite Strength / Ishta Bala）
#
# ★ 依据：BPHS（Brihat Parashara Hora Shastra）第 27 章，
#         与 B.V. Raman《Hindu Predictive Astrology》第 10 章引用值完全一致。
#         顺序：Sun, Moon, Mars, Mercury, Jupiter, Venus, Saturn
#
# ⚠️ 注意：PyJHora const.shad_bala_factors = [5, 6, 5, 7, 6.5, 5.5, 5]
#         其中 Sun = 5.0，与 BPHS 原典的 6.5 不符（偏低 30%）。
#         原因：PyJHora 引用了 Jagannatha Hora 软件的简化值。
#         本模块覆盖此值，改用 BPHS 标准，以确保 strength_pct 的百分比基准正确。
#
# 各行星值（Rupas）：
#   Sun      = 6.5  （BPHS 原典；PyJHora 用 5.0，此处不采用）
#   Moon     = 6.0
#   Mars     = 5.0
#   Mercury  = 7.0
#   Jupiter  = 6.5
#   Venus    = 5.5
#   Saturn   = 5.0
_REQUIRED_RUPAS_BPHS = {
    'Sun': 6.5, 'Moon': 6.0, 'Mars': 5.0,
    'Mercury': 7.0, 'Jupiter': 6.5, 'Venus': 5.5, 'Saturn': 5.0,
}
# 列表形式（顺序与 SUN_TO_SATURN_NAMES 一致：Sun Moon Mars Mercury Jupiter Venus Saturn）
_REQUIRED_RUPAS = [
    _REQUIRED_RUPAS_BPHS['Sun'],
    _REQUIRED_RUPAS_BPHS['Moon'],
    _REQUIRED_RUPAS_BPHS['Mars'],
    _REQUIRED_RUPAS_BPHS['Mercury'],
    _REQUIRED_RUPAS_BPHS['Jupiter'],
    _REQUIRED_RUPAS_BPHS['Venus'],
    _REQUIRED_RUPAS_BPHS['Saturn'],
]


def _classify(pct):
    if pct >= 150:
        return '强'
    if pct >= 100:
        return '中'
    return '弱'


def _phala_pair(uccha, cheshta):
    """经典 Ishta/Kashta Phala：分量先 clamp 到 [0, 60] 再开方。"""
    u = max(0.0, min(60.0, uccha))
    c = max(0.0, min(60.0, cheshta))
    ishta = math.sqrt(u * c)
    kashta = math.sqrt((60.0 - u) * (60.0 - c))
    return round(ishta, 2), round(kashta, 2)


def calculate_shadbala_fixed(year, month, day, hour, minute, lat, lon, tz_offset):
    jd, place = build_jd_place(year, month, day, hour, minute, lat, lon, tz_offset)

    with _silence_stdout():
        # [stb, kb, dgb, cb, nb, dkb, sb_sum, sb_rupa, sb_strength]，每项 list[7]
        sb = strength.shad_bala(jd, place)
        # Ishta/Kashta 需 Uccha Bala；日月不逆行，其「运动力」分别取 Ayana / Paksha Bala
        pp = charts.rasi_chart(jd, place)[:const._pp_count_upto_ketu]
        uccha = strength._uchcha_bala(pp)
        ayana = strength._ayana_bala(jd, place)
        paksha = strength._paksha_bala(jd, place)

    stb, kb, dgb, cb, nb, dkb, sb_sum, sb_rupa, sb_strength = sb

    # Phaladeepika：太阳的「运动力」用 Ayana Bala，月亮用 Paksha Bala
    cheshta_for_phala = list(cb)
    cheshta_for_phala[0] = ayana[0]
    cheshta_for_phala[1] = paksha[1]

    result = {}
    for p, name in enumerate(SUN_TO_SATURN_NAMES):
        # 用 BPHS 基准重新计算百分比（覆盖 PyJHora 内部的 sb_strength[p]，
        # 后者基于 const.shad_bala_factors[Sun]=5.0，与 BPHS 的 6.5 不符）
        bphs_required = _REQUIRED_RUPAS[p]
        pct = round(sb_rupa[p] / bphs_required * 100.0, 2)
        ishta, kashta = _phala_pair(uccha[p], cheshta_for_phala[p])
        result[name] = {
            'total_60ths': round(sb_sum[p], 2),
            'total_rupas': round(sb_rupa[p], 2),
            'required_rupas': bphs_required,   # BPHS 基准，供下游透明验证
            'sthana': round(stb[p], 2),
            'kaala': round(kb[p], 2),
            'dig': round(dgb[p], 2),
            'cheshta': round(cb[p], 2),
            'naisargika': round(nb[p], 2),
            'drik': round(dkb[p], 2),
            'strength_pct': pct,
            'classification': _classify(pct),
            'ishta_phala': ishta,
            'kashta_phala': kashta,
        }
    return result


if __name__ == '__main__':
    r = calculate_shadbala_fixed(2002, 12, 11, 20, 47, 25.4333, 119.0, 8.0)
    print(f"{'Planet':<9}{'Rupas':>7}{'Pct%':>8}{'Cls':>5}{'Ishta':>8}{'Kashta':>8}")
    for name in SUN_TO_SATURN_NAMES:
        d = r[name]
        print(f"{name:<9}{d['total_rupas']:>7}{d['strength_pct']:>8}{d['classification']:>5}"
              f"{d['ishta_phala']:>8}{d['kashta_phala']:>8}")
