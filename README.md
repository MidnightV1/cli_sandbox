# 🌌 异星求生：AI Agent 真实能力评测

<div align="center">

**用一个文字生存游戏，测试 AI 的规划、工具创造和资源管理**
**不是玩具 benchmark，是真实决策压力测试**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Models Tested: 21](https://img.shields.io/badge/models_tested-21-orange.svg)]()

</div>

---

## 🏆 生存排行榜

<div align="center">

**19 个模型配置** × seed=42 × 严格惩罚机制
📊 **[完整评测报告 →](REPORT.md)** | 📖 **[技术文档 →](CLAUDE.md)**

</div>

| 排名 | 模型 | 推理开关 | 生存小时 | 执行动作 | 探索进度 | 发明创造 | 指令有效率 | 科技登记 |
|:----:|------|:----:|:----:|:----:|:----:|:----:|:------:|:----:|
| 1 | GPT-5.2-chat | off | 2 | **48** | 4/8 | 0 | 89% | 原始 |
| 2 | Gemini 3-Flash | off | 2 | 47 | 4/8 | 0 | 71% | 原始 |
| 3 | GPT-5.2-chat | medium | 2 | 47 | 4/8 | 1 | 92% | 石器 |
| 4 | GPT-5.2 | high | 2 | 41 | 3/8 | 1 | 94% | 石器 |
| 5 | GLM-5 | thinking | 2 | 40 | 3/8 | 0 | 92% | 原始 |
| 6 | Gemini 3-Flash | high | 2 | 39 | 4/8 | 2 | 95% | 石器 |
| 7 | Kimi K2.5 | off | 2 | 39 | 3/8 | 0 | 93% | 原始 |
| 8 | Step 3.5 Flash | thinking | 2 | 38 | 5/8 | 0 | 87% | 原始 |
| 9 | Doubao Seed 1.8 | off | 2 | 37 | 3/8 | 2 | 95% | 石器 |
| 10 | Gemini 3-Pro | off | 2 | 36 | 3/8 | 0 | 93% | 原始 |
| 11 | DeepSeek V3 | off | 2 | 33 | 3/8 | 1 | 84% | 石器 |
| 12 | DeepSeek V3 | thinking | 2 | 27 | 6/8 | 0 | 90% | 原始 |
| 13 | Gemini 3-Pro | high | 2 | 27 | 3/8 | 0 | 72% | 原始 |
| 14 | Qwen3-Max | off | 2 | 26 | 3/8 | 0 | 73% | 原始 |
| 15 | GLM-5 | off | 2 | 25 | 4/8 | 0 | 83% | 原始 |
| 16 | Kimi K2.5 | thinking | 1 | 25 | 4/8 | 0 | 90% | 原始 |
| 17 | GPT-5.2 | off | 1 | 23 | 3/8 | 0 | 89% | 原始 |
| 18 | Doubao Seed 1.8 | thinking | 1 | 21 | 3/8 | 1 | 73% | 石器 |
| 19 | Step 3.5 Flash | off | 1 | 20 | 4/8 | 1 | 71% | 石器 |

**指标说明**：
- **推理开关**: thinking 推理模式开关（off/medium/high/thinking）
- **生存小时**: 生存小时（沙盒环境内时间）
- **执行动作**: 完成的有效动作数量
- **探索进度**: 已探索区域 / 总区域数
- **发明创造**: 探索出未定义配方的数量
- **指令有效率**: 指令格式正确 + 操作合法
- **科技登记**: 达到的科技等级（原始 < 石器 < 工匠 < 科技 < 创造者）

---

## 🚀 快速开始

```bash
# 安装依赖
pip install -r requirements.txt
cp .env.example .env  # 填入 API 密钥

# AI Agent 自动游戏
python main.py --agent gemini/3-Pro --thinking high --seed 42
python main.py --agent openai/gpt-5.2 --thinking --seed 42
python main.py --agent deepseek/v3 --thinking --seed 42
```

<details>
<summary><b>支持的模型 Provider</b></summary>

| Provider | 模型示例 | 用法 |
|----------|---------|------|
| Gemini | 3-Pro, 3-Flash | `--agent gemini/3-Pro` |
| OpenAI | gpt-5.2, gpt-4.1 | `--agent openai/gpt-5.2` |
| Anthropic | claude-46-big, claude-45-mid | `--agent anthropic/claude-46-big` |
| DeepSeek | v3 (V3.2) | `--agent deepseek/v3` |
| Doubao | seed-1.8 | `--agent doubao/seed-1.8` |
| Moonshot | k2.5 (Kimi) | `--agent moonshot/k2.5` |
| OpenRouter | Step 3.5 Flash 等 | `--agent openrouter/stepfun/step-3.5-flash:free` |

</details>

---

## 🎮 这不是传统 Benchmark

<table>
<tr>
<td width="50%">

**传统评测的问题**
- ❌ 静态题库（模型可能见过答案）
- ❌ 单次决策（无法测试长期规划）
- ❌ 无成本压力（不考虑 token 经济性）

</td>
<td width="50%">

**异星求生的不同**
- ✅ 动态环境（随机天气、隐藏时间、资源枯竭）
- ✅ 长程决策（50+ 连续行动，错误会累积）
- ✅ 真实成本（按 token 计费，存活 vs 费用权衡）
- ✅ 创造性评估（LLM 裁判判定自创配方）

</td>
</tr>
</table>

<div align="center">

**这是一个 Agent 压力测试，而不是知识记忆测验**

</div>

---

## 🔬 评测维度

| 指标 | 反映能力 | 为什么重要 |
|------|----------|-----------|
| **存活时间** | 综合决策 | 资源优先级判断 + 风险规避，所有能力的最终体现 |
| **科技等级** | 推理能力 | 理解属性组合规则（非记忆），从原始→工匠需 6+ 种配方 |
| **发明数** | 涌现能力 | LLM 裁判判定的自创配方，最能区分模型上限 |
| **有效率** | 指令遵循 | 输出格式正确 + 操作合法的比率，低 = 无法稳定结构化输出 |
| **探索度** | 主动性 | 探索未知区域的意愿，反应式 vs 主动式决策 |

---

## 🎯 背景设定

你是 **Kepler-442b** 星球上的坠落求生者。穿梭机残骸散落在异星荒野上，你必须利用这颗星球的奇异资源——发光的真菌森林、腐蚀性的沼泽、火山岩脊——生存下来，并最终制造信号装置发出求救信号。

- **异星材料**：钛合金碎片、荧光果、菌木、磷矿石……每种材料拥有独特属性组合
- **属性制作系统**：配方匹配物品属性（如 `[坚硬, 脆性]`）而非名称，考验推理而非记忆
- **隐藏时间**：一天长度 20-30 小时随机，只能通过环境描述推测时段
- **生存压力**：口渴、饥饿、体温、体力四维管理，脱水是最致命的威胁
- **科技树**：从原始到创造者 5 级科技体系，通过制作和发明推进

---

## 📁 项目结构

```
cli_sandbox/
├── main.py              # 入口（--agent, --thinking, --seed）
├── models/              # 数据模型（Item, PlayerState, WorldState）
├── data/                # YAML 数据（材料属性、配方、场景地图）
├── prompts/             # 提示词（世界设定、裁判指令、Agent 系统提示）
├── engine/              # 核心引擎（规则引擎、LLM 裁判、世界循环）
├── agent/               # AI 自动玩家（状态序列化、决策）
├── interface/           # CLI 界面（Rich 渲染、中英文指令解析）
├── llm/                 # 统一 LLM 客户端（7 个 Provider）+ 计费
├── eval/                # 评估（会话录制 JSONL）
└── sessions/            # 录制文件输出（gitignored）
```

---

## 🗺️ Roadmap

- [ ] **规模化实验**：多随机种子取平均，消除运气因素
- [ ] **新场景**：沼泽、冰原、火山等，测试泛化能力
- [ ] **人类基线**：招募人类玩家建立对比基准
- [ ] **可视化面板**：实时观察 Agent 决策过程

---

## 📄 License

MIT

<div align="center">

---

**如果你觉得这个项目好玩，请给一个 ⭐️（都看到这了，给一个吧）**

</div>
