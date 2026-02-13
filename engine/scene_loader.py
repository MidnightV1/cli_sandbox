# -*- coding: utf-8 -*-
"""场景加载器：从场景目录加载 5 个文件，构建 WorldState"""

import os
import random
import yaml
from models.items import Item, Inventory, create_item_from_material
from models.state import PlayerState, PlayerStatus, WorldState, Goal
from models.map import Location, LocationResource


def _load_yaml(path: str) -> dict:
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


# ── 方向旋转系统（Layer 3）──
# 8 方位按顺时针排列，每 90° = 2 个位置
_DIR_ORDER = ['北', '东北', '东', '东南', '南', '西南', '西', '西北']
_DIR_INDEX = {d: i for i, d in enumerate(_DIR_ORDER)}
_SPECIAL_DIRS = {'深处', '外面', '上', '下'}  # 逻辑方向，不参与旋转


def _rotate_direction(direction: str, rotation: int) -> str:
    """将罗盘方向顺时针旋转 rotation×90°"""
    if direction in _SPECIAL_DIRS:
        return direction
    idx = _DIR_INDEX.get(direction)
    if idx is None:
        return direction  # 未知方向，保持原样
    new_idx = (idx + rotation * 2) % 8
    return _DIR_ORDER[new_idx]


def _resolve_quantity(raw_qty) -> int:
    """解析资源数量：固定值直接返回，[min, max] 范围用 seed 随机"""
    if isinstance(raw_qty, list) and len(raw_qty) == 2:
        return random.randint(raw_qty[0], raw_qty[1])
    return int(raw_qty)


def load_scene(scene_dir: str) -> tuple[WorldState, dict, dict]:
    """
    从场景目录加载完整场景。

    场景目录结构：
        scenario.yaml   - 元数据、起始状态、目标、天气
        locations.yaml  - 地点网络
        materials.yaml  - 材料定义
        recipes.yaml    - 配方定义
        intro.md        - 场景引入文本（可选）

    返回 (world_state, materials_db, recipes_db)
    """
    scene_dir = os.path.abspath(scene_dir)

    # 加载 4 个必需文件
    scenario = _load_yaml(os.path.join(scene_dir, 'scenario.yaml'))
    locations_data = _load_yaml(os.path.join(scene_dir, 'locations.yaml'))
    materials_raw = _load_yaml(os.path.join(scene_dir, 'materials.yaml'))
    recipes_raw = _load_yaml(os.path.join(scene_dir, 'recipes.yaml'))

    # materials.yaml 兼容两种格式：有 'materials' key 或直接是 flat dict
    materials = materials_raw.get('materials', materials_raw)
    recipes = recipes_raw.get('recipes', recipes_raw)

    # 方向旋转（Layer 3）：seed 决定地图朝向，0=原始 / 1=90° / 2=180° / 3=270°
    rotation = random.randint(0, 3)

    # 构建地图
    start_location = scenario['start']['location']
    locations = {}
    for loc_id, loc_data in locations_data.items():
        # Layer 1：资源数量随机化
        resources = []
        for r in loc_data.get('resources', []):
            resources.append(LocationResource(
                item_id=r['item_id'],
                quantity=_resolve_quantity(r.get('quantity', 1)),
                renewable=r.get('renewable', False),
                regen_ticks=r.get('regen_ticks', 10),
            ))
        # Layer 3：连接方向旋转
        raw_connections = loc_data.get('connections', {})
        rotated_connections = {
            _rotate_direction(d, rotation): target
            for d, target in raw_connections.items()
        }
        locations[loc_id] = Location(
            id=loc_id,
            name=loc_data['name'],
            description=loc_data['description'].strip(),
            resources=resources,
            connections=rotated_connections,
            hazards=loc_data.get('hazards', []),
            discovered=loc_data.get('discovered', True),
            visited=(loc_id == start_location),
            visibility=loc_data.get('visibility', []),
            shelter=loc_data.get('shelter', False),
        )

    # 构建玩家初始状态
    start = scenario['start']
    inventory = Inventory()
    for item_def in start.get('inventory', []):
        item = create_item_from_material(
            item_def['id'], materials, item_def.get('quantity', 1)
        )
        inventory.add(item)

    s = start.get('status', {})
    player = PlayerState(
        location=start_location,
        inventory=inventory,
        status=PlayerStatus(
            health=s.get('health', 100),
            hunger=s.get('hunger', 0),
            thirst=s.get('thirst', 0),
            warmth=s.get('warmth', 70),
            energy=s.get('energy', 80),
        ),
        known_recipes=list(start.get('known_recipes', [])),
        discovered_locations={start_location},
    )

    # 构建目标
    goals = []
    for g in scenario.get('goals', []):
        goals.append(Goal(
            id=g['id'],
            description=g['description'],
            goal_type=g.get('type', 'primary'),
        ))

    # 天气池
    weather_pool = scenario.get('weather_pool', [{'type': '晴朗', 'weight': 1, 'effects': {}}])

    # 时间系统：日长由运行时 seed 控制
    time_config = scenario.get('time_system', {})
    day_length_min = time_config.get('day_length_min', 20)
    day_length_max = time_config.get('day_length_max', 30)
    day_length = random.randint(day_length_min, day_length_max)

    checkpoint_interval = scenario.get('checkpoint_interval', 100)

    world = WorldState(
        player=player,
        locations=locations,
        day_length=day_length,
        max_days=0,
        checkpoint_interval=checkpoint_interval,
        goals=goals,
        scenario_name=scenario.get('name', ''),
    )
    world._weather_pool = weather_pool

    return world, materials, recipes
