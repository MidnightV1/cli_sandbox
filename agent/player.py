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
        self.max_history = 100

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

        # ★ 背包（放在位置信息之后、已知配方之前，提升优先级）
        lines.append("\n★ ── 你的背包 ── ★")
        items = world.player.inventory.list_all()
        if items:
            lines.append(f"【当前携带 {len(items)} 种物品】")
            for item in items:
                props_str = ','.join(item.properties)
                qty_str = f"(x{item.quantity})" if item.quantity > 1 else ""
                dur_str = f" 耐久{item.durability}/{item.max_durability}" if item.durability is not None and item.durability > 0 else ""
                act_str = f" 可：{'、'.join(item.actions)}" if item.actions else ""
                lines.append(f"  ✓ {item.name}{qty_str} [{props_str}]{dur_str}{act_str}")
        else:
            lines.append("【背包空空如也】")

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

        # 小本本（笔记本）
        if hasattr(world.player, 'notebook') and world.player.notebook:
            lines.append("\n📔 ── 你的小本本 ── 📔")
            lines.append(f"【剩余空间：{world.player.notebook_capacity - len(world.player.notebook)}/{world.player.notebook_capacity}条】")
            for note in world.player.notebook:
                lines.append(f"  · {note}")

        return "\n".join(lines)

    # ── 决策 ──

    def decide(self, game_state_text: str) -> str:
        """给定当前状态文本，返回一行指令"""
        user_prompt = game_state_text

        if self.action_history:
            history_text = "\n".join(self.action_history[-self.max_history:])
            user_prompt += f"\n\n── 近3天行动记录 ──\n{history_text}"

        user_prompt += "\n\n请输出你的下一步指令（仅输出一行指令，不要解释）："

        result = self.llm.call(
            system_prompt=self.system_prompt,
            user_prompt=user_prompt,
            provider=self.provider,
            model=self.model,
            temperature=0.5,
            thinking=self.thinking,
        )

        # 保存原始输出和思考过程用于记录
        self.last_raw_response = result['content']
        self.last_thinking = result.get('thinking', '')
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

    def record_action(self, command: str, world, result_msg: str = "",
                       success: bool = True, events: list[str] = None):
        """记录一次行动 + 当时状态快照 + 结果摘要 + 事件（维持上下文窗口）"""
        s = world.player.status
        loc_name = world.locations[world.player.location].name
        phase = world.time_phase
        mark = "✓" if success else "✗"
        day = world.current_day
        h = world.total_hours
        # 结果摘要：截断到150字符，去掉换行
        summary = result_msg.replace('\n', ' ').strip()[:150] if result_msg else ""
        entry = (
            f"第{day}天 {h:.1f}h {mark}[{command}] "
            f"生命{s.health} 饥饿{s.hunger} 口渴{s.thirst} 体温{s.warmth} 体力{s.energy} "
            f"@{loc_name} {world.weather} {phase}"
        )
        if summary:
            entry += f" → {summary}"
        if events:
            entry += f" | {'；'.join(events)}"
        self.action_history.append(entry)

    # ── 响应解析 ──

    def _extract_command(self, raw_response: str) -> str:
        """从LLM响应中提取指令（严格要求XML格式，不允许任何额外文本）"""
        import re

        text = raw_response.strip()

        # 移除markdown代码块包裹（某些模型会用```xml...```包裹输出）
        text = re.sub(r'^```(?:xml)?\s*\n', '', text, flags=re.MULTILINE)
        text = re.sub(r'\n```\s*$', '', text, flags=re.MULTILINE)
        text = text.strip()

        # 严格模式：只允许 XML 标签，不允许任何额外文本
        # 合法格式：<action>...</action> 或 <action>...</action><detail>...</detail>
        # 非法格式：任何 XML 标签外的文本都会导致解析失败

        # 移除所有 XML 标签后，剩余内容必须为空或只有空白字符
        text_without_xml = re.sub(r'</?(?:action|detail|reason)>.*?</(?:action|detail|reason)>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text_without_xml = re.sub(r'<(?:action|detail|reason)>.*?</(?:action|detail|reason)>', '', text, flags=re.DOTALL | re.IGNORECASE)

        # 检查是否有额外内容（允许空白字符和换行）
        extra_content = text_without_xml.strip()
        if extra_content:
            # 有额外文本，严格拒绝
            return ""

        # 解析 XML 格式 <action>...</action><detail>...</detail>
        try:
            action_match = re.search(r'<action>(.+?)</action>', text, re.DOTALL | re.IGNORECASE)
            detail_match = re.search(r'<detail>(.+?)</detail>', text, re.DOTALL | re.IGNORECASE)

            if action_match:
                action = action_match.group(1).strip()
                detail = detail_match.group(1).strip() if detail_match else ''

                # 验证 action 不为空（避免空标签）
                if not action:
                    return ""

                # 拼接完整命令
                if detail:
                    return f"{action} {detail}"
                else:
                    return action
        except Exception:
            pass

        # XML 解析失败，返回空字符串（触发格式错误）
        return ""
