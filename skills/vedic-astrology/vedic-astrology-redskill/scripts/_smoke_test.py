"""
smoke_test.py — 吠陀占星计算引擎回归测试套件
运行：python _smoke_test.py
全部通过时：exit code 0，打印 ✅ 全部通过
任何失败时：exit code 1，打印具体失败项

覆盖：
  - 核心计算（SAV/BAV/行星/分盘）
  - 所有大运系统（7套）
  - 精度增强层（Avastha/Argala/Sodhya/Gochara等）
  - 确定性判定层（verdict/career/love/d60）
  - reference_date 参数化
  - 字段一致性
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from engine import calculate_full_chart
from formatter import format_structured_data

SIGNS = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
         'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces']
PLANET_NAMES = ['Sun', 'Moon', 'Mars', 'Mercury', 'Jupiter',
                'Venus', 'Saturn', 'Rahu', 'Ketu']

PASS = []
FAIL = []


def check(name, condition, detail=''):
    if condition:
        PASS.append(name)
        print(f'  ✅ {name}')
    else:
        FAIL.append(name)
        print(f'  ❌ {name}' + (f': {detail}' if detail else ''))


def is_ok_layer(v):
    """层存在且无 error：不是 None，且（若为 dict）无 'error' 键。"""
    if v is None:
        return False
    if isinstance(v, dict) and 'error' in v:
        return False
    return True


# ============================================================
# 计算样本星盘（带 reference_date，结果可复现）
#   2005-12-14 10:28 上海 男
# ============================================================
print('\n=== 计算样本星盘（reference_date=2024-01-15）===')
chart = calculate_full_chart(
    2005, 12, 14, 10, 28, 31.2304, 121.4737, 'Asia/Shanghai',
    reference_date='2024-01-15')


# ------------------------------------------------------------
# GROUP 1: 核心计算
# ------------------------------------------------------------
print('\n--- GROUP 1: 核心计算 ---')

sav_total = sum(chart['sav'].get(s, 0) for s in SIGNS)
check('G1 SAV 总和 == 337', sav_total == 337, f'实际 {sav_total}')

planet_count = len(chart['planets'])
check('G1 行星数 == 9', planet_count == 9, f'实际 {planet_count}')

check('G1 行星集合完整（9颗）',
      all(p in chart['planets'] for p in PLANET_NAMES),
      f"缺失 {[p for p in PLANET_NAMES if p not in chart['planets']]}")

WESTERN = {'六合(60°)', '刑(90°)', '三合(120°)', '对冲(180°)'}
bad_aspects = [a for a in chart['aspects'] if a.get('type') in WESTERN]
check('G1 无西占相位类型', len(bad_aspects) == 0, f'残留 {len(bad_aspects)} 条')

check('G1 D1 Lagna == Capricorn',
      chart['lagna']['sign'] == 'Capricorn', f"实际 {chart['lagna']['sign']}")


# ------------------------------------------------------------
# GROUP 2: 所有大运系统存在且有数据
#   vimsottari = 顶层 chart['dashas'] (list)
#   其余 = chart['<name>_dasha'] (dict, 含 'dashas' 列表)
# ------------------------------------------------------------
print('\n--- GROUP 2: 大运系统 ---')

# vimsottari 特殊处理：顶层 dashas 是 list
vim = chart.get('dashas')
check('G2 vimsottari 存在为列表', isinstance(vim, list) and len(vim) > 0,
      f'类型 {type(vim).__name__}')
if isinstance(vim, list) and vim:
    check('G2 vimsottari 条目含 is_current',
          any(e.get('is_current') for e in vim),
          '无 is_current 条目')
    cur_cnt = sum(1 for e in vim if e.get('is_current'))
    check('G2 vimsottari 恰有一个 is_current', cur_cnt == 1, f'实际 {cur_cnt}')
else:
    check('G2 vimsottari 条目含 is_current', False, 'vimsottari 无数据')
    check('G2 vimsottari 恰有一个 is_current', False, 'vimsottari 无数据')

DASHA_DICTS = ['chara_dasha', 'narayana_dasha', 'shoola_dasha',
               'kalachakra_dasha', 'yogardha_dasha']
for key in DASHA_DICTS:
    v = chart.get(key)
    check(f'G2 {key} 存在且无 error', is_ok_layer(v),
          repr(v.get('error'))[:60] if isinstance(v, dict) and 'error' in v else 'None')
    if is_ok_layer(v):
        ds = v.get('dashas')
        check(f'G2 {key} 有 dashas 且非空',
              isinstance(ds, list) and len(ds) > 0,
              f'dashas={type(ds).__name__}')
        if isinstance(ds, list) and ds:
            cur = sum(1 for e in ds if e.get('is_current'))
            check(f'G2 {key} 至少一个 is_current', cur >= 1, f'实际 {cur}')


# ------------------------------------------------------------
# GROUP 3: 精度增强层存在
# ------------------------------------------------------------
print('\n--- GROUP 3: 精度增强层 ---')

# 期望的关键子键（存在性验证）
PRECISION_EXPECT = {
    'avastha': PLANET_NAMES,               # 9 行星状态
    'argala': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],  # 12 宫
    'gochara_full': ['date', 'planets'],
    'panchanga': ['date', 'tithi', 'nakshatra'],
    'arudha_padas': ['A1', 'A7', 'A10'],
    'tajaka': ['current_year', 'next_year'],
    'special_planets': ['manglik', 'kala_sarpa'],
}
for key, expected_keys in PRECISION_EXPECT.items():
    v = chart.get(key)
    ok = is_ok_layer(v)
    check(f'G3 {key} 存在且无 error', ok,
          repr(v.get('error'))[:60] if isinstance(v, dict) and 'error' in v else 'None')
    if ok:
        missing = [k for k in expected_keys if k not in v]
        check(f'G3 {key} 含预期键', len(missing) == 0, f'缺失 {missing}')


# ------------------------------------------------------------
# GROUP 4: 确定性判定层
# ------------------------------------------------------------
print('\n--- GROUP 4: 判定层 ---')

roles = chart.get('roles')
check('G4 roles 含 9 行星',
      isinstance(roles, dict) and all(p in roles for p in PLANET_NAMES),
      f"实际键 {list(roles.keys()) if isinstance(roles, dict) else type(roles).__name__}")

dv = chart.get('dasha_verdicts')
check('G4 dasha_verdicts 含 9 条',
      isinstance(dv, list) and len(dv) == 9,
      f'实际 {len(dv) if isinstance(dv, list) else type(dv).__name__}')

yogas = chart.get('yogas')
check('G4 yogas 是列表（非 None）', isinstance(yogas, list),
      f'类型 {type(yogas).__name__}')

check('G4 career_niche 存在', is_ok_layer(chart.get('career_niche')),
      'None 或 error')

check('G4 love_spouse_triangle 存在',
      is_ok_layer(chart.get('love_spouse_triangle')), 'None 或 error')


# ------------------------------------------------------------
# GROUP 5: 字段命名一致性
# ------------------------------------------------------------
print('\n--- GROUP 5: 字段一致性 ---')

kala = chart.get('kalachakra_dasha') or {}
check('G5 kalachakra_dasha 同含 current 与 current_sign',
      'current' in kala and 'current_sign' in kala,
      f'键 {list(kala.keys())}')

yog = chart.get('yogardha_dasha') or {}
check('G5 yogardha_dasha 同含 current 与 current_sign',
      'current' in yog and 'current_sign' in yog,
      f'键 {list(yog.keys())}')

chara = chart.get('chara_dasha') or {}
check('G5 chara_dasha 含 current_sign',
      'current_sign' in chara, f'键 {list(chara.keys())}')

# 所有 error 值必须是 dict（不是裸字符串）
str_errors = []
for k, v in chart.items():
    if isinstance(v, dict) and 'error' in v and not isinstance(v['error'], (dict, str)):
        # 'error' 值本身可以是字符串消息；这里检查的是"层用字符串代替 dict"的反模式
        pass
    if k.endswith('_error') and not isinstance(v, dict):
        str_errors.append(k)
check('G5 所有 *_error 值均为 dict', len(str_errors) == 0, f'非 dict: {str_errors}')


# ------------------------------------------------------------
# GROUP 6: reference_date 参数
# ------------------------------------------------------------
print('\n--- GROUP 6: reference_date 参数 ---')

goc_date = (chart.get('gochara_full') or {}).get('date')
check('G6 gochara date == 2024-01-15', goc_date == '2024-01-15',
      f'实际 {goc_date}')

pg_date = (chart.get('panchanga') or {}).get('date')
check('G6 panchanga date 年份为 2024',
      isinstance(pg_date, str) and pg_date.startswith('2024'),
      f'实际 {pg_date}')

# 无 reference_date：输出仍有效
chart_now = calculate_full_chart(
    2005, 12, 14, 10, 28, 31.2304, 121.4737, 'Asia/Shanghai')
check('G6 无 reference_date 输出有效',
      isinstance(chart_now, dict) and 'error' not in chart_now
      and chart_now.get('lagna', {}).get('sign') == 'Capricorn',
      'chart_now 无效')


# ------------------------------------------------------------
# GROUP 7: Formatter 输出
# ------------------------------------------------------------
print('\n--- GROUP 7: Formatter 输出 ---')

meta = {'dob': '2005-12-14', 'time': '10:28', 'place': 'Shanghai',
        'lat': 31.2304, 'lon': 121.4737}
md = format_structured_data(chart, None, meta,
                            {'gender': '男', 'relationship': '单身'})
line_count = len(md.splitlines())
check('G7 structured_data 行数 > 800', line_count > 800, f'实际 {line_count}')

KEY_SECTIONS = [
    '### 行星位置',
    '### Vimsottari Dasha',
    '### 主要相位关系',
    '### P1 角色身份表',
    '### 大运吉凶判定',
    '### 格局判定（Yogas）',
    '### Avastha 行星状态（Baladi + Jagradadi）',
    '### Argala 干预链',
    '### Chara Dasha（Jaimini 环境层）',
]
for sec in KEY_SECTIONS:
    check(f'G7 含章节 {sec}', sec in md, '未找到')


# ============================================================
# 汇总
# ============================================================
print(f'\n=== 回归测试完成: {len(PASS)}通过 / {len(FAIL)}失败 ===')
if FAIL:
    print('失败项:', FAIL)
    sys.exit(1)
else:
    print('✅ 全部通过')
    sys.exit(0)
