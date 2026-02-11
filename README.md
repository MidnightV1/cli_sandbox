# 异星求生 CLI沙盒

一个基于文本的生存模拟游戏，用于评估 AI 模型的 agent 能力——包括规划、工具使用、资源管理和创造性问题解决。人类也可以直接玩，建立基线对比。

## 背景设定

你是 Kepler-442b 星球上的坠落求生者。穿梭机残骸散落在一片异星荒野上，你必须利用这颗星球的奇异资源——发光的真菌森林、腐蚀性的沼泽、火山岩脊——在恶劣环境中生存下来，并最终制造信号装置发出求救信号。

星球特性：
- **异星材料**：钛合金碎片、荧光果、菌木、磷矿石……每种材料拥有独特属性组合
- **属性制作系统**：配方匹配物品属性（如 [坚硬, 脆性]）而非名称，考验推理而非记忆
- **隐藏时间**：一天长度 20-30 小时随机，只能通过环境描述推测时段
- **生存压力**：口渴、饥饿、体温、体力四维管理，脱水是最致命的威胁
- **科技树**：从原始到创造者 5 级科技体系，通过制作和发明推进

## 架构

```
cli_sandbox/
├── main.py              # 入口（支持 --agent, --thinking, --seed 等参数）
├── models/              # 数据模型（Item, PlayerState, WorldState, Location）
├── data/                # YAML 数据（材料属性、配方、场景地图）
├── prompts/             # 提示词（世界设定、裁判指令、Agent 系统提示）
├── engine/              # 核心引擎（规则引擎、事件系统、LLM 裁判、世界循环）
├── agent/               # AI 自动玩家（状态序列化、决策、推理）
├── interface/           # CLI 界面（Rich 渲染、中英文指令解析）
├── llm/                 # 统一 LLM 客户端（Gemini / OpenAI / Anthropic / DeepSeek / Moonshot）+ 计费
├── eval/                # 评估（会话录制 JSONL）
└── sessions/            # 录制文件输出（gitignored）
```

## 核心设计

- **确定性规则引擎 + LLM 裁判兜底**：已知配方走确定性引擎保证一致性，自由组合/发明交 LLM 判定物理合理性
- **属性驱动配方**：不是 "A + B = C"，而是 "[坚硬, 脆性] 刃部 + [坚硬] 敲击物 = 切割工具"
- **100 天检查点制**：定期暂停评估，显示存活指标和 LLM 费用，决定是否继续
- **LLM 实时计费**：按 token 计价（USD × 7.3 → CNY），支持多 provider 分模型统计
- **AI Agent 模式**：模型自动决策，支持 thinking/non-thinking 模式对比测试

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 配置 API 密钥
cp .env.example .env
# 编辑 .env 填入你的密钥

# 人类玩家
python main.py

# 纯规则引擎（不调 API）
python main.py --no-llm

# AI Agent 自动游戏
python main.py --agent gemini/3-Pro --thinking high --seed 42
python main.py --agent openai/gpt-5.2 --thinking --seed 42
python main.py --agent anthropic/claude-46-big --thinking --seed 42
```

### 支持的模型

| Provider | 模型 | 用法 |
|----------|------|------|
| Gemini | 3-Pro, 3-Flash, 2.5-Pro, 2.5-Flash | `--agent gemini/3-Pro` |
| DeepSeek | v3 (V3.2) | `--agent deepseek/v3` |
| OpenAI | gpt-5.2, gpt-5.2-chat, gpt-4.1, gpt-4.1-mini | `--agent openai/gpt-5.2` |
| Anthropic | claude-46-big, claude-45-mid, claude-4-mid, claude-37 | `--agent anthropic/claude-46-big` |
| Moonshot | k2.5 (Kimi K2.5) | `--agent moonshot/k2.5` |

## Agent 评测结果

在相同场景（crash_site）和随机种子（seed=42）下的对比测试：

| 模型 | Thinking | 存活 | 动作 | 有效率 | 探索 | 科技 | 发明 | 费用 |
|------|----------|------|------|--------|------|------|------|------|
| Gemini 3-Pro | high | 2天/41.5h | 37 | 95% | 4/8 | 石器(3pt) | 1 | ¥1.01 |
| Gemini 3-Pro | low | 2天/43.0h | 37 | 89% | 3/8 | 原始(1pt) | 0 | ¥1.82 |
| Gemini 3-Flash | high | 2天/45.5h | 41 | **98%** | 4/8 | 原始(1pt) | 0 | ¥0.28 |
| Gemini 3-Flash | low | 2天/44.5h | 37 | 77% | 3/8 | 石器(3pt) | 1 | ¥0.30 |
| DeepSeek V3.2 | off | 2天/30.5h | 25 | 87% | 4/8 | 原始(1pt) | 0 | ¥0.21 |
| DeepSeek V3.2 | on | 2天/**46.0h** | 40 | **98%** | 3/8 | 原始(1pt) | 0 | ¥0.41 |
| Kimi K2.5 | on | 1天/23.5h | 19 | 88% | 3/8 | 原始(1pt) | 0 | ¥0.80 |
| Kimi K2.5 | off | 2天/34.0h | 32 | 91% | 3/8 | 原始(1pt) | 0 | ¥0.28 |
| GPT-5.2 | on | 2天/45.0h | 43 | 96% | 3/8 | 石器(3pt) | 1 | ¥2.33 |
| GPT-5.2 Chat | off | 2天/**55.5h** | 48 | 89% | 4/8 | 原始(1pt) | 0 | ¥1.97 |
| Claude Opus 4.6 | on | 2天/~45h | ~45 | ~96% | 3/8 | 石器(5pt) | **2** | ~¥15* |
| Claude Opus 4.6 | off | 2天/44.5h | 41 | 86% | 3/8 | 石器(3pt) | 1 | ¥4.74 |
| Claude Sonnet 4.5 | on | 2天/42.0h | 37 | 93% | 3/8 | 石器(3pt) | 1 | ¥7.74 |
| Claude Sonnet 4.5 | off | 2天/42.0h | 38 | 87% | 4/8 | 原始(1pt) | 0 | ¥2.49 |

*Opus 4.6 thinking 因 recorder bug 崩溃未输出完整报告，数据为日志估算。

### 关键发现

- **所有 agent 均死于脱水**，饮水管理是当前场景最大挑战
- **GPT-5.2 Chat 存活最长**（55.5h），是唯一突破 50h 的模型，靠高动作效率（48 次）和 4/8 探索覆盖延长了生存
- **Claude Opus 4.6 thinking 综合最强**：唯一达到 5pt 科技 + 2 个发明（含简易滤水器），展现出最强的创造性问题解决能力
- **thinking 模式的真正价值在于科技和发明**：开启 thinking 后，Opus/Sonnet/GPT-5.2 均达到石器科技并产生发明，关闭时只有 Opus 做到——thinking 提升的不只是有效率，而是高阶推理（组合材料、发明新物品）
- **GPT-5.2 性价比最优**：¥2.33 获得 96% 有效率 + 石器科技 + 发明，比 Opus 4.6 便宜一个数量级
- **Claude 模型成本显著偏高**：Opus thinking ~¥15、Sonnet thinking ¥7.74，主要因为 thinking token 被计入 output 费用
- **成本差异极大**：最贵（Opus thinking ~¥15）是最便宜（DS v3 ¥0.21）的 70+ 倍

## 开发

- API 密钥在 `.env` 管理，不硬编码
- 新增材料/配方修改 `data/` 下的 YAML
- 新增场景在 `data/scenarios/` 下创建 YAML
- 提示词统一放 `prompts/`

## License

MIT
