# -*- coding: utf-8 -*-
"""LLM裁判 —— 处理自由行为和新发明"""

import json
import os
from models.state import WorldState, ActionResult
from models.items import Item


class LLMJudge:
    def __init__(self, llm_client, world_rules: str, provider: str = 'anthropic', model: str = 'claude-37'):
        self.llm = llm_client
        self.world_rules = world_rules
        self.provider = provider
        self.model = model

    def evaluate_combine(self, items: list[Item], reasoning: str, world: WorldState) -> ActionResult:
        """评估自由组合"""
        items_desc = "\n".join(
            f"- {item.name}：属性=[{', '.join(item.properties)}]，{item.description}"
            for item in items
        )

        prompt = f"""## 当前情况

玩家尝试组合以下物品：
{items_desc}

玩家的推理过程：
{reasoning if reasoning else "（玩家未提供推理）"}

## 世界规则
{self.world_rules}

## 任务

判断这个组合是否在物理上合理。
如果合理，定义产出物品的属性、耐久度和可用动作。
如果不合理，解释原因。

严格按照JSON格式返回结果，不要输出任何其他内容。"""

        return self._call_judge(prompt, items, world)

    def evaluate_free_action(self, action_text: str, world: WorldState) -> ActionResult:
        """评估完全自由的行为"""
        loc = world.locations[world.player.location]
        inv_desc = "\n".join(f"- {item}" for item in world.player.inventory.list_all()) or "（空）"

        prompt = f"""## 当前情况

玩家位于：{loc.name}
环境：{loc.description}
天气：{world.weather}
背包：
{inv_desc}

玩家身体状态：
- 生命：{world.player.status.health}/{world.player.status.max_health}
- 体力：{world.player.status.energy}/{world.player.status.max_energy}

玩家尝试的行为：
{action_text}

## 世界规则
{self.world_rules}

## 任务

判断这个行为在当前环境下是否可行。
考虑玩家的身体状态、可用工具和环境条件。

严格按照JSON格式返回结果，不要输出任何其他内容。"""

        return self._call_judge(prompt, [], world)

    def _call_judge(self, prompt: str, items: list, world: WorldState) -> ActionResult:
        """调用LLM获取裁判结果"""
        judge_prompt_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'prompts', 'judge_system.md'
        )
        try:
            with open(judge_prompt_path, 'r', encoding='utf-8') as f:
                system_prompt = f.read()
        except FileNotFoundError:
            system_prompt = "你是一个物理规则裁判，判定玩家行为是否合理。返回JSON格式结果。"

        try:
            response = self.llm.call(
                system_prompt=system_prompt,
                user_prompt=prompt,
                provider=self.provider,
                model=self.model,
                temperature=0.3,
            )
            content = response.get('content', '')
            # 尝试从响应中提取JSON
            result = self._parse_judge_response(content)

            if result.get('valid'):
                # 创建新物品
                res = result.get('result', {})
                if res:
                    new_item = Item(
                        id=f"invented_{world.action_count}",
                        name=res.get('name', '未知物品'),
                        description=res.get('description', ''),
                        properties=res.get('properties', []),
                        durability=res.get('durability', 5),
                        max_durability=res.get('durability', 5),
                        actions=res.get('actions', []),
                    )
                    # 缓存为新配方
                    world.invented_recipes[f"invented_{world.action_count}"] = {
                        'name': new_item.name,
                        'source_items': [item.id for item in items],
                        'result': res,
                    }

                    # 消耗材料
                    for item in items:
                        world.player.inventory.remove(item.id, 1)

                    world.player.inventory.add(new_item)

                    # 发明奖励科技点数
                    invented_id = f"invented_{world.action_count}"
                    if invented_id not in world.crafted_recipes:
                        world.crafted_recipes.append(invented_id)
                        world.tech_points += 2

                    return ActionResult(
                        success=True,
                        message=result.get('narrative', f"你成功制作了【{new_item.name}】！") + "\n（科技 +2，发明创造）",
                        items_consumed=[item.id for item in items],
                        items_gained=[new_item],
                        energy_cost=2,
                    )
                else:
                    return ActionResult(
                        success=True,
                        message=result.get('narrative', '行为成功。'),
                        energy_cost=result.get('side_effects', {}).get('energy_mod', 1) * -1 if result.get('side_effects', {}).get('energy_mod', 0) < 0 else 1,
                    )
            else:
                return ActionResult(
                    success=False,
                    message=result.get('narrative', '这样做行不通。') + f"\n（{result.get('reasoning', '')}）",
                    energy_cost=1,
                )

        except Exception as e:
            return ActionResult(
                success=False,
                message=f"[裁判系统异常：{str(e)}] 这个行为暂时无法判定，请尝试其他方式。",
                energy_cost=0,
            )

    def _parse_judge_response(self, content: str) -> dict:
        """从LLM响应中提取JSON"""
        # 尝试直接解析
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # 尝试提取代码块中的JSON
        import re
        json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试找到第一个 { 到最后一个 }
        start = content.find('{')
        end = content.rfind('}')
        if start != -1 and end != -1:
            try:
                return json.loads(content[start:end + 1])
            except json.JSONDecodeError:
                pass

        return {'valid': False, 'reasoning': 'LLM返回格式无法解析', 'narrative': '裁判系统无法理解这个行为。'}
