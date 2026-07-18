# 报告打包规则

> 用途：当用户说"生成报告""打包""导出HTML"时执行

---

## 脚本位置

`report_builder.py` 在本 skill 的 `scripts/` 目录下。
**完整路径**：使用相对于 SKILL.md 的路径 `scripts/report_builder.py`。

如果执行时提示找不到脚本，按以下顺序查找：
1. 当前 skill 目录下的 `scripts/report_builder.py`
2. 工作目录下的 `report_builder.py`（用户可能手动复制过）
3. 如果都找不到 → 告诉用户脚本路径，让用户确认位置

---

## 单人报告打包命令

```bash
# 打包全部已有文件（推荐）
python scripts/report_builder.py [工作目录] --name "姓名" --lagna "上升星座" --lang cn

# 只打包核心分析（不含事业/感情）
python scripts/report_builder.py [工作目录] --name "姓名" --include core --lang cn

# 打包核心 + 事业
python scripts/report_builder.py [工作目录] --name "姓名" --include core,career --lang cn

# 打包核心 + 感情
python scripts/report_builder.py [工作目录] --name "姓名" --include core,love --lang cn
```

`report_builder` 自动检测目录中存在哪些 MD 文件，只打包存在的。

### 单人报告支持的 MD 文件命名规范

| 模块 | 文件名（新规范） | 报告章节 |
|:-----|:--------------|:---------|
| 行星审计 | `p2a_planets.md` ~ `p2d_planets.md` | 第二部分 A–D |
| D9 分析 | `p3a_d9.md` | 第三部分 A |
| 分盘交叉 | `p3b_divisional.md` | 第三部分 B |
| D30/D60/多系统 | `d30_analysis.md` / `d60_karma.md` / `karma_dasha.md` | 第三部分 C–E |
| D11 | `d11_analysis.md` | 第三部分 F |
| 宫位诊断 | `p4a_houses.md` / `p4b_houses.md` | 第四部分 A–B |
| 人生架构 | `p5a_life.md` / `p5b_life.md` | 第五部分（续） |
| 事业 | `career_part1.md` ~ `career_part5.md` | 第六部分（续×4） |
| 感情 | `love_part1.md` ~ `love_part3.md` | 第七部分（续×2） |
| 技术附录 | `appendix.md` | 技术附录（末尾） |
| 问答 | `qa_*.md`（glob） | 附录：追问答疑 |

---

## 合盘报告打包命令（二人合盘）

合盘报告需要**两步**：先生成 MD，再打包 HTML。

### 第一步：生成合盘 MD 文件

```bash
# 使用 synastry_formatter.py 计算并格式化
python scripts/synastry_formatter.py \
    --p1-name "甲方姓名" --p1-dob 1990-01-15 --p1-time 10:30 --p1-place "Shanghai" \
    --p2-name "乙方姓名" --p2-dob 1992-06-20 --p2-time 14:00 --p2-place "Beijing" \
    --output-dir [输出目录]
```

生成的文件：
- `synastry_overview.md` — 否决检查 + 总分 + 8 项 Koota 明细
- `synastry_jaimini.md`  — Jaimini 双盘交叉 + 深层信号
- `synastry_advice.md`   — 综合建议 + 实践指引

### 第二步：打包 HTML 合盘报告

```bash
python scripts/report_builder.py [输出目录] \
    --type synastry \
    --p1 "甲方姓名" \
    --p2 "乙方姓名" \
    --lang cn
```

`--type synastry` 触发合盘专用封面（显示双方信息 + Ashtakoota 总分），
并自动跳过单人报告章节，只打包三个合盘 MD 文件。

---

## ⚠️ 禁止行为

1. **禁止自动打开浏览器预览**：生成 HTML 后不要用 `open`/`start`/`xdg-open` 打开浏览器。只告诉用户文件路径，让用户自己决定是否打开。
2. **禁止在聊天框中输出 HTML 代码**：HTML 文件由脚本生成，不要在对话中贴代码。
3. **生成完成后只报路径**：`"报告已生成：[完整文件路径]"`，不做其他操作。

