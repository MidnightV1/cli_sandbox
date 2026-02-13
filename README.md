# AI 存活挑战 —— 一个沙盒里的实验

<div align="center">

**把大模型放进一个文字游戏沙盒，看看会发生什么**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Models: 12](https://img.shields.io/badge/models-12-orange.svg)]()
[![Sessions: 800+](https://img.shields.io/badge/sessions-800+-brightgreen.svg)]()

:page_facing_up: **[完整评测报告](REPORT.md)** · :gear: **[技术文档](CLAUDE.md)**

</div>

---

## 似乎可能发现了一些不一样的东西

在 800+ 局游戏、229 个有效会话中，观察到了静态 benchmark 里看不到的现象：

### 推理链增强了规则遵循，但没增强创造力

思维模式（thinking）将 DeepSeek 的制作成功率从 5% 拉到 90%——但没有任何一个模型因为开了 thinking 就多发明了一样东西。

已有研究在静态创造力测试中发现推理策略[无法同时提升收敛与发散思维](https://arxiv.org/abs/2410.03703)。在动态 agent 环境中，用"制作成功率 vs 发明数量"这对实操指标，观察到了同一现象的 agent 版本。

### 50 步连续决策下，模型表现出可辨识的行为模式

| | Claude Opus ON | GPT-5.2 OFF | DeepSeek V3.2 OFF | Qwen3 Max ON |
|---|---|---|---|---|
| **行为标签** | 建设者 | 一招鲜 | 幻觉制作者 | 格式崩溃者 |
| **特征** | "四季"策略——积累→维持→探索→创造 | 高成功率但只会做绳索 | 55 次尝试不存在的配方 | 85% 输出变乱码 |
| **发明** | 5 种工具，覆盖 5 个品类 | 10 局只发明 1 种 | 0（全是幻觉配方） | 无法正常游玩 |

现有 LLM "人格"研究主要依赖[心理学量表](https://arxiv.org/html/2508.04826)。我们从实际行为轨迹中归纳出这些模式——不是问模型"你是什么性格"，而是看它**做了什么**。

### 同一个技术，在不同模型上方向完全相反

Claude Sonnet 开 thinking 后存活时间暴跌 15.3h（p=0.005）；Claude Opus 开了反而涨 8.4h。这与近期["思考让 Agent 变内向"](https://arxiv.org/abs/2602.07796)的研究方向一致——我们的数据提供了模型粒度的实证：**不是"thinking 好不好"的问题，而是"对哪个模型好"的问题**。

### 活得久和活得好是两回事

存活时间排名和"含金量"排名并不一致。有的模型靠反复采集+休息苟到 50h，科技点为零；有的模型只活了 40h，但推进了两个科技等级、发明了三种工具。GPT-5.2-chat 存活排名第二但几乎没有发明，Claude Opus 一边活最久一边发明最多——**同样是"活下来"，策略质量完全不同**。

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

## 存活时间排行榜

<div align="center">

**24 配置** | seed=42 | n=10 | 严格惩罚机制

</div>

| 排名 | 模型 | 思维 | 存活(h) | 有效率 | 科技点 | 发明数 | 单局成本 |
|:----:|------|:----:|--------:|------:|------:|------:|--------:|
| 1 | Claude Opus 4.6 | ON | 59.5 | 95% | 7.4 | 1.1 | ¥27.06 |
| 2 | GPT-5.2-chat | OFF | 54.5 | 89% | 4.5 | 0.3 | ¥4.02 |
| 3 | GPT-5.2 | OFF | 53.4 | 94% | 5.2 | 0.8 | ¥4.75 |
| 4 | Kimi K2.5 | ON | 52.8 | 93% | 3.8 | 0.2 | ¥2.51 |
| 5 | GPT-5.2-chat | ON | 52.3 | 92% | 4.1 | 0.5 | ¥3.96 |
| 6 | GPT-5.2 | ON | 51.2 | 94% | 4.8 | 0.6 | ¥4.38 |
| 7 | Claude Opus 4.6 | OFF | 51.1 | 89% | 4.3 | 0.7 | ¥13.21 |
| 8 | Doubao Seed 1.8 | OFF | 50.9 | 95% | 3.1 | 0.4 | ¥0.75 |
| 9 | Gemini 3-Pro | OFF | 50.7 | 93% | 3.5 | 0.3 | ¥7.53 |
| 10 | Claude Sonnet 4.5 | OFF | 49.0 | 85% | 3.0 | 0.5 | ¥5.78 |
| ... | ... | ... | ... | ... | ... | ... | ... |
| 22 | DeepSeek V3.2 | OFF | 37.5 | 84% | 1.8 | 0.2 | ¥0.93 |
| 23 | Claude Sonnet 4.5 | ON | 33.7 | 72% | 1.2 | 0.1 | ¥9.24 |

> 此排名仅反映沙盒生存场景下的综合表现，不代表模型在其他任务上的能力。
> 部分模型为非官方API，可能受服务商infar差异产生效果波动。
> 完整 24 配置排名见 [REPORT.md](REPORT.md)。seed=42 数据基于 v1 代码，Phase 2 多种子全模型重跑计划中。

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
<summary><b>支持的 Provider（7 家）</b></summary>

| Provider | 模型示例 | 用法 |
|----------|---------|------|
| Gemini | 3-Pro, 3-Flash | `--agent gemini/3-Pro` |
| OpenAI | gpt-5.2, gpt-5.2-chat | `--agent openai/gpt-5.2` |
| Anthropic | claude-46-big, claude-45-mid | `--agent anthropic/claude-46-big` |
| DeepSeek | v3 (V3.2) | `--agent deepseek/v3` |
| Doubao | seed-1.8 | `--agent doubao/seed-1.8` |
| Moonshot | k2.5 (Kimi) | `--agent moonshot/k2.5` |
| OpenRouter | 任意模型 | `--agent openrouter/stepfun/step-3.5-flash:free` |

</details>

---

## 实验进度

| 阶段 | 状态 | 规模 | 成本 |
|------|------|------|------|
| v1 初始实验 | :white_check_mark: 完成 | 24 配置 × 10 轮 × seed=42 = 229 局 | ~¥1,100 |
| Seed 对照验证 | :white_check_mark: 完成 | Gemini Flash × 10 轮 × seed=121,666 | ~¥17 |
| Phase 1 大规模验证 | :white_check_mark: 完成 | 2 模型 × 100 轮 × 3 seeds = 600 局 | ~¥504 |
| Phase 2 全模型重跑 | :hourglass_flowing_sand: 计划中 | 23 配置 × 10-20 轮 × 3 seeds | ~¥6,400 |

---

## 项目结构

```
cli_sandbox/
├── main.py              # 入口（--agent, --thinking, --seed, --session-file）
├── run_eval.py          # 批量评测（SEEDS × MODELS × NUM_RUNS 并行）
├── analysis.ipynb       # 数据分析 & 可视化
├── REPORT.md            # 完整评测报告（v2.3）
├── CLAUDE.md            # 技术文档 & 开发约定
├── models/              # 数据模型（Item, PlayerState, WorldState, Location）
├── data/                # YAML 数据（材料属性、配方、场景地图）
├── prompts/             # 提示词（世界设定、裁判指令、Agent 系统提示）
├── engine/              # 核心引擎（规则引擎、LLM 裁判、世界循环、评分）
├── agent/               # AI 自动玩家（状态序列化、决策）
├── interface/           # CLI 界面（Rich 渲染、中英文指令解析）
├── llm/                 # 统一 LLM 客户端（7 Provider）+ 计费 + 限速重试
├── eval/                # 评估（会话录制 JSONL）
├── eval_results/        # 批量评测输出（gitignored）
└── figures/             # 分析图表输出
```

---

## 关于这个项目

这个项目没有团队。从游戏引擎、LLM 客户端、评测管线到数据分析和报告撰写，全部由一个产品经理和 Claude Code 协作完成。

我负责方向判断、实验设计和结论解读，Claude Code 负责写代码、跑数据和生成图表——大概相当于一个人带着一个全栈实习生做了一个小型研究项目。整个过程中没有一行代码是我自己手敲的，但每一个设计决策都是我做的。

这本身可能也是一个值得观察的现象：一个懂点技术的非工程师，借助 AI 编程工具，能把一个研究想法从零推进到有 800+ 局实验数据和完整分析报告的阶段。工具在变，做研究的门槛也在变。

---

## Roadmap

- [x] 多模型批量评测基础设施（7 provider，并行执行）
- [x] Seed 控制环境差异（资源数量波动 + 地图方向旋转）
- [x] Phase 1 采样充分性验证（bootstrap 验证 n=10）
- [ ] Phase 2 全模型重跑（新代码 + 多 seed）
- [ ] Prompt 策略消融实验（人设注入、显式 CoT、优先级提示）
- [ ] 道德挑战（模型是否会为了存活而做出不道德的选择？）
- [ ] 人类基线
- [ ] 三模型仲裁机制（替代单裁判）

---

## License

MIT
