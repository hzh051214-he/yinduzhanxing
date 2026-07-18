"""
_pyjhora_base — PyJHora 5 个包装模块的共享底座
=================================================
职责：
  1. swisseph 兼容补丁：pysweph 2.10.03 的 calc_ut/calc 返回 3 元组
     (xx, retflag, serr)，而 PyJHora 4.8.6 内部按 2 元组解包
     (`longi,_ = swe.calc_ut(...)`)。不打补丁则 import jhora 即崩。
  2. 全局设置 Lahiri ayanamsa + Mean Node（calculator.md 技术规格固定要求）。
  3. 抑制 PyJHora import / 调用期写入 stdout 的噪音（geocoder、版本横幅等），
     避免污染 engine 的 JSON / Markdown 输出。
  4. 提供 build_jd_place() 统一构造 PyJHora 所需的 (jd, place)。
  5. 行星 / 星座的 ID ↔ 英文名映射，供各包装模块复用。

所有 *_pyjhora 模块只需 `from _pyjhora_base import ...`，无需各自重复补丁逻辑。
"""
import io
import sys
import contextlib

import swisseph as swe


# ── 1. swisseph 3 元组 → 2 元组兼容补丁（必须在 import jhora 之前执行）──
def _patch_swisseph():
    """pysweph 2.10.03 的 calc_ut/calc 返回 (xx, retflag, serr) 三元组；
    PyJHora 4.8.6 全程按 `longi,_ = swe.calc_ut(...)` 两元组解包。
    包装成只返回前两项，使 jhora 内部解包成立，且不改变数值结果。
    幂等：重复调用不会二次包装。"""
    if getattr(swe, '_pyjhora_patched', False):
        return

    def _wrap(orig):
        def inner(*args, **kwargs):
            r = orig(*args, **kwargs)
            if isinstance(r, tuple) and len(r) > 2:
                return (r[0], r[1])
            return r
        return inner

    swe.calc_ut = _wrap(swe.calc_ut)
    swe.calc = _wrap(swe.calc)
    swe._pyjhora_patched = True


_patch_swisseph()


# ── 2. 抑制 PyJHora 噪音 import ──
@contextlib.contextmanager
def _silence_stdout():
    """临时把 stdout 重定向到内存缓冲，吞掉 PyJHora 的打印噪音。"""
    real = sys.stdout
    sys.stdout = io.StringIO()
    try:
        yield
    finally:
        sys.stdout = real


with _silence_stdout():
    from jhora.panchanga import drik
    from jhora import const, utils
    from jhora.horoscope.chart import charts, ashtakavarga, strength
    from jhora.horoscope.dhasa.graha import vimsottari


# ── 3. 全局设置：Lahiri + Mean Node ──
def _configure():
    """固定 Lahiri ayanamsa + Mean Node。与 engine.py 的
    swe.set_sid_mode(SIDM_LAHIRI) 及 calculator.md 技术规格保持一致。"""
    with _silence_stdout():
        drik.set_ayanamsa_mode('LAHIRI')
        # use_true=False → Mean Node（罗睺/计都用平均交点）
        try:
            const.set_node_mode(use_true=False)
        except Exception:
            # 老版本签名兜底
            const._use_true_nodes_for_rahu_ketu = False


_configure()


# ── 4. ID / 名称映射 ──
# PyJHora planet id：0=Sun ... 6=Saturn, 7=Rahu, 8=Ketu，'L'=Lagna
PLANET_ID_TO_NAME = {
    0: 'Sun', 1: 'Moon', 2: 'Mars', 3: 'Mercury',
    4: 'Jupiter', 5: 'Venus', 6: 'Saturn', 7: 'Rahu', 8: 'Ketu',
}
SUN_TO_SATURN_NAMES = ['Sun', 'Moon', 'Mars', 'Mercury', 'Jupiter', 'Venus', 'Saturn']

# raasi idx 0=Aries ... 11=Pisces（与 engine.py SIGNS 完全一致）
SIGNS = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
         'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces']

_ASC = const._ascendant_symbol  # 'L'


# ── 5. 构造 (jd, place) ──
def build_jd_place(year, month, day, hour, minute, lat, lon, tz_offset, name='birth'):
    """从出生数据构造 PyJHora 所需的 (jd, place)。

    @param tz_offset: float，本地时区相对 UTC 的小时偏移（如 +8.0 / +5.5）。
                      engine 传入的 _tz_offset 即此值。
    @return: (jd, place)
        jd    — PyJHora 约定的 local Julian Day（不做 UTC 换算，时区由 place 携带）。
        place — drik.Place(name, latitude, longitude, timezone)。
    """
    jd = utils.julian_day_number((year, month, day), (hour, minute, 0))
    place = drik.Place(name, float(lat), float(lon), float(tz_offset))
    return jd, place


__all__ = [
    'drik', 'const', 'utils', 'charts', 'ashtakavarga', 'strength', 'vimsottari',
    '_silence_stdout', 'build_jd_place',
    'PLANET_ID_TO_NAME', 'SUN_TO_SATURN_NAMES', 'SIGNS', '_ASC',
]
