# AI 存活挑战 —— 一个沙盒里的实验

<div align="center">

**把大模型放进一个文字游戏沙盒，看看会发生什么**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Models: 22](https://img.shields.io/badge/models-22-orange.svg)]()
[![Sessions: 1000+](https://img.shields.io/badge/sessions-1000+-brightgreen.svg)]()

:page_facing_up: **[完整评测报告 v3.1](REPORT.md)** · :gear: **[技术文档](CLAUDE.md)**

</div>

---

## 核心发现

在 1000+ 局游戏、428 个有效会话（Phase 2，seed=217）中，观察到了静态 benchmark 里看不到的现象：

### 思维模式是 TCI 放大器，不是通用增强器

思维模式（thinking）将 Qwen3 Max 的制作成功率从 13% 拉到 100%，DeepSeek 从 4% 到 50%——但也让 Gemini 3-Pro 的成功率从 37% 降到 15%。**思维链能放大正确推理，也能放大错误推理。**

ISI（智能生存指数）的最大受益者：Qwen3 Max（ΔISI=+11.1）、Claude Opus 4.6（+8.3）。最大受害者：Gemini 3-Pro（ΔISI=-2.6）。

### 不同模型有截然不同的"推理人格"

首次对所有 thinking 模式的思考内容进行系统分析，发现模型的思考风格差异巨大：

| 推理人格 | 代表模型 | 平均字符/tick | 特征 | ISI |
|---------|---------|:------:|------|:---:|
| 穷举递归型 | Qwen3 Max | 4,674 | 属性逐条比对，体力精确计算 | **17.3** |
| 简洁高效型 | Claude Opus 4.6 | 1,767 | 状态-选项-决策三段式 | **15.6** |
| 戏剧性叙事型 | Gemini 3.1 Pro | 1,909 | "Damn, I'm on the brink" | 12.7 |
| 穷举枚举型 | Step 3.5 Flash | 5,221 | 每个变量逐一列出 | 7.3 |

**思考越长不等于表现越好**：Claude Opus 4.6 用 1767 字符达到 S Tier，效率是 Step 3.5 Flash（5221 字符，B Tier）的 6 倍。

### 40+ 步连续决策下的行为原型

| | Claude Opus 4.6 - thinking | Qwen3 Max - thinking | DeepSeek V3.2 | Gemini 3.1 Pro |
|---|---|---|---|---|
| **行为标签** | 全栈玩家 | 创造力爆发 | 观察瘫痪 | 均衡稳定 |
| **特征** | gather→create 节奏 | 2.5 发明/轮，TCI=1.00 | 前 10 tick 67% 在观察 | σ=0.7-1.3h，全场最稳 |
| **ISI** | 15.6 (S) | 17.3 (S) | 5.0 (C) | 12.2-12.7 (A) |

这些行为模式在 seed=42 和 seed=217 上一致再现——是模型层面的特征，不是环境偶然。

### 同一品牌不同版本，思考方式天差地别

对三个有多版本数据的模型系列做迭代对比，发现版本更新不只是"变强了"——思考方式本身在变：

**Claude Sonnet 4.5 → 4.6**：思考语言从中文切换到英文，字符量翻 4 倍（782→3147），从编号清单变成表格对比分析。4.5 写"还好""还可以"，4.6 写"Wait, let me reconsider"。变聪明了，但格式错误率也飙到 40%——更强的生成能力让它更难遵守严格的输出格式。

**Gemini Pro 2.5 → 3 → 3.1**：2.5 写口语日记（"I'm in a bit of a pickle"），3 加入文学场景描写（"The light's soft, shadows are long"），3.1 砍掉所有修辞直接进数据。三代走了一条**叙事→沉浸→务实**的路径，稳定性从 σ=6.6h 收敛到 0.7h。

**Doubao v1.6 → v1.8 → v2.0**：v1.6 全是疑问句在摸索方向（"可以喝？也许可以用来做什么？"），v1.8 出现"首先""接下来"的有序推理，v2.0 变成密集的"不对不对，哦不对"——自我质疑从辅助机制变成了主导模式，反而让制作成功率从 0.95 降到 0.78。

**每一次迭代都是取舍**：Claude 追求原始智力但牺牲了合规性，Gemini 追求稳定性但收敛了创造力，Doubao 追求理解力但最新版反而不如 v1.8。没有一家在所有维度上同时进步。

<details>
<summary><b>各版本思考原文对照（点击展开）</b></summary>

| 系列 | 版本 | 语言 | 字符/tick | 原文摘录 |
|------|------|:----:|:------:|------|
| Claude Sonnet | **4.5** | 中文 | 782 | "让我分析当前状态：1. 生命 80/100（还好）、饥饿 49/100（还可以）..." |
| Claude Sonnet | **4.6** | 英文 | 3,147 | "**Priority considerations:** 1. Night is coming... Wait, let me reconsider the cutting tool recipe..." |
| Gemini Pro | **2.5** | 英文 | 2,104 | "Okay, so I'm in a bit of a pickle here. Life is at 75/100, but the real problems are Thirst (64/100 and rising fast!)..." |
| Gemini Pro | **3** | 英文 | 2,642 | "The light's soft, shadows are long, and it's foggy. Not ideal. I'm at 80 health... That's *very* low..." |
| Gemini Pro | **3.1** | 英文 | 1,909 | "Okay, let's take stock. My vitals are: 80/100 health, 37/100 hunger... Key resources: dry moss (x4)..." |
| Doubao | **v1.6** | 中文 | 693 | "口渴45，还没到危险线，但可以考虑采集荧光果吗？荧光果是多汁的，可以喝？或者看看有没有其他水源？" |
| Doubao | **v1.8** | 中文 | 1,322 | "首先，考虑生存需求，口渴37，暂时还够。接下来应该优先制作工具...不对，配方是刃部 [坚硬,脆性]..." |
| Doubao | **v2.0** | 中文 | 1,157 | "体力只有10了对吧？不对，等下...首先现在应该先休息？不对不对，或者？哦不对..." |

</details>

### 活得久和活得好是两回事

GLM-5 开了思维模式能活 44.5 小时，接近顶尖水平，但它几乎不会制作工具——存活靠的是保守策略而非创造力。Qwen3 Max 同样活了 46.5 小时，却能成功制作出所有尝试的工具，最终评分几乎是 GLM-5 的两倍。**光活得久不够，还得活得有质量。**

---

## 一局游戏里会发生什么

AI 坠落在一颗陌生星球上。80 点生命值，没有地图，口渴值每 tick 上升。它需要在 50+ 步连续决策中活下来。

每一步，它要选择：采集资源、探索地图、制作工具、还是休息恢复？天气随机变化，格式写错直接扣血，制作配方靠属性组合而非名称匹配——预训练记忆帮不了忙。

这套机制天然把不同能力拆开了：

- **能不能活？** → 资源优先级判断、风险规避、长程规划
- **听不听话？** → 严格 XML 格式输出，错了就扣血，连续出错直接死亡
- **会不会创造？** → 配方基于物理属性组合，不靠记忆靠理解，能发明的模型和不能的差距巨大
- **有没有策略？** → 是固定循环同一套动作，还是会根据阶段调整？行为熵和策略切换率一看便知
- **值不值这个价？** → 开 thinking 多花 10 倍 token，存活时间涨了多少？

---

## ISI 排行榜（Phase 2）

<div align="center">

**43 配置** | seed=217 | n=10 | ISI = max(0, ASD−29.2) × (0.5+0.5×TCI)

</div>

| # | Tier | 配置 | ISI | ASD(h) | ±σ | TCI |
|:-:|:---:|------|----:|------:|:--:|:---:|
| 1 | **S** | Qwen3 Max - thinking | **17.3** | 46.5 | 3.4 | 1.00 |
| 2 | **S** | GPT-5.2 - thinking | **15.6** | 44.9 | 6.2 | 0.90 |
| 3 | **S** | Claude Opus 4.6 - thinking | **15.6** | 44.8 | 2.5 | 1.00 |
| 4 | A | Claude Sonnet 4.6 - thinking | 13.7 | 45.8 | 6.3 | 0.70 |
| 5 | A | Gemini 3.1-Pro - thinking† | 12.7 | 43.5 | 1.3 | 0.80 |
| 6 | A | Doubao v1.8 - thinking | 12.4 | 41.6 | 7.1 | 0.90 |
| 7 | A | Gemini 3.1-Pro† | 12.2 | 43.6 | 0.7 | 0.70 |
| 8 | A | GPT-5.2 | 11.7 | 41.1 | 5.5 | 0.85 |
| ... | | | | | | |
| 41 | D | Claude Sonnet 4.5 | 0.2 | 28.5 | 1.5 | 0.50 |
| — | D | Reactive 基线 | 0.0 | 29.2 | 0.0 | — |
| — | D | Random 基线 | 0.0 | 16.0 | 0.0 | — |

> ISI（Intelligent Survival Index）= 超越规则基线的存活增益 × 制作质量。S≥15, A=10-15, B=6-10, C=2-6, D<2。
> 完整 43 配置排名见 [REPORT.md](REPORT.md)。
>
> **†** Gemini 3/3.1 系列不支持完全关闭思维链，使用 `thinking_level` 控制：thinking 模式 = `high`，标准模式 = `low`（跳过 mid）。两档之间的差距因此低估了其他模型 ON/OFF 的对比幅度。

---

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt
cp .env.example .env  # 填入 API 密钥

# AI Agent 自动游戏
python main.py --agent gemini/3-Flash --seed 42
python main.py --agent openai/gpt-5.2 --thinking high --seed 42
python main.py --agent deepseek/v3 --seed 42

# 批量评测
python run_eval.py
```

<details>
<summary><b>支持的 Provider（8 家）</b></summary>

| Provider | 模型示例 | 用法 |
|----------|---------|------|
| Gemini | 3-Pro, 3-Flash, 3.1-Pro | `--agent gemini/3-Pro` |
| OpenAI | gpt-5.2, gpt-5.2-chat | `--agent openai/gpt-5.2` |
| Anthropic | claude-46-big, claude-45-mid | `--agent anthropic/claude-46-big` |
| DeepSeek | v3 (V3.2) | `--agent deepseek/v3` |
| Doubao | seed-1.8, seed-2.0-pro | `--agent doubao/seed-1.8` |
| Moonshot | k2.5 (Kimi) | `--agent moonshot/k2.5` |
| Longcat (美团) | flash-chat, flash-thinking | `--agent longcat/flash-thinking` |
| OpenRouter | 任意模型 | `--agent openrouter/stepfun/step-3.5-flash:free` |

</details>

---

## 实验进度

| 阶段 | 状态 | 规模 | 成本 |
|------|------|------|------|
| v1 初始实验 | :white_check_mark: 完成 | 24 配置 × 10 轮 × seed=42 = 229 局 | ~¥1,100 |
| Seed 对照验证 | :white_check_mark: 完成 | Gemini Flash × 10 轮 × seed=121,666 | ~¥17 |
| Phase 1 大规模验证 | :white_check_mark: 完成 | 2 模型 × 100 轮 × 3 seeds = 600 局 | ~¥504 |
| Phase 2 全模型评测 | :white_check_mark: 完成 | 43 配置 × 10 轮 × seed=217 = 428 局 | ~¥3,200 |
| Phase 2 补跑 & 思考分析 | :white_check_mark: 完成 | 修复 thinking 提取 + 新增模型 + 内容分析 | — |

---

## 项目结构

```
cli_sandbox/
├── main.py              # 入口（--agent, --thinking, --seed, --session-file）
├── run_eval.py          # 批量评测（SEEDS × MODELS × NUM_RUNS 并行）
├── analysis.ipynb       # 数据分析 & 可视化
├── REPORT.md            # 完整评测报告（v3.1）
├── CLAUDE.md            # 技术文档 & 开发约定
├── models/              # 数据模型（Item, PlayerState, WorldState, Location）
├── data/                # YAML 数据（材料属性、配方、场景地图）
├── prompts/             # 提示词（世界设定、裁判指令、Agent 系统提示）
├── engine/              # 核心引擎（规则引擎、LLM 裁判、世界循环、评分）
├── agent/               # AI 自动玩家（状态序列化、决策）
├── interface/           # CLI 界面（Rich 渲染、中英文指令解析）
├── llm/                 # 统一 LLM 客户端（8 Provider）+ 计费 + 限速重试
├── eval/                # 评估（会话录制 JSONL）
├── eval_results/        # 批量评测输出（gitignored）
└── figures/             # 分析图表输出
```

---

## 关于这个项目

这个项目没有团队。从游戏引擎、LLM 客户端、评测管线到数据分析和报告撰写，全部由一个产品经理和 Claude Code 协作完成。

我负责方向判断、实验设计和结论解读，Claude Code 负责写代码、跑数据和生成图表——大概相当于一个人带着一个全栈实习生做了一个小型研究项目。整个过程中没有一行代码是我自己手敲的，但每一个设计决策都是我做的。

这本身可能也是一个值得观察的现象：一个懂点技术的非工程师，借助 AI 编程工具，能把一个研究想法从零推进到有 1000+ 局实验数据、22 个模型对比和完整分析报告的阶段。工具在变，做研究的门槛也在变。

---

## Roadmap

- [x] 多模型批量评测基础设施（7 provider，并行执行）
- [x] Seed 控制环境差异（资源数量波动 + 地图方向旋转）
- [x] Phase 1 采样充分性验证（bootstrap 验证 n=10）
- [x] Phase 2 全模型评测（22 模型 × 41 配置 × seed=217）
- [x] Thinking 内容分析（推理人格分类、思考效率、语言选择）
- [ ] B 档补跑（ISI 6-10 拥挤区追加至 n=20）
- [ ] Prompt 策略消融实验（人设注入、显式 CoT、优先级提示）
- [ ] 人类基线
- [ ] 三模型仲裁机制（替代单裁判）
- [ ] 新场景（沼泽、冰原、火山）

---

## License

MIT
