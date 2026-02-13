# AI 存活挑战 —— 技术文档

## 项目概述

CLI 文本沙盒游戏，用于评估 AI 模型的 agent 能力。基于属性的配方系统测推理而非记忆，严格 XML 输出测结构化能力，50+ 步连续决策测长程规划。人类也可以直接玩，用于建立基线对比。

## 架构

```
cli_sandbox/
├── main.py              # 入口（--agent, --thinking, --seed, --scenario, --no-llm, --session-file）
├── run_eval.py          # 批量评测（SEEDS × MODELS × NUM_RUNS 并行，输出到 eval_results/seed_N/player_tag/）
├── analysis.ipynb       # 数据分析 & 可视化（21 张图表，输出到 figures/）
├── REPORT.md            # 完整评测报告（v2.3）
├── models/              # 数据模型（Item, PlayerState, WorldState, Location）
├── data/                # YAML 数据文件（材料属性、配方、场景地图）
├── prompts/             # 提示词（世界设定、LLM 裁判指令、Agent 系统提示）
├── engine/              # 核心引擎（规则引擎、事件系统、LLM 裁判、世界循环、评分）
├── agent/               # AI 自动玩家（状态序列化、决策、推理）
├── interface/           # CLI 界面（Rich 渲染、动作解析，支持中英文指令）
├── llm/                 # 统一 LLM 客户端（7 Provider）+ 计费 + 限速重试
├── eval/                # 评估（会话录制 JSONL）
├── eval_results/        # 批量评测输出（gitignored）
│   └── seed_N/player_tag/  # run_1.jsonl + run_1.log, ...
└── figures/             # 分析图表输出（gitignored）
```

## 核心设计

- **基于属性的物品系统**：配方匹配属性组合而非具体物品名，测推理而非记忆
- **确定性规则引擎 + LLM 裁判兜底**：已知行为走确定性引擎，自由发明交 LLM 判定
- **严格 XML 输出**：Agent 必须输出 `<action>动作</action><detail>目标</detail>` 格式，无 few-shot 示例，无兜底解析，格式错误扣体力
- **小时制时间系统**：日长 20-30 小时随机（对玩家隐藏），环境描述暗示时间阶段
- **科技等级**：制作配方获得科技点，5 级体系（原始→石器→工匠→工程师→创造者）
- **100 天检查点制**：每 100 天暂停评估，显示得分和 LLM 费用
- **LLM 计费追踪**：按 token 实时计费（USD×7.3→CNY），支持多 provider 分模型统计
- **AI Agent 模式**：`--agent provider/model` 自动游玩，支持 `--thinking` 控制推理深度，agent 模式裁判统一用 Gemini 3-Pro
- **Seed 环境差异**：seed 控制资源数量波动（Layer 1）和地图方向旋转（Layer 3），多 seed 测试验证排名稳定性

## 游戏机制

### XML 格式输出（Agent 专用）

- `<action>` 必需：动作指令（移动/采集/制作/组合/使用/吃/喝/休息/观察/尝试/记录）
- `<detail>` 可选：动作目标或参数（如 `北`、`荧光果`、`黑曜碎片, 火山岩`）
- 无 few-shot 示例，避免模板过拟合
- 无兜底解析（JSON/纯文本均不接受），格式错误返回空指令，走 engine 标准流程：扣 2 体力 + 0.25h + tick 递增

### 动作时间与计数（定义在 `models/state.py:ACTION_TIME_COSTS`）

| 动作 | 成功耗时 | 失败耗时 | 说明 |
|------|---------|---------|------|
| 移动 move | 1.0h | 0.5h | |
| 采集 gather | 0.5h | 0.25h | |
| 制作 craft | 2.0h | 0.5h | |
| 组合 combine | 2.0h | 0.5h | |
| 使用 use | 1.0h | 0.5h | |
| 吃 eat | 0.5h | 0.25h | |
| 喝 drink | 0.5h | 0.25h | |
| 休息 rest | 3.0h | — | 不会失败 |
| 尝试 free_action | 1.0h | — | LLM 裁判判定 |
| 观察 look | 0.25h | — | 不会失败 |
| 记录 note | 0.0h | — | 免费 |
| 格式错误 empty/unknown | — | 0.25h | 走 engine 失败分支 |

JSONL 中有两个计数字段：
- `tick`（决策序号）：每次 LLM 调用必递增，从 1 开始，连续无重复。对应 `WorldState.decision_count`
- `turn`（游戏回合）：仅在成功+耗时动作或格式错误时递增。对应 `WorldState.action_count`

`tick` 用于上下文疲劳分析（第 N 次决策的表现），`turn` 用于策略阶段分析（第 N 个有效回合的动作分布）。

### 能量惩罚机制（能量范围 0-100，定义在 `engine/world.py`）

**成功动作**：按动作类型扣完整体力
- 简单操作：移动 10，采集 10，使用 10
- 复杂操作：制作 20，组合 20
- 休息：恢复 30（庇护所/放置庇护物品）或 20（露天）

**失败动作**：分级惩罚（`FAILURE_PENALTIES`）

| 分类 | 体力惩罚 | 动作 |
|------|---------|------|
| 零成本 | 0 | look, inventory, help, recipes, note |
| 格式错误 | 2 | empty（XML 解析失败）, unknown（无法识别指令） |
| 低成本 | 3-5 | move:3, gather:5, use:5 |
| 高成本 | 10 | craft, combine（成功成本的 50%） |
| 默认 | 5 | 未列出的其他类型 |

- 体力不足导致的失败不额外扣体力（避免恶性循环）

**状态恶化伤害**：饥饿/口渴/体温越过阈值后按比例计算伤害，使用越线时长而非整个动作时长（`engine/events.py:process_time()`）。

### 时间系统
- 每天长度在场景配置的 `day_length_min`~`day_length_max` 范围内随机，对玩家隐藏
- 玩家通过环境描述（"天边泛起微光"、"光照强烈"等）感知时间阶段
- 饥饿/口渴按小时累积（浮点），整数部分才展示

### 科技等级
- 首次制作已知配方或 LLM 发明都获得科技点
- 基础配方 1 点，中级 3 点，高级 5 点，LLM 发明 2 点（仅 `is_creation=true`）
- 等级阈值：0→原始, 2→石器, 6→工匠, 12→工程师, 20→创造者

### LLM 裁判（`engine/judge.py`）
- Agent 模式统一使用 Gemini 3-Pro 裁判（Flash 物理推理不够严格）
- 裁判注入当前实际可采集资源列表，防止 agent 通过"尝试"绕过资源耗尽限制
- `is_creation` 字段区分创造性行为和简单操作，只有创造才奖励科技点
- 裁判定义的 `consumable` 字段正确传递，发明的可食用/可饮用物品可正常消耗

### 小本本工具
- 8 条笔记容量，满了需要整理
- 零时间零体力消耗
- 测试模型记忆管理策略（记录物资位置 vs 临时状态）

### Seed 环境控制
- **Layer 1（资源数量波动）**：`locations.yaml` 中 `quantity` 支持 `[min, max]` 范围，由 seed 决定实际数量
- **Layer 3（方向旋转）**：seed 决定地图朝向（0°/90°/180°/270°），所有罗盘方向统一旋转，逻辑方向（深处/外面）不受影响
- 实现：`scene_loader.py` 的 `_resolve_quantity()` 和 `_rotate_direction()`

### 检查点与 goal_trigger
- 每 100 天触发检查点（可配置 `checkpoint_interval`），显示存活天数、科技等级、探索率、LLM 费用
- 配方的 `result.goal_trigger` 通过 `ActionResult.extra` 传递，`GameEngine.process_action()` 检查后完成对应目标

## 评测方法论

### 已完成实验

| 阶段 | 规模 | 结论 |
|------|------|------|
| v1 初始实验 | 24 配置 × 10 轮 × seed=42 = 229 局 | 基线数据，发现行为模式差异 |
| Seed 对照验证 | seed=121 vs 666（n=10） | 均值差 2.5h，p=0.47 ns → seed 不引入系统偏差 |
| 代码版本对照 | 旧代码 vs 新代码（seed=121） | 44.4h → 37.1h（delta=-7.3h）→ 旧数据不可混用 |
| Phase 1 采样充分性 | 2 模型 × 3 seeds × 100 轮 = 600 局 | n=10 MAE≈2h，可区分 delta>5h；拥挤区需 n=20+ |

### 待执行

- Phase 2 全模型对比：23 配置 × 10 轮 × 3 seeds = 690 局（Step 1），拥挤区 15 配置追加到 n=20（Step 2），预算 ~¥6,400

## 运行方式

```bash
# 安装依赖
pip install -r requirements.txt

# AI Agent 自动游玩（格式：--agent provider/model）
python main.py --agent gemini/3-Pro --seed 42
python main.py --agent openai/gpt-5.2 --thinking --seed 42
python main.py --agent deepseek/v3 --seed 42

# 人类玩家模式（需要 .env 中的 API 密钥支持 LLM 裁判）
python main.py --seed 42

# 纯规则引擎模式（不调用 API）
python main.py --no-llm

# 批量评测
python run_eval.py
```

### 支持的 Provider（7 家）

| Provider | 模型示例 | 用法 |
|----------|----------|------|
| Gemini | 3-Pro, 3-Flash | `--agent gemini/3-Pro` |
| Anthropic | claude-46-big, claude-45-mid | `--agent anthropic/claude-46-big` |
| OpenAI | gpt-5.2, gpt-5.2-chat | `--agent openai/gpt-5.2` |
| DeepSeek | v3 (V3.2) | `--agent deepseek/v3` |
| Doubao | seed-1.8 | `--agent doubao/seed-1.8` |
| Moonshot | k2.5 (Kimi K2.5) | `--agent moonshot/k2.5` |
| OpenRouter | 任意模型 | `--agent openrouter/stepfun/step-3.5-flash:free` |

## 开发约定

- API 密钥在 `.env` 中管理，不硬编码
- 提示词统一放 `prompts/` 目录
- 新增材料/配方修改 `data/` 下的 YAML 文件，配方必须包含 `tech_points` 字段
- 新增场景在 `data/scenarios/` 下创建 YAML 文件
- 会话录制为 JSONL 格式：批量评测输出到 `eval_results/seed_{N}/player_tag/`，单次调试输出到 `sessions/`
- 格式错误统一走 `engine.process_action()` 标准流程，不在 main.py 手动处理

## Roadmap

- [x] 多模型批量评测基础设施（7 provider，并行执行）
- [x] Seed 控制环境差异（资源数量波动 + 地图方向旋转）
- [x] Phase 1 采样充分性验证（bootstrap 验证 n=10）
- [x] 数据分析与可视化（analysis.ipynb，21 张图表）
- [ ] Phase 2 全模型重跑（新代码 + 多 seed）
- [ ] Prompt 策略消融实验（人设注入、显式 CoT、优先级提示）
- [ ] 道德挑战（模型是否会为了存活而做出不道德的选择？）
- [ ] 人类基线
- [ ] 三模型仲裁机制（替代单裁判）
