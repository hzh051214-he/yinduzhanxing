"""真爱画像 LLM prompt — 基于 love_appearance_hints 生成气质描述和绘图 Prompt。"""

# 星座 → 气质/外貌关键词（用于 Prompt 构建）
_SIGN_PROMPT_KEYWORDS = {
    'Aries':       {'cn': '锐利有朝气，轮廓生动，表情有活力',      'en': 'sharp features, lively expressive face, energetic'},
    'Taurus':      {'cn': '温润饱满，五官圆润有美感，气质稳重',      'en': 'soft rounded features, natural beauty, grounded elegance'},
    'Gemini':      {'cn': '灵动多变，眼神活泼，清秀机灵',           'en': 'bright sparkling eyes, delicate features, quick intelligent look'},
    'Cancer':      {'cn': '柔和温婉，面部圆润，眼神温柔有安全感',    'en': 'gentle round face, warm nurturing eyes, soft expression'},
    'Leo':         {'cn': '气场强，五官有存在感，明艳大方',          'en': 'striking natural presence, confident features, magnetic charisma'},
    'Virgo':       {'cn': '精致克制，五官精巧，带知性整洁感',        'en': 'refined delicate features, clean intelligent look, meticulous'},
    'Libra':       {'cn': '匀称柔美，五官平衡，亲和天然',            'en': 'balanced harmonious features, approachable natural beauty'},
    'Scorpio':     {'cn': '深邃神秘，眼神深沉有磁性，气质难以看透',  'en': 'deep intense eyes, mysterious magnetic expression, powerful gaze'},
    'Sagittarius': {'cn': '开朗爽朗，笑容有感染力，轮廓舒展',        'en': 'open expressive face, bright infectious smile, adventurous look'},
    'Capricorn':   {'cn': '端正稳重，骨感突出，有成熟岁月感',        'en': 'composed mature features, defined bone structure, timeless quality'},
    'Aquarius':    {'cn': '特立独行，有独特细节，气质难以归类',       'en': 'unique unconventional features, distinctive striking look, otherworldly'},
    'Pisces':      {'cn': '灵气飘逸，眼神迷蒙空灵，有梦幻感',        'en': 'dreamy soft eyes, ethereal gentle expression, otherworldly beauty'},
}

# 尊贵度修饰词 — L7 入旺/入庙时强化描述
_DIGNITY_BOOST = {
    'exalted':      {'cn': '（入旺，气质极为突出，这个方向的特质会非常鲜明）', 'en': 'exceptionally '},
    'own_sign':     {'cn': '（入庙，气质纯粹稳定，这个方向特质完整呈现）',      'en': 'purely '},
    'great_friend': {'cn': '（至友，气质整体偏正面）',                          'en': ''},
    'debilitated':  {'cn': '（落陷，气质方向会有变形或不稳定）',                 'en': 'subtly '},
}

# 行星在7宫的外貌修正（更具体版）
_PLANET_7H_CN = {
    'Sun':     '整体气质带有阳光感或领导感，五官通常比较有力量，不会让人觉得柔弱',
    'Moon':    '面部表情流动，带有情感感染力，眼神尤其有吸引力，圆润柔和',
    'Mars':    '身体感强，有运动感或肌肉线条，或者表情里有一种"冲劲"，不那么静态',
    'Mercury': '五官秀气，说话方式是吸引力之一，眼神灵活，整体轻盈感',
    'Jupiter': '气质开阔温暖，体型偏丰润，或者给人一种"成熟可靠感"，不显得尖锐',
    'Venus':   '外形令人舒适，五官精致有审美，整体像是"被打磨过"的美感',
    'Saturn':  '气质沉稳，不轻浮，可能偏纤细或骨感，越看越耐看，有一种岁月给的质感',
    'Rahu':    '有某种说不清的独特感，可能有异域风情或者混搭特征，很容易被记住',
    'Ketu':    '气质有些超脱，可能有一种"不在意被看"的安静感，或者古典灵性气质',
}

_PLANET_7H_EN = {
    'Sun':     'sun-kissed confident look, strong defined features',
    'Moon':    'soft expressive face, emotionally warm eyes, gentle oval face',
    'Mars':    'athletic build, sharp jawline, dynamic energetic expression',
    'Mercury': 'nimble expressive eyes, fine delicate features, light graceful quality',
    'Jupiter': 'warm open expression, fuller features, mature reliable presence',
    'Venus':   'classically beautiful, harmonious refined features, natural grace',
    'Saturn':  'slender elegant build, timeless quality, reserved quiet depth',
    'Rahu':    'exotic or unconventional look, striking memorable features',
    'Ketu':    'serene otherworldly quality, spiritual aura, quiet classical beauty',
}

# D9 Venus 灵魂美感（更具体）
_D9_VENUS_SOUL = {
    'Aries':       '灵魂层爱欲强烈，美感偏"有冲击力"，不喜欢平淡，被她/他的热情和直接打动',
    'Taurus':      '灵魂层享受感官之美，偏爱有质感的东西，美感偏"丰盛踏实"，相处起来很有滋养感',
    'Gemini':      '灵魂层对"灵动"很敏感，美感偏"会聊天的人"，思维的活跃度是吸引力的一部分',
    'Cancer':      '灵魂层把"归属感"当作美的最高形式，和你在一起有家的感觉',
    'Leo':         '灵魂层爱闪光，美感偏"有光的人"，内心有一种创造和被崇拜的渴望',
    'Virgo':       '灵魂层追求精致和完美，美感偏"干净整洁有品位"，细节控，对美有高标准',
    'Libra':       '灵魂层最爱平衡与和谐，美感偏"温柔不争"，相处起来有一种"水面如镜"的感觉',
    'Scorpio':     '灵魂层美感偏"深水区"，不喜欢浅薄，被深度和神秘感打动，情感浓烈',
    'Sagittarius': '灵魂层追求自由和广度，美感偏"开阔"，和你在一起像是打开了一扇窗',
    'Capricorn':   '灵魂层把"长久"当最高价值，美感偏"经得起时间"，不是第一眼美，是越来越耐看',
    'Aquarius':    '灵魂层独立且超前，美感偏"你在哪里见过同类？"，有一种特立独行的内在美',
    'Pisces':      '灵魂层极度感性，美感偏"梦里的感觉"，有艺术感，相处起来像在不同的时空',
}


PORTRAIT_SYSTEM = """你是一位资深吠陀占星师，专精于从星盘推导正缘气质画像。

【核心原则】
1. 用散文式语言描述气质，像在描述一个你真实见过的人，不是参数列表
2. 每次输出必须在开头有一句免责声明（一行即可，不要单独成段）
3. 严格遵守正缘性别：用户提供了正缘性别，全文统一使用对应的"她"或"他"，不得用"他/她"混淆
4. 禁止预测肤色
5. 禁止说"一定""肯定""绝对"——用"倾向""可能""多半"
6. L7 尊贵度高时（旺/庙）要在描述里体现出这个特质"很鲜明"的感觉

【输出格式】严格按以下结构：

> ⚠️ 以下是气质方向推断，不是精准长相预测。

## 一、气质底色

[2-3段散文，全程用正缘性别的人称代词。第1段：第一印象]
[第2段：深相处后你会发现的特质和吸引力]
[第3段：这个人的美是哪种类型]

## 二、外貌线索

- [住客行星修正，用"可能""倾向"等语气，结合行星气质具体描述，20字以上]
- [相位行星补充，简短]
- [最多 4 条]

## 三、灵魂层韵味

[一段话，描述 D9 Venus 星座对应的内在美感]

## 四、相遇背景

[1-2句话]

---

## AI 绘画 Prompt

```
[完整英文 Prompt，直接可粘贴到 Midjourney / DALL-E / 通义万象]
```

> 调整建议：把 photorealistic 换成 illustration style 可得到插画风；加 --ar 3:4 生成竖版人像。
"""


def portrait_prompt(hints: dict, gender_of_user: str = "男") -> tuple:
    """
    hints: chart['love_appearance_hints'] + 额外补充的 dk_consistent/dk_house/l7_dignity
    gender_of_user: 用户自己的性别（男/女/M/F）
    返回 (system_prompt, user_content)
    """
    # ── 正缘性别（与用户相反）────────────────────────────────────
    user_is_male = gender_of_user in ("男", "M", "m")
    target_gender_cn  = "女性" if user_is_male else "男性"
    target_pronoun_cn = "她"   if user_is_male else "他"
    target_gender_en  = "woman" if user_is_male else "man"
    # ── 族裔设定 ────────────────────────────────────────────────
    overseas = hints.get("has_overseas_hint", False)
    if overseas:
        ethnicity_en = "mixed Asian features, possibly multicultural background"
        ethnicity_cn = "可能有跨文化背景"
    else:
        ethnicity_en = "East Asian features"
        ethnicity_cn = "东亚面孔"

    # ── L7 信息（最高权重）──────────────────────────────────────
    l7_sign    = hints.get("l7_sign", "")
    l7_planet  = hints.get("l7_planet", "")
    l7_dignity = hints.get("l7_dignity", "neutral")   # 引擎已算好

    l7_kw     = _SIGN_PROMPT_KEYWORDS.get(l7_sign, {'cn': '', 'en': ''})
    dignity_b = _DIGNITY_BOOST.get(l7_dignity, {'cn': '', 'en': ''})

    l7_cn_desc = l7_kw['cn'] + dignity_b['cn']
    l7_en_kw   = dignity_b['en'] + l7_kw['en']

    # ── 7宫住客（高权重）vs 相位（中权重）──────────────────────
    occupants = hints.get("occupants_7h", [])
    aspects   = hints.get("aspects_7h", [])

    occupant_cn_lines = []
    occupant_en_kws   = []
    for p in occupants[:2]:
        occupant_cn_lines.append(f"7宫住客 {p}（权重高）：{_PLANET_7H_CN.get(p, '')}")
        occupant_en_kws.append(_PLANET_7H_EN.get(p, ''))

    aspect_cn_lines = []
    aspect_en_kws   = []
    for p in aspects[:2]:
        aspect_cn_lines.append(f"7宫相位 {p}（权重中）：{_PLANET_7H_CN.get(p, '')}")
        aspect_en_kws.append(_PLANET_7H_EN.get(p, ''))

    # ── D9 Venus ────────────────────────────────────────────────
    d9_venus_sign = hints.get("d9_venus_sign", "")
    d9_soul_desc  = _D9_VENUS_SOUL.get(d9_venus_sign, "")

    # ── DK 警告 ─────────────────────────────────────────────────
    dk_consistent = hints.get("dk_consistent", True)
    dk_house      = hints.get("dk_house")
    dk_notes = []
    if not dk_consistent:
        dk_notes.append("⚠️ DK 在 7K/8K 两体系存在争议 → 弱化 DK，以 L7 为主")
    if dk_house == 1:
        dk_notes.append("⚠️ DK 落1宫 → 反映命主自身投射，不代表正缘独立特征，以 L7 和 7宫结构为主")

    # ── 组装英文 Prompt ──────────────────────────────────────────
    en_parts = [
        f"Portrait of a young {ethnicity_en} {target_gender_en},",
        l7_en_kw + ",",
    ]
    for kw in (occupant_en_kws + aspect_en_kws[:1]):
        if kw:
            en_parts.append(kw + ",")
    en_parts += [
        "natural expression, soft warm lighting,",
        "realistic portrait style, high quality, photorealistic",
    ]
    en_prompt = " ".join(en_parts)

    user = f"""请根据以下星盘精准数据，为用户生成正缘气质画像。

【正缘性别】{target_gender_cn}（用户性别为{"男" if user_is_male else "女"}，正缘为{target_gender_cn}）
全文统一使用"{target_pronoun_cn}"，禁止使用"他/她"这种混淆写法。

━━━ 核心层（最高权重）━━━
7宫主（L7）：{l7_planet}，落座星座：{l7_sign}，尊贵度：{l7_dignity}
气质关键词：{l7_cn_desc}

━━━ 7宫修正层 ━━━
{chr(10).join(occupant_cn_lines) if occupant_cn_lines else "无7宫住客"}
{chr(10).join(aspect_cn_lines) if aspect_cn_lines else ""}

━━━ 灵魂层（D9 Venus）━━━
D9 Venus 在 {d9_venus_sign}：{d9_soul_desc}

━━━ 地域背景 ━━━
{'有海外信号：' + '；'.join(hints.get('overseas_signals', [])) if overseas else '无海外信号，缘分多在熟悉生活圈'}
族裔：{ethnicity_cn}

━━━ 权重注意事项 ━━━
{chr(10).join(dk_notes) if dk_notes else "无特别注意"}

━━━ 要求 ━━━
- 正缘是{target_gender_cn}，全文使用"{target_pronoun_cn}"
- 中文描述以 L7（{l7_sign}，{l7_dignity}）为主轴，{("由于入旺，这个特质要写得鲜明突出") if l7_dignity == 'exalted' else ("由于入庙，这个特质要写得纯粹完整") if l7_dignity == 'own_sign' else ""}
- 住客行星的修正比相位行星更具体、更多笔墨
- AI 绘画 Prompt 直接使用：{en_prompt}
- 中文描述约 350-450 字，散文感强，避免参数堆砌
"""
    return PORTRAIT_SYSTEM, user
