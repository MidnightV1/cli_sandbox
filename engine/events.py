# -*- coding: utf-8 -*-
"""事件系统 —— 基于小时的状态衰减与环境事件"""

import random
from models.state import WorldState, PHASE_BOUNDARIES


# 每小时状态衰减率（0-100 范围）
HUNGER_RATE = 3.5    # 约28小时从0到100（需要每天吃2-3次）
THIRST_RATE = 4.5    # 约22小时从0到100（比饥饿更紧急）


class EventSystem:

    def process_time(self, hours: float, world: WorldState) -> list[str]:
        """
        推进时间，处理状态衰减和环境事件。
        hours: 本次动作消耗的小时数
        返回事件描述列表
        """
        if hours <= 0:
            return []

        events = []
        player = world.player
        status = player.status
        loc = world.locations[player.location]

        # 记录旧阶段
        old_phase = world.time_phase

        # 1. 推进时间
        world.total_hours += hours

        # 2. 检测时间阶段切换
        new_phase = world.time_phase
        if new_phase != old_phase:
            events.append(self._describe_phase_change(old_phase, new_phase))
            # 阶段切换时可能变天
            new_weather = self._roll_weather(world)
            if new_weather != world.weather:
                world.weather = new_weather
                events.append(f"天气变化：{world.weather}。")
            world._prev_phase = new_phase

        # 3. 饥饿和口渴累积
        status._hunger_acc += hours * HUNGER_RATE
        while status._hunger_acc >= 1.0:
            status.hunger += 1
            status._hunger_acc -= 1.0

        status._thirst_acc += hours * THIRST_RATE
        while status._thirst_acc >= 1.0:
            status.thirst += 1
            status._thirst_acc -= 1.0

        # 4. 体温：基于环境、时段、天气
        warmth_change = self._calc_warmth_change(hours, world, loc)
        if warmth_change != 0:
            status.warmth += warmth_change

        # 5. 天气直接伤害（酸雨等，0-100 范围）
        weather_effects = self._get_weather_effects(world)
        if weather_effects:
            h_mod = weather_effects.get('health_mod', 0)
            exposed_only = weather_effects.get('exposed_only', False)
            if h_mod and (not exposed_only or not self._has_shelter(loc)):
                # 按小时比例计算伤害（health_mod 已是 0-100 范围的值）
                damage = int(h_mod * hours * 10)  # ×10 适配新范围
                if damage != 0:
                    status.health += damage
                    events.append(f"{world.weather}持续侵蚀你的身体（生命{damage:+d}）")

        # 6. 预警信号（65-80 区间，仅提示不扣血，每天最多一次）
        _warned = getattr(world, '_thirst_warned_day', -1)
        if 65 <= status.thirst < 80 and _warned != world.current_day:
            events.append("你感到有些口干。")
            world._thirst_warned_day = world.current_day

        # 7. 状态恶化（0-100 范围，移除最小伤害限制）
        if status.hunger >= 80:
            dmg = int(hours * 5)  # 5点/小时
            if dmg > 0:
                status.health -= dmg
                events.append(f"饥饿折磨着你（生命-{dmg}）")
        if status.thirst >= 80:
            dmg = int(hours * 8)  # 8点/小时（更快）
            if dmg > 0:
                status.health -= dmg
                events.append(f"严重脱水！（生命-{dmg}）")
        if status.warmth <= 20:
            dmg = int(hours * 5)  # 5点/小时
            if dmg > 0:
                status.health -= dmg
                events.append(f"寒冷刺骨（生命-{dmg}）")

        # 7. 限制数值
        status.clamp_all()

        # 8. 死亡检查
        if not status.is_alive():
            world.game_over = True
            if status.thirst >= status.max_thirst:
                world.game_over_reason = "你因脱水而死。"
            elif status.hunger >= status.max_hunger:
                world.game_over_reason = "你因饥饿而死。"
            elif status.warmth <= 0:
                world.game_over_reason = "你因失温而死。"
            else:
                world.game_over_reason = "你的身体再也撑不住了。"
            events.append(world.game_over_reason)

        # 9. 检查点检测（每N天触发一次）
        next_cp = world.next_checkpoint_day
        if world.current_day >= next_cp and not world.checkpoint_reached and not world.game_over:
            world.checkpoint_reached = True
            # 第一个检查点同时完成生存目标
            if world.checkpoints_passed == 0:
                for g in world.goals:
                    if g.id == 'survive' and not g.completed:
                        g.completed = True
                        events.append(f"你在这颗星球上存活了{next_cp}天！（生存目标完成）")
            events.append(f"── 第{world.checkpoints_passed + 1}阶段检查点（第{next_cp}天）──")

        return events

    def _describe_phase_change(self, old: str, new: str) -> str:
        """描述时间阶段变化（不直接说阶段名，而是用感受描述）"""
        transitions = {
            ("夜晚", "黎明"): "天际出现了微弱的光——新的一天开始了。",
            ("黎明", "白天"): "光线变得明亮起来，温度也开始回升。",
            ("白天", "黄昏"): "你注意到光线开始变暗，气温似乎也在下降。",
            ("黄昏", "夜晚"): "黑暗吞噬了最后的光线，夜晚降临了。",
        }
        return transitions.get((old, new), f"周围的光线发生了变化。")

    def _calc_warmth_change(self, hours: float, world: WorldState, loc) -> int:
        """计算体温变化（0-100 范围）"""
        rate = 0.0  # 每小时变化

        # 基础：户外缓慢降温
        if self._has_shelter(loc):
            rate += 1.5  # 庇护所缓慢回温
        else:
            rate -= 1.5  # 户外缓慢降温

        # 夜晚额外降温
        if world.is_night:
            rate -= 3.0

        # 天气影响
        weather_effects = self._get_weather_effects(world)
        if weather_effects:
            w_mod = weather_effects.get('warmth_mod', 0)
            exposed_only = weather_effects.get('exposed_only', False)
            if w_mod and (not exposed_only or not self._has_shelter(loc)):
                rate += w_mod * 3.0  # 天气效果每小时

        # 计算整数变化
        total = rate * hours
        if abs(total) >= 0.5:
            return round(total)
        return 0

    def _has_shelter(self, loc) -> bool:
        """检查位置是否有庇护"""
        if loc.shelter:
            return True
        for item in loc.placed_items:
            if hasattr(item, 'properties') and '庇护' in item.properties:
                return True
        return False

    def _roll_weather(self, world: WorldState) -> str:
        """加权随机天气"""
        pool = getattr(world, '_weather_pool', [{'type': '晴朗', 'weight': 1}])
        types = [w['type'] for w in pool]
        weights = [w.get('weight', 1) for w in pool]
        return random.choices(types, weights=weights, k=1)[0]

    def _get_weather_effects(self, world: WorldState) -> dict:
        pool = getattr(world, '_weather_pool', [])
        for w in pool:
            if w['type'] == world.weather:
                return w.get('effects', {})
        return {}
