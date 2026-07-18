"""
tajaka_pyjhora.py — Tajaka (Varshaphal / Solar Return) annual chart
Computes the solar return moment for current and next year, then derives:
  - Annual Lagna at that moment
  - Muntha position (annual indicator)
  - Annual planet positions
  - Year lord (lord of annual Lagna sign)

Uses swisseph directly (Lahiri sidereal), matching engine.py conventions.
"""

import swisseph as swe
from datetime import datetime, timezone
import pytz

# ── Constants (mirrored from engine.py) ──────────────────────────────────────

SIGNS = [
    'Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
    'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces'
]

SIGN_LORDS = {
    0: 'Mars',    1: 'Venus',   2: 'Mercury', 3: 'Moon',
    4: 'Sun',     5: 'Mercury', 6: 'Venus',   7: 'Mars',
    8: 'Jupiter', 9: 'Saturn', 10: 'Saturn', 11: 'Jupiter'
}

PLANETS_SWE = {
    'Sun':     swe.SUN,
    'Moon':    swe.MOON,
    'Mars':    swe.MARS,
    'Mercury': swe.MERCURY,
    'Jupiter': swe.JUPITER,
    'Venus':   swe.VENUS,
    'Saturn':  swe.SATURN,
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _to_jd(year, month, day, hour, minute, tz_str):
    """Local datetime → Julian Day (UT)."""
    tz = pytz.timezone(tz_str)
    local_dt = tz.localize(datetime(year, month, day, hour, minute))
    utc_dt = local_dt.astimezone(pytz.utc)
    ut_hour = utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0
    return swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, ut_hour)


def _sun_sidereal_lon(jd):
    """Return sidereal Sun longitude at JD (Lahiri)."""
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    flags = swe.FLG_SIDEREAL | swe.FLG_SPEED
    result = swe.calc_ut(jd, swe.SUN, flags)
    return result[0][0]  # 0–360


def _angle_diff(target, current):
    """Signed shortest arc from current to target (degrees, range -180..+180)."""
    diff = (target - current) % 360.0
    if diff > 180.0:
        diff -= 360.0
    return diff


def _find_solar_return_jd(birth_sun_lon, search_year):
    """
    Binary-search the JD when the sidereal Sun longitude equals birth_sun_lon,
    within the 365-day window starting Jan 1 of search_year (UTC).

    Returns JD (float).
    Tolerance: < 0.001 degrees.
    """
    swe.set_sid_mode(swe.SIDM_LAHIRI)

    # Start of search window: Jan 1 00:00 UTC of search_year
    jd_start = swe.julday(search_year, 1, 1, 0.0)
    jd_end = jd_start + 366.0  # slightly over a year to be safe

    # Walk forward in ~1-day steps until we bracket the return
    # Sun moves ~1°/day; we need the crossing point.
    step = 1.0
    jd_lo = jd_start
    lon_lo = _sun_sidereal_lon(jd_lo)

    # Normalise target relative to lo so we track a monotone function
    # diff(lo) = angular distance still to travel (positive forward)
    def remaining(jd):
        lon = _sun_sidereal_lon(jd)
        return _angle_diff(birth_sun_lon, lon)   # positive = target ahead

    # Find bracket where remaining flips sign (crosses zero)
    jd_a = jd_lo
    rem_a = remaining(jd_a)

    found_bracket = False
    for _ in range(400):
        jd_b = jd_a + step
        if jd_b > jd_end:
            break
        rem_b = remaining(jd_b)
        # Sign change (or exact zero)
        if rem_a * rem_b <= 0:
            found_bracket = True
            break
        jd_a, rem_a = jd_b, rem_b

    if not found_bracket:
        # Fallback: search second half of window (handles edge cases near
        # year boundary where Sun crosses 0° Aries / 360° wrap)
        jd_a = jd_start + 180.0
        rem_a = remaining(jd_a)
        for _ in range(200):
            jd_b = jd_a + step
            if jd_b > jd_end:
                break
            rem_b = remaining(jd_b)
            if rem_a * rem_b <= 0:
                found_bracket = True
                break
            jd_a, rem_a = jd_b, rem_b

    if not found_bracket:
        raise ValueError(
            f"Could not find solar return bracket in {search_year} "
            f"for birth Sun longitude {birth_sun_lon:.4f}°"
        )

    # Binary search within [jd_a, jd_b]
    for _ in range(60):
        jd_mid = (jd_a + jd_b) / 2.0
        rem_mid = remaining(jd_mid)
        if abs(rem_mid) < 0.0001:
            return jd_mid
        if rem_a * rem_mid <= 0:
            jd_b = jd_mid
        else:
            jd_a = jd_mid
            rem_a = rem_mid

    return (jd_a + jd_b) / 2.0


def _jd_to_date_str(jd, tz_str):
    """Convert JD to 'YYYY-MM-DD' in the given timezone."""
    tz = pytz.timezone(tz_str)
    # swe.revjul returns (year, month, day, hour_float) in UT
    y, m, d, hf = swe.revjul(jd)
    # Build UTC datetime then convert
    h = int(hf)
    mins = int((hf - h) * 60)
    secs = int(((hf - h) * 60 - mins) * 60)
    utc_dt = datetime(y, m, d, h, mins, secs, tzinfo=pytz.utc)
    local_dt = utc_dt.astimezone(tz)
    return local_dt.strftime('%Y-%m-%d')


def _calc_annual_lagna(jd, lat, lon_deg):
    """Compute sidereal Lagna (Ascendant) at JD for given location."""
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    flags = swe.FLG_SIDEREAL
    cusps, ascmc = swe.houses_ex(jd, lat, lon_deg, b'W', flags)
    asc_lon = ascmc[0]
    sign_idx = int(asc_lon / 30)
    degree = asc_lon % 30
    deg_int = int(degree)
    min_int = round((degree - deg_int) * 60)
    return {
        'longitude': asc_lon,
        'sign': SIGNS[sign_idx],
        'sign_idx': sign_idx,
        'degree': degree,
        'deg_str': f"{deg_int}°{min_int:02d}'",
    }


def _calc_annual_planets(jd, annual_lagna_sign_idx):
    """Calculate all 9 planet positions at solar return JD."""
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    flags = swe.FLG_SIDEREAL | swe.FLG_SPEED
    planets = {}

    for name, pid in PLANETS_SWE.items():
        result = swe.calc_ut(jd, pid, flags)
        lon = result[0][0]
        speed = result[0][3]
        sign_idx = int(lon / 30)
        degree = lon % 30
        deg_int = int(degree)
        min_int = round((degree - deg_int) * 60)
        house = ((sign_idx - annual_lagna_sign_idx) % 12) + 1
        planets[name] = {
            'sign': SIGNS[sign_idx],
            'sign_idx': sign_idx,
            'degree': degree,
            'deg_str': f"{deg_int}°{min_int:02d}'",
            'house': house,
            'retrograde': speed < 0,
        }

    # Rahu (Mean Node) and Ketu
    result = swe.calc_ut(jd, swe.MEAN_NODE, flags)
    rahu_lon = result[0][0]
    rahu_sign_idx = int(rahu_lon / 30)
    rahu_deg = rahu_lon % 30
    planets['Rahu'] = {
        'sign': SIGNS[rahu_sign_idx],
        'sign_idx': rahu_sign_idx,
        'degree': rahu_deg,
        'deg_str': f"{int(rahu_deg)}°{round((rahu_deg % 1) * 60):02d}'",
        'house': ((rahu_sign_idx - annual_lagna_sign_idx) % 12) + 1,
        'retrograde': True,
    }
    ketu_lon = (rahu_lon + 180) % 360
    ketu_sign_idx = int(ketu_lon / 30)
    ketu_deg = ketu_lon % 30
    planets['Ketu'] = {
        'sign': SIGNS[ketu_sign_idx],
        'sign_idx': ketu_sign_idx,
        'degree': ketu_deg,
        'deg_str': f"{int(ketu_deg)}°{round((ketu_deg % 1) * 60):02d}'",
        'house': ((ketu_sign_idx - annual_lagna_sign_idx) % 12) + 1,
        'retrograde': True,
    }

    return planets


def _build_annual_chart(solar_return_jd, birth_lagna_sign_idx,
                        years_elapsed, lat, lon_deg, tz_str, year_int):
    """
    Build one annual chart dict from the solar return JD.

    years_elapsed: how many solar returns have occurred since birth year
                   (0 = first birthday / year of birth, 1 = first full year, …)
    """
    # Annual Lagna
    annual_lagna = _calc_annual_lagna(solar_return_jd, lat, lon_deg)
    annual_lagna_sign_idx = annual_lagna['sign_idx']

    # Muntha: starts from birth Lagna sign, advances one sign per year
    muntha_sign_idx = (birth_lagna_sign_idx + years_elapsed) % 12
    muntha_house = ((muntha_sign_idx - annual_lagna_sign_idx) % 12) + 1

    # Annual planets
    planets = _calc_annual_planets(solar_return_jd, annual_lagna_sign_idx)

    # Year lord = lord of annual Lagna sign
    year_lord = SIGN_LORDS[annual_lagna_sign_idx]

    return {
        'year': year_int,
        'solar_return_date': _jd_to_date_str(solar_return_jd, tz_str),
        'annual_lagna': {
            'sign': annual_lagna['sign'],
            'sign_idx': annual_lagna_sign_idx,
            'deg_str': annual_lagna['deg_str'],
        },
        'muntha': {
            'sign': SIGNS[muntha_sign_idx],
            'sign_idx': muntha_sign_idx,
            'house': muntha_house,
        },
        'planets': planets,
        'year_lord': year_lord,
    }


# ── Public API ────────────────────────────────────────────────────────────────

def calculate_tajaka(year, month, day, hour, minute, lat, lon, tz_str='Asia/Shanghai',
                     reference_date=None):
    """
    Returns Tajaka (Solar Return) chart for current and next year.

    Parameters
    ----------
    reference_date : datetime | None
        基准日期，决定"当年"是哪一年。None → datetime.now()。

    Parameters
    ----------
    year, month, day, hour, minute : birth date/time (local)
    lat, lon : geographic coordinates (float)
    tz_str   : IANA timezone string, default 'Asia/Shanghai'

    Returns
    -------
    {
      'current_year': {
        'year': int,
        'solar_return_date': 'YYYY-MM-DD',
        'annual_lagna': {'sign': str, 'sign_idx': int, 'deg_str': str},
        'muntha': {'sign': str, 'sign_idx': int, 'house': int},
        'planets': {name: {'sign': str, 'sign_idx': int, 'house': int,
                           'degree': float, 'deg_str': str, 'retrograde': bool}},
        'year_lord': str,
      },
      'next_year': { ... same structure ... }
    }
    On error: {'error': str}
    """
    try:
        swe.set_sid_mode(swe.SIDM_LAHIRI)

        # Birth JD and Sun longitude
        birth_jd = _to_jd(year, month, day, hour, minute, tz_str)
        birth_sun_lon = _sun_sidereal_lon(birth_jd)

        # Birth Lagna
        birth_lagna = _calc_annual_lagna(birth_jd, lat, lon)
        birth_lagna_sign_idx = birth_lagna['sign_idx']

        # 基准日期（决定"当年"是哪一年）— reference_date 参数化
        _now_dt = reference_date if reference_date is not None else datetime.now()
        today_year = _now_dt.year

        # years_elapsed for current year:
        #   how many solar returns since birth year up to today_year
        current_years_elapsed = today_year - year

        # Find solar return JDs
        sr_jd_current = _find_solar_return_jd(birth_sun_lon, today_year)
        sr_jd_next    = _find_solar_return_jd(birth_sun_lon, today_year + 1)

        current_chart = _build_annual_chart(
            sr_jd_current,
            birth_lagna_sign_idx,
            current_years_elapsed,
            lat, lon, tz_str,
            today_year,
        )
        next_chart = _build_annual_chart(
            sr_jd_next,
            birth_lagna_sign_idx,
            current_years_elapsed + 1,
            lat, lon, tz_str,
            today_year + 1,
        )

        return {
            'current_year': current_chart,
            'next_year': next_chart,
        }

    except Exception as e:
        return {'error': str(e)}


# ── Mudda Dasha (Varsha Vimsottari) ──────────────────────────────────────────

PLANET_ID_TO_NAME = {
    0: 'Sun', 1: 'Moon', 2: 'Mars', 3: 'Mercury',
    4: 'Jupiter', 5: 'Venus', 6: 'Saturn', 7: 'Rahu', 8: 'Ketu'
}


def _patch_jhora_drik():
    """
    Monkey-patch jhora's drik.sidereal_longitude to handle swisseph >= 2.10
    which returns a 3-tuple (values, retflag, errmsg) instead of 2-tuple.
    Safe to call multiple times (checks if already patched).
    """
    from jhora.panchanga import drik as _drik
    from jhora import const as _const
    import swisseph as _swe

    if getattr(_drik, '_swe_patched', False):
        return

    _orig_sl = _drik.sidereal_longitude

    def _patched_sidereal_longitude(jd_utc, planet):
        if _const._TROPICAL_MODE:
            flags = _swe.FLG_SWIEPH + _swe.FLG_SPEED
        else:
            from jhora.panchanga.drik import PLANET_FLAGS
            flags = PLANET_FLAGS
        if planet == _const._KETU:
            result = _swe.calc_ut(jd_utc, _const._RAHU, flags=flags)
            longi = result[0]
            ketu_long = (longi[0] + 180) % 360
            return ketu_long
        else:
            result = _swe.calc_ut(jd_utc, planet, flags=flags)
            longi = result[0]
        from jhora import utils as _utils
        return _utils.norm360(longi[0])

    _drik.sidereal_longitude = _patched_sidereal_longitude
    _drik._swe_patched = True


def calculate_mudda_dasha(year, month, day, hour, minute, lat, lon, tz_str='Asia/Shanghai',
                          reference_date=None):
    """
    Calculate Mudda Dasha (Varsha Vimsottari) for the current solar year.

    Parameters
    ----------
    year, month, day, hour, minute : birth date/time (local)
    lat, lon : geographic coordinates (float)
    tz_str   : IANA timezone string, default 'Asia/Shanghai'

    Returns
    -------
    {
      'year': int,
      'solar_return_date': 'YYYY-MM-DD',
      'dashas': [{'planet':str,'start':'YYYY-MM-DD','end':'YYYY-MM-DD',
                  'days':float,'is_current':bool}],
      'current_period': str,
      'current_start': str,
      'current_end': str,
      'antardashas_current': [{'planets':'MD-AD','start':'YYYY-MM-DD',
                               'end':'YYYY-MM-DD','is_current':bool}],
    }
    On error: {'error': str}
    """
    try:
        # Apply swisseph compatibility patch before importing jhora dhasa modules
        _patch_jhora_drik()

        from jhora.horoscope.dhasa.annual import mudda
        from jhora import const as jhora_const
        from collections import namedtuple

        swe.set_sid_mode(swe.SIDM_LAHIRI)

        # Birth JD and solar longitude
        birth_jd = _to_jd(year, month, day, hour, minute, tz_str)
        birth_sun_lon = _sun_sidereal_lon(birth_jd)

        # Solar return JD for the reference year
        _now_dt = reference_date if reference_date is not None else datetime.now()
        today_year = _now_dt.year
        sr_jd = _find_solar_return_jd(birth_sun_lon, today_year)
        solar_return_date = _jd_to_date_str(sr_jd, tz_str)

        # Next solar return JD marks the end of the current solar year
        sr_jd_next = _find_solar_return_jd(birth_sun_lon, today_year + 1)
        solar_year_end_date = _jd_to_date_str(sr_jd_next, tz_str)

        # Build place namedtuple expected by jhora
        tz = pytz.timezone(tz_str)
        sr_y, sr_m, sr_d, sr_hf = swe.revjul(sr_jd)
        sr_h = int(sr_hf)
        sr_min_v = int((sr_hf - sr_h) * 60)
        utc_dt = datetime(sr_y, sr_m, sr_d, sr_h, sr_min_v, tzinfo=pytz.utc)
        local_dt = utc_dt.astimezone(tz)
        tz_offset_hours = local_dt.utcoffset().total_seconds() / 3600.0

        Place = namedtuple('Place', ['name', 'latitude', 'longitude', 'timezone'])
        place = Place('', lat, lon, tz_offset_hours)

        # Call mudda with years=0 (sr_jd IS the solar year start) and
        # MEAN_SIDEREAL_YEAR to avoid a broken jhora code path
        raw = mudda.varsha_vimsottari_dhasa_bhukthi(
            sr_jd, place, years=0,
            dhasa_duration_type=jhora_const.DHASA_YEAR_DURATION.MEAN_SIDEREAL_YEAR
        )

        if not raw:
            return {'error': 'mudda.varsha_vimsottari_dhasa_bhukthi returned empty list'}

        # ── Detect return format ──────────────────────────────────────────────
        # New jhora format: (md_idx, ad_idx, date_str, dur_days)  flat tuple
        # Old jhora format: ((md_idx, ad_idx), (y,m,d,h), dur_years)  nested
        first = raw[0]
        if isinstance(first[0], tuple):
            # Old format
            def _parse_entry(e):
                (md_idx, ad_idx), ymdhtz, dur = e
                y_v, m_v, d_v, h_v = ymdhtz
                date_str = f"{int(y_v):04d}-{int(m_v):02d}-{int(d_v):02d}"
                return md_idx, ad_idx, date_str, dur
        else:
            # New format: e[0]=md_idx, e[1]=ad_idx, e[2]=date_str, e[3]=dur_days
            def _parse_entry(e):
                md_idx = e[0]
                ad_idx = e[1]
                # date_str may be 'YYYY-MM-DD HH:MM:SS AM/PM' — take first 10 chars
                date_str = str(e[2])[:10]
                dur = e[3]
                return md_idx, ad_idx, date_str, dur

        parsed = [_parse_entry(e) for e in raw]
        today_str = datetime.now().strftime('%Y-%m-%d')

        # ── Group by md_idx ───────────────────────────────────────────────────
        seen_md = []
        md_groups = {}
        for md_idx, ad_idx, date_str, dur in parsed:
            if md_idx not in seen_md:
                seen_md.append(md_idx)
                md_groups[md_idx] = []
            md_groups[md_idx].append((md_idx, ad_idx, date_str, dur))

        # ── Build main dasha list ─────────────────────────────────────────────
        from datetime import date as _date

        dashas = []
        for i, md_idx in enumerate(seen_md):
            ads = md_groups[md_idx]
            start_str = ads[0][2]

            if i + 1 < len(seen_md):
                end_str = md_groups[seen_md[i + 1]][0][2]
            else:
                end_str = solar_year_end_date

            # Skip periods entirely outside the solar year window
            if end_str <= solar_return_date or start_str >= solar_year_end_date:
                continue

            display_start = max(start_str, solar_return_date)
            display_end = min(end_str, solar_year_end_date)

            try:
                days = (_date.fromisoformat(display_end) - _date.fromisoformat(display_start)).days
            except Exception:
                days = 0

            planet_name = PLANET_ID_TO_NAME.get(md_idx, str(md_idx))
            is_current = display_start <= today_str < display_end

            dashas.append({
                'planet': planet_name,
                'start': display_start,
                'end': display_end,
                'days': float(days),
                'is_current': is_current,
            })

        # ── Find current main dasha ───────────────────────────────────────────
        current_dasha = next((d for d in dashas if d['is_current']), None)
        if current_dasha is None and dashas:
            current_dasha = dashas[-1]

        current_period = current_dasha['planet'] if current_dasha else ''
        current_start = current_dasha['start'] if current_dasha else ''
        current_end = current_dasha['end'] if current_dasha else ''

        # ── Build antardashas for the current main dasha ──────────────────────
        antardashas_current = []
        if current_dasha:
            current_md_idx = None
            for md_idx in seen_md:
                if PLANET_ID_TO_NAME.get(md_idx, str(md_idx)) == current_period:
                    current_md_idx = md_idx
                    break

            if current_md_idx is not None:
                ads = md_groups[current_md_idx]
                md_pos = seen_md.index(current_md_idx)

                for j, (_, ad_idx, ad_start_str, _dur) in enumerate(ads):
                    if j + 1 < len(ads):
                        ad_end_str = ads[j + 1][2]
                    else:
                        if md_pos + 1 < len(seen_md):
                            ad_end_str = md_groups[seen_md[md_pos + 1]][0][2]
                        else:
                            ad_end_str = solar_year_end_date

                    ad_planet = PLANET_ID_TO_NAME.get(ad_idx, str(ad_idx))
                    ad_is_current = ad_start_str <= today_str < ad_end_str

                    antardashas_current.append({
                        'planets': f"{current_period}-{ad_planet}",
                        'start': ad_start_str,
                        'end': ad_end_str,
                        'is_current': ad_is_current,
                    })

        return {
            'year': today_year,
            'solar_return_date': solar_return_date,
            'dashas': dashas,
            'current_period': current_period,
            'current_start': current_start,
            'current_end': current_end,
            'antardashas_current': antardashas_current,
        }

    except Exception as e:
        import traceback
        return {'error': str(e), 'traceback': traceback.format_exc()}
