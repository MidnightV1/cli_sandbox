# -*- coding: utf-8 -*-
"""游戏引擎 —— 主循环与状态协调"""

import os
from models.state import WorldState, ActionResult, TickResult, ACTION_TIME_COSTS
from engine.rules import RuleEngine
from engine.events import EventSystem
from engine.judge import LLMJudge
from engine.scene_loader import load_scene

# 默认场景路径
DEFAULT_SCENE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'scenes', 'crash_site_42')


class GameEngine:
    def __init__(self, scene_dir: str = None, llm_client=None):
        # 加载场景
        self.world, self.materials, self.recipes = load_scene(scene_dir or DEFAULT_SCENE)

        # 初始化子系统
        self.rules = RuleEngine(self.materials, self.recipes)
        self.events = EventSystem()

        # LLM裁判（可选）
        world_rules = self._load_world_rules()
        self.llm_client = llm_client
        if llm_client:
            self.judge = LLMJudge(llm_client, world_rules, materials=self.materials)
        else:
            self.judge = None

        self.history: list[TickResult] = []

    def process_action(self, action_type: str, args: dict) -> TickResult:
        """处理一个玩家动作并推进游戏状态"""
        world = self.world

        # 记录状态快照
        status_before = self._snapshot_status()

        # 动作路由
        if action_type == 'free_action':
            result = self._handle_free_action(args)
        elif action_type == 'combine':
            result = self._handle_combine(args)
        else:
            result = self.rules.resolve(action_type, args, world)

        # 如果规则引擎标记需要LLM
        if result.needs_llm and not result.success and self.judge:
            if action_type == 'combine':
                result = self._prompt_and_judge_combine(args, result)
            elif action_type == 'use':
                result = self._handle_generic_use_llm(args)

        # 疲劳动作检测（能量不足时的惩罚）
        is_fatigued = False
        if result.success and result.energy_cost > 0 and world.player.status.energy < result.energy_cost:
            # 能量不足但仍执行动作 = 疲劳动作
            is_fatigued = True
            fatigue_cost = 5  # 疲劳惩罚：消耗 5 点生命
            world.player.status.health -= fatigue_cost
            result.time_cost *= 1.5  # 疲劳动作耗时 ×1.5
            result.message += f"\n⚠️ 你拖着疲惫的身体勉强完成了动作（生命 -{fatigue_cost}，耗时增加 50%）"

        # 扣体力
        if result.success:
            # 成功动作：扣完整体力（即使能量不足也扣，可能变成负数后被 clamp 到 0）
            if result.energy_cost > 0:
                world.player.status.energy = max(0, world.player.status.energy - result.energy_cost)

            # 应用 side_effects（如裁判判定的直接效果）
            side_effects = result.extra.get('side_effects', {})
            if side_effects:
                if 'health_mod' in side_effects:
                    world.player.status.health += side_effects['health_mod']
                if 'hunger_mod' in side_effects:
                    world.player.status.hunger += side_effects['hunger_mod']
                if 'thirst_mod' in side_effects:
                    world.player.status.thirst += side_effects['thirst_mod']
                if 'warmth_mod' in side_effects:
                    world.player.status.warmth += side_effects['warmth_mod']
                # 状态值限制在 0-100
                world.player.status.health = max(0, min(100, world.player.status.health))
                world.player.status.hunger = max(0, min(100, world.player.status.hunger))
                world.player.status.thirst = max(0, min(100, world.player.status.thirst))
                world.player.status.warmth = max(0, min(100, world.player.status.warmth))
        else:
            # 失败动作：分级惩罚机制（0-100 范围）
            # 排除：体力不足导致的失败（避免恶性循环）
            is_energy_failure = "疲惫" in result.message or "体力" in result.message
            if not is_energy_failure:
                # 分级失败惩罚表
                FAILURE_PENALTIES = {
                    # 零成本失败（信息探索）
                    'look': 0,
                    'inventory': 0,
                    'help': 0,
                    'recipes': 0,
                    'note': 0,
                    # 低成本失败（物理操作）
                    'move': 3,
                    'gather': 5,
                    'use': 5,
                    # 高成本失败（复杂操作，成功成本的 50%）
                    'craft': 10,
                    'combine': 10,
                    # 格式错误（轻微惩罚）
                    'empty': 2,
                    'unknown': 2,
                }
                penalty = FAILURE_PENALTIES.get(action_type, 5)  # 默认 5
                if penalty > 0:
                    world.player.status.energy = max(0, world.player.status.energy - penalty)

        # 目标检查
        if result.extra.get('goal_trigger'):
            trigger = result.extra['goal_trigger']
            for g in world.goals:
                if g.id == trigger and not g.completed:
                    g.completed = True
                    result.message += f"\n\n★ 目标完成：{g.description}"
                    if trigger == 'signal':
                        world.game_over = True
                        world.game_over_reason = "你成功发出了求救信号！任务完成！"

        # 时间推进 + 被动事件
        time_cost = result.time_cost
        events = []
        if result.success:
            # 成功动作：完整时间
            if time_cost > 0:
                world.action_count += 1
                events = self.events.process_time(time_cost, world)
            hours_elapsed = time_cost
        else:
            # 失败动作：物理类消耗一半时间（信息类为 0）
            FAILURE_TIME_COSTS = {
                'move': 0.5, 'gather': 0.25, 'use': 0.5,
                'craft': 0.5, 'combine': 0.5,
                'eat': 0.25, 'drink': 0.25,
            }
            failure_time = FAILURE_TIME_COSTS.get(action_type, 0.0)
            if failure_time > 0:
                events = self.events.process_time(failure_time, world)
            hours_elapsed = failure_time

        # 状态快照
        status_after = self._snapshot_status()

        tick_result = TickResult(
            action_count=world.action_count,
            hours_elapsed=hours_elapsed,
            action_result=result,
            events=events,
            status_before=status_before,
            status_after=status_after,
            game_over=world.game_over,
            game_over_reason=world.game_over_reason,
        )
        self.history.append(tick_result)

        return tick_result

    def _handle_combine(self, args: dict) -> ActionResult:
        """处理combine，先走规则引擎"""
        return self.rules.resolve('combine', args, self.world)

    def _handle_free_action(self, args: dict) -> ActionResult:
        """处理完全自由的行为"""
        action_text = args.get('target', '')
        if not self.judge:
            return ActionResult(
                success=False,
                message="自由行为需要LLM裁判系统，但裁判未启用。请使用预定义指令。",
                energy_cost=0,
            )
        result = self.judge.evaluate_free_action(action_text, self.world)
        result.time_cost = ACTION_TIME_COSTS.get('free_action', 1.0)
        return result

    def _prompt_and_judge_combine(self, args: dict, prev_result: ActionResult) -> ActionResult:
        """combine未匹配配方时，交LLM裁判"""
        items = prev_result.extra.get('items', [])
        reasoning = args.get('reasoning', '')
        result = self.judge.evaluate_combine(items, reasoning, self.world)
        result.time_cost = ACTION_TIME_COSTS.get('combine', 2.0)
        return result

    def _handle_generic_use_llm(self, args: dict) -> ActionResult:
        """通用use行为交由LLM裁判"""
        tool_name = args.get('tool', '')
        target = args.get('target', '')
        action_text = f"使用{tool_name}对{target}进行操作"
        result = self.judge.evaluate_free_action(action_text, self.world)
        result.time_cost = ACTION_TIME_COSTS.get('use', 1.0)
        return result

    def _snapshot_status(self) -> dict:
        s = self.world.player.status
        return {
            'health': s.health,
            'hunger': s.hunger,
            'thirst': s.thirst,
            'warmth': s.warmth,
            'energy': s.energy,
        }

    def _load_world_rules(self) -> str:
        rules_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'prompts', 'world_setting.md'
        )
        try:
            with open(rules_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            return "这颗星球遵循基本物理定律。"

    def get_score(self) -> dict:
        """计算当前得分"""
        world = self.world
        goals_completed = sum(1 for g in world.goals if g.completed)
        goals_total = len(world.goals)

        valid_actions = sum(1 for tr in self.history if tr.action_result.success)
        total_actions = len(self.history)
        invalid_rate = (total_actions - valid_actions) / total_actions if total_actions > 0 else 0

        total_locations = len(world.locations)
        visited = sum(1 for loc in world.locations.values() if loc.visited)

        inventions = len(world.invented_recipes)

        # 科技等级
        tech_level_num, tech_level_name = world.tech_level

        # LLM计费
        cost_summary = None
        if self.llm_client and hasattr(self.llm_client, 'cost_tracker'):
            cost_summary = self.llm_client.cost_tracker.summary()

        return {
            'days_survived': world.current_day,
            'hours_survived': round(world.total_hours, 1),
            'actions_taken': world.action_count,
            'goals_completed': goals_completed,
            'goals_total': goals_total,
            'goal_rate': goals_completed / goals_total if goals_total > 0 else 0,
            'valid_actions': valid_actions,
            'total_actions': total_actions,
            'invalid_rate': round(invalid_rate, 2),
            'exploration': f"{visited}/{total_locations}",
            'inventions': inventions,
            'final_health': world.player.status.health,
            'tech_points': world.tech_points,
            'tech_level': tech_level_name,
            'tech_level_num': tech_level_num,
            'checkpoints_passed': world.checkpoints_passed,
            'cost': cost_summary,
        }
