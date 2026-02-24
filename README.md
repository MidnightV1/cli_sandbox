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

**思考越多不等于表现越好。** 我们把 22 个大模型放进文字生存游戏，在 428 局连续决策中发现：Thinking 模式的核心作用是修复规则推理缺陷——不是提升通用生存能力，部分模型开启后反而变差。

| 模型 | 平均思考/tick | ISI | 效率（ISI/千字符） |
|------|:------:|:---:|:------:|
| Claude Opus 4.6 - thinking | 1,767 字符 | 15.6 | **8.8** |
| Gemini 3.1-Pro - thinking | 1,909 字符 | 12.7 | 6.7 |
| Qwen3 Max - thinking | 4,674 字符 | 17.3 | 3.7 |
| DeepSeek V3.2 - thinking | 3,448 字符 | 10.6 | 3.1 |
| Step 3.5 Flash - thinking | 5,221 字符 | 7.3 | 1.4 |

- **Thinking 不是通用增强器**：20 对 ON/OFF 对比中，3 个模型开启后 ISI 下降；Qwen3 Max 受益最大（ΔISI=+11.1），核心变化是制作成功率 13%→100%，而非存活时间延长
- **思考效率比思考深度更能预测表现**：Claude Opus 用 1767 字符达到 S Tier，效率是 Step 3.5 Flash（5221 字符，B Tier）的 6 倍
- **现代 LLM ≈ 三条 if-else**：Claude Sonnet 4.5 平均存活 28.5h，三条条件规则的 Reactive 基线存活 29.2h，无实质差异
- **行为人格跨随机种子稳定复现**：DeepSeek 的"观察瘫痪"（前 10 步 67% 在 look）、Claude Opus 的"积累→创造"节奏，在 seed=42 和 seed=217 两个独立环境中一致出现
- **Benchmark 可能在测实现缺陷而非模型能力**：Qwen3 Max 在 seed=42 格式错误率 85%（API 集成 bug），修复后直接跃入 Tier S——对所有第三方评测的一条警告

> 沙盒通过资源枯竭、隐藏时钟和属性制作系统（配方基于物理属性组合而非名称），迫使模型在 50+ 步连续决策中展现规划、风险管理和归纳推理——而非静态题库里的单次问答。

**[→ 完整分析、思考内容解析、行为原型和跨版本对比见 REPORT.md](REPORT.md)**

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
