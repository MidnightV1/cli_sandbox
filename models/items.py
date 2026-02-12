# -*- coding: utf-8 -*-
"""物品与材料系统 —— 基于属性的物品模型"""

from dataclasses import dataclass, field
from typing import Optional
import copy


@dataclass
class Item:
    """物品实例（背包中的具体物品）"""
    id: str                 # 材料/配方ID（如 "obsidian_shard"）
    name: str               # 显示名（如 "黑曜碎片"）
    description: str
    properties: list[str]   # 属性列表（如 ["坚硬", "脆性", "锋利"]）
    durability: int = -1    # -1 = 不适用（原材料）/ 无限耐久
    max_durability: int = -1
    actions: list[str] = field(default_factory=list)
    quantity: int = 1
    consumable: Optional[dict] = None  # {"type": "food"/"water"/"both", "food_value": N, "water_value": N}
    placed: bool = False    # 是否为放置物（庇护所等）

    def has_property(self, prop: str) -> bool:
        return prop in self.properties

    def has_all_properties(self, props: list[str]) -> bool:
        return all(p in self.properties for p in props)

    def use_once(self) -> bool:
        """使用一次，耐久度-1。返回是否仍可用"""
        if self.durability is None or self.durability == -1:
            return True
        self.durability -= 1
        return self.durability > 0

    def clone(self) -> 'Item':
        return copy.deepcopy(self)

    def __str__(self) -> str:
        parts = [self.name]
        if self.quantity > 1:
            parts[0] += f"(x{self.quantity})"
        if self.durability is not None and self.durability > 0:
            parts.append(f"[耐久 {self.durability}/{self.max_durability}]")
        return " ".join(parts)


def create_item_from_material(material_id: str, materials: dict, quantity: int = 1) -> Item:
    """从材料模板创建物品实例"""
    tmpl = materials[material_id]
    return Item(
        id=material_id,
        name=tmpl['name'],
        description=tmpl['description'],
        properties=list(tmpl.get('properties', [])),
        consumable=tmpl.get('consumable'),
        quantity=quantity,
    )


class Inventory:
    """背包管理"""

    def __init__(self):
        self.items: list[Item] = []

    def add(self, item: Item):
        """添加物品。原材料按ID合并数量，工具单独存放"""
        if item.durability == -1 and item.max_durability == -1:
            # 原材料，尝试合并
            for existing in self.items:
                if existing.id == item.id:
                    existing.quantity += item.quantity
                    return
        self.items.append(item)

    def remove(self, item_id: str, quantity: int = 1) -> bool:
        """移除物品。返回是否成功"""
        for i, item in enumerate(self.items):
            if item.id == item_id:
                if item.quantity > quantity:
                    item.quantity -= quantity
                    return True
                elif item.quantity == quantity:
                    self.items.pop(i)
                    return True
                else:
                    return False  # 数量不足
        return False  # 未找到

    def find(self, name_or_id: str) -> Optional[Item]:
        """模糊匹配查找物品（支持ID、全名、部分名称）"""
        # 精确匹配ID
        for item in self.items:
            if item.id == name_or_id:
                return item
        # 精确匹配名称
        for item in self.items:
            if item.name == name_or_id:
                return item
        # 子串匹配名称
        for item in self.items:
            if name_or_id in item.name or item.name in name_or_id:
                return item
        return None

    def find_all(self, name_or_id: str) -> list[Item]:
        """查找所有匹配的物品"""
        results = []
        for item in self.items:
            if item.id == name_or_id or item.name == name_or_id or name_or_id in item.name:
                results.append(item)
        return results

    def has_item(self, name_or_id: str, quantity: int = 1) -> bool:
        item = self.find(name_or_id)
        return item is not None and item.quantity >= quantity

    def list_all(self) -> list[Item]:
        return list(self.items)

    def is_empty(self) -> bool:
        return len(self.items) == 0

    def __len__(self) -> int:
        return sum(item.quantity for item in self.items)
