# -*- coding: utf-8 -*-
"""数据加载器：YAML → 游戏对象"""

import os
import random
import yaml
from models.items import Item, Inventory
from models.state import PlayerState, PlayerStatus, WorldState, Goal
from models.map import Location, LocationResource

DATA_DIR = os.path.dirname(os.path.abspath(__file__))


def load_yaml(filename: str) -> dict:
    path = os.path.join(DATA_DIR, filename)
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def load_materials() -> dict:
    """加载材料模板库 → {material_id: template_dict}"""
    data = load_yaml('materials.yaml')
    return data.get('materials', {})


def load_recipes() -> dict:
    """加载配方库 → {recipe_id: recipe_dict}"""
    data = load_yaml('recipes.yaml')
    return data.get('recipes', {})


def create_item_from_material(material_id: str, materials: dict, quantity: int = 1) -> Item:
    """从材料模板创建物品实例"""
    tmpl = materials[material_id]
    return Item(
        id=material_id,
        name=tmpl['name'],
        description=tmpl['description'],
        properties=list(tmpl.get('properties', [])),
        consumable=tmpl.get('consumable'),
        quantity=quantity,
    )


def load_scenario(scenario_name: str) -> tuple[WorldState, dict, dict]:
    """
    加载场景，返回 (world_state, materials_db, recipes_db)
    """
    materials = load_materials()
    recipes = load_recipes()
    scenario_data = load_yaml(f'scenarios/{scenario_name}.yaml')
    sc = scenario_data['scenario']

    # 构建地图
    locations = {}
    for loc_id, loc_data in sc['locations'].items():
        resources = []
        for r in loc_data.get('resources', []):
            resources.append(LocationResource(
                item_id=r['item_id'],
                quantity=r.get('quantity', 1),
                renewable=r.get('renewable', False),
                regen_ticks=r.get('regen_ticks', 10),
            ))
        locations[loc_id] = Location(
            id=loc_id,
            name=loc_data['name'],
            description=loc_data['description'].strip(),
            resources=resources,
            connections=loc_data.get('connections', {}),
            hazards=loc_data.get('hazards', []),
            discovered=loc_data.get('discovered', True),
            visited=(loc_id == sc['start']['location']),
            visibility=loc_data.get('visibility', []),
            shelter=loc_data.get('shelter', False),
        )

    # 构建玩家初始状态
    start = sc['start']
    inventory = Inventory()
    for item_def in start.get('inventory', []):
        item = create_item_from_material(
            item_def['id'], materials, item_def.get('quantity', 1)
        )
        inventory.add(item)

    s = start.get('status', {})
    player = PlayerState(
        location=start['location'],
        inventory=inventory,
        status=PlayerStatus(
            health=s.get('health', 10),
            hunger=s.get('hunger', 0),
            thirst=s.get('thirst', 0),
            warmth=s.get('warmth', 7),
            energy=s.get('energy', 8),
        ),
        known_recipes=list(start.get('known_recipes', [])),
        discovered_locations={start['location']},
    )

    # 构建目标
    goals = []
    for g in sc.get('goals', []):
        goals.append(Goal(
            id=g['id'],
            description=g['description'],
            goal_type=g.get('type', 'primary'),
        ))

    # 构建天气池
    weather_pool = sc.get('weather_pool', [{'type': '晴朗', 'weight': 1, 'effects': {}}])

    # 时间系统：日长在范围内随机生成（对玩家隐藏）
    time_config = sc.get('time_system', {})
    day_length_min = time_config.get('day_length_min', 20)
    day_length_max = time_config.get('day_length_max', 30)
    day_length = random.randint(day_length_min, day_length_max)
    checkpoint_interval = sc.get('checkpoint_interval', 100)

    world = WorldState(
        player=player,
        locations=locations,
        day_length=day_length,
        max_days=0,  # 无硬性上限
        checkpoint_interval=checkpoint_interval,
        goals=goals,
        scenario_name=sc['name'],
    )
    world._weather_pool = weather_pool

    return world, materials, recipes
