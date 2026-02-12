# -*- coding: utf-8 -*-
"""游戏状态模型"""

from dataclasses import dataclass, field
from typing import Optional
from .items import Inventory


# ═══ 时间描述系统 ═══
# 玩家不会看到这些阈值，只看到对应的文字描述
# 时间阶段按日长百分比划分
PHASE_BOUNDARIES = [
    (0.00, 0.10, "黎明"),
    (0.10, 0.55, "白天"),
    (0.55, 0.70, "黄昏"),
    (0.70, 1.00, "夜晚"),
]

# 更细粒度的环境描述（玩家看到的）
TIME_DESCRIPTIONS = [
    (0.00, 0.05, "天边刚刚泛起一丝微光，空气冰凉。"),
    (0.05, 0.10, "天色逐渐亮起来，远处的轮廓变得清晰。"),
    (0.10, 0.25, "光线明亮，视野开阔。"),
    (0.25, 0.45, "头顶的光照强烈而炽热。"),
    (0.45, 0.55, "光线开始变得柔和，阴影拉长。"),
    (0.55, 0.65, "暮色渐浓，天边染上一层橘红。"),
    (0.65, 0.70, "最后一缕光线正在消散。"),
    (0.70, 0.85, "天色已完全暗下来。"),
    (0.85, 0.95, "深夜，周围一片寂静。"),
    (0.95, 1.00, "黑暗中似乎能感觉到一丝将至的变化。"),
]

# ═══ 科技等级系统 ═══
# (最低科技点, 等级名称)
TECH_LEVELS = [
    (0, "原始"),      # 刚坠落，没有任何工具
    (2, "石器"),      # 制作了基础切割/绳索
    (6, "工匠"),      # 掌握中级工具
    (12, "工程师"),   # 能建造庇护所和复杂装置
    (20, "创造者"),   # 大量发明创造
]

# 动作时间消耗（小时）
ACTION_TIME_COSTS = {
    'move': 1.0,
    'gather': 0.5,
    'craft': 2.0,
    'combine': 2.0,
    'use': 1.0,
    'eat': 0.5,
    'drink': 0.5,
    'rest': 3.0,
    'free_action': 1.0,
    # 零消耗
    'look': 0.0,
    'inventory': 0.0,
    'help': 0.0,
    'recipes': 0.0,
    'note': 0.0,
}


@dataclass
class PlayerStatus:
    """玩家身体状态（0-100 范围，提升颗粒度）"""
    health: int = 100       # 0=死亡
    max_health: int = 100
    hunger: int = 0         # 越高越饿，>=80开始掉血
    max_hunger: int = 100
    thirst: int = 0         # 越高越渴，>=80开始掉血（更快）
    max_thirst: int = 100
    warmth: int = 70        # 越低越冷，<=20开始掉血
    max_warmth: int = 100
    energy: int = 80        # 0=无法执行体力动作（但可疲劳行动）
    max_energy: int = 100
    # 内部累积器（保持状态值为整数，但时间推进用浮点）
    _hunger_acc: float = 0.0
    _thirst_acc: float = 0.0

    def is_alive(self) -> bool:
        return self.health > 0

    def clamp_all(self):
        """把所有数值限制在有效范围内"""
        self.health = max(0, min(self.health, self.max_health))
        self.hunger = max(0, min(self.hunger, self.max_hunger))
        self.thirst = max(0, min(self.thirst, self.max_thirst))
        self.warmth = max(0, min(self.warmth, self.max_warmth))
        self.energy = max(0, min(self.energy, self.max_energy))


@dataclass
class Goal:
    """任务目标"""
    id: str
    description: str
    goal_type: str = "primary"  # primary / secondary / survival
    completed: bool = False
    condition: str = ""  # 条件描述，用于判定


@dataclass
class PlayerState:
    """玩家完整状态"""
    location: str  # 当前位置ID
    inventory: Inventory = field(default_factory=Inventory)
    status: PlayerStatus = field(default_factory=PlayerStatus)
    known_recipes: list[str] = field(default_factory=list)
    discovered_locations: set[str] = field(default_factory=set)
    # 小本本（记事本）
    notebook: list[str] = field(default_factory=list)
    notebook_capacity: int = 8  # 最多8条笔记


@dataclass
class WorldState:
    """世界完整状态"""
    player: PlayerState
    locations: dict = field(default_factory=dict)  # location_id -> Location
    # 时间系统
    total_hours: float = 0.0        # 累计经过的小时数
    day_length: int = 25            # 一天多少小时（20-30随机，对玩家隐藏）
    max_days: int = 0               # 无硬性上限（由检查点控制）
    action_count: int = 0           # 动作计数器
    # 检查点系统
    checkpoint_interval: int = 100  # 每N天触发一次检查点
    checkpoints_passed: int = 0     # 已通过的检查点数
    checkpoint_reached: bool = False  # 是否刚触发检查点（由事件系统设置）
    # 科技系统
    tech_points: int = 0            # 科技积分
    crafted_recipes: list[str] = field(default_factory=list)  # 已制作过的配方ID
    # 环境
    weather: str = "晴朗"
    _prev_phase: str = ""           # 上一次的时间阶段（用于检测阶段切换）
    # 游戏状态
    goals: list[Goal] = field(default_factory=list)
    game_over: bool = False
    game_over_reason: str = ""
    scenario_name: str = ""
    invented_recipes: dict = field(default_factory=dict)

    @property
    def current_day(self) -> int:
        """当前是第几天"""
        return int(self.total_hours // self.day_length) + 1

    @property
    def current_day_hour(self) -> float:
        """当天已过去的小时数"""
        return self.total_hours % self.day_length

    @property
    def day_progress(self) -> float:
        """当天进度 0.0 - 1.0"""
        return self.current_day_hour / self.day_length

    @property
    def time_phase(self) -> str:
        """当前时间阶段（内部用，不直接展示给玩家）"""
        p = self.day_progress
        for start, end, name in PHASE_BOUNDARIES:
            if start <= p < end:
                return name
        return "夜晚"

    @property
    def is_night(self) -> bool:
        return self.time_phase == "夜晚"

    @property
    def time_description(self) -> str:
        """玩家能看到的时间环境描述"""
        p = self.day_progress
        for start, end, desc in TIME_DESCRIPTIONS:
            if start <= p < end:
                return desc
        return "天色已完全暗下来。"

    @property
    def max_hours(self) -> float:
        if self.max_days > 0:
            return self.max_days * self.day_length
        return float('inf')

    @property
    def next_checkpoint_day(self) -> int:
        """下一个检查点的天数"""
        return (self.checkpoints_passed + 1) * self.checkpoint_interval

    @property
    def tech_level(self) -> tuple[int, str]:
        """当前科技等级 → (等级序号, 等级名称)"""
        level_num = 0
        level_name = "原始"
        for i, (threshold, name) in enumerate(TECH_LEVELS):
            if self.tech_points >= threshold:
                level_num = i
                level_name = name
        return level_num, level_name


@dataclass
class ActionResult:
    """动作执行结果"""
    success: bool
    message: str
    items_consumed: list[str] = field(default_factory=list)
    items_gained: list = field(default_factory=list)  # list[Item]
    energy_cost: int = 1
    time_cost: float = 0.0  # 小时
    needs_llm: bool = False
    extra: dict = field(default_factory=dict)


@dataclass
class TickResult:
    """一个动作回合的完整结果"""
    action_count: int
    hours_elapsed: float    # 本次动作耗时
    action_result: ActionResult
    events: list[str] = field(default_factory=list)
    status_before: dict = field(default_factory=dict)
    status_after: dict = field(default_factory=dict)
    game_over: bool = False
    game_over_reason: str = ""
