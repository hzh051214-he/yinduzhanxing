"""城市搜索服务 — 城市名 → (lat, lon, tz_str)。

使用 geopy + timezonefinder（已在 vedic venv 中安装）。
内置常用亚洲城市快速查找表，避免每次都走网络 API。
"""
import json
from functools import lru_cache
from typing import Optional

# 内置常用城市表（亚洲区域，减少网络依赖）
BUILTIN_CITIES = {
    # 中国大陆
    "上海": (31.2304, 121.4737, "Asia/Shanghai"),
    "北京": (39.9042, 116.4074, "Asia/Shanghai"),
    "广州": (23.1291, 113.2644, "Asia/Shanghai"),
    "深圳": (22.5431, 114.0579, "Asia/Shanghai"),
    "成都": (30.5728, 104.0668, "Asia/Shanghai"),
    "杭州": (30.2741, 120.1551, "Asia/Shanghai"),
    "南京": (32.0603, 118.7969, "Asia/Shanghai"),
    "武汉": (30.5928, 114.3055, "Asia/Shanghai"),
    "西安": (34.3416, 108.9398, "Asia/Shanghai"),
    "重庆": (29.5630, 106.5516, "Asia/Shanghai"),
    "苏州": (31.2990, 120.5853, "Asia/Shanghai"),
    "天津": (39.3434, 117.3616, "Asia/Shanghai"),
    "长沙": (28.2282, 112.9388, "Asia/Shanghai"),
    "郑州": (34.7466, 113.6254, "Asia/Shanghai"),
    "青岛": (36.0671, 120.3826, "Asia/Shanghai"),
    "沈阳": (41.8057, 123.4315, "Asia/Shanghai"),
    "哈尔滨": (45.8038, 126.5349, "Asia/Shanghai"),
    "长春": (43.8171, 125.3235, "Asia/Shanghai"),
    "厦门": (24.4798, 118.0819, "Asia/Shanghai"),
    "宁波": (29.8683, 121.5440, "Asia/Shanghai"),
    "合肥": (31.8206, 117.2272, "Asia/Shanghai"),
    "济南": (36.6512, 117.1201, "Asia/Shanghai"),
    "昆明": (25.0389, 102.7183, "Asia/Shanghai"),
    "福州": (26.0745, 119.2965, "Asia/Shanghai"),
    "贵阳": (26.6470, 106.6302, "Asia/Shanghai"),
    "南昌": (28.6820, 115.8581, "Asia/Shanghai"),
    "太原": (37.8706, 112.5489, "Asia/Shanghai"),
    "石家庄": (38.0428, 114.5149, "Asia/Shanghai"),
    "呼和浩特": (40.8426, 111.7500, "Asia/Shanghai"),
    "乌鲁木齐": (43.8256, 87.6168, "Asia/Urumqi"),
    "拉萨": (29.6520, 91.1721, "Asia/Kolkata"),
    # 港澳台
    "香港": (22.3193, 114.1694, "Asia/Hong_Kong"),
    "澳门": (22.1987, 113.5439, "Asia/Macau"),
    "台北": (25.0330, 121.5654, "Asia/Taipei"),
    "高雄": (22.6273, 120.3014, "Asia/Taipei"),
    # 东亚
    "东京": (35.6762, 139.6503, "Asia/Tokyo"),
    "大阪": (34.6937, 135.5023, "Asia/Tokyo"),
    "首尔": (37.5665, 126.9780, "Asia/Seoul"),
    "釜山": (35.1796, 129.0756, "Asia/Seoul"),
    "新加坡": (1.3521, 103.8198, "Asia/Singapore"),
    # 东南亚
    "曼谷": (13.7563, 100.5018, "Asia/Bangkok"),
    "吉隆坡": (3.1390, 101.6869, "Asia/Kuala_Lumpur"),
    "雅加达": (-6.2088, 106.8456, "Asia/Jakarta"),
    "马尼拉": (14.5995, 120.9842, "Asia/Manila"),
    "胡志明市": (10.8231, 106.6297, "Asia/Ho_Chi_Minh"),
    # 南亚
    "孟买": (19.0760, 72.8777, "Asia/Kolkata"),
    "新德里": (28.6139, 77.2090, "Asia/Kolkata"),
    "班加罗尔": (12.9716, 77.5946, "Asia/Kolkata"),
    # 英文别名
    "shanghai": (31.2304, 121.4737, "Asia/Shanghai"),
    "beijing": (39.9042, 116.4074, "Asia/Shanghai"),
    "guangzhou": (23.1291, 113.2644, "Asia/Shanghai"),
    "shenzhen": (22.5431, 114.0579, "Asia/Shanghai"),
    "chengdu": (30.5728, 104.0668, "Asia/Shanghai"),
    "hangzhou": (30.2741, 120.1551, "Asia/Shanghai"),
    "hongkong": (22.3193, 114.1694, "Asia/Hong_Kong"),
    "hong kong": (22.3193, 114.1694, "Asia/Hong_Kong"),
    "singapore": (1.3521, 103.8198, "Asia/Singapore"),
    "tokyo": (35.6762, 139.6503, "Asia/Tokyo"),
    "seoul": (37.5665, 126.9780, "Asia/Seoul"),
    "taipei": (25.0330, 121.5654, "Asia/Taipei"),
    "mumbai": (19.0760, 72.8777, "Asia/Kolkata"),
    "delhi": (28.6139, 77.2090, "Asia/Kolkata"),
    "new delhi": (28.6139, 77.2090, "Asia/Kolkata"),
    "bangkok": (13.7563, 100.5018, "Asia/Bangkok"),
}


def search_city(query: str, limit: int = 8) -> list[dict]:
    """
    搜索城市，返回候选列表。

    优先精确匹配内置表；内置表无结果时用 geopy Nominatim 网络查询。
    每项返回: {name, lat, lon, tz_str, source}
    """
    query_lower = query.strip().lower()
    results = []

    # 1. 精确匹配内置表
    if query_lower in BUILTIN_CITIES:
        lat, lon, tz = BUILTIN_CITIES[query_lower]
        results.append({
            "name": query.strip(),
            "lat": lat, "lon": lon, "tz_str": tz,
            "source": "builtin"
        })
        return results

    # 中文匹配
    if query.strip() in BUILTIN_CITIES:
        lat, lon, tz = BUILTIN_CITIES[query.strip()]
        results.append({
            "name": query.strip(),
            "lat": lat, "lon": lon, "tz_str": tz,
            "source": "builtin"
        })
        return results

    # 2. 前缀匹配内置表
    for city_name, (lat, lon, tz) in BUILTIN_CITIES.items():
        if city_name.startswith(query_lower) or city_name.startswith(query.strip()):
            results.append({
                "name": city_name,
                "lat": lat, "lon": lon, "tz_str": tz,
                "source": "builtin"
            })
        if len(results) >= limit:
            break

    if results:
        return results[:limit]

    # 3. 网络查询（geopy Nominatim，仅在内置表无结果时调用）
    try:
        from geopy.geocoders import Nominatim
        from timezonefinder import TimezoneFinder

        geolocator = Nominatim(user_agent="vedic-astrology-app/1.0")
        tf = TimezoneFinder()

        locations = geolocator.geocode(query, exactly_one=False, limit=limit, language="zh")
        if locations:
            for loc in locations[:limit]:
                tz = tf.timezone_at(lat=loc.latitude, lng=loc.longitude) or "Asia/Shanghai"
                results.append({
                    "name": loc.address.split(",")[0],
                    "lat": round(loc.latitude, 4),
                    "lon": round(loc.longitude, 4),
                    "tz_str": tz,
                    "source": "nominatim"
                })
    except Exception:
        pass  # 网络不可用时返回空结果，不崩溃

    return results[:limit]


def get_city_coords(city_name: str) -> Optional[tuple[float, float, str]]:
    """直接按城市名返回 (lat, lon, tz_str)，未找到返回 None。"""
    results = search_city(city_name, limit=1)
    if results:
        r = results[0]
        return r["lat"], r["lon"], r["tz_str"]
    return None
