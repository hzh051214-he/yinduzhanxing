"""
panchanga_pyjhora — 五要素 Panchanga 计算
==========================================
吠陀占星的五大时间要素：
  Tithi      — 月相日（阴历日期，1-30）
  Vara       — 星期（1=日 7=土）
  Nakshatra  — 当日月亮星宿（1-27）
  Yoga       — 日月合度（1-27）
  Karana     — 半日（1-60）

还包括三类 Muhurta 吉凶时段：
  Abhijit    — 当日最吉时段（正午附近约1小时）
  Amrit Kalam— 甘露吉时（每日2段）
  Rahu Kala  — 罗睺凶时（需避免重要行动）
  Gulika Kala— 土卡凶时
  Durmuhurta — 其他凶时段（与 Abhijit 同一时段但代表标准值）

对外接口：
  calculate_panchanga(year, month, day, hour, minute, lat, lon, tz_str)
  → 返回完整的当日 Panchanga 数据，供 formatter 渲染和 AI 使用
"""

import swisseph as swe
from datetime import datetime, timedelta
import pytz

from _pyjhora_base import build_jd_place, _silence_stdout, SIGNS

# Tithi 名称（1-30）
TITHI_NAMES = [
    'Pratipada', 'Dwitiya', 'Tritiya', 'Chaturthi', 'Panchami',
    'Shashthi', 'Saptami', 'Ashtami', 'Navami', 'Dashami',
    'Ekadashi', 'Dwadashi', 'Trayodashi', 'Chaturdashi', 'Purnima/Amavasya',
    'Pratipada', 'Dwitiya', 'Tritiya', 'Chaturthi', 'Panchami',
    'Shashthi', 'Saptami', 'Ashtami', 'Navami', 'Dashami',
    'Ekadashi', 'Dwadashi', 'Trayodashi', 'Chaturdashi', 'Amavasya'
]
TITHI_PAKSHA = ['शुक्ल(盈月)'] * 15 + ['कृष्ण(亏月)'] * 15

# Vara (weekday) 名称
VARA_NAMES = {
    0: '日曜(Sunday, 太阳)', 1: '月曜(Monday, 月亮)',
    2: '火曜(Tuesday, 火星)', 3: '水曜(Wednesday, 水星)',
    4: '木曜(Thursday, 木星)', 5: '金曜(Friday, 金星)',
    6: '土曜(Saturday, 土星)',
}

# Nakshatra 名称（1-27）
NAKSHATRA_NAMES = [
    'Ashwini', 'Bharani', 'Krittika', 'Rohini', 'Mrigashira', 'Ardra',
    'Punarvasu', 'Pushya', 'Ashlesha', 'Magha', 'Purva Phalguni', 'Uttara Phalguni',
    'Hasta', 'Chitra', 'Swati', 'Vishakha', 'Anuradha', 'Jyeshtha',
    'Moola', 'Purva Ashadha', 'Uttara Ashadha', 'Shravana', 'Dhanishta',
    'Shatabhisha', 'Purva Bhadrapada', 'Uttara Bhadrapada', 'Revati'
]

# Yoga 名称（1-27）
YOGA_NAMES = [
    'Vishkambha', 'Priti', 'Ayushman', 'Saubhagya', 'Shobhana',
    'Atiganda', 'Sukarman', 'Dhriti', 'Shoola', 'Ganda',
    'Vriddhi', 'Dhruva', 'Vyaghata', 'Harshana', 'Vajra',
    'Siddhi', 'Vyatipata', 'Variyana', 'Parigha', 'Shiva',
    'Siddha', 'Sadhya', 'Shubha', 'Shukla', 'Brahma',
    'Indra', 'Vaidhriti'
]
YOGA_QUALITY = {
    'Vishkambha': '凶', 'Priti': '吉', 'Ayushman': '吉', 'Saubhagya': '吉',
    'Shobhana': '吉', 'Atiganda': '凶', 'Sukarman': '吉', 'Dhriti': '吉',
    'Shoola': '凶', 'Ganda': '凶', 'Vriddhi': '吉', 'Dhruva': '吉',
    'Vyaghata': '凶', 'Harshana': '吉', 'Vajra': '凶', 'Siddhi': '吉',
    'Vyatipata': '凶', 'Variyana': '吉', 'Parigha': '凶', 'Shiva': '吉',
    'Siddha': '吉', 'Sadhya': '吉', 'Shubha': '吉', 'Shukla': '吉',
    'Brahma': '吉', 'Indra': '吉', 'Vaidhriti': '凶'
}

# Karana 名称（前4固定 + 7循环×8）
KARANA_NAMES_FIXED = ['Kimstughna']
KARANA_NAMES_CYCLE = ['Bava', 'Balava', 'Kaulava', 'Taitila', 'Gara', 'Vanija', 'Vishti']
KARANA_QUALITY = {
    'Vishti': '凶（Bhadra，重要事务须避免）',
    'Kimstughna': '凶',
}

# Nakshatra 吉凶分类
NAKSHATRA_QUALITY = {
    'Rohini': '吉★★★', 'Mrigashira': '吉★★', 'Punarvasu': '吉★★★',
    'Pushya': '吉★★★', 'Hasta': '吉★★★', 'Chitra': '吉★★',
    'Swati': '吉★★', 'Anuradha': '吉★★', 'Shravana': '吉★★★',
    'Dhanishta': '吉★★', 'Shatabhisha': '中', 'Uttara Phalguni': '吉★★',
    'Uttara Ashadha': '吉★★', 'Uttara Bhadrapada': '吉★★',
    'Revati': '吉★★', 'Ashwini': '吉★★', 'Magha': '中',
    'Vishakha': '中', 'Purva Phalguni': '中', 'Purva Ashadha': '中',
    'Purva Bhadrapada': '中', 'Bharani': '凶', 'Krittika': '中',
    'Ardra': '凶', 'Ashlesha': '凶', 'Jyeshtha': '凶', 'Moola': '凶'
}


def _karana_name(karana_idx):
    """karana_idx 1-60 → 名称"""
    if karana_idx == 1:
        return 'Kimstughna'
    cycle_pos = (karana_idx - 2) % 7
    return KARANA_NAMES_CYCLE[cycle_pos]


def _to_jd_local(year, month, day, hour, minute, tz_str):
    tz = pytz.timezone(tz_str)
    local_dt = tz.localize(datetime(year, month, day, hour, minute))
    utc_dt = local_dt.astimezone(pytz.utc)
    ut_hour = utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0
    return swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, ut_hour)


def calculate_panchanga(year, month, day, hour, minute, lat, lon, tz_str='Asia/Shanghai'):
    """计算指定日期时刻的完整 Panchanga（五要素）+ 当日 Muhurta 吉凶时段。

    Returns:
      {
        'date': 'YYYY-MM-DD HH:MM',
        'tithi': {'number': int, 'name': str, 'paksha': str, 'quality': str},
        'vara': {'number': int, 'name': str, 'ruler': str},
        'nakshatra': {'number': int, 'name': str, 'pada': int, 'quality': str},
        'yoga': {'number': int, 'name': str, 'quality': str},
        'karana': {'number': int, 'name': str, 'quality': str},
        'abhijit_muhurta': {'start': str, 'end': str},  # 最吉时段
        'amrit_kalam': [{'start': str, 'end': str}],    # 甘露吉时
        'rahu_kalam': {'start': str, 'end': str},        # 罗睺凶时
        'gulika_kalam': {'start': str, 'end': str},      # 土卡凶时
        'sunrise': str,
        'sunset': str,
        'overall_quality': str,  # 当日综合吉凶评估
      }
    """
    try:
        jd, place = build_jd_place(year, month, day, hour, minute, lat, lon,
                                    _tz_offset_from_str(tz_str, year, month, day, hour, minute))
        from jhora.panchanga import drik

        with _silence_stdout():
            # 1. Tithi
            ti_raw = drik.tithi(jd, place)
            ti_num = int(ti_raw[0])
            ti_name = TITHI_NAMES[ti_num - 1] if 1 <= ti_num <= 30 else '?'
            ti_paksha = TITHI_PAKSHA[ti_num - 1] if 1 <= ti_num <= 30 else '?'

            # 2. Vara (weekday)
            try:
                va_num = int(drik.vaara(jd, place))
            except Exception:
                va_num = datetime(year, month, day).weekday()  # 0=Mon
                va_num = (va_num + 1) % 7  # convert to Sun=0 scale
            va_info = VARA_NAMES.get(va_num, str(va_num))
            va_ruler = va_info.split('(')[-1].rstrip(')') if '(' in va_info else '?'

            # 3. Nakshatra
            na_raw = drik.nakshatra(jd, place)
            na_num = int(na_raw[0])
            na_pada = int(na_raw[1])
            na_name = NAKSHATRA_NAMES[na_num - 1] if 1 <= na_num <= 27 else '?'
            na_quality = NAKSHATRA_QUALITY.get(na_name, '中')

            # 4. Yoga
            yo_raw = drik.yogam(jd, place)
            yo_num = int(yo_raw[0])
            yo_name = YOGA_NAMES[yo_num - 1] if 1 <= yo_num <= 27 else '?'
            yo_quality = YOGA_QUALITY.get(yo_name, '中')

            # 5. Karana
            ka_raw = drik.karana(jd, place)
            ka_num = int(ka_raw[0])
            ka_name = _karana_name(ka_num)
            ka_quality = KARANA_QUALITY.get(ka_name, '中性')

            # Sunrise / Sunset
            sr_raw = drik.sunrise(jd, place)
            ss_raw = drik.sunset(jd, place)
            sr_str = sr_raw[1] if isinstance(sr_raw, (list, tuple)) and len(sr_raw) > 1 else str(sr_raw)
            ss_str = ss_raw[1] if isinstance(ss_raw, (list, tuple)) and len(ss_raw) > 1 else str(ss_raw)

            # Abhijit Muhurta (most auspicious window ~1hr around noon)
            ab_raw = drik.abhijit_muhurta(jd, place)
            ab = {'start': ab_raw[0], 'end': ab_raw[1]} if isinstance(ab_raw, (list, tuple)) and len(ab_raw) >= 2 else {}

            # Amrit Kalam
            ak_raw = drik.amrit_kaalam(jd, place)
            amrit = []
            if isinstance(ak_raw, (list, tuple)):
                for item in ak_raw:
                    if isinstance(item, (list, tuple)) and len(item) >= 2:
                        amrit.append({'start': item[0], 'end': item[1]})
                    elif isinstance(item, str):
                        amrit.append({'time': item})

            # Rahu Kalam (凶时，避免重要行动)
            rahu_raw = drik.gulikai_kaalam(jd, place)
            rahu_str = {'start': rahu_raw[0], 'end': rahu_raw[1]} if isinstance(rahu_raw, (list, tuple)) and len(rahu_raw) >= 2 else {}

            # Gulika Kalam
            gulika_raw = drik.gulikai_kaalam(jd, place)
            gulika_str = {'start': gulika_raw[0], 'end': gulika_raw[1]} if isinstance(gulika_raw, (list, tuple)) and len(gulika_raw) >= 2 else {}

        # 综合质量评估
        bad_count = sum([
            ti_name in ('Chaturdashi', 'Amavasya', 'Purnima/Amavasya'),
            yo_quality == '凶',
            ka_name == 'Vishti',
            na_quality.startswith('凶'),
        ])
        good_count = sum([
            yo_quality == '吉',
            na_quality.startswith('吉★★★'),
        ])
        if bad_count >= 2:
            overall = '凶日（建议避免重要行动）'
        elif bad_count == 1 and good_count == 0:
            overall = '偏凶（可正常行事，重大决策需谨慎）'
        elif good_count >= 2 and bad_count == 0:
            overall = '吉日★★（宜重要行动）'
        elif good_count >= 1 and bad_count == 0:
            overall = '吉日（宜一般行事）'
        else:
            overall = '普通（中性，无特别宜忌）'

        return {
            'date': f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}",
            'tithi': {'number': ti_num, 'name': ti_name, 'paksha': ti_paksha,
                      'quality': '吉' if ti_num not in (6, 8, 14, 30) else '凶'},
            'vara': {'number': va_num, 'name': va_info, 'ruler': va_ruler},
            'nakshatra': {'number': na_num, 'name': na_name, 'pada': na_pada, 'quality': na_quality},
            'yoga': {'number': yo_num, 'name': yo_name, 'quality': yo_quality},
            'karana': {'number': ka_num, 'name': ka_name, 'quality': ka_quality},
            'abhijit_muhurta': ab,
            'amrit_kalam': amrit,
            'rahu_kalam': rahu_str,
            'gulika_kalam': gulika_str,
            'sunrise': sr_str,
            'sunset': ss_str,
            'overall_quality': overall,
        }
    except Exception as e:
        return {'error': str(e)}


def find_eclipses_near(year, month, day, search_days=180):
    """查找指定日期前后各 search_days 天内的日蚀和月蚀。

    蚀日在吠陀占星择吉中是强制排除窗口：
      蚀日前后 2 周（14 天）= 高敏感窗口，不宜启动重要行动。
      原理：日蚀/月蚀时 Rahu/Ketu 正好合 Sun/Moon，
            业力节点能量被激活，结果不稳定且难以预测。

    使用 Swiss Ephemeris 精确计算，Lahiri Ayanamsa。
    返回：
      {
        'solar_eclipses':  [{'date': 'YYYY-MM-DD', 'type': str, 'blackout_start': str, 'blackout_end': str}, ...],
        'lunar_eclipses':  [{'date': 'YYYY-MM-DD', 'type': str, 'blackout_start': str, 'blackout_end': str}, ...],
        'in_blackout': bool,         # 今天是否在任意蚀日的 ±14 天窗口内
        'active_blackout': str|None, # 若在窗口内，描述原因（如"日蚀后 7 天"）
      }
    """
    from datetime import date, timedelta

    center_date = date(year, month, day)
    jd_start = swe.julday(year, month, day, 0.0)
    jd_search_back  = jd_start - search_days
    jd_search_end   = jd_start + search_days
    blackout_days = 14

    def _jd_to_date(jd):
        y, m, d, _ = swe.revjul(jd)
        return date(int(y), int(m), int(d))

    def _eclipse_type_label(ecl_type_flag, is_solar):
        """把 swe 返回的类型标志转为人话。"""
        if is_solar:
            if ecl_type_flag & swe.ECL_TOTAL:    return '日全食'
            if ecl_type_flag & swe.ECL_ANNULAR:  return '日环食'
            if ecl_type_flag & swe.ECL_HYBRID:   return '全环食'
            if ecl_type_flag & swe.ECL_PARTIAL:  return '日偏食'
            return '日蚀'
        else:
            if ecl_type_flag & swe.ECL_TOTAL:    return '月全食'
            if ecl_type_flag & swe.ECL_PARTIAL:  return '月偏食'
            if ecl_type_flag & swe.ECL_PENUMBRAL:return '半影月食'
            return '月蚀'

    solar_eclipses = []
    lunar_eclipses = []

    # 从搜索起点向后扫描
    try:
        jd_cur = jd_search_back
        while jd_cur < jd_search_end:
            # 日蚀
            ret = swe.sol_eclipse_when_glob(jd_cur, swe.FLG_SIDEREAL,
                                            swe.ECL_ALLTYPES_SOLAR, False)
            if ret[0] < 0:
                break
            ecl_type, ecl_times = ret[0], ret[1]
            jd_ecl = ecl_times[0]  # 最大蚀时刻
            if jd_ecl >= jd_search_end:
                break
            ecl_date = _jd_to_date(jd_ecl)
            bo_start = ecl_date - timedelta(days=blackout_days)
            bo_end   = ecl_date + timedelta(days=blackout_days)
            solar_eclipses.append({
                'date': str(ecl_date),
                'type': _eclipse_type_label(ecl_type, True),
                'blackout_start': str(bo_start),
                'blackout_end':   str(bo_end),
            })
            jd_cur = jd_ecl + 1.0  # 跳过当前蚀，继续搜索下一个

        jd_cur = jd_search_back
        while jd_cur < jd_search_end:
            # 月蚀
            ret = swe.lun_eclipse_when(jd_cur, swe.FLG_SIDEREAL,
                                       swe.ECL_ALLTYPES_LUNAR, False)
            if ret[0] < 0:
                break
            ecl_type, ecl_times = ret[0], ret[1]
            jd_ecl = ecl_times[0]
            if jd_ecl >= jd_search_end:
                break
            ecl_date = _jd_to_date(jd_ecl)
            bo_start = ecl_date - timedelta(days=blackout_days)
            bo_end   = ecl_date + timedelta(days=blackout_days)
            lunar_eclipses.append({
                'date': str(ecl_date),
                'type': _eclipse_type_label(ecl_type, False),
                'blackout_start': str(bo_start),
                'blackout_end':   str(bo_end),
            })
            jd_cur = jd_ecl + 1.0
    except Exception:
        pass  # 若 swe API 不支持则静默返回已收集的结果

    # 判断 center_date 是否在任意 blackout 窗口内
    in_blackout = False
    active_blackout = None
    for ecl in solar_eclipses + lunar_eclipses:
        bo_s = date.fromisoformat(ecl['blackout_start'])
        bo_e = date.fromisoformat(ecl['blackout_end'])
        if bo_s <= center_date <= bo_e:
            in_blackout = True
            ecl_d = date.fromisoformat(ecl['date'])
            delta = (center_date - ecl_d).days
            direction = f"前 {abs(delta)} 天" if delta < 0 else (f"后 {delta} 天" if delta > 0 else "当日")
            active_blackout = f"{ecl['type']}（{ecl['date']}）{direction}，仍在 ±{blackout_days} 天禁忌窗口内"
            break

    return {
        'solar_eclipses': solar_eclipses,
        'lunar_eclipses': lunar_eclipses,
        'in_blackout': in_blackout,
        'active_blackout': active_blackout,
    }


def _tz_offset_from_str(tz_str, year, month, day, hour, minute):
    """Convert tz_str to float offset hours."""
    try:
        tz = pytz.timezone(tz_str)
        dt = tz.localize(datetime(year, month, day, hour, minute))
        return dt.utcoffset().total_seconds() / 3600.0
    except Exception:
        return 8.0


if __name__ == '__main__':
    import sys
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    r = calculate_panchanga(2026, 7, 1, 12, 0, 31.2304, 121.4737, 'Asia/Shanghai')
    if 'error' in r:
        print('ERROR:', r['error'])
    else:
        print(f"日期: {r['date']}")
        print(f"Tithi: {r['tithi']['number']} {r['tithi']['name']} ({r['tithi']['paksha']})")
        print(f"Vara: {r['vara']['name']}")
        print(f"Nakshatra: {r['nakshatra']['name']} Pada{r['nakshatra']['pada']} [{r['nakshatra']['quality']}]")
        print(f"Yoga: {r['yoga']['name']} [{r['yoga']['quality']}]")
        print(f"Karana: {r['karana']['name']} [{r['karana']['quality']}]")
        print(f"日出: {r['sunrise']}  日落: {r['sunset']}")
        print(f"Abhijit: {r['abhijit_muhurta']}")
        print(f"Amrit Kalam: {r['amrit_kalam']}")
        print(f"Rahu Kala: {r['rahu_kalam']}")
        print(f"综合评估: {r['overall_quality']}")
