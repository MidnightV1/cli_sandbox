# -*- coding: utf-8 -*-
"""确定性规则引擎 —— 处理所有预定义动作"""

from models.state import WorldState, ActionResult, ACTION_TIME_COSTS
from models.items import Item
from data.loader import create_item_from_material


class RuleEngine:
    def __init__(self, materials: dict, recipes: dict):
        self.materials = materials
        self.recipes = recipes

    def resolve(self, action_type: str, args: dict, world: WorldState) -> ActionResult:
        """分发到对应处理器，自动注入time_cost"""
        handlers = {
            'move': self._handle_move,
            'look': self._handle_look,
            'gather': self._handle_gather,
            'use': self._handle_use,
            'craft': self._handle_craft,
            'combine': self._handle_combine,
            'eat': self._handle_consume,
            'drink': self._handle_consume,
            'rest': self._handle_rest,
            'inventory': self._handle_inventory,
            'help': self._handle_help,
            'recipes': self._handle_recipes,
        }
        handler = handlers.get(action_type)
        if handler:
            result = handler(args, world)
            # 自动注入 time_cost（仅成功的动作消耗时间）
            if result.success and result.time_cost == 0.0:
                result.time_cost = ACTION_TIME_COSTS.get(action_type, 0.0)
            return result
        return ActionResult(success=False, message="未知指令。输入 help 查看可用指令。", energy_cost=0)

    # ──────────── 移动 ────────────
    def _handle_move(self, args: dict, world: WorldState) -> ActionResult:
        direction = args.get('target', '')
        loc = world.locations[world.player.location]

        # 模糊匹配方向
        matched_dir = None
        matched_loc_id = None
        for d, lid in loc.connections.items():
            if direction == d or direction in d:
                matched_dir = d
                matched_loc_id = lid
                break

        if not matched_loc_id:
            dirs = "、".join(f"[{d}] {world.locations[lid].name}" if lid in world.locations else f"[{d}]"
                           for d, lid in loc.connections.items())
            return ActionResult(success=False, message=f"无法向 {direction} 移动。可用方向：{dirs}", energy_cost=0)

        target_loc = world.locations.get(matched_loc_id)
        if not target_loc:
            return ActionResult(success=False, message=f"那个方向似乎不通。", energy_cost=0)

        if not target_loc.discovered:
            return ActionResult(success=False, message=f"你还不知道那个方向有什么。先在高处观察或探索周围。", energy_cost=0)

        # 能量检查
        if world.player.status.energy <= 0:
            return ActionResult(success=False, message="你精疲力竭，无法移动。先休息恢复体力。", energy_cost=0)

        # 执行移动
        world.player.location = matched_loc_id
        target_loc.visited = True
        world.player.discovered_locations.add(matched_loc_id)

        # 发现可见位置
        newly_discovered = []
        for vis_id in target_loc.visibility:
            if vis_id in world.locations and not world.locations[vis_id].discovered:
                world.locations[vis_id].discovered = True
                newly_discovered.append(world.locations[vis_id].name)

        msg = f"你向{matched_dir}移动，来到了【{target_loc.name}】。"
        if newly_discovered:
            msg += f"\n从这里你发现了新的地点：{'、'.join(newly_discovered)}"

        return ActionResult(success=True, message=msg, energy_cost=1)

    # ──────────── 观察 ────────────
    def _handle_look(self, args: dict, world: WorldState) -> ActionResult:
        target = args.get('target')
        loc = world.locations[world.player.location]

        if not target:
            # 环顾四周
            lines = [f"【{loc.name}】", loc.description, ""]

            # 可采集资源
            available = loc.get_available_resources(world.action_count)
            if available:
                res_strs = []
                for r in available:
                    mat = self.materials.get(r.item_id, {})
                    name = mat.get('name', r.item_id)
                    res_strs.append(f"{name}(x{r.quantity})")
                lines.append(f"可采集：{'  '.join(res_strs)}")

            # 放置物
            if loc.placed_items:
                placed_strs = [str(item) for item in loc.placed_items]
                lines.append(f"已建造：{'  '.join(placed_strs)}")

            # 通路
            conn_strs = []
            for d, lid in loc.connections.items():
                if lid in world.locations:
                    tloc = world.locations[lid]
                    if tloc.discovered:
                        visited_mark = "" if tloc.visited else "（未探索）"
                        conn_strs.append(f"[{d}] {tloc.name}{visited_mark}")
                    else:
                        conn_strs.append(f"[{d}] ???")
            if conn_strs:
                lines.append(f"通往：{'  '.join(conn_strs)}")

            # 危险
            if loc.hazards:
                lines.append(f"威胁：{'、'.join(loc.hazards)}")

            return ActionResult(success=True, message="\n".join(lines), energy_cost=0)

        # 查看特定物品（背包或周围资源）
        item = world.player.inventory.find(target)
        if item:
            props_str = "、".join(item.properties)
            lines = [
                f"【{item.name}】",
                item.description,
                f"属性：{props_str}",
            ]
            if item.actions:
                lines.append(f"可用于：{'、'.join(item.actions)}")
            if item.durability > 0:
                lines.append(f"耐久度：{item.durability}/{item.max_durability}")
            if item.quantity > 1:
                lines.append(f"数量：{item.quantity}")
            return ActionResult(success=True, message="\n".join(lines), energy_cost=0)

        # 查看周围资源
        for r in loc.resources:
            mat = self.materials.get(r.item_id, {})
            if target in mat.get('name', '') or target == r.item_id:
                props_str = "、".join(mat.get('properties', []))
                lines = [
                    f"【{mat['name']}】",
                    mat.get('description', ''),
                    f"属性：{props_str}",
                    f"可采集数量：{r.quantity}",
                ]
                return ActionResult(success=True, message="\n".join(lines), energy_cost=0)

        # 查看方向
        for d, lid in loc.connections.items():
            if target in d and lid in world.locations and world.locations[lid].discovered:
                tloc = world.locations[lid]
                return ActionResult(success=True, message=f"向{d}望去，那是【{tloc.name}】——{tloc.description[:50]}...", energy_cost=0)

        return ActionResult(success=False, message=f"你四处张望，但没有找到「{target}」。", energy_cost=0)

    # ──────────── 采集 ────────────
    def _handle_gather(self, args: dict, world: WorldState) -> ActionResult:
        target = args.get('target', '')
        loc = world.locations[world.player.location]

        if world.player.status.energy <= 0:
            return ActionResult(success=False, message="你太疲惫了，无法采集。", energy_cost=0)

        # 模糊匹配资源
        matched_resource = None
        for r in loc.resources:
            mat = self.materials.get(r.item_id, {})
            mat_name = mat.get('name', '')
            if target == r.item_id or target in mat_name or mat_name in target:
                if r.quantity > 0:
                    matched_resource = r
                    break

        if not matched_resource:
            return ActionResult(success=False, message=f"这里没有可采集的「{target}」。", energy_cost=0)

        # 检查可再生资源的冷却
        if matched_resource.renewable:
            ticks_since = world.action_count - matched_resource.last_gathered
            if ticks_since < matched_resource.regen_ticks and matched_resource.quantity <= 0:
                return ActionResult(success=False, message=f"这种资源还没有再生，需要等待。", energy_cost=0)

        # 执行采集
        item = create_item_from_material(matched_resource.item_id, self.materials)
        matched_resource.quantity -= 1
        matched_resource.last_gathered = world.action_count
        world.player.inventory.add(item)

        return ActionResult(
            success=True,
            message=f"你采集了【{item.name}】。{item.description}",
            items_gained=[item],
            energy_cost=1,
        )

    # ──────────── 使用工具 ────────────
    def _handle_use(self, args: dict, world: WorldState) -> ActionResult:
        tool_name = args.get('tool', '')
        target = args.get('target', '')

        tool = world.player.inventory.find(tool_name)
        if not tool:
            return ActionResult(success=False, message=f"背包里没有「{tool_name}」。", energy_cost=0)

        if world.player.status.energy <= 0:
            return ActionResult(success=False, message="你太疲惫了。", energy_cost=0)

        # 信号装置 + 信号塔 = 通关
        loc = world.locations[world.player.location]
        if '发送信号' in tool.actions and world.player.location == 'signal_tower':
            # 通关！
            return ActionResult(
                success=True,
                message="你将信号装置放入塔顶的碗状凹陷中。装置开始发出强烈的光芒，"
                        "信号塔上的几何纹样随之亮起，一道光柱直冲云霄。\n"
                        "求救信号已发送！你成功了！",
                extra={'goal_trigger': 'signal'},
                energy_cost=1,
            )

        # 火把照明 - 发现未发现的区域
        if '照明' in tool.actions:
            newly_found = []
            for d, lid in loc.connections.items():
                if lid in world.locations and not world.locations[lid].discovered:
                    world.locations[lid].discovered = True
                    newly_found.append(world.locations[lid].name)
            tool.use_once()
            durability_msg = f"（耐久 {tool.durability}/{tool.max_durability}）" if tool.durability > 0 else ""
            if tool.durability == 0:
                world.player.inventory.remove(tool.id)
                durability_msg = "（已损坏）"

            if newly_found:
                return ActionResult(
                    success=True,
                    message=f"火光照亮了周围。你发现了新的通路：{'、'.join(newly_found)}{durability_msg}",
                    energy_cost=1,
                )
            return ActionResult(
                success=True,
                message=f"你举起火把照亮四周，但没有发现新的东西。{durability_msg}",
                energy_cost=1,
            )

        # 净水
        if '净水' in tool.actions and target:
            water_item = world.player.inventory.find(target)
            if water_item and '可饮用' in water_item.properties:
                # 净化水：移除副作用
                if water_item.consumable and water_item.consumable.get('side_effect'):
                    water_item.consumable.pop('side_effect', None)
                    water_item.consumable['water_value'] = max(water_item.consumable.get('water_value', 1), 2)
                    tool.use_once()
                    return ActionResult(success=True, message=f"你用滤水器净化了{water_item.name}，现在可以安全饮用了。", energy_cost=1)
                return ActionResult(success=True, message=f"{water_item.name}已经是干净的了。", energy_cost=0)

        # 通用工具使用：扣耐久
        tool.use_once()
        durability_msg = ""
        if tool.durability == 0:
            world.player.inventory.remove(tool.id)
            durability_msg = f" {tool.name}已经损坏了。"
        elif tool.durability > 0:
            durability_msg = f"（耐久 {tool.durability}/{tool.max_durability}）"

        return ActionResult(
            success=True,
            message=f"你对{target}使用了{tool.name}。{durability_msg}",
            energy_cost=1,
            needs_llm=True,  # 通用使用需要LLM判定效果
        )

    # ──────────── 制作（已知配方）────────────
    def _handle_craft(self, args: dict, world: WorldState) -> ActionResult:
        recipe_name = args.get('target', '')

        if world.player.status.energy < 2:
            return ActionResult(success=False, message="制作需要至少2点体力。", energy_cost=0)

        # 模糊匹配配方
        matched_id, matched_recipe = self._find_recipe(recipe_name, world)
        if not matched_recipe:
            known_names = [self.recipes[rid]['name'] for rid in world.player.known_recipes if rid in self.recipes]
            return ActionResult(
                success=False,
                message=f"你不知道怎么制作「{recipe_name}」。\n已知配方：{'、'.join(known_names) if known_names else '无'}",
                energy_cost=0,
            )

        # 检查玩家是否知道这个配方
        if matched_id not in world.player.known_recipes:
            return ActionResult(
                success=False,
                message=f"你还不知道{matched_recipe['name']}的制作方法。尝试用 combine 组合材料来发现新配方。",
                energy_cost=0,
            )

        # 自动匹配背包物品到配方槽位
        assignment = self._auto_assign_slots(matched_recipe, world.player.inventory)
        if not assignment:
            # 告诉玩家缺什么
            missing = self._describe_missing(matched_recipe, world.player.inventory)
            return ActionResult(
                success=False,
                message=f"材料不足，无法制作{matched_recipe['name']}。\n{missing}",
                energy_cost=0,
            )

        # 执行制作
        return self._execute_craft(matched_id, matched_recipe, assignment, world)

    # ──────────── 组合（可能触发已知配方或新发明）────────────
    def _handle_combine(self, args: dict, world: WorldState) -> ActionResult:
        item_names = args.get('items', [])

        if len(item_names) < 2:
            return ActionResult(success=False, message="至少需要两个物品才能组合。", energy_cost=0)

        if world.player.status.energy < 2:
            return ActionResult(success=False, message="组合需要至少2点体力。", energy_cost=0)

        # 查找物品
        items = []
        for name in item_names:
            item = world.player.inventory.find(name)
            if not item:
                return ActionResult(success=False, message=f"背包里没有「{name}」。", energy_cost=0)
            items.append(item)

        # 尝试匹配已知配方
        for recipe_id, recipe in self.recipes.items():
            assignment = self._try_match_items_to_recipe(items, recipe)
            if assignment:
                if recipe_id not in world.player.known_recipes:
                    world.player.known_recipes.append(recipe_id)
                    msg_prefix = f"你发现了新配方：【{recipe['name']}】！\n"
                else:
                    msg_prefix = ""
                result = self._execute_craft(recipe_id, recipe, assignment, world)
                result.message = msg_prefix + result.message
                return result

        # 没有匹配的配方 → 需要LLM裁判
        return ActionResult(
            success=False,
            message="",
            needs_llm=True,
            energy_cost=0,
            extra={'items': items},
        )

    # ──────────── 消耗（吃/喝）────────────
    def _handle_consume(self, args: dict, world: WorldState) -> ActionResult:
        target = args.get('target', '')
        action_type = args.get('action_type', 'eat')

        item = world.player.inventory.find(target)
        if not item:
            return ActionResult(success=False, message=f"背包里没有「{target}」。", energy_cost=0)

        if not item.consumable:
            return ActionResult(success=False, message=f"{item.name}不能{'吃' if action_type == 'eat' else '喝'}。", energy_cost=0)

        cons = item.consumable
        msgs = []
        side_effects = {}

        if cons['type'] in ('food', 'both'):
            food_val = cons.get('food_value', 1)
            world.player.status.hunger = max(0, world.player.status.hunger - food_val)
            msgs.append(f"饥饿感缓解了（-{food_val}）")

        if cons['type'] in ('water', 'both'):
            water_val = cons.get('water_value', 1)
            world.player.status.thirst = max(0, world.player.status.thirst - water_val)
            msgs.append(f"口渴缓解了（-{water_val}）")

        if cons.get('side_effect') == 'health_minus_1':
            world.player.status.health -= 1
            msgs.append("但你感觉胃里一阵翻涌（生命-1）")
            side_effects['health_mod'] = -1

        # 消耗物品
        world.player.inventory.remove(item.id, 1)

        return ActionResult(
            success=True,
            message=f"你{'吃' if action_type != 'drink' else '喝'}了{item.name}。{'，'.join(msgs)}。",
            items_consumed=[item.id],
            energy_cost=0,
        )

    # ──────────── 休息 ────────────
    def _handle_rest(self, args: dict, world: WorldState) -> ActionResult:
        loc = world.locations[world.player.location]
        recovery = 3 if loc.shelter else 2
        # 如果有庇护所放置物也算
        for placed in loc.placed_items:
            if '庇护' in placed.properties:
                recovery = 3
                break

        world.player.status.energy = min(
            world.player.status.max_energy,
            world.player.status.energy + recovery
        )
        return ActionResult(
            success=True,
            message=f"你休息了一会儿。体力恢复了{recovery}点。"
                    + ("（庇护所让你休息得更好）" if recovery == 3 and not loc.shelter else ""),
            energy_cost=-recovery,  # 负值表示恢复
        )

    # ──────────── 背包 ────────────
    def _handle_inventory(self, args: dict, world: WorldState) -> ActionResult:
        inv = world.player.inventory
        if inv.is_empty():
            return ActionResult(success=True, message="背包是空的。", energy_cost=0)

        lines = ["── 背包 ──"]
        for item in inv.list_all():
            line = f"  {item}"
            if item.properties:
                line += f"  [{', '.join(item.properties[:3])}{'...' if len(item.properties) > 3 else ''}]"
            lines.append(line)

        return ActionResult(success=True, message="\n".join(lines), energy_cost=0)

    # ──────────── 帮助 ────────────
    def _handle_help(self, args: dict, world: WorldState) -> ActionResult:
        tech_num, tech_name = world.tech_level
        help_text = f"""── 可用指令 ──
  移动/move <方向>         向某个方向移动
  观察/look [目标]         环顾四周或查看具体物品/方向
  采集/gather <资源名>     采集当前位置的资源
  使用/use <工具> on <目标> 使用工具
  制作/craft <配方名>      用已知配方制作物品
  组合/combine <物品> <物品> [<物品>...]  自由组合物品
  吃/eat <食物>            食用物品
  喝/drink <饮品>          饮用物品
  休息/rest                休息恢复体力
  背包/inventory           查看背包
  配方/recipes             查看已知配方
  尝试/try "<描述>"        尝试任意行为（由AI裁判判定）
  帮助/help                显示此帮助

── 当前状态 ──
  科技等级：{tech_name}（{world.tech_points}点）
  下一检查点：第{world.next_checkpoint_day}天

── 机制说明 ──
  每个动作消耗时间，不同动作耗时不同。
  制作新配方可获得科技点数，提升科技等级。
  每{world.checkpoint_interval}天触发一次阶段检查点。"""
        return ActionResult(success=True, message=help_text, energy_cost=0)

    # ──────────── 查看配方 ────────────
    def _handle_recipes(self, args: dict, world: WorldState) -> ActionResult:
        known = world.player.known_recipes
        if not known:
            return ActionResult(success=True, message="你还没有学会任何配方。", energy_cost=0)

        lines = ["── 已知配方 ──"]
        for rid in known:
            if rid in self.recipes:
                r = self.recipes[rid]
                slots_desc = []
                for slot_name, slot_def in r['slots'].items():
                    reqs = "、".join(slot_def['requires'])
                    slots_desc.append(f"{slot_def['description']}[需要: {reqs}]")
                lines.append(f"  {r['name']}：{'  +  '.join(slots_desc)}")
            elif rid in world.invented_recipes:
                ir = world.invented_recipes[rid]
                lines.append(f"  {ir.get('name', rid)}（自创配方）")

        return ActionResult(success=True, message="\n".join(lines), energy_cost=0)

    # ──────────── 内部工具方法 ────────────

    def _find_recipe(self, name: str, world: WorldState) -> tuple:
        """模糊匹配配方名"""
        # 所有可用配方 = 系统配方 + 发明配方
        all_recipes = {**self.recipes, **world.invented_recipes}
        for rid, recipe in all_recipes.items():
            if name == rid or name == recipe['name'] or name in recipe['name']:
                return rid, recipe
        return None, None

    def _auto_assign_slots(self, recipe: dict, inventory) -> dict | None:
        """自动将背包物品分配到配方槽位。返回 {slot_name: Item} 或 None
        同一物品 quantity>=2 时可分配给多个槽位。"""
        slots = recipe['slots']
        assignment = {}
        # 追踪每个物品已被分配的次数
        used_count: dict[int, int] = {}  # index → 已用次数

        for slot_name, slot_def in slots.items():
            required_props = slot_def['requires']
            assigned = False
            for i, item in enumerate(inventory.list_all()):
                already_used = used_count.get(i, 0)
                if already_used >= item.quantity:
                    continue
                if item.has_all_properties(required_props):
                    assignment[slot_name] = item
                    used_count[i] = already_used + 1
                    assigned = True
                    break
            if not assigned:
                return None
        return assignment

    def _try_match_items_to_recipe(self, items: list, recipe: dict) -> dict | None:
        """尝试将给定物品匹配到配方槽位"""
        slots = recipe['slots']
        if len(items) != len(slots):
            return None

        # 尝试所有排列（物品数量不多，暴力枚举）
        from itertools import permutations
        slot_names = list(slots.keys())

        for perm in permutations(range(len(items))):
            assignment = {}
            valid = True
            for idx, slot_name in zip(perm, slot_names):
                required_props = slots[slot_name]['requires']
                if items[idx].has_all_properties(required_props):
                    assignment[slot_name] = items[idx]
                else:
                    valid = False
                    break
            if valid:
                return assignment
        return None

    def _execute_craft(self, recipe_id: str, recipe: dict, assignment: dict, world: WorldState) -> ActionResult:
        """执行制作：消耗材料，产出物品"""
        result_def = recipe['result']

        # 生成物品名称
        name = result_def.get('name_template', recipe['name'])
        for slot_name, item in assignment.items():
            name = name.replace(f"{{{slot_name}}}", item.name)

        # 创建产出物品
        new_item = Item(
            id=f"crafted_{recipe_id}_{world.action_count}",
            name=name,
            description=recipe.get('method', '').format(**{k: v.name for k, v in assignment.items()}),
            properties=list(result_def.get('properties', [])),
            durability=result_def.get('durability', 10),
            max_durability=result_def.get('durability', 10),
            actions=list(result_def.get('actions', [])),
        )

        # 消耗材料
        consumed = []
        for slot_name, item in assignment.items():
            world.player.inventory.remove(item.id, 1)
            consumed.append(item.id)

        # 放置物还是背包物？
        if result_def.get('placed'):
            loc = world.locations[world.player.location]
            loc.placed_items.append(new_item)
            # 庇护所标记
            if '庇护' in new_item.properties:
                loc.shelter = True
            msg = f"你成功建造了【{new_item.name}】！它被放置在了当前位置。"
        else:
            world.player.inventory.add(new_item)
            msg = f"你成功制作了【{new_item.name}】！"

        # 科技点数（每种配方只算首次）
        if recipe_id not in world.crafted_recipes:
            world.crafted_recipes.append(recipe_id)
            tp = recipe.get('tech_points', recipe.get('difficulty', 1))
            world.tech_points += tp
            msg += f"\n（科技 +{tp}）"

        # 制作描述
        method_desc = recipe.get('method', '').format(**{k: v.name for k, v in assignment.items()})
        msg += f"\n{method_desc}"

        return ActionResult(
            success=True,
            message=msg,
            items_consumed=consumed,
            items_gained=[new_item],
            energy_cost=2,
            extra={'goal_trigger': result_def.get('goal_trigger')},
        )

    def _describe_missing(self, recipe: dict, inventory) -> str:
        """描述缺少的材料"""
        lines = []
        for slot_name, slot_def in recipe['slots'].items():
            required = slot_def['requires']
            found = False
            for item in inventory.list_all():
                if item.has_all_properties(required):
                    found = True
                    break
            if not found:
                lines.append(f"  缺少 {slot_def['description']}（需要属性：{'、'.join(required)}）")
        return "\n".join(lines) if lines else "材料不足"
