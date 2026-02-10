# CLI沙盒 —— 异星求生

## 项目概述

一个CLI文本沙盒游戏，用于评估AI模型的agent能力、工具使用和工具制造能力。
人类也可以直接玩，用于建立基线对比。

## 架构

```
cli_sandbox/
├── main.py              # 入口（支持参数控制场景、LLM、随机种子）
├── models/              # 数据模型（Item, PlayerState, WorldState, Location）
├── data/                # YAML数据文件（材料、配方、场景）+ 加载器
├── prompts/             # 提示词文件（世界设定、LLM裁判指令）
├── engine/              # 核心引擎（规则引擎、事件系统、LLM裁判、世界循环）
├── interface/           # CLI界面（渲染、动作解析，支持中英文指令）
├── llm/                 # 统一LLM客户端（Claude、GPT、Gemini）+ 计费追踪
├── eval/                # 评估（会话录制）
└── sessions/            # 录制文件输出目录（gitignored）
```

## 核心设计

- **基于属性的物品系统**：配方匹配属性而非具体物品名，测推理而非记忆
- **确定性规则引擎 + LLM裁判兜底**：已知行为走确定性引擎，自由发明交LLM判定
- **小时制时间系统**：日长20-30小时随机（对玩家隐藏），不同动作消耗不同时间，环境描述暗示时间阶段
- **科技等级**：制作配方获得科技点数，5级体系（原始→石器→工匠→工程师→创造者）
- **100天检查点制**：每100天暂停评估，显示得分和LLM费用，决定是否继续
- **LLM计费追踪**：按 token 实时计费（USD→CNY），结算时显示明细
- **中文界面**：指令和描述均为中文，支持中英文双语指令输入

## 关键机制

### 时间系统
- 每天长度在场景配置的 `day_length_min`~`day_length_max` 范围内随机生成，对玩家隐藏
- 玩家只能通过环境描述（"天边泛起微光"、"光照强烈"等）感知时间阶段
- 饥饿/口渴按小时累积（浮点），整数部分才展示

### 科技等级
- 首次制作已知配方或LLM发明都会获得科技点
- 基础配方1点，中级3点，高级5点，LLM发明2点
- 等级阈值：0→原始, 2→石器, 6→工匠, 12→工程师, 20→创造者

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
```

## 开发约定

- API密钥全部在 `.env` 中管理，不硬编码
- 提示词统一放 `prompts/` 目录
- 新增材料/配方修改 `data/` 下的YAML文件
- 新增场景在 `data/scenarios/` 下创建YAML文件
- 会话录制为JSONL格式，存入 `sessions/`
- 配方必须包含 `tech_points` 字段

## 待实现

- [ ] AI agent 自动玩接口（protocol.py）
- [ ] 三模型仲裁机制（tribunal）
- [ ] 场景切片（vignette）系统
- [ ] 评分器（scorer.py）
- [ ] 荒野求生场景
