# -*- coding: utf-8 -*-
"""地图系统 —— 节点图"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LocationResource:
    """地点资源"""
    item_id: str
    quantity: int
    renewable: bool = False     # 是否可再生
    regen_ticks: int = 10       # 再生间隔（tick数）
    last_gathered: int = -100   # 上次采集的tick


@dataclass
class Location:
    """地图节点"""
    id: str
    name: str
    description: str
    resources: list[LocationResource] = field(default_factory=list)
    connections: dict[str, str] = field(default_factory=dict)  # 方向 -> 目标位置ID
    hazards: list[str] = field(default_factory=list)
    discovered: bool = True
    visited: bool = False
    visibility: list[str] = field(default_factory=list)  # 可远眺到的位置ID
    shelter: bool = False  # 是否有庇护（自然或人造）
    placed_items: list = field(default_factory=list)  # 放置在此处的物品

    def get_available_resources(self, current_tick: int) -> list[LocationResource]:
        """获取当前可采集的资源"""
        available = []
        for r in self.resources:
            if r.quantity > 0:
                if r.renewable and (current_tick - r.last_gathered) < r.regen_ticks:
                    continue  # 还没再生
                available.append(r)
        return available

    def gather_resource(self, item_id: str, current_tick: int) -> bool:
        """采集资源，返回是否成功"""
        for r in self.resources:
            if r.item_id == item_id and r.quantity > 0:
                r.quantity -= 1
                r.last_gathered = current_tick
                return True
        return False
