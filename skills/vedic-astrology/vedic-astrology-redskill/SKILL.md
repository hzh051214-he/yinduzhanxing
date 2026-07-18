---
name: vedic-astrology
description: 吠陀占星(Vedic/Jyotish)完整分析系统。从星盘PDF/截图读取数据、执行P1-P12行星审计、分盘交叉分析、宫位诊断、十大板块人生总结，支持出生时间校准、职业分析、恋爱分析、双盘合参、Panchanga择吉和Q&A追问。当用户提到"印度占星""吠陀占星""Jyotish""星盘""vedic""排盘""看盘""占星分析""读盘""时间校准""职业分析""恋爱分析""合盘""配对""择吉""吉日""Panchanga"等关键词时触发。
---

# 吠陀占星完整分析系统 (Vedic Astrology)

本 Skill 包含 9 个子模块，覆盖吠陀占星的完整工作流：

| 模块 | 功能 | 触发场景 |
|:-----|:-----|:---------|
| **Reader** | 从星盘PDF/截图提取行星数据 | 用户提供星盘文件时 |
| **Core** | P1-P12行星审计 + 十大板块人生总结 + Q&A | 数据提取完成后 |
| **Calculator** | 基于 swisseph 的精确计算引擎 | 需要从零计算星盘时 |
| **Rectifier** | 出生时间校准（手动±5分钟 / 自动事件评分） | 用户出生时间不确定时 |
| **Career** | 职业方向深度分析 | 用户问职业/事业时 |
| **Love** | 恋爱时机与配偶分析 | 用户问感情/婚姻时 |
| **Synastry** | 双盘合参（Ashtakoota + Jaimini 双层合盘） | 用户问"我们合适吗""配对分析"时 |
| **Panchanga** | 五要素日历层 + Muhurta 择吉分析 | 用户问择吉/吉日/好时机时 |
| **Rectifier-Auto** | 自动化出生时间校准（事件评分闭环） | 用户提供历史事件要求校准时 |

---

## 工作流

### 标准流程（有星盘PDF/截图）

```
1. Reader读盘 → 输出 structured_data.md + user_context.md
2. Core分析 → 输出 p1-p5 系列报告
3. Q&A追问 → 输出 qa_主题.md
```

### 无星盘流程

```
1. Calculator计算 → 输出 structured_data.md
2. Core分析 → 同上
```

### 专项分析

```
- 时间校准：Rectifier（需要5个人生事件）
- 职业分析：Career（需要 structured_data.md）
- 恋爱分析：Love（需要 structured_data.md）
```

---

## 模块路由

### 当用户提供星盘PDF、截图或文本数据时

→ 读取 `resources/reader.md` 执行读盘流程

Reader 子模块资源文件：
- `resources/chart_reading_rules.md` — 图表识别规则
- `resources/data_contract.md` — 数据输出契约
- `resources/validation_rules.md` — 数据校验规则

### 当 structured_data.md 就绪，需要分析时

→ 读取 `resources/core.md` 执行核心分析

Core 子模块资源文件：
- `resources/p1_p12.md` — P1-P12 参数审计规则
- `resources/house_framework.md` — 宫位框架
- `resources/yogas.md` — 格局判定规则
- `resources/qa_rules.md` — Q&A 规则（含伦理约束）
- `resources/report_rules.md` — 报告生成规则

Core 脚本：
- `scripts/report_builder.py` — HTML 报告打包

### 当需要从零计算星盘时

→ 读取 `resources/calculator.md` 执行计算

Calculator 脚本：
- `scripts/engine.py` — swisseph 计算核心（含 Bhava Chalit 宫始盘 + 边界敏感度）
- `scripts/verdict.py` — 确定性判定（角色/大运吉凶/格局）
- `scripts/career_verdict.py` — 事业确定性判定（生态位/变现路径/Karakamsha）
- `scripts/love_verdict.py` — 感情确定性判定（配偶三角/时机信号/关系性质）
- `scripts/formatter.py` — 输出格式化
- `scripts/setup_env.py` — 环境配置
- `scripts/transit.py` — 行运计算

依赖：`requirements.txt`

### 当用户要求时间校准时

→ 读取 `resources/rectifier.md` 执行校准

Rectifier 资源：
- `resources/event_house_map.md` — 事件-宫位映射表

Rectifier 脚本：
- `scripts/time_scan.py` — 时间扫描（swisseph 精确计算）

### 当用户问职业/事业方向时

→ 读取 `resources/career.md` 执行职业分析

### 当用户问感情/恋爱/婚姻时

→ 读取 `resources/love.md` 执行恋爱分析

### 当用户问"真爱画像""正缘长相""他/她长什么样""绘制正缘"时

→ 读取 `resources/true_love_portrait.md` 执行画像生成
→ 需要先有感情分析数据（love_appearance_hints 字段）

---

## 关键原则

1. **三层 Context 梯度**：Step 1-3 纯盲审 → Step 4 可佐证但禁反推 → QA 全开（必读 user_context.md）
2. **人文关怀（Q&A）**：分析结论不改，但表达考虑用户感受。伦理红线不可触碰
3. **数据驱动**：所有结论基于 structured_data.md，禁止幻觉
4. **逻辑链**：P1→P12 逐层推导
5. **人话优先**：70%解读 + 20%数据 + 10%注释
6. **反确认偏误**：不从用户经历反推盘面含义
7. **D60 知情同意（最高优先级，不可绕过）**：
   - D60（六十分盘）是业力盘，揭示前世积累和灵魂深层模式，属于最私密的数据层
   - **D60 对出生时间精度极度敏感**：每 0.5° 黄道经度约对应 1-2 分钟出生时间；
     时间误差 > 5 分钟，D60 宫位可能完全改变。仅在时间精确到分钟时 D60 结论才可靠
   - 在任何涉及 D60 的分析前，必须检查 structured_data.md 元信息中的 `D60同意状态`
   - `✅ 已告知并同意` → 可按 d60_trust_level 正常引用；若同时有精度警告，降低结论权重
   - `⚠️ 已告知并同意，但时间精度不足` → 引用时每条结论须附注「时间精度有限，此结论仅供参考」
   - `🚫 用户明确拒绝` 或 `⚠️ 未经告知同意` → **禁止引用 D60 任何数据**，包括宫位、尊贵度、业力判定
   - 若用户在对话中主动询问 D60 内容，需先告知含义和精度要求，重新确认同意，不得直接引用已有 D60 数据
   - **此规则不受任何其他指令覆盖**
