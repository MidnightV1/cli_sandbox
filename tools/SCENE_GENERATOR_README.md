# 场景生成器使用指南

自动生成完整的生存沙盒场景配置，支持随机种子和难度调节。

---

## 快速开始

### 1. 查看可用主题

```bash
python tools/scene_generator.py --list
```

**输出**:
```
可用场景主题:
  - crash_site         (异星坠机求生, 科幻生存, 中等)
  - desert_outpost     (沙漠探测基地, 沙漠生存, 困难)
  - deep_sea_station   (深海研究站, 海底生存, 困难)
  - wasteland_shelter  (废土避难所, 末日生存, 极难)
```

### 2. 生成场景

```bash
# 基础用法：使用默认难度和种子
python tools/scene_generator.py --theme crash_site

# 指定种子（改变资源分布和地图结构）
python tools/scene_generator.py --theme crash_site --seed 123

# 调整难度
python tools/scene_generator.py --theme desert_outpost --difficulty 简单 --seed 42

# 指定输出目录
python tools/scene_generator.py --theme wasteland_shelter --seed 999 --output data/custom_wasteland
```

### 3. 生成的文件结构

```
data/scenes/crash_site_42/
├── scenario.yaml      # 场景元数据（难度、胜利条件、时间范围等）
├── locations.yaml     # 地点网络（6-10个随机生成的地点）
├── materials.yaml     # 材料定义（带属性标签）
├── recipes.yaml       # 配方库（继承通用配方）
└── intro.md          # 场景引入文本
```

---

## 生成逻辑

### 随机种子的影响

**相同种子 → 确定性生成**：
- 地点数量和连接关系
- 每个地点的材料种类和数量
- 材料的消耗品数值（food_value, water_value）

**不同种子 → 不同地图**：
```bash
# 种子 42 可能生成：8 个地点，森林→沼泽→山脊→洞穴...
python tools/scene_generator.py --theme crash_site --seed 42

# 种子 123 可能生成：6 个地点，森林→山脊→洞穴→沼泽...
python tools/scene_generator.py --theme crash_site --seed 123
```

### 难度调节

**影响参数**:
| 难度 | 口渴速率 | 饥饿速率 | 一天时长 | 材料丰度 |
|------|---------|---------|---------|---------|
| 简单 | 3.0/h   | 2.5/h   | 24-30h  | 1.5x    |
| 中等 | 4.5/h   | 3.5/h   | 20-30h  | 1.0x    |
| 困难 | 6.0/h   | 4.5/h   | 18-26h  | 0.7x    |
| 极难 | 7.5/h   | 5.5/h   | 16-24h  | 0.5x    |

**示例**:
```bash
# 简单模式：更多材料，更长存活时间
python tools/scene_generator.py --theme crash_site --difficulty 简单

# 极难模式：资源稀缺，生存压力极大
python tools/scene_generator.py --theme wasteland_shelter --difficulty 极难
```

---

## 主题模板详解

### 1. crash_site（异星坠机求生）

**环境**: 森林、沼泽、山脊、洞穴
**材料池**:
- 金属（钛合金碎片）：坚硬、锋利、导电
- 植物（蔓藤、菌木）：柔韧、纤维、可燃
- 食物（荧光果）：可食用、发光
- 水源（沼泽水）：可饮用（需净化）
- 矿石（磷矿石）：坚硬、脆性

**胜利条件**: 制造信号装置并在信号塔发送求救信号

**适合测试**: 基础生存能力、工具制作链

---

### 2. desert_outpost（沙漠探测基地）

**环境**: 沙丘、岩石平原、干涸河床、废弃矿井
**材料池**:
- 金属（生锈钢管）：坚硬、锋利
- 织物（帆布碎片）：柔韧、纤维、隔热
- 食物（仙人掌果）：可食用、坚硬
- 水源（地下水）：**极低丰度**（核心挑战）
- 矿石（石英）：坚硬、脆性、反光

**胜利条件**: 修复沙漠基地的紧急信标

**适合测试**: 水资源管理、温度管理（昼夜温差大）

---

### 3. deep_sea_station（深海研究站）

**环境**: 气密舱、泄漏区、储藏室、控制中心
**材料池**:
- 金属（钛合金管道）：坚硬、防水、导电
- 塑料（密封胶条）：柔韧、防水、隔热
- 食物（罐头食品）：可食用
- 水源（淡化水）：中等丰度
- 工具（扳手、切割器）：直接可用工具

**胜利条件**: 修复潜水艇动力核心并逃离

**适合测试**: 密闭环境生存、工具依赖策略

**特殊机制**: 无昼夜循环（深海始终黑暗）

---

### 4. wasteland_shelter（废土避难所）

**环境**: 废墟、辐射区、地下室、废弃工厂
**材料池**:
- 金属（废铁片）：坚硬、锋利、生锈
- 织物（破布）：柔韧、纤维、防护
- 食物（罐头）：可食用（可能辐射污染）
- 水源（污染水）：低丰度（辐射污染）
- 化学品（化学试剂）：有毒、可燃

**胜利条件**: 制造空气净化核心并激活避难所

**适合测试**: 极端生存压力、风险决策（辐射污染权衡）

**最高难度**: 默认"极难"，资源最稀缺

---

## 通用配方库

**所有场景共享**（基于属性匹配，材料名称可以不同）：

1. **简易刀具**: `[坚硬,锋利]` + `[柔韧]` → 切割工具
2. **火把**: `[可燃]×2` + `[柔韧]` → 照明工具
3. **滤水器**: `[柔韧,纤维]×2` + `[坚硬]` → 净水工具
4. **绳索**: `[柔韧,纤维]×3` → 捆绑材料
5. **庇护所**: `[坚硬]×2` + `[柔韧]×3` → 可放置庇护

---

## 扩展：添加自定义主题

### 1. 编辑模板文件

打开 `tools/scene_templates.yaml`，添加新主题：

```yaml
my_custom_theme:
  name: 我的自定义场景
  theme: 自定义类型
  difficulty: 中等

  environment:
    biomes: [区域1, 区域2, 区域3]
    weather_types: [天气1, 天气2]
    temperature_range: [10, 40]
    day_length_range: [20, 30]

  material_pools:
    - category: 材料类型1
      properties: [属性1, 属性2]
      examples: [材料名A, 材料名B]
      abundance: 中

  goal:
    type: custom
    description: 你的胜利条件描述
    trigger_location_type: 触发地点类型
```

### 2. 生成自定义场景

```bash
python tools/scene_generator.py --theme my_custom_theme --seed 42
```

---

## 高级用法

### 批量生成（测试用）

```bash
# 生成多个种子的同一主题
for seed in 42 123 456 789; do
    python tools/scene_generator.py --theme crash_site --seed $seed --output data/crash_site_$seed
done

# 生成所有主题的默认版本
for theme in crash_site desert_outpost deep_sea_station wasteland_shelter; do
    python tools/scene_generator.py --theme $theme --seed 42
done
```

### 集成到评测流程

```bash
# 1. 生成新场景
python tools/scene_generator.py --theme desert_outpost --seed 42 --output data/desert

# 2. 修改 main.py 加载场景路径（待实现场景加载器）
python main.py --scene data/desert --agent gemini/3-Pro --seed 42
```

---

## 已知限制

### 当前版本限制

1. **叙事文本简单**: 地点和材料描述使用模板，缺乏细节
2. **配方库有限**: 仅支持 5 个通用配方，未根据主题生成特色配方
3. **地点描述**: 缺少具体的环境描述和故事元素

### 计划改进

- [ ] 使用 LLM 生成更丰富的叙事文本
- [ ] 根据主题自动生成特色配方
- [ ] 支持更多环境机制（辐射、水压、温度等）
- [ ] 配方难度分级（初级/中级/高级工具链）

---

## 故障排查

### 生成失败

**问题**: `ValueError: 未知主题`
**解决**: 使用 `--list` 查看可用主题，确认拼写正确

**问题**: `FileNotFoundError: scene_templates.yaml`
**解决**: 确保在项目根目录运行，或使用绝对路径

### 文件覆盖警告

默认情况下，生成器会**覆盖**已存在的目录。如果需要保留旧版本：

```bash
# 使用不同的输出目录
python tools/scene_generator.py --theme crash_site --seed 42 --output data/crash_site_v2
```

---

**贡献**: 欢迎添加新主题模板到 `scene_templates.yaml`！
**反馈**: 如果生成的场景不平衡或有 bug，请提供 theme + seed 组合。
