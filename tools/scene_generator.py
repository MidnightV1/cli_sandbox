#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
场景生成器 - 基于主题模板自动生成完整场景配置

用法:
    python tools/scene_generator.py --theme crash_site --seed 42 --output data/crash_site_v2
    python tools/scene_generator.py --theme desert_outpost --seed 123 --difficulty 困难
    python tools/scene_generator.py --list  # 列出所有可用主题
"""

import argparse
import random
import yaml
import os
from pathlib import Path
from typing import Dict, List, Any


class SceneGenerator:
    def __init__(self, templates_path: str = "tools/scene_templates.yaml"):
        with open(templates_path, 'r', encoding='utf-8') as f:
            self.data = yaml.safe_load(f)
        self.templates = {k: v for k, v in self.data.items()
                         if k not in ['universal_recipes', 'generation_config']}
        self.universal_recipes = self.data['universal_recipes']
        self.config = self.data['generation_config']

    def list_themes(self) -> List[str]:
        """列出所有可用主题"""
        return list(self.templates.keys())

    def generate_scene(self, theme: str, seed: int = 42, difficulty: str = None) -> Dict[str, Any]:
        """
        生成完整场景配置

        Args:
            theme: 主题名称（crash_site, desert_outpost 等）
            seed: 随机种子
            difficulty: 难度等级（简单/中等/困难/极难），None 则使用模板默认

        Returns:
            包含所有场景文件内容的字典
        """
        if theme not in self.templates:
            raise ValueError(f"未知主题: {theme}. 可用主题: {self.list_themes()}")

        template = self.templates[theme]
        random.seed(seed)

        # 应用难度调节
        if difficulty:
            template = self._apply_difficulty(template, difficulty)

        # 生成各部分
        scenario = self._generate_scenario(template, seed)
        locations = self._generate_locations(template)
        materials = self._generate_materials(template)
        recipes = self._generate_recipes(template)
        intro = self._generate_intro(template)

        return {
            'scenario.yaml': scenario,
            'locations.yaml': locations,
            'materials.yaml': materials,
            'recipes.yaml': recipes,
            'intro.md': intro,
        }

    def _apply_difficulty(self, template: Dict, difficulty: str) -> Dict:
        """应用难度修正"""
        if difficulty not in self.config['difficulty_modifiers']:
            raise ValueError(f"未知难度: {difficulty}")

        modifiers = self.config['difficulty_modifiers'][difficulty]
        template = template.copy()
        template['difficulty'] = difficulty

        # 修改环境参数
        if 'environment' in template:
            env = template['environment']
            env['day_length_range'] = modifiers['day_length_range']

        return template

    def _generate_scenario(self, template: Dict, seed: int) -> Dict:
        """生成 scenario.yaml（与 scene_loader 格式对齐）"""
        env = template['environment']
        goal = template['goal']
        difficulty = template.get('difficulty', '中等')

        # 起始地点 ID
        start_loc_id = self._to_id(env['biomes'][0])

        # 起始背包：从食物/水源材料池各取一个
        start_inventory = self._generate_start_inventory(template)

        # 起始状态：根据难度调整
        start_status = self._generate_start_status(difficulty)

        # 天气池：从天气类型列表生成带权重版本
        weather_pool = self._generate_weather_pool(env['weather_types'])

        return {
            'name': template['name'],
            'theme': template['theme'],
            'difficulty': difficulty,
            'seed': seed,
            'time_system': {
                'day_length_min': env['day_length_range'][0],
                'day_length_max': env['day_length_range'][1],
            },
            'checkpoint_interval': 100,
            'start': {
                'location': start_loc_id,
                'inventory': start_inventory,
                'status': start_status,
                'known_recipes': ['cutting_tool', 'rope'],
            },
            'goals': [
                {'id': 'survive', 'description': '存活100天', 'type': 'survival'},
                {'id': goal['type'], 'description': goal['description'], 'type': 'primary'},
                {'id': 'shelter', 'description': '建造庇护所', 'type': 'secondary'},
            ],
            'weather_pool': weather_pool,
        }

    def _generate_start_inventory(self, template: Dict) -> List[Dict]:
        """根据场景材料池生成起始背包（食物/水源各取一个）"""
        inventory = []
        for pool in template['material_pools']:
            if 'consumable' in pool:
                example = pool['examples'][0]
                inventory.append({'id': example, 'quantity': 1})
        if not inventory:
            example = template['material_pools'][0]['examples'][0]
            inventory.append({'id': example, 'quantity': 1})
        return inventory

    def _generate_start_status(self, difficulty: str) -> Dict:
        """根据难度生成起始状态"""
        presets = {
            '简单': {'health': 100, 'hunger': 10, 'thirst': 10, 'warmth': 80, 'energy': 90},
            '中等': {'health': 80, 'hunger': 20, 'thirst': 20, 'warmth': 70, 'energy': 70},
            '困难': {'health': 70, 'hunger': 30, 'thirst': 30, 'warmth': 60, 'energy': 60},
            '极难': {'health': 60, 'hunger': 40, 'thirst': 40, 'warmth': 50, 'energy': 50},
        }
        return presets.get(difficulty, presets['中等'])

    def _generate_weather_pool(self, weather_types: List[str]) -> List[Dict]:
        """从天气类型列表生成带权重的天气池"""
        pool = []
        for i, wt in enumerate(weather_types):
            weight = 4 if i == 0 else max(1, 3 - i)
            effects = {}
            if any(kw in wt for kw in ['暴', '雨', '寒', '辐射', '酸']):
                effects = {'warmth_mod': -2, 'exposed_only': True}
            if any(kw in wt for kw in ['酸', '辐射']):
                effects['health_mod'] = -1
            pool.append({'type': wt, 'weight': weight, 'effects': effects})
        return pool

    def _generate_locations(self, template: Dict) -> Dict:
        """生成 locations.yaml"""
        env = template['environment']
        biomes = env['biomes']
        material_pools = template['material_pools']

        # 随机生成 6-10 个地点
        location_count = random.randint(*self.config['location_count_range'])
        locations = {}

        # 第一个地点是起点
        start_id = self._to_id(biomes[0])
        locations[start_id] = self._create_location(
            biomes[0],
            is_start=True,
            shelter=True,
            material_pools=material_pools
        )

        # 生成其他地点
        used_biomes = [biomes[0]]
        for i in range(1, location_count):
            biome = random.choice([b for b in biomes if b not in used_biomes] or biomes)
            loc_id = self._to_id(biome) if biome not in used_biomes else f"{self._to_id(biome)}_{i}"
            used_biomes.append(biome)

            locations[loc_id] = self._create_location(
                biome,
                is_start=False,
                shelter=random.random() < 0.2,  # 20% 概率是庇护所
                material_pools=material_pools
            )

        # 生成地点连接网络（保证连通性）
        locations = self._connect_locations(locations)

        # 添加胜利触发地点
        goal = template['goal']
        trigger_type = goal.get('trigger_location_type', '高地')
        trigger_id = self._get_trigger_location_id(trigger_type)
        if trigger_id not in locations:
            locations[trigger_id] = self._create_location(
                trigger_type,
                is_start=False,
                shelter=False,
                material_pools=material_pools,
                discovered=False
            )

        return locations

    def _create_location(self, name: str, is_start: bool, shelter: bool,
                        material_pools: List[Dict], discovered: bool = None) -> Dict:
        """创建单个地点"""
        if discovered is None:
            discovered = is_start

        # 从材料池中随机选择 2-4 种材料
        materials_count = random.randint(*self.config['materials_per_location'])
        selected_pools = random.sample(material_pools, min(materials_count, len(material_pools)))

        resources = []
        for pool in selected_pools:
            material_name = random.choice(pool['examples'])
            abundance = pool.get('abundance', '中')
            quantity = self._get_quantity_by_abundance(abundance)
            resources.append({'item_id': material_name, 'quantity': quantity})

        return {
            'name': name,
            'description': self._generate_location_description(name),
            'shelter': shelter,
            'connections': {},  # 稍后填充
            'resources': resources,
            'discovered': discovered,
        }

    def _get_quantity_by_abundance(self, abundance: str) -> int:
        """根据丰度返回材料数量"""
        abundance_map = {
            '极低': (1, 2),
            '低': (2, 3),
            '中': (3, 5),
            '高': (4, 6),
        }
        min_q, max_q = abundance_map.get(abundance, (2, 5))
        return random.randint(min_q, max_q)

    def _connect_locations(self, locations: Dict) -> Dict:
        """生成地点连接网络（确保连通）"""
        loc_ids = list(locations.keys())
        if len(loc_ids) < 2:
            return locations

        # 使用最小生成树保证连通性
        connected = {loc_ids[0]}
        unconnected = set(loc_ids[1:])

        directions = ['北', '南', '东', '西', '东北', '西北', '东南', '西南']

        while unconnected:
            # 从已连接中随机选一个
            from_id = random.choice(list(connected))
            # 从未连接中随机选一个
            to_id = random.choice(list(unconnected))

            # 随机选方向
            direction = random.choice(directions)
            reverse_direction = self._get_reverse_direction(direction)

            # 建立双向连接
            locations[from_id]['connections'][direction] = to_id
            locations[to_id]['connections'][reverse_direction] = from_id

            connected.add(to_id)
            unconnected.remove(to_id)

        # 添加一些额外连接（让网络不那么线性）
        extra_connections = random.randint(2, len(loc_ids) // 2)
        for _ in range(extra_connections):
            from_id = random.choice(loc_ids)
            to_id = random.choice([lid for lid in loc_ids if lid != from_id])

            # 避免重复连接
            if to_id not in locations[from_id]['connections'].values():
                direction = random.choice([d for d in directions
                                          if d not in locations[from_id]['connections']])
                reverse_direction = self._get_reverse_direction(direction)

                locations[from_id]['connections'][direction] = to_id
                locations[to_id]['connections'][reverse_direction] = from_id

        return locations

    def _get_reverse_direction(self, direction: str) -> str:
        """获取相反方向"""
        reverse_map = {
            '北': '南', '南': '北', '东': '西', '西': '东',
            '东北': '西南', '西南': '东北', '西北': '东南', '东南': '西北',
        }
        return reverse_map.get(direction, '未知')

    def _generate_materials(self, template: Dict) -> Dict:
        """生成 materials.yaml（包含 materials: 顶层 key，与手写格式一致）"""
        materials = {}
        for pool in template['material_pools']:
            for example in pool['examples']:
                mat = {
                    'name': example,
                    'description': self._generate_material_description(example, pool),
                    'properties': pool['properties'].copy(),
                }

                # 添加消耗品属性
                if 'consumable' in pool:
                    consumable = pool['consumable'].copy()
                    if 'food_value' in consumable and isinstance(consumable['food_value'], (list, tuple)):
                        consumable['food_value'] = random.randint(*consumable['food_value'])
                    if 'water_value' in consumable and isinstance(consumable['water_value'], (list, tuple)):
                        consumable['water_value'] = random.randint(*consumable['water_value'])
                    # 把描述性的 side_effect 转为引擎识别的格式
                    if 'side_effect' in consumable and consumable['side_effect'] not in ('health_minus_1',):
                        consumable['side_effect'] = 'health_minus_1'
                    if 'type' not in consumable:
                        # 根据有无 food/water value 推断类型
                        has_food = consumable.get('food_value', 0) > 0
                        has_water = consumable.get('water_value', 0) > 0
                        if has_food and has_water:
                            consumable['type'] = 'both'
                        elif has_food:
                            consumable['type'] = 'food'
                        else:
                            consumable['type'] = 'water'

                    mat['consumable'] = consumable

                materials[example] = mat

        return {'materials': materials}

    def _generate_recipes(self, template: Dict) -> Dict:
        """生成 recipes.yaml（继承通用配方，包含 recipes: 顶层 key）"""
        recipes = {}

        # 继承通用配方
        for recipe in self.universal_recipes:
            name = recipe['name']
            recipes[name] = recipe.copy()

        return {'recipes': recipes}

    def _generate_intro(self, template: Dict) -> str:
        """生成 intro.md（场景引入文本）"""
        return f"""# {template['name']}

**主题**: {template['theme']}
**难度**: {template.get('difficulty', '中等')}

## 背景故事

{self._generate_story_intro(template)}

## 生存目标

{template['goal']['description']}

## 环境特征

- **气候**: {', '.join(template['environment']['weather_types'])}
- **地形**: {', '.join(template['environment']['biomes'])}
- **温度范围**: {template['environment']['temperature_range'][0]}°C - {template['environment']['temperature_range'][1]}°C

## 关键挑战

{self._generate_challenges(template)}

---

*这是一个自动生成的场景。祝你好运，生存者。*
"""

    def _generate_story_intro(self, template: Dict) -> str:
        """根据主题生成故事引入"""
        theme_stories = {
            '科幻生存': '你的穿梭机在未知星球坠毁，残骸散落在异星荒野。生存系统受损，补给有限。你必须利用这颗星球的资源，制造信号装置发出求救信号。',
            '沙漠生存': '沙漠探测基地遭遇沙尘暴袭击，通讯中断，补给耗尽。你必须在酷热的沙漠中寻找资源，修复紧急信标，等待救援。',
            '海底生存': '深海研究站发生泄漏事故，部分舱室被水淹没。氧气和食物储备告急，你必须修复潜水艇并逃离这个深海陷阱。',
            '末日生存': '核战争后的废土世界，辐射、饥荒、污染环绕四周。避难所的空气净化系统失效，你必须寻找零件修复它，否则将窒息而死。',
        }
        return theme_stories.get(template['theme'], '这是一个生存挑战。')

    def _generate_challenges(self, template: Dict) -> str:
        """生成关键挑战描述"""
        difficulty = template.get('difficulty', '中等')
        modifiers = self.config['difficulty_modifiers'].get(difficulty,
                                                            self.config['difficulty_modifiers']['中等'])

        return f"""1. **水源稀缺**: 口渴值每小时增加 {modifiers['thirst_rate']}，必须尽快找到可靠水源
2. **资源有限**: 每个区域的材料采集后不再生，需要谨慎规划
3. **时间压力**: 昼夜循环隐藏，需要通过环境线索推测时间
4. **工具制作**: 必须理解材料属性组合规律，制作关键工具
"""

    def _generate_location_description(self, name: str) -> str:
        """生成地点描述"""
        # 简单的模板描述，实际可以更复杂
        return f"这是一个{name}区域。"

    def _generate_material_description(self, name: str, pool: Dict) -> str:
        """生成材料描述"""
        category = pool['category']
        return f"{category}材料，具有{'、'.join(pool['properties'][:2])}等特性。"

    def _get_trigger_location_id(self, trigger_type: str) -> str:
        """获取胜利触发地点 ID"""
        type_map = {
            '高地': 'signal_tower',
            '基地中心': 'base_center',
            '停泊舱': 'docking_bay',
            '避难所中心': 'shelter_core',
        }
        return type_map.get(trigger_type, 'goal_location')

    def _to_id(self, name: str) -> str:
        """将名称转为 ID"""
        id_map = {
            '森林': 'forest',
            '沼泽': 'swamp',
            '山脊': 'ridge',
            '洞穴': 'cave',
            '沙丘': 'dunes',
            '岩石平原': 'rocky_plain',
            '干涸河床': 'dry_riverbed',
            '废弃矿井': 'abandoned_mine',
            '气密舱': 'airlock',
            '泄漏区': 'flooded_zone',
            '储藏室': 'storage',
            '控制中心': 'control_center',
            '废墟': 'ruins',
            '辐射区': 'radiation_zone',
            '地下室': 'basement',
            '废弃工厂': 'factory',
            '高地': 'signal_tower',
        }
        return id_map.get(name, name.lower().replace(' ', '_'))

    def save_scene(self, scene_data: Dict[str, Any], output_dir: str):
        """保存场景文件到指定目录"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        for filename, content in scene_data.items():
            file_path = output_path / filename

            if filename.endswith('.yaml'):
                with open(file_path, 'w', encoding='utf-8') as f:
                    yaml.dump(content, f, allow_unicode=True, sort_keys=False, indent=2)
            else:  # .md
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)

        print(f"✓ 场景已生成到: {output_dir}")
        print(f"  - scenario.yaml")
        print(f"  - locations.yaml")
        print(f"  - materials.yaml")
        print(f"  - recipes.yaml")
        print(f"  - intro.md")


def main():
    parser = argparse.ArgumentParser(description='生存沙盒场景生成器')
    parser.add_argument('--theme', type=str, help='场景主题（crash_site, desert_outpost 等）')
    parser.add_argument('--seed', type=int, default=42, help='随机种子（默认: 42）')
    parser.add_argument('--difficulty', type=str, choices=['简单', '中等', '困难', '极难'],
                       help='难度等级（可选，默认使用模板难度）')
    parser.add_argument('--output', type=str, help='输出目录（默认: data/scenes/<theme>_<seed>）')
    parser.add_argument('--list', action='store_true', help='列出所有可用主题')

    args = parser.parse_args()

    generator = SceneGenerator()

    if args.list:
        print("可用场景主题:")
        for theme in generator.list_themes():
            template = generator.templates[theme]
            print(f"  - {theme:<20} ({template['name']}, {template['theme']}, {template.get('difficulty', '中等')})")
        return

    if not args.theme:
        parser.error("请指定 --theme 或使用 --list 查看可用主题")

    # 生成场景
    try:
        scene_data = generator.generate_scene(args.theme, args.seed, args.difficulty)

        # 确定输出目录
        output_dir = args.output or f"data/scenes/{args.theme}_{args.seed}"

        # 保存
        generator.save_scene(scene_data, output_dir)

        print(f"\n场景生成成功！")
        print(f"主题: {generator.templates[args.theme]['name']}")
        print(f"种子: {args.seed}")
        if args.difficulty:
            print(f"难度: {args.difficulty}")

    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
