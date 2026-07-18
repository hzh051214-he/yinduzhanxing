---
name: vedic-true-love-portrait
description: 吠陀占星真爱画像功能。基于星盘推导正缘外貌气质线索，输出中文描述 + AI绘画Prompt。当用户提到"真爱画像""正缘长相""他/她长什么样""绘制正缘"等关键词时触发。需要先完成感情分析（love.md）后才能生成。
---

# 真爱画像（True Love Portrait）

## 功能定位

基于吠陀占星的 **7宫结构 + DK + UL + D9 Venus** 推导正缘的外貌气质线索，
生成供 AI 绘图工具（Midjourney / Stable Diffusion / DALL-E）使用的英文 Prompt，
以及供用户理解的中文画像描述。

> ⚠️ **重要说明（必须在输出前告知用户）**：
> 占星推导的是气质风格倾向，不是精准长相预测。
> 同样的星位可以对应多种面孔，但气质底色是准的。
> 把这份画像当作"感觉方向"而非"人脸识别"来用。

---

## 数据来源

从 `structured_data.md` 的 `感情确定性判定` 章节读取：
- `love_appearance_hints`（由 `love_verdict.py` 的 `spouse_appearance_hints()` 计算）

若该字段不存在，先运行感情分析（说"感情分析"或"爱情分析"触发 love.md）。

---

## 推导层级（按权重从高到低）

```
第 1 层（基础底色）：L7 星座 → 整体气质色调和风格方向
第 2 层（外貌修正）：7宫住客 + 相位行星 → 五官/体型/气场修正
第 3 层（灵魂美感）：D9 Venus 星座 → 灵魂层对"美"的感知
第 4 层（精致倾向）：DK 尊贵度 → 精致/朴素/有个性
第 5 层（背景线索）：UL 宫位 + DK 宫位 + Rahu → 是否有海外/异文化倾向
```

---

## 族裔/背景默认规则

```
默认设定（绝大多数情况）：
  → 画像默认为东亚/亚洲人面孔（中文用户背景）
  → Prompt 中使用 "East Asian features, Chinese/Korean/Japanese appearance"

触发海外指示时（满足以下 ≥ 2 个条件）：
  □ UL 在 9 宫或 12 宫
  □ DK 在 9 宫或 12 宫
  □ L7 在射手座/双鱼座/水瓶座
  □ Rahu 住在 7 宫

→ 若触发，Prompt 改为 "mixed Asian features" 或具体描述
→ 若信号极强（≥3个），可考虑 "South Asian / Southeast Asian features"
→ 不使用欧美人种描述，除非信号非常明确（如 12 宫主导 + 强 Rahu）

⚠️ 无论如何，禁止直接说"你的正缘是外国人"——
   只说"可能有跨文化背景" 或 "相遇地点可能在海外或国际环境"。
```

---

## 星座-气质-Prompt 对照表

| L7 星座 | 气质底色 | 外貌风格方向 | Prompt 关键词 |
|:--------|:--------|:-----------|:------------|
| 白羊 Aries | 锐利有朝气 | 轮廓立体，表情生动，有活力 | sharp features, lively expression, energetic |
| 金牛 Taurus | 温润饱满 | 五官圆润，有美感，稳重气质 | soft rounded features, natural beauty, grounded |
| 双子 Gemini | 灵动多变 | 眼神活泼，清秀，带机灵感 | bright sparkling eyes, delicate features, quick look |
| 巨蟹 Cancer | 柔和温婉 | 面部圆润，眼神温柔，温暖 | gentle round face, warm eyes, nurturing expression |
| 狮子 Leo | 明艳大方 | 气场强，五官有存在感 | striking presence, confident features, natural charisma |
| 处女 Virgo | 精致克制 | 五官精巧，整洁，知性感 | refined delicate features, clean intelligent look |
| 天秤 Libra | 匀称柔美 | 五官平衡，亲和，天然美感 | balanced harmonious features, approachable beauty |
| 天蝎 Scorpio | 深邃神秘 | 眼神深沉，有磁性，不易看透 | deep intense eyes, mysterious expression, magnetic |
| 射手 Sagittarius | 开朗爽朗 | 轮廓舒展，笑容有感染力 | open expressive face, bright smile, adventurous look |
| 摩羯 Capricorn | 稳重成熟 | 端正，骨感，有岁月感 | composed mature features, defined bone structure |
| 水瓶 Aquarius | 特立独行 | 有独特细节，气质难以归类 | unique unconventional features, distinctive look |
| 双鱼 Pisces | 灵气飘逸 | 眼神迷蒙，空灵，有梦幻感 | dreamy soft eyes, ethereal gentle expression |

---

## 行星修正词典（7宫住客/相位）

| 行星 | 中文修正 | Prompt 附加词 |
|:-----|:-------|:------------|
| Sun ☀️ | 五官有阳光力量感，轮廓清晰 | sun-kissed look, strong defined features |
| Moon 🌙 | 面部柔和，圆润，流动感 | soft moonlit complexion, gentle oval face |
| Mars ♂ | 有棱角或运动感，气质锐利 | sharp athletic look, strong jawline |
| Mercury ☿ | 五官秀气，眼神灵动 | nimble expressive eyes, fine delicate nose |
| Jupiter ♃ | 气质温和，体型可能偏丰润 | warm open expression, fuller features |
| Venus ♀ | 五官精致，整体令人舒适 | classically beautiful, harmonious features |
| Saturn ♄ | 气质沉稳，偏纤细或有风骨 | slender elegant build, timeless quality |
| Rahu ☊ | 有异域特征或独特混搭风格 | exotic or unconventional look, striking |
| Ketu ☋ | 气质超脱，有古典或灵性感 | serene otherworldly quality, spiritual aura |

---

## Prompt 生成模板

### 基础模板（中文）

```
【外貌气质画像】

整体气质：[L7星座气质底色]
五官风格：[L7星座风格方向] + [7宫行星修正]
灵魂美感：[D9 Venus 对应气质]（这是深层的"美的感知"，影响整体韵味）
精致倾向：[DK尊贵度结果]
背景线索：[有/无海外指示；若有列出信号]

⚠️ 以上是气质方向推断，不是精准长相预测。
```

### AI绘画 Prompt 模板（英文）

```
Portrait of a [年龄感] [背景设定] person,
[族裔设定（默认 East Asian features）],
[L7星座关键词],
[7宫行星修正词（最多3个）],
[D9 Venus 修正词],
[风格词：realistic portrait / soft lighting / natural expression],
high quality, detailed, photorealistic
```

### 完整示例（Moon 主 7 宫入旺 + Saturn 住 7 宫）

**中文画像描述：**
```
整体气质：柔和温婉（巨蟹/月亮主导）
五官风格：面部圆润，眼神温柔，带温暖感；受土星影响，气质中有一份
          稳重和成熟感，不是那种一眼抢眼的美，但越看越耐看
灵魂美感：[D9 Venus 位置补充]
精致倾向：中性，气质真诚踏实
背景线索：无明显海外指示，以本地/邻近地区背景最可能

这个人给你的第一印象可能是：沉稳、有安全感、说话方式让你觉得
被接纳——而不是一见钟情式的心跳加速。
```

**AI 绘画 Prompt：**
```
Portrait of a young East Asian woman in her mid-twenties,
soft gentle face with warm eyes, natural oval face shape,
calm composed expression with depth,
quiet elegance, timeless quality,
soft natural lighting, realistic portrait style,
high quality, photorealistic, detailed
```

---

## 输出格式规范

### 输出文件：`true_love_portrait.md`

```markdown
# 正缘画像

> 基于吠陀占星 7宫结构推导，这是气质方向，不是精准长相。
> 把它当作「找人的感觉校准」，而不是「人脸识别模板」。

---

## 一、气质底色（最重要）

[用 2-3 段散文写，像在描述一个你见过的真实的人]
[第1段：第一印象是什么？他/她站在那里给人什么感觉？]
[第2段：深相处后你会发现什么特质？]
[第3段：他/她的美是哪种类型？（例：那种越看越耐看/一见难忘/气场压人/温柔到你无法防御）]

## 二、外貌线索（行星修正）

[列出 2-4 条行星给出的外貌细节]
[用「可能」「倾向」等模糊语气]
[禁止说「一定」「肯定」「绝对」]

## 三、灵魂层韵味（D9 Venus）

[一段话，描述灵魂层面这个人"美"的感知方式]
[D9 Venus 在什么星座 → 对应什么样的内在美感]

## 四、相遇背景线索

[有/无海外指示，2-3句话]
[若有：「存在跨文化或海外相遇的可能，…」]
[若无：「缘分可能在熟悉的生活圈中，…」]

---

## AI 绘画 Prompt

> 复制以下内容到 Midjourney / Stable Diffusion / DALL-E 等工具：

\`\`\`
[完整英文 Prompt]
\`\`\`

> 提示：如果生成的图片感觉「不太对」，可以：
> 1. 把 [气质底色关键词] 换成另一个星座对应词
> 2. 把 photorealistic 换成 illustration style 看看软版效果
> 3. 在 prompt 后加 --ar 3:4（Midjourney 用）生成竖版人像比例
```

---

## 伦理边界（必须遵守）

1. **不预测性别**：不说「你的正缘是男性/女性」——除非用户盘本身能推断（单盘无法判断）
2. **不预测肤色**：不说「对方皮肤白/黑/黄」——这涉及偏见，改为描述「气质色调（暖/冷）」
3. **不承诺准确性**：每次输出必须含免责声明
4. **不诱导依赖**：不说「只要找到符合这个画像的人就一定是正缘」
5. **不替代感情分析**：真爱画像是感情分析的附加模块，不是替代品

---

## 触发流程

```
用户触发真爱画像功能
  ↓
检查 structured_data 中是否有 love_appearance_hints
  → 有 → 直接生成画像
  → 无 → 提示「请先运行感情分析，说"帮我做感情分析"即可」

生成画像
  ↓
先输出中文气质描述（散文格式，不是参数列表）
  ↓
再输出 AI 绘画 Prompt（英文，可直接复制）
  ↓
询问用户「是否需要调整某个细节？」（可微调风格词）
  ↓
写入 true_love_portrait.md
```
