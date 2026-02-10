# -*- coding: utf-8 -*-
"""游戏引擎 —— 主循环与状态协调"""

import os
from models.state import WorldState, ActionResult, TickResult, ACTION_TIME_COSTS
from engine.rules import RuleEngine
from engine.events import EventSystem
from engine.judge import LLMJudge
from data.loader import load_scenario


class GameEngine:
    def __init__(self, scenario_name: str = 'crash_site', llm_client=None):
        # 加载场景
        self.world, self.materials, self.recipes = load_scenario(scenario_name)

        # 初始化子系统
        self.rules = RuleEngine(self.materials, self.recipes)
        self.events = EventSystem()

        # LLM裁判（可选）
        world_rules = self._load_world_rules()
        self.llm_client = llm_client
        if llm_client:
            self.judge = LLMJudge(llm_client, world_rules)
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

        # 扣体力（仅成功且有消耗的动作）
        if result.energy_cost > 0 and result.success:
            world.player.status.energy = max(0, world.player.status.energy - result.energy_cost)

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

        # 时间推进 + 被动事件（仅消耗时间的成功动作触发）
        time_cost = result.time_cost
        events = []
        if time_cost > 0 and result.success:
            world.action_count += 1
            events = self.events.process_time(time_cost, world)

        # 状态快照
        status_after = self._snapshot_status()

        tick_result = TickResult(
            action_count=world.action_count,
            hours_elapsed=time_cost if result.success else 0,
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
