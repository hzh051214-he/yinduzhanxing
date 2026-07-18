"""
vedic-calculator v0.5 - PyJHora 精确计算引擎
基于 pysweph 天文核心 + PyJHora 精确算法（含 9 项 Shadbala bug 修正）
输出完整的 structured_data 所需数据

v0.5: 移除所有 dashaflow fallback（错误结果比无结果更糟），fail-fast
v0.4: Dasha 接入 PyJHora（≤2天）
v0.3: SAV/Shadbala fallback 显式 WARNING
"""
import swisseph as swe
from datetime import datetime, timedelta
import pytz
import json
import sys

# dashaflow — 仅用于 dignity/jaimini（这些无 PyJHora bug，不需要修正）
from dashaflow.dignity import get_dignity, get_compound_relationship, check_combustion, get_digbala
from dashaflow.jaimini import calculate_jaimini_karakas

# ── PyJHora 精确模块（必须全部加载，否则 fail-fast）──
_SETUP_HINT = (
    "\n╔══════════════════════════════════════════════════════╗\n"
    "║  PyJHora 未正确安装！请运行:                         ║\n"
    "║  python vedic-calculator/scripts/setup_env.py        ║\n"
    "╚══════════════════════════════════════════════════════╝"
)

_load_errors = []
try:
    from ashtakavarga_pyjhora import calculate_ashtakavarga_fixed as _av_pyjhora
except ImportError as e:
    _av_pyjhora = None
    _load_errors.append(f'ashtakavarga_pyjhora: {e}')
try:
    from shadbala_pyjhora import calculate_shadbala_fixed as _shadbala_pyjhora
except ImportError as e:
    _shadbala_pyjhora = None
    _load_errors.append(f'shadbala_pyjhora: {e}')
try:
    from dasha_pyjhora import calculate_dasha_fixed as _dasha_pyjhora
except ImportError as e:
    _dasha_pyjhora = None
    _load_errors.append(f'dasha_pyjhora: {e}')
try:
    from divisional_pyjhora import calculate_divisional_charts as _div_pyjhora
except ImportError as e:
    _div_pyjhora = None
    _load_errors.append(f'divisional_pyjhora: {e}')
try:
    from extras_pyjhora import (
        calculate_bhava_bala as _bhava_bala_pyjhora,
        calculate_special_lagnas as _special_lagnas_pyjhora,
        calculate_vargeeya_bala as _vargeeya_bala_pyjhora,
    )
except ImportError as e:
    _bhava_bala_pyjhora = None
    _special_lagnas_pyjhora = None
    _vargeeya_bala_pyjhora = None
    _load_errors.append(f'extras_pyjhora: {e}')

# Fail-fast: 核心模块必须全部加载
_REQUIRED = {'SAV': _av_pyjhora, 'Shadbala': _shadbala_pyjhora, 'Dasha': _dasha_pyjhora}
_missing = [name for name, mod in _REQUIRED.items() if mod is None]
if _missing:
    print(f"\n❌ FATAL: 以下核心模块加载失败: {', '.join(_missing)}", file=sys.stderr)
    for err in _load_errors:
        print(f"   → {err}", file=sys.stderr)
    print(_SETUP_HINT, file=sys.stderr)
    raise ImportError(f"vedic-calculator 核心模块缺失: {', '.join(_missing)}. 请运行 setup_env.py")

# === 配置 ===
swe.set_sid_mode(swe.SIDM_LAHIRI)

SIGNS = ['Aries','Taurus','Gemini','Cancer','Leo','Virgo',
         'Libra','Scorpio','Sagittarius','Capricorn','Aquarius','Pisces']
SIGN_ABBR = ['Ar','Ta','Ge','Cn','Le','Vi','Li','Sc','Sg','Cp','Aq','Pi']

PLANETS_SWE = {
    'Sun': swe.SUN, 'Moon': swe.MOON, 'Mars': swe.MARS,
    'Mercury': swe.MERCURY, 'Jupiter': swe.JUPITER,
    'Venus': swe.VENUS, 'Saturn': swe.SATURN
}

SIGN_LORDS = {
    0: 'Mars', 1: 'Venus', 2: 'Mercury', 3: 'Moon',
    4: 'Sun', 5: 'Mercury', 6: 'Venus', 7: 'Mars',
    8: 'Jupiter', 9: 'Saturn', 10: 'Saturn', 11: 'Jupiter'
}

NAKSHATRAS = [
    ('Ashwini','Ketu'), ('Bharani','Venus'), ('Krittika','Sun'),
    ('Rohini','Moon'), ('Mrigashira','Mars'), ('Ardra','Rahu'),
    ('Punarvasu','Jupiter'), ('Pushya','Saturn'), ('Ashlesha','Mercury'),
    ('Magha','Ketu'), ('Purva Phalguni','Venus'), ('Uttara Phalguni','Sun'),
    ('Hasta','Moon'), ('Chitra','Mars'), ('Swati','Rahu'),
    ('Vishakha','Jupiter'), ('Anuradha','Saturn'), ('Jyeshtha','Mercury'),
    ('Moola','Ketu'), ('Purva Ashadha','Venus'), ('Uttara Ashadha','Sun'),
    ('Shravana','Moon'), ('Dhanishta','Mars'), ('Shatabhisha','Rahu'),
    ('Purva Bhadrapada','Jupiter'), ('Uttara Bhadrapada','Saturn'), ('Revati','Mercury')
]

DASHA_ORDER = ['Ketu','Venus','Sun','Moon','Mars','Rahu','Jupiter','Saturn','Mercury']
DASHA_YEARS = {'Ketu':7,'Venus':20,'Sun':6,'Moon':10,'Mars':7,'Rahu':18,'Jupiter':16,'Saturn':19,'Mercury':17}

HOUSE_DOMAINS = {
    1:'自我', 2:'财富', 3:'兄弟', 4:'家庭', 5:'子女',
    6:'疾病', 7:'婚姻', 8:'变故', 9:'运势', 10:'事业',
    11:'收入', 12:'损耗'
}

# === 核心计算函数 ===

def to_jd(year, month, day, hour, minute, tz_str):
    tz = pytz.timezone(tz_str)
    local_dt = tz.localize(datetime(year, month, day, hour, minute))
    utc_dt = local_dt.astimezone(pytz.utc)
    ut_hour = utc_dt.hour + utc_dt.minute/60.0 + utc_dt.second/3600.0
    return swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, ut_hour)

def calc_planet(jd, planet_id):
    flags = swe.FLG_SIDEREAL | swe.FLG_SPEED
    result = swe.calc_ut(jd, planet_id, flags)
    lon = result[0][0]
    speed = result[0][3]
    sign_idx = int(lon / 30)
    degree = lon % 30
    deg_int = int(degree)
    min_int = round((degree - deg_int) * 60)
    return {
        'longitude': lon, 'sign': SIGNS[sign_idx], 'sign_idx': sign_idx,
        'degree': degree, 'deg_str': f"{deg_int}°{min_int:02d}'",
        'retrograde': speed < 0, 'speed': speed
    }

def calc_lagna(jd, lat, lon):
    flags = swe.FLG_SIDEREAL
    cusps, ascmc = swe.houses_ex(jd, lat, lon, b'W', flags)
    asc_lon = ascmc[0]
    sign_idx = int(asc_lon / 30)
    degree = asc_lon % 30
    deg_int = int(degree)
    min_int = round((degree - deg_int) * 60)
    return {
        'longitude': asc_lon, 'sign': SIGNS[sign_idx], 'sign_idx': sign_idx,
        'degree': degree, 'deg_str': f"{deg_int}°{min_int:02d}'"
    }

def get_nakshatra(longitude):
    nak_idx = int(longitude / (360/27))
    pada = int((longitude % (360/27)) / (360/108)) + 1
    name, lord = NAKSHATRAS[nak_idx]
    return {'name': name, 'pada': pada, 'lord': lord}

def get_house(planet_sign_idx, lagna_sign_idx):
    return ((planet_sign_idx - lagna_sign_idx) % 12) + 1

def calc_bhava_chalit(planet_lon, lagna_lon):
    """宫始盘（Bhava Chalit）— KN Rao 等宫制。

    整宫制(Rāśi)按星座算宫；宫始盘按 Lagna 精确度数居中划宫：
    第1宫 = [Lagna度数 - 15°, Lagna度数 + 15°)，其余宫位每 30° 递推。
    当行星靠近星座边界时，两套宫位可能不同 —— 这是判断行星"真实宫位归属"的关键。
    返回 1-12 的宫位号。
    """
    diff = (planet_lon - lagna_lon) % 360
    # 落在 [-15°, +15°) 为 1 宫，[15°,45°) 为 2 宫 ...
    return int(((diff + 15) % 360) / 30) + 1

def calc_navamsha(longitude):
    """D9 Navamsha: each sign divided into 9 parts of 3°20'"""
    nav_part = int((longitude % 30) / (30/9))
    sign_idx = int(longitude / 30)
    # Navamsha starts from: Fire→Ar, Earth→Cp, Air→Li, Water→Cn
    element_start = [0, 9, 6, 3]  # Ar, Cp, Li, Cn
    element = sign_idx % 4  # 0=fire, 1=earth, 2=air, 3=water
    d9_sign_idx = (element_start[element] + nav_part) % 12
    return SIGNS[d9_sign_idx], d9_sign_idx

def calc_dashamsha(longitude):
    """D10 Dashamsha: each sign divided into 10 parts of 3°
    Odd signs: count from same sign
    Even signs: count from 9th sign (= +8 in 0-indexed)
    """
    part = int((longitude % 30) / 3)
    sign_idx = int(longitude / 30)
    if sign_idx % 2 == 0:  # Odd signs (Ar, Ge, Le...)
        d10_sign_idx = (sign_idx + part) % 12
    else:  # Even signs: 9th from sign = +8 (0-indexed)
        d10_sign_idx = (sign_idx + part + 8) % 12
    return SIGNS[d10_sign_idx], d10_sign_idx

def calc_chaturthamsha(longitude):
    """D4"""
    part = int((longitude % 30) / (30/4))
    sign_idx = int(longitude / 30)
    d4_sign_idx = (sign_idx + part * 3) % 12
    return SIGNS[d4_sign_idx], d4_sign_idx

def calc_panchamsha(longitude):
    """D5 Panchamsha: each sign divided into 5 parts of 6°
    BPHS lords:
      Odd signs:  Mars(Ar), Saturn(Aq), Jupiter(Sg), Mercury(Ge), Venus(Li)
      Even signs: Venus(Ta), Mercury(Vi), Jupiter(Pi), Saturn(Cp), Mars(Sc)
    """
    part = int((longitude % 30) / 6)
    sign_idx = int(longitude / 30)
    if sign_idx % 2 == 0:  # odd sign (0-indexed even = zodiac odd)
        starts = [0, 10, 8, 2, 6]    # Ar, Aq, Sg, Ge, Li
    else:  # even sign
        starts = [1, 5, 11, 9, 7]    # Ta, Vi, Pi, Cp, Sc
    d5_sign_idx = starts[part] if part < 5 else sign_idx
    return SIGNS[d5_sign_idx], d5_sign_idx

def calc_chara_karakas_7k8k(planets):
    """同时计算 7K 和 8K Chara Karaka 体系，输出 DK 争议检测结果。

    ── 体系说明 ────────────────────────────────────────────────────
    7K 体系（KN Rao / Parashara 原典）：
      行星：Sun Moon Mars Mercury Jupiter Venus Saturn（共 7 颗）
      Rahu 不参与排序。
      DK（配偶指示星）= 第 7 位（度数最小者）。
      KN Rao 明确使用此体系；是 Parashari 传统的正统立场。

    8K 体系（部分现代学者，如 K. N. Krishnamurti 旁系）：
      行星：上述 7 颗 + Rahu（有效度数 = 30° − 在座度数）
      共 8 颗，插入 PiK（父亲指示星）位，DK 降至第 8 位。
      Jagannatha Hora 软件默认此体系。

    ── 本系统的设计选择 ────────────────────────────────────────────
    主分析（core / love / career）使用 **8K** 表（`chart['karakas']['8k']`），
    原因：与主流软件（JHora）的输出对齐，方便用户 PDF 交叉验证。

    但同时保留 **7K** 计算（`chart['karakas']['7k']`），用于：
      1. DK 争议检测：若加入 Rahu 后第 7 位行星改变，则标注不一致
      2. 当 DK 不一致时，分析应优先用 7K-DK，并以 `dk_consistent` 字段告知 AI
      3. KN Rao 嫡传 Synastry 分析若需 7K-DK，可直接读取

    ── Rahu 有效度数计算 ────────────────────────────────────────────
    Rahu 始终逆行，其在星座内的"前进程度"从 30° 反算：
      有效度数 = 30 − (Rahu 在座度数)
    例：Rahu 在 Pisces 16° → 有效度数 = 30 − 16 = 14°
    """
    # Effective degree = degree in sign (for Rahu: 30 - degree)
    karaka_data = []
    for name in ['Sun','Moon','Mars','Mercury','Jupiter','Venus','Saturn']:
        karaka_data.append((name, planets[name]['degree']))

    # 7K: sort by degree descending, top 7（KN Rao 正统体系）
    sorted_7k = sorted(karaka_data, key=lambda x: x[1], reverse=True)
    karaka_names_7k = ['AK','AmK','BK','MK','PK','GK','DK']
    karakas_7k = [(karaka_names_7k[i], sorted_7k[i][0], sorted_7k[i][1])
                  for i in range(7)]

    # 8K: add Rahu（现代软件通用体系，与 JHora 对齐）
    rahu_eff_deg = 30 - planets['Rahu']['degree']
    karaka_data_8k = karaka_data + [('Rahu', rahu_eff_deg)]
    sorted_8k = sorted(karaka_data_8k, key=lambda x: x[1], reverse=True)
    karaka_names_8k = ['AK','AmK','BK','MK','PiK','PK','GK','DK']
    karakas_8k = [(karaka_names_8k[i], sorted_8k[i][0], sorted_8k[i][1])
                  for i in range(8)]

    # DK 争议检测：加入 Rahu 是否改变了第 7 位（DK 候选）
    # 注：8K 的 DK 是 sorted_8k[7]（第 8 位），7K 的 DK 是 sorted_7k[6]（第 7 位）
    # 争议检测比较的是"加入 Rahu 后第 7 位是否换人"（影响配偶指示星的候选行星池）
    dk_7k = karakas_7k[6][1]   # 7K 第 7 位行星（= 7K-DK）
    dk_8k = sorted_8k[6][0]    # 8K 第 7 位行星（Rahu 是否挤入前 7）
    dk_consistent = dk_7k == dk_8k

    return {
        '7k': karakas_7k,           # KN Rao 正统 7K
        '8k': karakas_8k,           # 现代 8K（主分析用）
        'dk_7k': dk_7k,             # 7K 配偶指示星
        'dk_8k': sorted_8k[7][0],   # 8K 真正的 DK（第 8 位）
        'dk_consistent': dk_consistent,  # False → DK 有争议，分析须注明
    }

# 吠陀整宫相位（Graha Drishti）— 全行星看第7宫，特殊行星额外相位
# 数值 = 从行星自身星座顺数的"宫位距离"（自身=1）
SPECIAL_DRISHTI = {
    'Sun':     [7],
    'Moon':    [7],
    'Mars':    [4, 7, 8],
    'Mercury': [7],
    'Jupiter': [5, 7, 9],
    'Venus':   [7],
    'Saturn':  [3, 7, 10],
    'Rahu':    [5, 7, 9],   # KN Rao 派：罗睺/计都投射 5/7/9
    'Ketu':    [5, 7, 9],
}

def _drishti_target_signs(planet, sign_idx):
    """返回该行星相位射中的星座 idx -> 相位类型(如 '7th') 的映射"""
    targets = {}
    for dist in SPECIAL_DRISHTI.get(planet, [7]):
        tgt = (sign_idx + dist - 1) % 12
        targets[tgt] = f"{dist}th"
    return targets

def calc_aspects(planets, lagna_sign_idx):
    """吠陀 graha drishti（整宫制，全相位，无容许度）。

    返回:
      aspects: 行星→行星的有向相位列表
        {p1(发出), p2(接收), type('合相'/'Nth'), degree_diff(参考)}
      house_aspects: {
        'by_house': {house_num(1-12): [发出相位的行星...]},
        'by_planet': {planet: [所相位宫位...]}
      }
    """
    names = ['Sun','Moon','Mars','Mercury','Jupiter','Venus','Saturn','Rahu','Ketu']

    # 行星 -> 行星
    aspects = []
    for p1 in names:
        s1 = planets[p1]['sign_idx']
        targets = _drishti_target_signs(p1, s1)
        for p2 in names:
            if p1 == p2:
                continue
            s2 = planets[p2]['sign_idx']
            diff = abs(planets[p1]['longitude'] - planets[p2]['longitude'])
            if diff > 180:
                diff = 360 - diff
            if s2 == s1:
                # 同星座 = 合相（Sun/Moon/Rahu/Ketu 也计合相）
                aspects.append({'p1': p1, 'p2': p2, 'type': '合相',
                                'degree_diff': round(diff, 2)})
            elif s2 in targets:
                aspects.append({'p1': p1, 'p2': p2, 'type': targets[s2],
                                'degree_diff': round(diff, 2)})

    # 行星 -> 宫位（从 Lagna 数的 1-12 宫）
    by_house = {h: [] for h in range(1, 13)}
    by_planet = {}
    for p in names:
        sidx = planets[p]['sign_idx']
        houses = []
        for tgt_sign, _typ in _drishti_target_signs(p, sidx).items():
            h = ((tgt_sign - lagna_sign_idx) % 12) + 1
            houses.append(h)
            by_house[h].append(p)
        by_planet[p] = sorted(houses)

    house_aspects = {'by_house': by_house, 'by_planet': by_planet}
    return aspects, house_aspects

def calc_house_lords(lagna_sign_idx):
    """Calculate house lord table"""
    lords = {}
    for house in range(1, 13):
        sign_idx = (lagna_sign_idx + house - 1) % 12
        lord = SIGN_LORDS[sign_idx]
        lords[house] = {'sign': SIGNS[sign_idx], 'lord': lord, 'domain': HOUSE_DOMAINS[house]}
    return lords

def calc_vimsottari_dasha(moon_lon, birth_year, birth_month, birth_day, birth_hour, birth_minute):
    """Calculate Vimsottari Dasha periods"""
    nak = get_nakshatra(moon_lon)
    nak_lord = nak['lord']
    start_idx = DASHA_ORDER.index(nak_lord)
    
    nak_span = 360/27
    elapsed_in_nak = moon_lon % nak_span
    remaining_fraction = 1 - (elapsed_in_nak / nak_span)
    
    birth_dt = datetime(birth_year, birth_month, birth_day, birth_hour, birth_minute)
    dashas = []
    # 第一个大运起始 = 出生日 - 已过大运年数（回溯到出生前）
    first_planet_years = DASHA_YEARS[DASHA_ORDER[start_idx]]
    elapsed_years = first_planet_years * (1 - remaining_fraction)
    current_dt = birth_dt - timedelta(days=elapsed_years * 365.25)
    
    for i in range(9):
        idx = (start_idx + i) % 9
        planet = DASHA_ORDER[idx]
        years = DASHA_YEARS[planet]
        days = years * 365.25
        end_dt = current_dt + timedelta(days=days)
        
        # Mark current
        now = datetime.now()
        is_current = current_dt <= now <= end_dt
        
        # Antardasha子期计算
        antardashas = []
        ad_start = current_dt
        for j in range(9):
            ad_idx = (idx + j) % 9
            ad_planet = DASHA_ORDER[ad_idx]
            ad_years = years * DASHA_YEARS[ad_planet] / 120
            ad_days = ad_years * 365.25
            ad_end = ad_start + timedelta(days=ad_days)
            ad_is_current = ad_start <= now <= ad_end
            antardashas.append({
                'planet': ad_planet,
                'start': ad_start.strftime('%Y-%m-%d'),
                'end': ad_end.strftime('%Y-%m-%d'),
                'is_current': ad_is_current
            })
            ad_start = ad_end
        
        dashas.append({
            'planet': planet,
            'start': current_dt.strftime('%Y-%m'),
            'end': end_dt.strftime('%Y-%m'),
            'years': round(years, 1),
            'is_current': is_current,
            'antardashas': antardashas
        })
        current_dt = end_dt
    
    return dashas

def calc_special_points(lagna, planets):
    """Calculate AL, UL and other special Jaimini points.
    Note: JHora may use different settings (Rahu/Ketu lord rules, dual-sign lords).
    Our implementation follows standard BPHS Jaimini method.
    """
    lagna_idx = lagna['sign_idx']
    
    def calc_arudha(house_num, lagna_idx):
        """Calculate Arudha Pada for a given house (BPHS standard)"""
        sign_idx = (lagna_idx + house_num - 1) % 12
        lord = SIGN_LORDS[sign_idx]
        lord_sign_idx = planets[lord]['sign_idx']
        # Count from house sign to lord (1-based: lord in same sign = 1st)
        dist = (lord_sign_idx - sign_idx) % 12
        # Arudha = same distance from lord's position
        arudha_idx = (lord_sign_idx + dist) % 12
        # BPHS Exception: arudha cannot be in 1st or 7th from house sign
        # If 1st → use 10th from house sign
        # If 7th → use 4th from house sign
        if arudha_idx == sign_idx:
            arudha_idx = (sign_idx + 9) % 12   # 10th from house sign
        elif arudha_idx == (sign_idx + 6) % 12:
            arudha_idx = (sign_idx + 3) % 12   # 4th from house sign
        return SIGNS[arudha_idx], arudha_idx
    
    al_sign, al_idx = calc_arudha(1, lagna_idx)
    al_house = get_house(al_idx, lagna_idx)
    
    ul_sign, ul_idx = calc_arudha(12, lagna_idx)
    ul_house = get_house(ul_idx, lagna_idx)
    
    return {
        'AL': {'sign': al_sign, 'sign_idx': al_idx, 'house': al_house},
        'UL': {'sign': ul_sign, 'sign_idx': ul_idx, 'house': ul_house},
    }


# 领域标签（与 engine 末尾 _DOMAINS 保持一致，供 Chara Lagna 判读复用）
_CL_DOMAINS = {1:'自我/体质',2:'财富/家庭财务',3:'兄弟/努力/短途',4:'家庭/居所/母亲',
               5:'子女/恋爱/创造',6:'疾病/竞争/服务',7:'婚姻/合伙',8:'变故/深度转化',
               9:'运势/高等教育/信仰',10:'事业/权威',11:'收入/社交/朋友',12:'损耗/灵性/海外'}


def calc_chara_lagna_reading(current_chara_sign_idx, natal_lagna_idx, planets, karakas, special_points):
    """以当前 Chara Dasha 主运星座为 Chara Lagna（变动上升）的正统 Jaimini 判读。

    Jaimini Chara Dasha 的标准做法：把正在运行的 Dasha Rasi 当作该时期的临时上升，
    再看关键指示点（Chara Karaka / AL / UL / 各宫主 / 宫内星）相对它落第几宫，
    从而判断"本大运真正激活的领域"。这与"Dasha Rasi 落本命第几宫"是互补的两个视角。

    返回 None 表示无当前 Chara 大运可读。
    """
    if current_chara_sign_idx is None:
        return None
    cl = int(current_chara_sign_idx)

    def house_from_cl(sign_idx):
        return ((int(sign_idx) - cl) % 12) + 1

    # 1) Chara Karaka 落宫（AK 灵魂 / AmK 事业 / DK 配偶 为最关键）
    kara_by_name = {}
    for _, pname, _deg in karakas.get('7k', []):
        kara_by_name.setdefault(pname, [])
    karaka_points = []
    for kname, pname, _deg in karakas.get('7k', []):
        p = planets.get(pname)
        if not p:
            continue
        h = house_from_cl(p['sign_idx'])
        karaka_points.append({
            'karaka': kname, 'planet': pname, 'sign': p['sign'],
            'house_from_cl': h, 'domain': _CL_DOMAINS.get(h, ''),
        })

    # 2) AL / UL 落宫（形象、配偶）
    special = []
    for tag, label in (('AL', 'Arudha Lagna(外在形象)'), ('UL', 'Upapada(婚姻)')):
        sp = special_points.get(tag)
        if sp:
            h = house_from_cl(sp['sign_idx'])
            special.append({
                'point': tag, 'label': label, 'sign': sp['sign'],
                'house_from_cl': h, 'domain': _CL_DOMAINS.get(h, ''),
            })

    # 3) 关键宫（1/5/7/10 from CL）的宫主落位 + 宫内星
    key_house_map = {1: '自身/本期主线', 5: '恋爱/创造/子女', 7: '婚姻/合伙', 10: '事业/地位'}
    key_houses = []
    for hnum, meaning in key_house_map.items():
        house_sign_idx = (cl + hnum - 1) % 12
        lord = SIGN_LORDS[house_sign_idx]
        lord_p = planets.get(lord)
        lord_house = house_from_cl(lord_p['sign_idx']) if lord_p else None
        # 宫内星（本命行星落在此 CL 宫）
        occupants = [pn for pn, pd in planets.items()
                     if pn in ('Sun', 'Moon', 'Mars', 'Mercury', 'Jupiter',
                               'Venus', 'Saturn', 'Rahu', 'Ketu')
                     and house_from_cl(pd['sign_idx']) == hnum]
        key_houses.append({
            'house_from_cl': hnum, 'meaning': meaning,
            'sign': SIGNS[house_sign_idx], 'lord': lord,
            'lord_in_house': lord_house, 'lord_domain': _CL_DOMAINS.get(lord_house, '') if lord_house else '',
            'occupants': occupants,
        })

    # 4) 领域激活提示：DK/UL 在角/三角宫，或 7 宫有吉星占据 → 婚姻主题活跃；AmK 强位 → 事业活跃
    notes = []
    dk_point = next((k for k in karaka_points if k['karaka'] == 'DK'), None)
    amk_point = next((k for k in karaka_points if k['karaka'] == 'AmK'), None)
    ak_point = next((k for k in karaka_points if k['karaka'] == 'AK'), None)
    ul_point = next((s for s in special if s['point'] == 'UL'), None)
    KENDRA_TRIKONA = {1, 4, 5, 7, 9, 10}
    if dk_point and dk_point['house_from_cl'] in KENDRA_TRIKONA:
        notes.append(f"DK({dk_point['planet']})落CL第{dk_point['house_from_cl']}宫(角/三角)——本期婚恋主题被点亮")
    if ul_point and ul_point['house_from_cl'] in KENDRA_TRIKONA:
        notes.append(f"UL落CL第{ul_point['house_from_cl']}宫(角/三角)——配偶宫环境活跃")
    seventh = next((h for h in key_houses if h['house_from_cl'] == 7), None)
    if seventh and seventh['occupants']:
        notes.append(f"CL第7宫({seventh['sign']})有{'/'.join(seventh['occupants'])}占据——合伙/婚姻能量集中")
    if amk_point and amk_point['house_from_cl'] in KENDRA_TRIKONA:
        notes.append(f"AmK({amk_point['planet']})落CL第{amk_point['house_from_cl']}宫(角/三角)——事业指示星有力")
    if ak_point and ak_point['house_from_cl'] == 1:
        notes.append(f"AK({ak_point['planet']})与CL同宫——灵魂主线与本期高度对齐")

    return {
        'chara_lagna_sign': SIGNS[cl],
        'chara_lagna_sign_idx': cl,
        'note': '以当前 Chara Dasha 主运星座为临时上升(Chara Lagna)，看关键点相对它落第几宫',
        'karaka_points': karaka_points,
        'special_points': special,
        'key_houses': key_houses,
        'activation_notes': notes,
    }

def calc_transits(lagna_sign_idx, moon_sign_idx):
    """Calculate current transit positions for slow planets.
    Used by core-pro for Sade Sati, BAV transit calibration, double transit.
    """
    now = datetime.now()
    jd_now = swe.julday(now.year, now.month, now.day, now.hour + now.minute/60)
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    flags = swe.FLG_SIDEREAL | swe.FLG_SPEED
    
    transits = {}
    # Slow planets: Saturn, Jupiter, Rahu, Ketu
    slow_planets = {'Saturn': swe.SATURN, 'Jupiter': swe.JUPITER}
    for name, pid in slow_planets.items():
        result = swe.calc_ut(jd_now, pid, flags)
        lon = result[0][0]
        sign_idx = int(lon / 30)
        house = get_house(sign_idx, lagna_sign_idx)
        transits[name] = {'sign': SIGNS[sign_idx], 'sign_idx': sign_idx, 'house': house}
    
    # Rahu (Mean Node)
    result = swe.calc_ut(jd_now, swe.MEAN_NODE, flags)
    rahu_lon = result[0][0]
    rahu_idx = int(rahu_lon / 30)
    transits['Rahu'] = {'sign': SIGNS[rahu_idx], 'sign_idx': rahu_idx, 
                        'house': get_house(rahu_idx, lagna_sign_idx)}
    ketu_idx = (rahu_idx + 6) % 12
    transits['Ketu'] = {'sign': SIGNS[ketu_idx], 'sign_idx': ketu_idx,
                        'house': get_house(ketu_idx, lagna_sign_idx)}
    
    # Sade Sati check
    saturn_idx = transits['Saturn']['sign_idx']
    sade_sati = 'inactive'
    if saturn_idx == (moon_sign_idx - 1) % 12:
        sade_sati = 'phase1_rising'
    elif saturn_idx == moon_sign_idx:
        sade_sati = 'phase2_peak'
    elif saturn_idx == (moon_sign_idx + 1) % 12:
        sade_sati = 'phase3_fading'
    transits['sade_sati'] = sade_sati
    
    # Double transit (Saturn-Jupiter intersection)
    sat_houses = {transits['Saturn']['house']}
    # Saturn aspects: 3rd, 7th, 10th
    sat_h = transits['Saturn']['house']
    for asp in [3, 7, 10]:
        sat_houses.add(((sat_h - 1 + asp - 1) % 12) + 1)
    
    jup_houses = {transits['Jupiter']['house']}
    # Jupiter aspects: 5th, 7th, 9th
    jup_h = transits['Jupiter']['house']
    for asp in [5, 7, 9]:
        jup_houses.add(((jup_h - 1 + asp - 1) % 12) + 1)
    
    double_transit = sorted(sat_houses & jup_houses)
    transits['double_transit_houses'] = double_transit
    transits['timestamp'] = now.strftime('%Y-%m-%d')
    
    return transits

# === 主计算函数 ===

def calculate_full_chart(year, month, day, hour, minute, lat, lon,
                          tz_str="Asia/Kolkata",
                          d60_trust_level="auto",
                          d60_consent=None,
                          time_precision_level=None,
                          reference_date=None):
    """计算完整星盘数据

    Parameters
    ----------
    reference_date : datetime | str | None
        分析基准日期，影响所有"当前时间"相关计算（过运、Panchanga、Mudda Dasha 等）。

        None       — 使用系统当前时间（默认行为）
        datetime   — 使用指定的 datetime 对象（需含时区或用 tz_str 补充）
        'YYYY-MM-DD' — 使用指定日期（取当天正午）

        用途示例：
          · 生成历史报告（已过去某日的过运状态）
          · 预先生成未来某日的 Panchanga
          · 让报告结果可复现（不随时间变化）
          · 'now' 或 None → 始终实时

        'auto'     — 根据校验结果自动推断（默认）
                     · d60_rake_ok=True 且 Ayanamsa 敏感行星≤3颗 → 'computed'
                     · 否则 → 'uncertain'
        'verified' — 用户已提供重大人生事件完成校验，D60 结论可大量引用
        'computed' — 计算通过基础校验，可有限参考（标注置信度中等）
        'uncertain'— 校验未通过或出生时间精度不足，仅展示数据不做推断
        'disabled' — 完全不参考 D60，数据不渲染入报告

        ⚠️ 'verified' 状态需要调用者记录已完成事件校验；此处不强制验证。

    d60_consent : bool | None
        用户知情同意状态（D60/D30 业力/逆境盘隐私告知后的选择）。

        None  — 未明确告知（默认）→ D60/D30 自动禁用
        True  — 用户已了解含义并同意分析 → 按 d60_trust_level 生效
        False — 用户明确拒绝 → D60/D30 均禁用

        ⚠️ 知情同意先于信任级别：即使 d60_trust_level='verified'，
           若 d60_consent=False/None，D60 仍不参与分析。
        ⚠️ 此参数由 calculator.md / reader.md 的 AI 对话流程收集后传入。

    time_precision_level : int | None
        出生时间精度等级（驱动高敏感分盘的可用性）：

        1 — 精确（精确到分钟，出生证明/医院记录）
        2 — 基本精确（±5分钟，可靠记忆）
        3 — 粗略（±15-30分钟）
        4 — 不确定（只知道上午/下午，或完全不知道）
        None — 未指定，等同于 2（保守估计）

        精度规则（优先于 d60_consent）：
        - Level 1-2：D60/D30 可以走同意流程
        - Level 3-4：D60/D30 强制禁用（不再询问同意，精度不足即无效）
        D9/D10/D4 在 Level 3-4 时加警告但不禁用（它们精度要求稍低）。
    """
    # ── 精度等级映射（来自 calculator.md Step1 的文字描述）──
    # 调用者也可直接传 int
    _PRECISION_TEXT_MAP = {
        '精确到分钟': 1, 'exact': 1,
        '±5分钟': 2, 'good': 2,
        '±15分钟': 3, '±30分钟': 3, 'approximate': 3,
        '不确定': 4, '只知道上午': 4, '只知道下午': 4, 'unknown': 4,
    }
    if isinstance(time_precision_level, str):
        time_precision_level = _PRECISION_TEXT_MAP.get(time_precision_level, 2)
    if time_precision_level is None:
        time_precision_level = 2   # 未指定 → 保守估计为"基本精确"

    # ── reference_date 解析（分析基准日期）──
    # None / 'now' → 实时；datetime → 直接用；'YYYY-MM-DD' → 解析为当天正午
    from datetime import datetime as _dt
    import pytz as _pytz
    if reference_date is None or reference_date == 'now':
        _ref_dt = None   # 各模块内部自行 datetime.now()
    elif isinstance(reference_date, str):
        try:
            _parsed = _dt.strptime(reference_date, '%Y-%m-%d')
            _ref_dt = _pytz.timezone(tz_str).localize(_parsed.replace(hour=12, minute=0))
        except ValueError:
            _ref_dt = None  # 解析失败 → 降级为实时
    elif isinstance(reference_date, _dt):
        _ref_dt = reference_date if reference_date.tzinfo else \
                  _pytz.timezone(tz_str).localize(reference_date)
    else:
        _ref_dt = None

    # ── 高敏感分盘精度拦截 ──
    # Level 3-4 下，D60/D30 无论同意与否都强制禁用
    _high_sensitivity_disabled_by_precision = (time_precision_level >= 3)
    if _high_sensitivity_disabled_by_precision:
        d60_trust_level = 'disabled'
        d60_consent = False   # 精度不足 → 视为不同意（跳过询问流程）

    # ── D60/D30 同意优先级拦截 ──
    # 精度足够但未明确同意 → 强制禁用
    if not _high_sensitivity_disabled_by_precision and d60_consent is not True:
        d60_trust_level = 'disabled'

    # 记录原始传入值，供 formatter 渲染
    _d60_consent_raw = d60_consent
    jd = to_jd(year, month, day, hour, minute, tz_str)
    ayanamsa = swe.get_ayanamsa_ut(jd)
    
    # 1. Lagna
    lagna = calc_lagna(jd, lat, lon)
    lagna['nakshatra'] = get_nakshatra(lagna['longitude'])
    lagna['house'] = 1
    
    # 2. Planets (7 main)
    planets = {}
    for name, pid in PLANETS_SWE.items():
        p = calc_planet(jd, pid)
        p['house'] = get_house(p['sign_idx'], lagna['sign_idx'])
        p['nakshatra'] = get_nakshatra(p['longitude'])
        planets[name] = p
    
    # 3. Rahu & Ketu
    flags = swe.FLG_SIDEREAL | swe.FLG_SPEED
    result = swe.calc_ut(jd, swe.MEAN_NODE, flags)
    rahu_lon = result[0][0]
    rahu_sign_idx = int(rahu_lon / 30)
    rahu_deg = rahu_lon % 30
    planets['Rahu'] = {
        'longitude': rahu_lon, 'sign': SIGNS[rahu_sign_idx],
        'sign_idx': rahu_sign_idx, 'degree': rahu_deg,
        'deg_str': f"{int(rahu_deg)}°{round((rahu_deg%1)*60):02d}'",
        'retrograde': True, 'speed': result[0][3],
        'house': get_house(rahu_sign_idx, lagna['sign_idx']),
        'nakshatra': get_nakshatra(rahu_lon)
    }
    ketu_lon = (rahu_lon + 180) % 360
    ketu_sign_idx = int(ketu_lon / 30)
    ketu_deg = ketu_lon % 30
    planets['Ketu'] = {
        'longitude': ketu_lon, 'sign': SIGNS[ketu_sign_idx],
        'sign_idx': ketu_sign_idx, 'degree': ketu_deg,
        'deg_str': f"{int(ketu_deg)}°{round((ketu_deg%1)*60):02d}'",
        'retrograde': True, 'speed': -result[0][3],
        'house': get_house(ketu_sign_idx, lagna['sign_idx']),
        'nakshatra': get_nakshatra(ketu_lon)
    }
    
    # 4. SAV/BAV (PyJHora — no fallback)
    tz = pytz.timezone(tz_str)
    _tz_dt = tz.localize(datetime(year, month, day, hour, minute))
    _tz_offset = _tz_dt.utcoffset().total_seconds() / 3600.0
    ashtak = _av_pyjhora(year, month, day, hour, minute, lat, lon, _tz_offset)
    
    # Map SAV to houses
    sav_by_house = {}
    for h in range(1, 13):
        sign_idx = (lagna['sign_idx'] + h - 1) % 12
        sign_name = SIGNS[sign_idx]
        sav_by_house[h] = {'sign': sign_name, 'value': ashtak['sarvashtakavarga'].get(sign_name, 0)}
    
    # 5. Divisional charts (PyJHora: 15 charts)
    if _div_pyjhora is not None:
        divisional_charts = _div_pyjhora(
            year, month, day, hour, minute, lat, lon, _tz_offset
        )
    else:
        divisional_charts = {}
    
    # Extract d9/d10/d4/d5/d60/d30 in legacy (sign_name, sign_idx) format for backward compat
    if divisional_charts:
        def _legacy_fmt(chart_key):
            ch = divisional_charts.get(chart_key, {})
            return {p: (ch[p]['sign'], ch[p]['sign_idx']) for p in ch if 'error' not in ch}
        d9  = _legacy_fmt('D9')
        d10 = _legacy_fmt('D10')
        d4  = _legacy_fmt('D4')
        d5  = _legacy_fmt('D5')
        d60 = _legacy_fmt('D60')
        d30 = _legacy_fmt('D30')   # D30 Trimsamsa 逆境盘
        d7  = _legacy_fmt('D7')    # D7 Saptamsa 子女盘
        d11 = _legacy_fmt('D11')   # D11 Ekadasamsha 深度转化盘（需知情同意）
    else:
        d9, d10, d4, d5, d60, d30, d7, d11 = {}, {}, {}, {}, {}, {}, {}, {}

    # D60 Ra-Ke 校验：D60(Shashtiamsa) 中 Ra/Ke 应为「对宫(180°)」。
    # 经多盘实测确认（非同宫）——因 Ra/Ke 相距 180°，而 180° mod 30°=0°，
    # 两者星座内度数相同 → D60 偏移相同 → 落座恒相差 6 宫。详见 validation_rules.md。
    if d60 and 'Rahu' in d60 and 'Ketu' in d60:
        d60_rake_ok = ((d60['Rahu'][1] - d60['Ketu'][1]) % 12) == 6
    else:
        d60_rake_ok = None

    # D30 Ra-Ke 校验
    # ⚠️ D30（BPHS Trimsamsa）使用奇偶星座不同起点的映射规则，
    # 对宫星座（差180°）在相同度数上会落入同一D30子星座，
    # 因此 Ra-Ke 在 D30 里必然同宫（差0），而非对宫（差6）。
    # 这是 BPHS D30 规则的数学特性，与 D60 的简单等分法不同。
    # 经5个独立测试盘验证（甘地/样本/测试A/B/C），D30 Ra-Ke 差值均为 0。
    if d30 and 'Rahu' in d30 and 'Ketu' in d30:
        d30_rake_ok = ((d30['Rahu'][1] - d30['Ketu'][1]) % 12) == 0   # D30规则：同宫=正确
    else:
        d30_rake_ok = None

    # D30 可信度：与 D60 完全相同逻辑（共享同一个 d60_consent 参数）
    # d60_trust_level 同时控制 D30，因为两者精度要求相近
    # d60_trust_resolved 稍后也作为 d30_trust_resolved 使用

    # D60 可信度：自动推断或用户手动指定
    _D60_TRUST_LEVELS = ('auto', 'verified', 'computed', 'uncertain', 'disabled')
    if d60_trust_level not in _D60_TRUST_LEVELS:
        d60_trust_level = 'auto'
    if d60_trust_level == 'auto':
        d60_trust_resolved = 'computed' if d60_rake_ok else 'uncertain'
        d30_trust_resolved = 'computed' if d30_rake_ok else 'uncertain'
    else:
        d60_trust_resolved = d60_trust_level
        d30_trust_resolved = d60_trust_level   # D30 与 D60 共用同意状态
    
    # Vargottama check
    vargottama = {}
    for name in planets:
        d9_sign = d9.get(name, (None, None))
        d9_sign_name = d9_sign[0] if isinstance(d9_sign, tuple) else d9_sign.get('sign', None) if isinstance(d9_sign, dict) else None
        vargottama[name] = planets[name]['sign'] == d9_sign_name
    
    # 6. Dignity & Compound Relationship (自建，不依赖dashaflow)
    # BPHS Panchadha Maitri 算法
    
    # Step 1: 旺/入庙/陷检测
    EXALTATION = {'Sun':'Aries','Moon':'Taurus','Mars':'Capricorn',
                  'Mercury':'Virgo','Jupiter':'Cancer','Venus':'Pisces','Saturn':'Libra'}
    DEBILITATION = {'Sun':'Libra','Moon':'Scorpio','Mars':'Cancer',
                    'Mercury':'Pisces','Jupiter':'Capricorn','Venus':'Virgo','Saturn':'Aries'}
    OWN_SIGNS = {'Sun':['Leo'],'Moon':['Cancer'],'Mars':['Aries','Scorpio'],
                 'Mercury':['Gemini','Virgo'],'Jupiter':['Sagittarius','Pisces'],
                 'Venus':['Taurus','Libra'],'Saturn':['Capricorn','Aquarius']}
    
    # Step 2: 自然关系表 (Naisargika Maitri) - BPHS标准
    NATURAL_REL = {
        'Sun':     {'friend':['Moon','Mars','Jupiter'], 'enemy':['Venus','Saturn'], 'neutral':['Mercury']},
        'Moon':    {'friend':['Sun','Mercury'], 'enemy':[], 'neutral':['Mars','Jupiter','Venus','Saturn']},
        'Mars':    {'friend':['Sun','Moon','Jupiter'], 'enemy':['Mercury'], 'neutral':['Venus','Saturn']},
        'Mercury': {'friend':['Sun','Venus'], 'enemy':['Moon'], 'neutral':['Mars','Jupiter','Saturn']},
        'Jupiter': {'friend':['Sun','Moon','Mars'], 'enemy':['Mercury','Venus'], 'neutral':['Saturn']},
        'Venus':   {'friend':['Mercury','Saturn'], 'enemy':['Sun','Moon'], 'neutral':['Mars','Jupiter']},
        'Saturn':  {'friend':['Mercury','Venus'], 'enemy':['Sun','Moon','Mars'], 'neutral':['Jupiter']},
    }
    
    def get_natural_rel(planet, lord):
        """查自然关系: friend/enemy/neutral"""
        if planet == lord:
            return 'own'
        rel = NATURAL_REL.get(planet, {})
        if lord in rel.get('friend', []): return 'friend'
        if lord in rel.get('enemy', []): return 'enemy'
        return 'neutral'
    
    def get_temporal_rel(planet_sign_idx, lord_sign_idx):
        """查临时关系: 座主落在行星的2/3/4/10/11/12宫=临时友"""
        dist = (lord_sign_idx - planet_sign_idx) % 12
        # 距离2,3,4,10,11,12宫 = dist值1,2,3,9,10,11 (0-indexed)
        return 'temp_friend' if dist in {1,2,3,9,10,11} else 'temp_enemy'
    
    # Step 4: Panchadha合成表
    COMPOUND_TABLE = {
        ('friend', 'temp_friend'):   'great_friend',
        ('friend', 'temp_enemy'):    'neutral',
        ('enemy',  'temp_friend'):   'neutral',
        ('enemy',  'temp_enemy'):    'great_enemy',
        ('neutral','temp_friend'):   'friend',
        ('neutral','temp_enemy'):    'enemy',
    }
    
    dignity_data = {}
    for name in ['Sun','Moon','Mars','Mercury','Jupiter','Venus','Saturn']:
        p = planets[name]
        sign = p['sign']
        lord = SIGN_LORDS[p['sign_idx']]
        
        # Step 1: 旺/入庙/陷直接确定
        if EXALTATION.get(name) == sign:
            compound = 'exalted'
        elif DEBILITATION.get(name) == sign:
            compound = 'debilitated'
        elif sign in OWN_SIGNS.get(name, []):
            compound = 'own_sign'
        else:
            # Step 2+3+4: 自然+临时→合成
            natural = get_natural_rel(name, lord)
            if natural == 'own':
                compound = 'own_sign'
            else:
                # 找座主的实际位置
                lord_sign_idx = planets[lord]['sign_idx'] if lord in planets else p['sign_idx']
                temporal = get_temporal_rel(p['sign_idx'], lord_sign_idx)
                compound = COMPOUND_TABLE.get((natural, temporal), 'neutral')
        
        dignity_data[name] = {'basic': compound, 'compound': compound}
    
    # 7. Combustion check
    sun_lon = planets['Sun']['longitude']
    combustion = {}
    for name in ['Moon','Mars','Mercury','Jupiter','Venus','Saturn']:
        is_retro = planets[name]['retrograde']
        comb_result = check_combustion(name, planets[name]['longitude'], sun_lon, is_retro)
        is_combust = comb_result if isinstance(comb_result, bool) else comb_result.get('is_combust', False)
        if is_combust:
            diff = abs(planets[name]['longitude'] - sun_lon)
            if diff > 180: diff = 360 - diff
            combustion[name] = {'distance': round(diff, 2)}
    
    # 8. Chara Karakas
    karakas = calc_chara_karakas_7k8k(planets)
    
    # 9. Aspects (吠陀 graha drishti)
    aspects, house_aspects = calc_aspects(planets, lagna['sign_idx'])
    
    # 10. House lords
    house_lords = calc_house_lords(lagna['sign_idx'])
    # Add planet positions to house lords
    for h, info in house_lords.items():
        planet = info['lord']
        if planet in planets:
            info['lord_house'] = planets[planet]['house']
    
    # 11. Vimsottari Dasha (PyJHora — no fallback)
    dashas = _dasha_pyjhora(year, month, day, hour, minute, lat, lon, _tz_offset,
                            reference_date=_ref_dt)
    
    # 12. Shadbala (PyJHora + 9 bug fixes — no fallback)
    shadbala_data = _shadbala_pyjhora(
        year, month, day, hour, minute, lat, lon, _tz_offset
    )
    
    # 13. Moon phase
    moon_sun_diff = (planets['Moon']['longitude'] - planets['Sun']['longitude']) % 360
    is_waxing = moon_sun_diff < 180
    
    # 14. Digbala
    digbala = {}
    for name in ['Sun','Moon','Mars','Mercury','Jupiter','Venus','Saturn']:
        digbala[name] = get_digbala(name, planets[name]['house'])
    
    # 15. Special Points (AL, UL)
    special_points = calc_special_points(lagna, planets)
    
    # 16. Transit positions (current slow planet positions)
    transits = calc_transits(lagna['sign_idx'], planets['Moon']['sign_idx'])
    
    # 17. Bhava Bala, Special Lagnas, Vargeeya Bala (via PyJHora)
    bhava_bala = None
    special_lagnas = None
    vargeeya_bala = None
    if any([_bhava_bala_pyjhora, _special_lagnas_pyjhora, _vargeeya_bala_pyjhora]):
        try:
            tz = pytz.timezone(tz_str)
            _tz_dt = tz.localize(datetime(year, month, day, hour, minute))
            _tz_offset = _tz_dt.utcoffset().total_seconds() / 3600.0
            if _bhava_bala_pyjhora:
                bhava_bala = _bhava_bala_pyjhora(year, month, day, hour, minute, lat, lon, _tz_offset)
            if _special_lagnas_pyjhora:
                special_lagnas = _special_lagnas_pyjhora(year, month, day, hour, minute, lat, lon, _tz_offset)
            if _vargeeya_bala_pyjhora:
                vargeeya_bala = _vargeeya_bala_pyjhora(year, month, day, hour, minute, lat, lon, _tz_offset)
        except Exception:
            pass

    # 18. Bhava Chalit（宫始盘）+ 边界敏感度
    #    整宫制(Rāśi)按星座算宫；宫始盘按 Lagna 精确度数居中划宫。
    #    两者不同的行星 = "宫位归属存在争议"，是精度关键。
    lagna_lon = lagna['longitude']
    bhava_chalit = {}
    chalit_shifts = []  # 整宫 ≠ 宫始 的行星
    for name in ['Sun','Moon','Mars','Mercury','Jupiter','Venus','Saturn','Rahu','Ketu']:
        p_lon = planets[name]['longitude']
        rasi_house = planets[name]['house']         # 整宫制
        chalit_house = calc_bhava_chalit(p_lon, lagna_lon)  # 宫始盘
        bhava_chalit[name] = {
            'rasi_house': rasi_house,
            'chalit_house': chalit_house,
            'shifted': rasi_house != chalit_house,
        }
        if rasi_house != chalit_house:
            chalit_shifts.append({
                'planet': name, 'rasi_house': rasi_house, 'chalit_house': chalit_house
            })

    # 边界敏感度：Lagna 距上一个/下一个星座边界的度数（换算成分钟）
    lagna_deg_in_sign = lagna_lon % 30
    deg_to_next = 30 - lagna_deg_in_sign          # 到下个星座
    deg_to_prev = lagna_deg_in_sign               # 到上个星座
    # 经验：Lagna 每 1° ≈ 4 分钟出生时间（赤道附近，随纬度变化，此处取近似）
    boundary_sensitivity = {
        'lagna_deg_in_sign': round(lagna_deg_in_sign, 2),
        'deg_to_next_sign': round(deg_to_next, 2),
        'deg_to_prev_sign': round(deg_to_prev, 2),
        'approx_min_to_next': round(deg_to_next * 4),
        'approx_min_to_prev': round(deg_to_prev * 4),
        # 距任一边界 < 5°（约20分钟出生时间）视为高敏感
        'near_boundary': min(deg_to_next, deg_to_prev) < 5.0,
    }

    chart_out = {
        'ayanamsa': ayanamsa,
        'lagna': lagna,
        'planets': planets,
        'sav': ashtak['sarvashtakavarga'],
        'sav_by_house': sav_by_house,
        'bav': ashtak['bhinnashtakavarga'],
        'd9': d9, 'd10': d10, 'd4': d4, 'd5': d5,
        'd60': d60,
        'd60_rake_ok': d60_rake_ok,
        'd30': d30,                              # D30 Trimsamsa 逆境盘
        'd30_rake_ok': d30_rake_ok,
        'd30_trust_level': d30_trust_resolved,   # D30 信任级别（与 D60 共用同意状态）
        'd7': d7,                                # D7 Saptamsa 子女盘
        'd11': d11,                              # D11 Ekadasamsha 深度转化盘（需知情同意）
        'd60_trust_level': d60_trust_resolved,   # 最终使用的信任级别
        'd60_trust_input': d60_trust_level,       # 用户传入的原始参数
        'd60_consent': _d60_consent_raw,          # 用户知情同意状态（True/False/None）
        'time_precision_level': time_precision_level,   # 出生时间精度等级（1-4）
        'high_sensitivity_disabled': _high_sensitivity_disabled_by_precision,  # 精度不足禁用高敏感分盘
        'reference_date': _ref_dt.strftime('%Y-%m-%d %H:%M') if _ref_dt else None,  # 分析基准日期
        'divisional_charts': divisional_charts,
        'vargottama': vargottama,
        'dignity': dignity_data,
        'combustion': combustion,
        'karakas': karakas,
        'aspects': aspects,
        'house_aspects': house_aspects,
        'house_lords': house_lords,
        'dashas': dashas,
        'shadbala': shadbala_data,
        'moon_phase': {'waxing': is_waxing, 'sun_moon_diff': round(moon_sun_diff, 1)},
        'digbala': digbala,
        'special_points': special_points,
        'transits': transits,
        'bhava_bala': bhava_bala,
        'special_lagnas': special_lagnas,
        'vargeeya_bala': vargeeya_bala,
        'bhava_chalit': bhava_chalit,
        'chalit_shifts': chalit_shifts,
        'boundary_sensitivity': boundary_sensitivity,
    }

    # ── 新增六大精度模块（fail-safe：每个独立 try，互不影响）──

    # 20. Argala（干预链）
    try:
        from argala import calculate_argala
        chart_out['argala'] = calculate_argala(chart_out)
    except Exception as e:
        chart_out['argala'] = {'error': str(e)}

    # 21. Avastha（行星状态：Baladi + Jagradadi）
    try:
        from avastha import calculate_avastha
        chart_out['avastha'] = calculate_avastha(chart_out)
    except Exception as e:
        chart_out['avastha'] = {'error': str(e)}

    # 22. Sodhya Pinda（Ashtakavarga 精细化）
    try:
        from ashtakavarga_pyjhora import calculate_sodhya_pinda
        chart_out['sodhya_pinda'] = calculate_sodhya_pinda(
            year, month, day, hour, minute, lat, lon, _tz_offset
        )
    except Exception as e:
        chart_out['sodhya_pinda'] = {'error': str(e)}

    # 23. Chara Dasha（Jaimini 环境层）
    try:
        from chara_dasha_pyjhora import calculate_chara_dasha
        chart_out['chara_dasha'] = calculate_chara_dasha(
            year, month, day, hour, minute, lat, lon, _tz_offset
        )
    except Exception as e:
        chart_out['chara_dasha'] = {'error': str(e)}

    # 24. 多 Ayanamsa 交叉
    try:
        from multi_ayanamsa import calculate_multi_ayanamsa
        chart_out['multi_ayanamsa'] = calculate_multi_ayanamsa(
            year, month, day, hour, minute, lat, lon, tz_str
        )
    except Exception as e:
        chart_out['multi_ayanamsa'] = {'error': str(e)}

    # 24b. D60 可信度精化：现在 multi_ayanamsa 已算，可以精化 auto 判定
    #   规则：Ra-Ke 通过 AND D60 Ayanamsa 敏感行星 ≤ 3颗 → 'computed'
    #        Ra-Ke 通过 AND 敏感行星 > 3颗 → 'uncertain'（Ayanamsa 影响大）
    #        Ra-Ke 不通过 → 'uncertain'
    if chart_out.get('d60_trust_input') == 'auto':
        ma = chart_out.get('multi_ayanamsa') or {}
        d60_sens_count = len([p for p, v in ma.get('d60_comparison', {}).items()
                              if v.get('sensitive')])
        rake_ok = chart_out.get('d60_rake_ok', False)
        if rake_ok and d60_sens_count <= 3:
            chart_out['d60_trust_level'] = 'computed'
        elif rake_ok:
            chart_out['d60_trust_level'] = 'uncertain'
        else:
            chart_out['d60_trust_level'] = 'uncertain'
        chart_out['d60_ayanamsa_sensitive_count'] = d60_sens_count
        # D30 跟 D60 共用同意状态，也同步精化
        chart_out['d30_trust_level'] = chart_out['d60_trust_level']

    # 25. D60/D30 客观化判定层（必须在 verdict 之前）
    try:
        from d60_verdict import compute_d60_verdicts
        chart_out.update(compute_d60_verdicts(chart_out))
    except Exception as e:
        chart_out['d60_verdict_error'] = {'error': str(e)}

    # 26. 新增精度增强模块：Narayana Dasha / Shoola Dasha / 特殊行星分析
    try:
        from narayana_dasha_pyjhora import calculate_narayana_dasha
        chart_out['narayana_dasha'] = calculate_narayana_dasha(
            year, month, day, hour, minute, lat, lon, _tz_offset)
    except Exception as e:
        chart_out['narayana_dasha'] = {'error': str(e)}
    try:
        from shoola_dasha_pyjhora import calculate_shoola_dasha
        chart_out['shoola_dasha'] = calculate_shoola_dasha(
            year, month, day, hour, minute, lat, lon, _tz_offset)
    except Exception as e:
        chart_out['shoola_dasha'] = {'error': str(e)}
    try:
        from special_planets_pyjhora import calculate_special_planets
        chart_out['special_planets'] = calculate_special_planets(
            year, month, day, hour, minute, lat, lon, _tz_offset)
    except Exception as e:
        chart_out['special_planets'] = {'error': str(e)}

    # 27. Tajaka 年度盘（当年/下年 Solar Return）
    try:
        from tajaka_pyjhora import calculate_tajaka
        chart_out['tajaka'] = calculate_tajaka(
            year, month, day, hour, minute, lat, lon, tz_str,
            reference_date=_ref_dt)
    except Exception as e:
        chart_out['tajaka'] = {'error': str(e)}

    # 28. Arudha Padas（完整12个社会现实层）
    try:
        from arudhas_pyjhora import calculate_arudha_padas
        chart_out['arudha_padas'] = calculate_arudha_padas(
            year, month, day, hour, minute, lat, lon, _tz_offset)
    except Exception as e:
        chart_out['arudha_padas'] = {'error': str(e)}

    # 29. Panchanga（五要素，参考日期所对应的日历层数据）
    try:
        from panchanga_pyjhora import calculate_panchanga
        # Panchanga 用 reference_date 而非出生日期（分析当日/指定日的五要素）
        if _ref_dt:
            _pg_y, _pg_m, _pg_d = _ref_dt.year, _ref_dt.month, _ref_dt.day
            _pg_h, _pg_mi = _ref_dt.hour, _ref_dt.minute
        else:
            from datetime import datetime as _dtx
            import pytz as _pyx
            _now_local = _dtx.now(_pyx.timezone(tz_str))
            _pg_y, _pg_m, _pg_d = _now_local.year, _now_local.month, _now_local.day
            _pg_h, _pg_mi = _now_local.hour, _now_local.minute
        chart_out['panchanga'] = calculate_panchanga(
            _pg_y, _pg_m, _pg_d, _pg_h, _pg_mi, lat, lon, tz_str)
    except Exception as e:
        chart_out['panchanga'] = {'error': str(e)}

    # 30. Kalachakra + Yogardha Dasha
    try:
        from kalachakra_pyjhora import calculate_kalachakra_dasha, calculate_yogardha_dasha
        chart_out['kalachakra_dasha'] = calculate_kalachakra_dasha(
            year, month, day, hour, minute, lat, lon, _tz_offset)
        chart_out['yogardha_dasha'] = calculate_yogardha_dasha(
            year, month, day, hour, minute, lat, lon, _tz_offset)
    except Exception as e:
        chart_out['kalachakra_dasha'] = {'error': str(e)}
        chart_out['yogardha_dasha'] = {'error': str(e)}

    # 31. Mudda Dasha
    try:
        from tajaka_pyjhora import calculate_mudda_dasha
        chart_out['mudda_dasha'] = calculate_mudda_dasha(
            year, month, day, hour, minute, lat, lon, tz_str,
            reference_date=_ref_dt)
    except Exception as e:
        chart_out['mudda_dasha'] = {'error': str(e)}

    # 32. Gochara 完整过运
    try:
        from gochara_pyjhora import calculate_gochara
        chart_out['gochara_full'] = calculate_gochara(
            birth_lagna_sign_idx=chart_out['lagna']['sign_idx'],
            birth_moon_sign_idx=chart_out['planets']['Moon']['sign_idx'],
            birth_planets_sign_idx={p: chart_out['planets'][p]['sign_idx']
                                     for p in ['Sun','Moon','Mars','Mercury','Jupiter','Venus','Saturn','Rahu','Ketu']},
            bav_data=chart_out['bav'],
            tz_str=tz_str,
            reference_date=_ref_dt,
            sav_by_house=chart_out.get('sav_by_house'),   # Bindu 宫位环境力量
        )
    except Exception as e:
        chart_out['gochara_full'] = {'error': str(e)}

    # 35. 健康敏感点（22nd Drekkana + 64th Navamsha）
    try:
        from health_markers_pyjhora import calculate_health_markers
        chart_out['health_markers'] = calculate_health_markers(
            year, month, day, hour, minute, lat, lon, _tz_offset)
    except Exception as e:
        chart_out['health_markers'] = {'error': str(e)}

    # 36. 多系统时机交叉扫描（未来60个月）
    try:
        from timing_confluence import scan_timing_confluence
        chart_out['timing_confluence'] = scan_timing_confluence(
            chart_out, months=60)
    except Exception as e:
        chart_out['timing_confluence'] = {'error': str(e)}

    # ── Chara/Narayana/Shoola 宫位激活标注（所有大运算完后统一注入）──
    # 每段大运的星座从 D1 Lagna 数是第几宫 → 该宫领域就是激活的生活主题
    _DOMAINS = {1:'自我/体质',2:'财富/家庭财务',3:'兄弟/努力/短途',4:'家庭/居所/母亲',
                5:'子女/恋爱/创造',6:'疾病/竞争/服务',7:'婚姻/合伙',8:'变故/深度转化',
                9:'运势/高等教育/信仰',10:'事业/权威',11:'收入/社交/朋友',12:'损耗/灵性/海外'}
    _li = lagna['sign_idx']
    for _key in ('chara_dasha', 'narayana_dasha', 'shoola_dasha',
                 'kalachakra_dasha', 'yogardha_dasha'):
        _d = chart_out.get(_key)
        if isinstance(_d, dict) and 'dashas' in _d:
            for _entry in _d['dashas']:
                _sidx = _entry.get('sign_idx')
                if _sidx is not None:
                    _h = ((_sidx - _li) % 12) + 1
                    _entry['house_from_lagna'] = _h
                    _entry['domain'] = _DOMAINS.get(_h, '')
                for _ad in _entry.get('antardashas', []):
                    _asidx = _ad.get('sign_idx')
                    if _asidx is not None:
                        _ah = ((_asidx - _li) % 12) + 1
                        _ad['house_from_lagna'] = _ah
                        _ad['domain'] = _DOMAINS.get(_ah, '')
            # 更新 current_* 的宫位信息
            _cc = [d for d in _d['dashas'] if d.get('is_current')]
            if _cc:
                _d['current_house'] = _cc[0].get('house_from_lagna')
                _d['current_domain'] = _cc[0].get('domain')

    # 32b. Chara Lagna 判读（以当前 Chara 主运星座为变动上升，Jaimini 正统视角）
    #      与 house_from_lagna（Dasha Rasi 落本命第几宫）互补：这里看关键点落 CL 第几宫。
    try:
        _cd = chart_out.get('chara_dasha') or {}
        _cd_curr = [x for x in _cd.get('dashas', []) if x.get('is_current')]
        _cl_sidx = _cd_curr[0].get('sign_idx') if _cd_curr else None
        chart_out['chara_lagna'] = calc_chara_lagna_reading(
            _cl_sidx, lagna['sign_idx'], planets, karakas, special_points)
    except Exception as e:
        chart_out['chara_lagna'] = {'error': str(e)}

    # 33. 确定性判定层（#6）：角色 / 大运吉凶 / 格局
    # ⚠️ 必须在 D60 判定之后——judge_dashas 会读取 d60_dasha_modifiers
    from verdict import compute_verdicts
    chart_out.update(compute_verdicts(chart_out))

    # 34. 事业 / 感情确定性判定层
    try:
        from career_verdict import compute_career_verdicts
        chart_out.update(compute_career_verdicts(chart_out))
    except Exception as e:
        chart_out['career_verdict_error'] = {'error': str(e)}
    try:
        from love_verdict import compute_love_verdicts
        chart_out.update(compute_love_verdicts(chart_out))
    except Exception as e:
        chart_out['love_verdict_error'] = {'error': str(e)}

    # ── 错误依赖图：检查模块依赖链，给出可见的传播警告 ──
    # 如果上游模块失败，下游模块的结果可能不完整，需显式标注
    _DEP_CHAINS = [
        # (下游key, 依赖的上游key列表, 说明)
        ('d60_karma', ['d60'], 'D60业力判定依赖D60分盘数据'),
        ('d60_dasha_modifiers', ['d60_karma', 'dasha_verdicts'], 'D60大运修正依赖业力判定'),
        ('career_niche', ['house_lords', 'karakas'], '事业生态位判定依赖宫主表和Karaka'),
        ('love_spouse_triangle', ['special_points', 'karakas'], '配偶三角依赖UL/DK数据'),
        ('health_markers', ['divisional_charts'], '健康敏感点依赖D3/D9分盘'),
        ('mudda_dasha', ['tajaka'], 'Mudda Dasha依赖太阳回归日期'),
    ]
    _dep_warnings = []
    for _downstream, _upstreams, _note in _DEP_CHAINS:
        for _up in _upstreams:
            _up_data = chart_out.get(_up)
            if _up_data is None:
                _dep_warnings.append(f'⚠️ {_downstream}: 上游{_up}缺失 — {_note}')
            elif isinstance(_up_data, dict) and 'error' in _up_data:
                _dep_warnings.append(f'⚠️ {_downstream}: 上游{_up}有错误({_up_data["error"][:50]}) — {_note}')
    if _dep_warnings:
        chart_out['dependency_warnings'] = _dep_warnings

    return chart_out


# === TEST ===
if __name__ == '__main__':
    print("=== vedic-calculator v0.2 Full Test ===\n")
    
    # Gandhi: 1869-10-02, 07:12, Porbandar
    chart = calculate_full_chart(1869, 10, 2, 7, 12, 21.6417, 69.6293, "Asia/Kolkata")
    
    print(f"Ayanamsa (Lahiri): {chart['ayanamsa']:.4f}°")
    print(f"Lagna: {chart['lagna']['sign']} {chart['lagna']['deg_str']}")
    
    print(f"\n--- Planets ---")
    print(f"  {'Planet':<10} {'Sign':<12} {'Deg':>8} {'H':>3} {'R':>2} {'Dignity':<16} {'Compound'}")
    for name in ['Sun','Moon','Mars','Mercury','Jupiter','Venus','Saturn','Rahu','Ketu']:
        p = chart['planets'][name]
        r = 'R' if p['retrograde'] else ''
        dig = chart['dignity'].get(name, {})
        basic = dig.get('basic', '-')
        compound = dig.get('compound', '-')
        print(f"  {name:<10} {p['sign']:<12} {p['deg_str']:>8} {p['house']:>3} {r:>2} {str(basic):<16} {compound}")
    
    print(f"\n--- SAV by House ---")
    total = 0
    for h in range(1, 13):
        s = chart['sav_by_house'][h]
        total += s['value']
        print(f"  {h}宫({s['sign'][:2]}): {s['value']}", end='  ')
        if h % 6 == 0: print()
    print(f"  Total: {total}")
    
    print(f"\n--- Chara Karakas (7K) ---")
    for k, planet, deg in chart['karakas']['7k']:
        print(f"  {k}: {planet} ({deg:.1f}°)")
    print(f"  DK争议: 7K={chart['karakas']['dk_7k']}, 8K={chart['karakas']['dk_8k']}, 一致={chart['karakas']['dk_consistent']}")
    
    print(f"\n--- Aspects (Vedic graha drishti, top 8) ---")
    for a in chart['aspects'][:8]:
        print(f"  {a['p1']} → {a['p2']}: {a['type']} ({a['degree_diff']}°)")
    
    print(f"\n--- Dasha ---")
    for d in chart['dashas']:
        marker = '→' if d['is_current'] else ' '
        print(f"  {marker} {d['planet']:<10} {d['start']} ~ {d['end']}  ({d['years']}yr)")
    
    print(f"\n--- D9 Navamsha ---")
    for name in ['Lagna','Sun','Moon','Mars','Mercury','Jupiter','Venus','Saturn','Rahu','Ketu']:
        sign = chart['d9'][name][0]
        varg = ' ★V' if chart['vargottama'].get(name, False) else ''
        print(f"  {name:<10} → {sign}{varg}")
    
    print(f"\n--- Shadbala ---")
    if 'error' in chart['shadbala']:
        print(f"  Error: {chart['shadbala']['error']}")
    else:
        for name, data in chart['shadbala'].items():
            if isinstance(data, dict):
                total = data.get('total_rupas', data.get('total', '?'))
                print(f"  {name:<10} {total}")
    
    print(f"\n--- Moon Phase ---")
    phase = chart['moon_phase']
    print(f"  {'盈月(Shukla)' if phase['waxing'] else '亏月(Krishna)'}, 距Sun {phase['sun_moon_diff']}°")
    
    print(f"\n--- Combustion ---")
    if chart['combustion']:
        for name, data in chart['combustion'].items():
            print(f"  {name}: {data}")
    else:
        print("  无燃烧行星")
    
    print(f"\n--- House Lords ---")
    for h in range(1, 13):
        info = chart['house_lords'][h]
        print(f"  {h}宫({info['domain']}): {info['lord']} → {info.get('lord_house','?')}宫")
    
    print(f"\n✅ 全部14个数据板块计算完成!")
