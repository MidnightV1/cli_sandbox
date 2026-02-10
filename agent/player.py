# -*- coding: utf-8 -*-
"""AI Agent 自动玩家 —— 接收游戏状态文本，输出指令"""

import os


class AIPlayer:
    """AI agent that plays the game autonomously"""

    def __init__(self, llm_client, provider: str, model: str,
                 thinking: bool = False, materials_db: dict = None, recipes_db: dict = None):
        self.llm = llm_client
        self.provider = provider
        self.model = model
        self.thinking = thinking
        self.materials = materials_db or {}
        self.recipes = recipes_db or {}
        self.system_prompt = self._load_system_prompt()
        self.action_history: list[str] = []
        self.max_history = 20

    def _load_system_prompt(self) -> str:
        prompt_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'prompts', 'agent_system.md'
        )
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read()

    # ── 状态文本构建 ──

    def build_state_text(self, world, last_tick=None) -> str:
        """将当前游戏状态序列化为文本，供LLM决策"""
        lines = []

        # 状态头
        day = world.current_day
        _, tech_name = world.tech_level
        s = world.player.status
        lines.append("── 状态 ──")
        lines.append(f"第{day}天 | {world.weather} | 科技：{tech_name}（{world.tech_points}点）")
        lines.append(world.time_description)
        lines.append(
            f"生命 {s.health}/{s.max_health} | 饥饿 {s.hunger}/{s.max_hunger} | "
            f"口渴 {s.thirst}/{s.max_thirst} | 体温 {s.warmth}/{s.max_warmth} | "
            f"体力 {s.energy}/{s.max_energy}"
        )

        # 当前位置
        loc = world.locations[world.player.location]
        lines.append(f"\n── 位置：{loc.name} ──")
        lines.append(loc.description.strip())

        # 可采集资源（带属性）
        available = loc.get_available_resources(world.action_count)
        if available:
            res_strs = []
            for r in available:
                mat = self.materials.get(r.item_id, {})
                name = mat.get('name', r.item_id)
                props = mat.get('properties', [])
                res_strs.append(f"{name}(x{r.quantity})[{','.join(props)}]")
            lines.append(f"可采集：{'；'.join(res_strs)}")

        # 危险
        if loc.hazards:
            lines.append(f"危险：{'、'.join(loc.hazards)}")

        # 庇护
        if loc.shelter:
            lines.append("此处有遮蔽，可避天气。")

        # 出口
        if loc.connections:
            exits = []
            for direction, target_id in loc.connections.items():
                target = world.locations.get(target_id)
                if target and target.discovered:
                    exits.append(f"{direction}→{target.name}")
                else:
                    exits.append(f"{direction}→未知")
            lines.append(f"出口：{'，'.join(exits)}")

        # 背包
        lines.append("\n── 背包 ──")
        items = world.player.inventory.list_all()
        if items:
            for item in items:
                props_str = ','.join(item.properties)
                qty_str = f"(x{item.quantity})" if item.quantity > 1 else ""
                dur_str = f" 耐久{item.durability}/{item.max_durability}" if item.durability > 0 else ""
                act_str = f" 可：{'、'.join(item.actions)}" if item.actions else ""
                lines.append(f"  {item.name}{qty_str} [{props_str}]{dur_str}{act_str}")
        else:
            lines.append("  （空）")

        # 已知配方
        if world.player.known_recipes:
            lines.append("\n── 已知配方 ──")
            for rid in world.player.known_recipes:
                recipe = self.recipes.get(rid, {})
                if recipe:
                    name = recipe.get('name', rid)
                    slots = recipe.get('slots', {})
                    slot_parts = []
                    for slot_def in slots.values():
                        reqs = slot_def.get('requires', [])
                        desc = slot_def.get('description', '')
                        slot_parts.append(f"{desc}[{','.join(reqs)}]")
                    lines.append(f"  {name}：{' + '.join(slot_parts)}")

        # 目标
        lines.append("\n── 目标 ──")
        for g in world.goals:
            mark = "✓" if g.completed else "○"
            lines.append(f"  {mark} {g.description}")

        # 上轮结果
        if last_tick:
            lines.append("\n── 上轮结果 ──")
            lines.append(last_tick.action_result.message)
            for event in last_tick.events:
                lines.append(f"  >> {event}")

        return "\n".join(lines)

    # ── 决策 ──

    def decide(self, game_state_text: str) -> str:
        """给定当前状态文本，返回一行指令"""
        user_prompt = game_state_text

        if self.action_history:
            history_text = "\n".join(self.action_history[-self.max_history:])
            user_prompt += f"\n\n── 近期行动记录 ──\n{history_text}"

        user_prompt += "\n\n请输出你的下一步指令（仅输出一行指令，不要解释）："

        result = self.llm.call(
            system_prompt=self.system_prompt,
            user_prompt=user_prompt,
            provider=self.provider,
            model=self.model,
            temperature=0.5,
            thinking=self.thinking,
        )

        command = self._extract_command(result['content'])
        return command

    def provide_reasoning(self, items: list[str], game_state_text: str) -> str:
        """为未知配方的组合提供推理"""
        items_str = "、".join(items)
        user_prompt = (
            f"{game_state_text}\n\n"
            f"你尝试组合：{items_str}\n"
            f"这不是已知配方。请描述你想用这些材料做什么，为什么物理上可行（1-2句话，不要输出指令）："
        )

        result = self.llm.call(
            system_prompt=self.system_prompt,
            user_prompt=user_prompt,
            provider=self.provider,
            model=self.model,
            temperature=0.5,
            thinking=self.thinking,
        )
        return result['content'].strip()

    def record_action(self, command: str, result_summary: str):
        """记录一次行动（维持上下文窗口）"""
        self.action_history.append(f"[{command}] → {result_summary}")

    # ── 响应解析 ──

    def _extract_command(self, raw_response: str) -> str:
        """从LLM响应中提取单行指令"""
        text = raw_response.strip()
        lines = [l.strip() for l in text.split('\n') if l.strip()]

        if not lines:
            return "观察"

        if len(lines) == 1:
            return lines[0]

        # 优先找以游戏指令开头的行
        command_prefixes = [
            '移动', '去', '走', '观察', '看', '查看', '检查',
            '采集', '捡', '收集', '使用', '用', '制作', '制造',
            '组合', '合成', '吃', '食用', '喝', '饮用', '休息', '睡',
            '背包', '物品', '帮助', '配方', '尝试', '试试',
            'move', 'look', 'gather', 'use', 'craft', 'combine',
            'eat', 'drink', 'rest', 'inventory', 'help', 'recipes',
        ]

        for line in lines:
            for prefix in command_prefixes:
                if line.startswith(prefix):
                    return line

        # 兜底：最后一行
        return lines[-1]
