# -*- coding: utf-8 -*-
"""随机基准 Agent —— 不调用 LLM，用于建立 benchmark 零点基线

两种模式：
  random  : 从当前所有合法动作中均匀随机选择（纯随机）
  reactive: 仅在危机阈值时做必要的生存响应，其余随机（最小规则基线）
"""

import random as _random


class RandomPlayer:
    """与 AIPlayer 同接口的随机 Agent，main.py 可直接替换使用"""

    def __init__(self, materials_db=None, recipes_db=None, mode='random'):
        self.materials = materials_db or {}
        self.recipes = recipes_db or {}
        self.mode = mode          # 'random' | 'reactive'
        self.action_history = []  # 保持接口兼容，不使用
        self.last_raw_response = ''
        self.last_thinking = ''
        self._world = None        # build_state_text() 时存储引用

    # ── 接口方法（与 AIPlayer 保持一致）──

    def build_state_text(self, world, last_tick=None) -> str:
        """存储 world 引用供 decide() 使用，返回空串（不需要文本）"""
        self._world = world
        return ''

    def decide(self, game_state_text: str) -> str:
        """返回下一步动作字符串"""
        w = self._world
        if w is None:
            return 'rest'
        cmd = self._reactive_decide(w) if self.mode == 'reactive' else self._random_decide(w)
        self.last_raw_response = cmd
        self.last_thinking = ''
        return cmd

    def provide_reasoning(self, items: list, game_state_text: str) -> str:
        """combine 推理：随机 agent 给出固定占位理由"""
        return '随机尝试组合这些材料，期待产生有用的工具。'

    def record_action(self, command, world, result_msg='', success=True, events=None):
        """随机 agent 不维护历史，接口兼容留空"""
        pass

    # ── 内部决策逻辑 ──

    def _available_actions(self, world) -> list[str]:
        """枚举当前状态下所有可执行的有意义动作"""
        actions = ['look', 'rest']
        loc = world.locations[world.player.location]
        items = world.player.inventory.list_all()

        # 移动：每个已知出口方向
        for direction in loc.connections:
            actions.append(f'move {direction}')

        # 采集：当前位置有资源
        for r in loc.get_available_resources(world.action_count):
            mat = self.materials.get(r.item_id, {})
            name = mat.get('name', r.item_id)
            actions.append(f'gather {name}')

        # 吃/喝：背包中有可消耗物
        for item in items:
            if item.consumable:
                ctype = item.consumable.get('type', '')
                if ctype in ('food', 'both'):
                    actions.append(f'eat {item.name}')
                if ctype in ('water', 'both'):
                    actions.append(f'drink {item.name}')

        # 制作：已知配方
        for rid in world.player.known_recipes:
            recipe = self.recipes.get(rid, {})
            if recipe:
                actions.append(f'craft {recipe.get("name", rid)}')

        return actions

    def _random_decide(self, world) -> str:
        """从所有合法动作中均匀随机选一个"""
        return _random.choice(self._available_actions(world))

    def _reactive_decide(self, world) -> str:
        """规则反应式：危机优先处理，其余随机采集/移动"""
        s = world.player.status
        items = world.player.inventory.list_all()

        # 优先级 1：极度口渴 (thirst > 70)
        if s.thirst > 70:
            for item in items:
                if item.consumable and item.consumable.get('type') in ('water', 'both'):
                    return f'drink {item.name}'

        # 优先级 2：极度饥饿 (hunger > 70)
        if s.hunger > 70:
            for item in items:
                if item.consumable and item.consumable.get('type') in ('food', 'both'):
                    return f'eat {item.name}'

        # 优先级 3：体力耗尽 (energy < 20)
        if s.energy < 20:
            return 'rest'

        # 其余：随机从基础动作中选（look / gather / move / rest）
        loc = world.locations[world.player.location]
        actions = ['look', 'rest']
        for r in loc.get_available_resources(world.action_count):
            mat = self.materials.get(r.item_id, {})
            name = mat.get('name', r.item_id)
            actions.append(f'gather {name}')
        for direction in loc.connections:
            actions.append(f'move {direction}')
        return _random.choice(actions)
