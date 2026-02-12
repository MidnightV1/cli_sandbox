# CLI沙盒 —— 异星求生

## 项目概述

一个CLI文本沙盒游戏，用于评估AI模型的agent能力、工具使用和工具制造能力。
人类也可以直接玩，用于建立基线对比。

## 架构

```
cli_sandbox/
├── main.py              # 入口（--agent, --thinking, --seed, --scenario, --no-llm）
├── models/              # 数据模型（Item, PlayerState, WorldState, Location）
├── data/                # YAML数据文件（材料、配方、场景）+ 加载器
├── prompts/             # 提示词文件（世界设定、LLM裁判指令、Agent系统提示）
├── engine/              # 核心引擎（规则引擎、事件系统、LLM裁判、世界循环、评分）
├── agent/               # AI自动玩家（状态序列化、决策、推理）
├── interface/           # CLI界面（Rich渲染、动作解析，支持中英文指令）
├── llm/                 # 统一LLM客户端（Gemini / Anthropic / OpenAI / DeepSeek / Moonshot / Doubao / OpenRouter）+ 计费
├── eval/                # 评估（会话录制JSONL）
└── sessions/            # 录制文件输出目录（gitignored）
```

## 核心设计

- **基于属性的物品系统**：配方匹配属性而非具体物品名，测推理而非记忆
- **确定性规则引擎 + LLM裁判兜底**：已知行为走确定性引擎，自由发明交LLM判定
- **小时制时间系统**：日长20-30小时随机（对玩家隐藏），不同动作消耗不同时间，环境描述暗示时间阶段
- **科技等级**：制作配方获得科技点数，5级体系（原始→石器→工匠→工程师→创造者）
- **100天检查点制**：每100天暂停评估，显示得分和LLM费用，决定是否继续
- **LLM计费追踪**：按 token 实时计费（USD×7.3→CNY），支持多 provider 分模型统计
- **AI Agent 模式**：`--agent provider/model` 自动游玩，支持 `--thinking` 控制推理深度，agent 模式裁判统一用 Gemini 3-Pro
- **中文界面**：指令和描述均为中文，支持中英文双语指令输入
- **严格 XML 输出**：Agent 必须输出 `<action>动作</action><detail>目标</detail>` 格式，无兜底解析，格式错误扣体力

## 关键机制

### XML 格式输出（Agent 专用）
- **严格要求**：Agent 必须输出 `<action>动作</action><detail>目标</detail>` 格式
  - `<action>` 必需：动作指令（移动/采集/制作/组合/使用/吃/喝/休息/观察/尝试/记录）
  - `<detail>` 可选：动作目标或参数（如 `北`、`荧光果`、`黑曜碎片, 火山岩`），无参数动作可省略
- **无 few-shot 示例**：prompt 只给格式说明，不给具体示例，避免模板过拟合
- **无兜底解析**：删除 JSON/纯文本兜底，格式错误直接返回空指令
- **格式错误惩罚**：XML 解析失败视为失败动作，扣 1 体力
- **评测维度**：格式稳定性、指令理解能力、零样本结构化输出

### 能量惩罚机制（能量范围0-100）
- **成功动作**：按动作类型扣完整体力
  - 简单操作：移动10，采集10，使用10
  - 复杂操作：制作20，组合20
  - 休息：恢复20-40（随机）
- **失败动作**：分级惩罚防止无限试错
  - 零成本失败（0点）：信息探索类（look/inventory/help/recipes/note）
  - 轻微惩罚（2点）：格式错误（XML解析失败）、无效指令
  - 低成本失败（3-5点）：简单操作（move:3, gather:5, use:5）
  - 高成本失败（10点）：复杂操作（craft/combine，成功成本50%）
  - 默认惩罚：5点
- **豁免情况**：体力不足导致的失败（避免恶性循环）

### 小本本工具
- **容量限制**：8 条笔记，满了需要整理
- **零消耗**：记录不消耗时间和体力
- **评测目标**：测试模型记忆管理策略（记录物资位置 vs 临时状态）

### 时间系统
- 每天长度在场景配置的 `day_length_min`~`day_length_max` 范围内随机生成，对玩家隐藏
- 玩家只能通过环境描述（"天边泛起微光"、"光照强烈"等）感知时间阶段
- 饥饿/口渴按小时累积（浮点），整数部分才展示

### 科技等级
- 首次制作已知配方或LLM发明都会获得科技点
- 基础配方1点，中级3点，高级5点，LLM发明2点
- 等级阶值：0→原始, 2→石器, 6→工匠, 12→工程师, 20→创造者

### 检查点制
- 默认每100天触发检查点（可在场景YAML中配置 `checkpoint_interval`）
- 检查点时显示：存活天数、科技等级、探索率、LLM费用
- 操作者决定是否继续下一阶段

### goal_trigger 机制
- 配方的 `result.goal_trigger` 字段通过 `ActionResult.extra` 传递
- `GameEngine.process_action()` 检查 `result.extra.get('goal_trigger')` 来完成对应目标

## 运行方式

```bash
# 安装依赖
pip install -r requirements.txt

# 人类玩家模式（需要 .env 中的API密钥支持LLM裁判）
python main.py

# 纯规则引擎模式（不调用API）
python main.py --no-llm

# 指定随机种子（可复现）
python main.py --seed 42

# AI Agent 自动游玩（格式：--agent provider/model）
python main.py --agent gemini/3-Pro --seed 42
python main.py --agent openai/gpt-5.2 --thinking --seed 42
python main.py --agent deepseek/v3 --thinking --seed 42
python main.py --agent openrouter/stepfun/step-3.5-flash:free --seed 42
```

### 支持的 Provider

| Provider | 模型示例 | 用法 |
|----------|----------|------|
| Gemini | 3-Pro, 3-Flash | `--agent gemini/3-Pro` |
| Anthropic | claude-46-big, claude-45-mid | `--agent anthropic/claude-46-big` |
| OpenAI | gpt-5.2, gpt-5.2-chat, gpt-4.1 | `--agent openai/gpt-5.2` |
| DeepSeek | v3 (V3.2) | `--agent deepseek/v3` |
| Doubao | seed-1.8 | `--agent doubao/seed-1.8` |
| Moonshot | k2.5 (Kimi K2.5) | `--agent moonshot/k2.5` |
| OpenRouter | 任意模型 | `--agent openrouter/stepfun/step-3.5-flash:free` |

## 开发约定

- API密钥全部在 `.env` 中管理，不硬编码
- 提示词统一放 `prompts/` 目录
- 新增材料/配方修改 `data/` 下的YAML文件
- 新增场景在 `data/scenarios/` 下创建YAML文件
- 会话录制为JSONL格式，存入 `sessions/`
- 配方必须包含 `tech_points` 字段

## 最近改动（2026-02-12）

### XML 格式输出优化
- **删除 reason 标签要求**：简化输出格式为 `<action>` + `<detail>`，聚焦指令执行能力
- **删除 few-shot 示例**：避免模板过拟合，测试模型零样本结构化输出能力
- **删除所有兜底解析**：严格要求 XML 格式，JSON/纯文本兜底全部移除
- **格式错误惩罚**：XML 解析失败返回空指令 → `'empty'` action type → 扣 1 体力

### 能量惩罚机制完善
- **修复 BUG**：原代码检查 `energy_cost > 0` 但失败动作都设 `energy_cost=0`，导致失败不扣体力
- **新逻辑**：成功动作扣完整体力，失败动作统一扣 1 体力（观察类和能量失败除外）
- **影响**：低有效率模型（如 Qwen3 35%）现在会正确受到惩罚，生存时间大幅缩短

### 状态可见性增强
- **背包突出显示**：用 ★ 符号标记，明确显示物品数量和空背包状态
- **系统消息标记**：log 输出加 `[系统]` 前缀，方便人类查看区分（不影响模型输入）
- **行动历史优化**：删除冗余的"上轮结果"，保留"近3天行动记录"

### 小本本工具
- **新增笔记工具**：8 条容量限制，测试模型记忆管理策略
- **零消耗设计**：不消耗时间和体力，鼓励使用
- **容量压力**：满了需要整理，考察优先级判断（记录资源位置 vs 临时状态）

### 裁判模型升级
- **Gemini Flash → Pro**：Agent 模式裁判从 3-Flash 升级到 3-Pro
- **原因**：Flash 的物理推理能力不够严格，可能通过不合理的组合（如用锋利碎片做手柄）
- **权衡**：Pro 成本略高但调用频率低（每局 5-10 次），对总成本影响有限
- **收益**：更准确的裁判 → 更公平的评测 → 更高的科技点含金量

### 裁判判定可见性
- **添加 [裁判] 标记**：所有裁判判定结果现在都显示 `[裁判]` 前缀
- **显示判定理由**：裁判的 `reasoning` 字段明确展示物理推理依据
- **完整思维链**：log 中可追溯 `Agent 推理 → 裁判判定 → 执行结果` 全过程
- **示例输出**：
  ```
  [AI] 尝试 使用钛合金碎片钻木取火...
  [系统] 你试图用冰冷的钛合金碎片在菌木上快速旋转，但金属只是不断带走热量...
  [裁判] 钻木取火依赖于木头与木头之间的摩擦产生高温炭屑。钛合金碎片导热性极高且表面光滑，
         摩擦时会迅速散热，无法像木头那样积累足够的热量点燃干苔，且缺乏合适的钻板。
  ```

## 待实现

- [x] AI Agent 自动玩（`agent/player.py`，已支持 7 个 provider）
- [x] 评分系统（内嵌于 `engine/world.py:get_score()`）
- [x] 新增评测指标（`eval/analyzer.py`）：运行耗时、总输出token、token效率、尝试成功率、创造成功率、重复动作率、首次制作tick
- [x] 能量惩罚机制（失败动作扣体力）
- [x] 结构化输出评测（严格 XML 格式）
- [x] 记忆管理评测（小本本工具）
- [ ] 规模化实验：多随机种子取平均，消除单次运气因素
- [ ] 新场景：沼泽、冰原、火山等，测试泛化能力
- [ ] 人类基线：招募人类玩家在相同条件下游玩
- [ ] 三模型仲裁机制（tribunal）
- [ ] 场景切片（vignette）系统
