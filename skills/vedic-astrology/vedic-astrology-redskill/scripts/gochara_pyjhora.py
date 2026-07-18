"""
Gochara (Transit) Analysis Module - PyJHora Edition
Calculates detailed transit analysis including BAV scores, Vedha, Sade Sati,
Double Transit, and Ashtama Gochara.

Based on BPHS Vedha pairs and traditional Gochara rules.
"""
import swisseph as swe
from datetime import datetime
import pytz

SIGNS = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
         'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces']

# BPHS Vedha pairs: planet transiting house H is blocked if another planet
# is simultaneously in the Vedha house.
# Key = house being transited, Value = the Vedha (blocking) house
VEDHA = {
    1: 12,
    2: 5,
    3: 9,
    4: 3,
    5: 2,
    6: 12,
    7: 2,
    8: 5,
    9: 3,
    10: 4,
    11: 9,
    12: 6,
}

# Planet IDs for swisseph
PLANETS_SWE = {
    'Sun':     swe.SUN,
    'Moon':    swe.MOON,
    'Mars':    swe.MARS,
    'Mercury': swe.MERCURY,
    'Jupiter': swe.JUPITER,
    'Venus':   swe.VENUS,
    'Saturn':  swe.SATURN,
}

ALL_PLANETS = ['Sun', 'Moon', 'Mars', 'Mercury', 'Jupiter', 'Venus', 'Saturn', 'Rahu', 'Ketu']

# Natural planet categories in transit (Gochara) context.
# Per BPHS, Vedha operates between opposite categories: a benefic's transit is
# obstructed by a malefic sitting in the Vedha house (and not vice versa).
NATURAL_BENEFICS_TRANSIT = {'Jupiter', 'Venus', 'Mercury', 'Moon'}
NATURAL_MALEFICS_TRANSIT = {'Saturn', 'Mars', 'Rahu', 'Ketu', 'Sun'}


def _get_current_jd(tz_str, reference_date=None):
    """Get Julian Day number — uses reference_date if provided, else datetime.now()."""
    tz = pytz.timezone(tz_str)
    if reference_date is not None:
        # reference_date may be tz-aware or naive
        if hasattr(reference_date, 'tzinfo') and reference_date.tzinfo:
            now = reference_date.astimezone(tz)
        else:
            now = tz.localize(reference_date)
    else:
        now = datetime.now(tz)
    utc = now.astimezone(pytz.utc)
    jd = swe.julday(utc.year, utc.month, utc.day,
                    utc.hour + utc.minute / 60.0 + utc.second / 3600.0)
    return jd, now


def _calc_current_positions(jd):
    """Calculate current sidereal positions of all 9 planets."""
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    flags = swe.FLG_SIDEREAL | swe.FLG_SPEED

    positions = {}

    # 7 main planets
    for name, pid in PLANETS_SWE.items():
        result = swe.calc_ut(jd, pid, flags)
        lon = result[0][0]
        sign_idx = int(lon / 30)
        positions[name] = {
            'longitude': lon,
            'sign_idx': sign_idx,
            'current_sign': SIGNS[sign_idx],
        }

    # Rahu (Mean Node) — always retrograde
    result = swe.calc_ut(jd, swe.MEAN_NODE, flags)
    rahu_lon = result[0][0]
    rahu_idx = int(rahu_lon / 30)
    positions['Rahu'] = {
        'longitude': rahu_lon,
        'sign_idx': rahu_idx,
        'current_sign': SIGNS[rahu_idx],
    }

    # Ketu = Rahu + 180°
    ketu_lon = (rahu_lon + 180) % 360
    ketu_idx = int(ketu_lon / 30)
    positions['Ketu'] = {
        'longitude': ketu_lon,
        'sign_idx': ketu_idx,
        'current_sign': SIGNS[ketu_idx],
    }

    return positions


def _transit_house(planet_sign_idx, reference_sign_idx):
    """House number counted from reference sign (1-based)."""
    return ((planet_sign_idx - reference_sign_idx) % 12) + 1


def _bav_score_and_strength(bav_data, planet_name, sign_idx):
    """Look up BAV score and derive strength label."""
    planet_bav = bav_data.get(planet_name, {})
    sign_name = SIGNS[sign_idx]
    score = planet_bav.get(sign_name, 0)

    if score >= 5:
        strength = 'strong'
    elif score >= 3:
        strength = 'medium'
    else:
        strength = 'weak'

    return score, strength


def _check_vedha(planet_name, transit_house_from_moon, all_transit_houses_from_moon):
    """
    Check if this planet's transit is blocked (Vedha) by another planet.

    Returns (is_blocked: bool, blocker_planet: str)

    Vedha rule (BPHS): a planet transiting house H is obstructed if another planet
    of the OPPOSITE natural category occupies the Vedha house for H.

    Per BPHS the obstruction is asymmetric: only a benefic's beneficial transit is
    spoiled by a malefic sitting in the Vedha house. A malefic's transit is not
    neutralised by a benefic in the Vedha house, so malefics are never reported as
    blocked here. This eliminates spurious pairs such as "Jupiter blocks Saturn"
    (both would otherwise match the raw house mapping).
    """
    # Only benefics are subject to Vedha obstruction.
    if planet_name not in NATURAL_BENEFICS_TRANSIT:
        return False, ''

    h = transit_house_from_moon
    vedha_house = VEDHA.get(h)
    if vedha_house is None:
        return False, ''

    for other_planet, other_house in all_transit_houses_from_moon.items():
        if other_planet == planet_name:
            continue
        # The blocker must sit in the Vedha house AND be of the opposite
        # (malefic) category.
        if other_house == vedha_house and other_planet in NATURAL_MALEFICS_TRANSIT:
            return True, other_planet

    return False, ''


def _calc_sade_sati(saturn_sign_idx, birth_moon_sign_idx):
    """Calculate Sade Sati status from Saturn's current sign vs natal Moon sign."""
    relative = (saturn_sign_idx - birth_moon_sign_idx) % 12

    if relative == 11:
        status = 'active'
        phase = 'phase1_rising'
    elif relative == 0:
        status = 'active'
        phase = 'phase2_peak'
    elif relative == 1:
        status = 'active'
        phase = 'phase3_fading'
    else:
        status = 'inactive'
        phase = 'none'

    return {'status': status, 'phase': phase}


def _calc_double_transit(saturn_house_from_lagna, jupiter_house_from_lagna):
    """
    Houses activated by both Saturn and Jupiter (their transit + aspect positions).

    Saturn aspects: 1st (own), 3rd, 7th, 10th (offsets 0, 2, 6, 9)
    Jupiter aspects: 1st (own), 5th, 7th, 9th (offsets 0, 4, 6, 8)
    """
    saturn_covers = set()
    for offset in [0, 2, 6, 9]:
        saturn_covers.add(((saturn_house_from_lagna - 1 + offset) % 12) + 1)

    jupiter_covers = set()
    for offset in [0, 4, 6, 8]:
        jupiter_covers.add(((jupiter_house_from_lagna - 1 + offset) % 12) + 1)

    return sorted(saturn_covers & jupiter_covers)


def calculate_gochara(birth_lagna_sign_idx, birth_moon_sign_idx,
                      birth_planets_sign_idx, bav_data, tz_str='Asia/Shanghai',
                      reference_date=None, sav_by_house=None):
    """
    Calculate detailed Gochara (transit) analysis.

    Parameters
    ----------
    birth_lagna_sign_idx : int
        Natal Lagna sign index (0=Aries ... 11=Pisces)
    birth_moon_sign_idx : int
        Natal Moon sign index
    birth_planets_sign_idx : dict
        {planet_name: sign_idx} for all 9 planets at birth
    bav_data : dict
        Bhinnashtakavarga data from chart['bav'].
        Format: {planet_name: {sign_name: int}}
        e.g. {'Sun': {'Aries': 4, 'Taurus': 3, ...}}
    tz_str : str
        Timezone string (default 'Asia/Shanghai')
    reference_date : datetime | None
        基准日期。None → datetime.now()；传入时使用指定日期的过运。
    sav_by_house : dict | None
        各宫 SAV 总分，来自 chart['sav_by_house']。
        格式：{house_num: {'sign': str, 'value': int}}
        用于计算过境宫位环境力量，同时决定行运预测置信度：
          SAV ≥ 30 → 环境充裕，过境效果接近预期（吉更吉/凶可中和）
          SAV 25-29 → 环境平稳，正常置信度
          SAV < 25  → 环境高阻/匮乏，预测置信度下降；
                      吉星过境效果有限，凶星过境影响也可能被环境消耗
        None 时跳过 Bindu 计算。

    Returns
    -------
    dict with keys: date, planets, sade_sati, double_transit, ashtama_gochara,
                    low_sav_warnings（SAV<25 的宫位过境警告汇总）
    """
    try:
        jd, now = _get_current_jd(tz_str, reference_date=reference_date)
        current_positions = _calc_current_positions(jd)

        # Build transit houses from Moon for all planets (needed for Vedha check)
        transit_houses_from_moon = {}
        for planet in ALL_PLANETS:
            pos = current_positions[planet]
            transit_houses_from_moon[planet] = _transit_house(
                pos['sign_idx'], birth_moon_sign_idx
            )

        planets_result = {}

        for planet in ALL_PLANETS:
            pos = current_positions[planet]
            sign_idx = pos['sign_idx']

            t_house_lagna = _transit_house(sign_idx, birth_lagna_sign_idx)
            t_house_moon = transit_houses_from_moon[planet]

            bav_score, bav_strength = _bav_score_and_strength(bav_data, planet, sign_idx)

            vedha_blocked, vedha_blocker = _check_vedha(
                planet, t_house_moon, transit_houses_from_moon
            )

            # Kaksha（八分位）：每星座30°分8份各3.75°，各Kaksha有不同宫主
            # 顺序（BPHS）：Saturn/Jupiter/Mars/Sun/Venus/Mercury/Moon/Lagna
            _KAKSHA_LORDS = ['Saturn','Jupiter','Mars','Sun','Venus','Mercury','Moon','Lagna']
            deg_in_sign = pos['longitude'] % 30
            kaksha_idx = int(deg_in_sign / 3.75)
            kaksha_lord = _KAKSHA_LORDS[min(kaksha_idx, 7)]

            # Bindu（宫位 SAV 总分）= 过运环境力量
            # 与 BAV 个人力量结合，给出综合强度判断
            house_bindu = None
            combined_strength = '中等'
            combined_label = '普通过运'
            if sav_by_house:
                _h_info = sav_by_house.get(t_house_lagna, {})
                house_bindu = _h_info.get('value')
                if house_bindu is not None and bav_score is not None:
                    _bav_high = bav_score >= 5
                    _bav_low  = bav_score <= 2
                    _bin_high = house_bindu >= 28
                    _bin_low  = house_bindu <= 22
                    if _bav_high and _bin_high:
                        combined_strength = 'strong'
                        combined_label = '最强过运（个人强×环境充裕）'
                    elif _bav_high and _bin_low:
                        combined_strength = 'mixed_high'
                        combined_label = '有力无处使（个人强但环境差）'
                    elif _bav_low and _bin_high:
                        combined_strength = 'mixed_low'
                        combined_label = '环境好底子不足（效果打折）'
                    elif _bav_low and _bin_low:
                        combined_strength = 'weak'
                        combined_label = '双弱（过运效果极微）'
                    elif _bav_high or _bin_high:
                        combined_strength = 'above_avg'
                        combined_label = '偏强过运'
                    elif _bav_low or _bin_low:
                        combined_strength = 'below_avg'
                        combined_label = '偏弱过运'
                    else:
                        combined_strength = 'medium'
                        combined_label = '中等过运'

            planets_result[planet] = {
                'current_sign': pos['current_sign'],
                'current_sign_idx': sign_idx,
                'transit_house': t_house_lagna,
                'transit_house_from_moon': t_house_moon,
                'bav_score': bav_score,
                'bav_strength': bav_strength,
                'kaksha_idx': kaksha_idx,
                'kaksha_lord': kaksha_lord,
                'house_bindu': house_bindu,        # 宫位 SAV 总分（环境力量）
                'combined_strength': combined_strength,  # 综合强度代码
                'combined_label': combined_label,  # 综合强度人话
                'vedha_blocked': vedha_blocked,
                'vedha_blocker': vedha_blocker,
                # ── SAV 置信度（行运预测可靠性）──
                # 置信度由过境宫位 SAV 总分（house_bindu）决定：
                #   high   : SAV ≥ 30，环境充裕，过境效果接近预期
                #   medium : SAV 25-29，环境平稳，正常置信度
                #   low    : SAV < 25，环境高阻/匮乏，预测降权
                #            吉星过境效果打折；凶星过境可能被环境消耗
                #   unknown: sav_by_house 未提供
                'sav_confidence': (
                    'unknown' if house_bindu is None else
                    'high'    if house_bindu >= 30 else
                    'medium'  if house_bindu >= 25 else
                    'low'
                ),
                'sav_confidence_note': (
                    None if house_bindu is None else
                    f'SAV={house_bindu}≥30，环境充裕，过境效果接近预期' if house_bindu >= 30 else
                    f'SAV={house_bindu}（25-29），环境平稳，置信度正常' if house_bindu >= 25 else
                    f'SAV={house_bindu}<25，环境高阻——吉星过境效果有限，凶星影响也可能被消耗，此行运预测降权'
                ),
            }

        # Sade Sati: Saturn vs natal Moon
        saturn_sign_idx = current_positions['Saturn']['sign_idx']
        sade_sati = _calc_sade_sati(saturn_sign_idx, birth_moon_sign_idx)

        # Double Transit: Saturn + Jupiter houses from Lagna
        saturn_h = planets_result['Saturn']['transit_house']
        jupiter_h = planets_result['Jupiter']['transit_house']
        double_transit = _calc_double_transit(saturn_h, jupiter_h)

        # Ashtama Gochara: planets transiting 8th from natal Moon
        ashtama_gochara = [
            planet for planet in ALL_PLANETS
            if planets_result[planet]['transit_house_from_moon'] == 8
        ]

        # 低 SAV 宫位过境警告汇总（供 formatter 和 core 快速定位需降权的行运预测）
        low_sav_warnings = [
            {
                'planet': p,
                'house': planets_result[p]['transit_house'],
                'sav': planets_result[p]['house_bindu'],
                'note': planets_result[p]['sav_confidence_note'],
            }
            for p in ALL_PLANETS
            if planets_result[p].get('sav_confidence') == 'low'
        ]

        return {
            'date': now.strftime('%Y-%m-%d'),
            'planets': planets_result,
            'sade_sati': sade_sati,
            'double_transit': double_transit,
            'ashtama_gochara': ashtama_gochara,
            'low_sav_warnings': low_sav_warnings,  # SAV<25 的宫位过境，需降低预测置信度
        }

    except Exception as e:
        return {'error': str(e)}


if __name__ == '__main__':
    # Quick standalone test
    print("gochara_pyjhora standalone test")
    result = calculate_gochara(
        birth_lagna_sign_idx=5,   # Virgo
        birth_moon_sign_idx=3,    # Cancer
        birth_planets_sign_idx={
            'Sun': 8, 'Moon': 3, 'Mars': 4, 'Mercury': 7,
            'Jupiter': 1, 'Venus': 9, 'Saturn': 10, 'Rahu': 6, 'Ketu': 0
        },
        bav_data={},
        tz_str='Asia/Shanghai'
    )
    print('date:', result.get('date'))
    for p, v in result.get('planets', {}).items():
        print(f"  {p}: {v['current_sign']} H={v['transit_house']} "
              f"BAV={v['bav_score']}({v['bav_strength']}) vedha={v['vedha_blocked']}")
    print('sade_sati:', result.get('sade_sati'))
    print('double_transit:', result.get('double_transit'))
    print('ashtama:', result.get('ashtama_gochara'))
