---
name: vedic-panchanga
description: 吠陀占星日历层分析（Panchanga 五要素 + Muhurta 择吉）。当用户问"什么时候做X最好""今天适合吗""择吉日""吉时"等关键词时触发。
---

# Panchanga 五要素 + Muhurta 择吉

## 概述

Panchanga（潘昌嘎）是吠陀占星的时间层，描述任何给定时刻的五个日历要素。这是所有"择时"分析的基础。

## 五要素说明

| 要素 | 含义 | 范围 | 影响 |
|------|------|------|------|
| **Tithi** | 月相日（阴历日期）| 1-30 | 每天的月亮能量类型 |
| **Vara** | 星期（对应七颗行星）| 日-土 | 当天的行星守护能量 |
| **Nakshatra** | 月亮所在星宿 | 1-27 | 月亮能量的具体性质 |
| **Yoga** | 太阳+月亮黄道经度之和的27分之一 | 1-27 | 综合日月能量吉凶 |
| **Karana** | 半个 Tithi | 1-60 | 每半天的行动宜忌 |

---

## ⛔ 蚀日禁忌（最高优先级，凌驾于一切择吉之上）

> **规则：蚀日前后 ±14 天为强制排除窗口，不得在此期间推荐任何重要行动。**
> 此规则优先于五要素、Muhurta、吉 Yoga 等一切正面指标。

### 原理

日蚀/月蚀时 Rahu 或 Ketu 正好与 Sun 或 Moon 合相：
- 日蚀 = Rahu/Ketu 合 Sun → 自我、灵魂、父亲领域被强烈激活
- 月蚀 = Rahu/Ketu 合 Moon → 情绪、母亲、心理领域被强烈激活

蚀日的业力节点能量极强但极不稳定，结果难以预测。传统吠陀占星视蚀日前后为"高度敏感不稳定期"，任何在此期间启动的重要事项都被认为结果难以保证。

### 使用流程

```python
from panchanga_pyjhora import find_eclipses_near

# 检查目标日期前后 180 天内的蚀日
eclipses = find_eclipses_near(year, month, day, search_days=180)

# eclipses 返回结构：
# {
#   'solar_eclipses': [{'date': 'YYYY-MM-DD', 'type': '日全食/日环食/...',
#                        'blackout_start': 'YYYY-MM-DD', 'blackout_end': 'YYYY-MM-DD'}, ...],
#   'lunar_eclipses':  [同上格式],
#   'in_blackout': bool,          # 目标日期是否在任意蚀日 ±14 天窗口内
#   'active_blackout': str|None,  # 若在窗口内，描述原因（如"日全食后 7 天"）
# }
```

### 择吉分析时的蚀日检查流程

```
Step 0（蚀日检查，择吉分析前必须先执行）：

1. 调用 find_eclipses_near(目标日期, search_days=180)
2. 检查 in_blackout：
   → True  → 输出：
     "⛔ 蚀日禁忌窗口：[active_blackout]
      蚀日 ±14 天内不建议启动重要事项。
      建议改期至 [blackout_end 之后] 的日期。"
     → 停止进一步择吉，直接给出改期建议
   → False → 检查目标日期附近是否有蚀日（即将进入窗口）：
     若 ≤ 21 天即将进入 → 提示用户：
     "⚠️ 注意：[N] 天后将有 [蚀日类型]（[日期]），
      建议在 [blackout_start] 前完成重要行动，否则再等 14 天后。"
     → 继续正常择吉流程

3. 禁止行为：
   × 不得在明知蚀日窗口内仍推荐"整体还好"的日期
   × 不得用"Abhijit Muhurta 可以抵消蚀日影响"做辩解
   × 五要素再好也无法覆盖蚀日禁忌
```

---

## 择吉核心规则

**最优先避开**（正常日期）：
- Karana = Vishti（Bhadra）—— 半天内禁忌一切重要行动，每周约出现1次
- Yoga = 凶性 Yoga（Vishkambha/Atiganda/Shoola/Ganda/Vajra/Vyatipata/Parigha/Vaidhriti）
- Rahu Kala 时段内（每天约1.5小时）禁止重要开始

**择吉优选组合**：
- Nakshatra = Rohini/Hasta/Pushya/Uttara 系列（★★★ 级别）
- Yoga = 吉性 Yoga（Priti/Vriddhi/Dhruva/Siddhi 等）
- Abhijit Muhurta 时段（每天约1小时，正午附近）= 通用最吉时段

## 使用流程

当用户询问择吉时：
1. **Step 0：先执行蚀日检查**（见上方）
2. 读取 structured_data 的 Panchanga 章节（出生日数据）
3. 如用户指定目标日期，用 `calculate_panchanga()` 计算目标日的五要素
4. 对比五要素的吉凶组合，给出具体建议时段

## 数据来源

`panchanga_pyjhora.py` — 直接调用，不依赖 structured_data。

```python
from panchanga_pyjhora import calculate_panchanga, find_eclipses_near

# 五要素计算
result = calculate_panchanga(year, month, day, hour, minute, lat, lon, tz_str)

# 蚀日检查（择吉前必须调用）
eclipses = find_eclipses_near(year, month, day, search_days=180)
```

输出包含：tithi/vara/nakshatra/yoga/karana + abhijit_muhurta + amrit_kalam + rahu_kalam + 综合评估。

## 常见用户需求对应

| 用户问题 | Panchanga 解答 |
|---------|--------------|
| "这个月哪天签合同最好？" | 先查蚀日 → 再找 Vishti-free + 吉 Yoga + Abhijit 时段的日期 |
| "今天适合出行吗？" | 先查蚀日 → 检查 Nakshatra 吉凶 + Yoga 吉凶 + Rahu Kala 是否避开 |
| "手术最好什么时候做？" | 先查蚀日 → 避免 Mars 强相位日 + 选 Hasta/Uttara Nakshatra |
| "婚礼最佳日期？" | 先查蚀日 → Pushya/Uttara Phalguni + 吉 Yoga + 避 Vishti 和 Ketu Nakshatra |
