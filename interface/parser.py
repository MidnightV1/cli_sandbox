# -*- coding: utf-8 -*-
"""动作解析器 —— 支持中英文指令"""

import re


# 中文指令映射
CN_COMMANDS = {
    '移动': 'move', '去': 'move', '走': 'move',
    '观察': 'look', '看': 'look', '查看': 'look', '检查': 'look',
    '采集': 'gather', '捡': 'gather', '拾取': 'gather', '收集': 'gather',
    '使用': 'use', '用': 'use',
    '制作': 'craft', '制造': 'craft', '打造': 'craft',
    '组合': 'combine', '合成': 'combine',
    '吃': 'eat', '食用': 'eat',
    '喝': 'drink', '饮用': 'drink',
    '休息': 'rest', '睡': 'rest',
    '背包': 'inventory', '物品': 'inventory',
    '帮助': 'help',
    '配方': 'recipes', '已知配方': 'recipes',
    '尝试': 'free_action', '试试': 'free_action',
    '记录': 'note', '小本本': 'note', '笔记': 'note', '记': 'note',
}


def parse_action(raw: str) -> tuple[str, dict]:
    """
    解析玩家输入，返回 (action_type, args_dict)
    args_dict 可能包含：target, tool, items, reasoning, action_type
    """
    raw = raw.strip()
    if not raw:
        return 'empty', {}

    # 分词：第一个词是指令，剩余是参数
    parts = raw.split(maxsplit=1)
    cmd = parts[0].lower()
    rest = parts[1] if len(parts) > 1 else ''

    # 映射中文指令
    action_type = CN_COMMANDS.get(cmd, cmd)

    # ── move ──
    if action_type == 'move':
        return 'move', {'target': rest}

    # ── look ──
    if action_type == 'look':
        return 'look', {'target': rest if rest else None}

    # ── gather ──
    if action_type == 'gather':
        return 'gather', {'target': rest}

    # ── use <tool> on <target> ──
    if action_type == 'use':
        # 支持 "use X on Y" 和 "用 X 对 Y"
        m = re.match(r'(.+?)\s+(?:on|对|作用于)\s+(.+)', rest, re.IGNORECASE)
        if m:
            return 'use', {'tool': m.group(1).strip(), 'target': m.group(2).strip()}
        # 如果没有on，整个rest当tool（target留空）
        return 'use', {'tool': rest, 'target': ''}

    # ── craft ──
    if action_type == 'craft':
        return 'craft', {'target': rest}

    # ── combine ──
    if action_type == 'combine':
        # 支持多种分隔：逗号、"和"、"与"、空格
        # 检查是否附带了推理（引号包裹的部分）
        reasoning = ''
        reasoning_match = re.search(r'["\u201c](.+?)["\u201d]', rest)
        if reasoning_match:
            reasoning = reasoning_match.group(1)
            rest = rest[:reasoning_match.start()].strip()

        items = re.split(r'\s*[,，]\s*|\s+(?:和|与|and)\s+|\s+', rest)
        items = [i.strip() for i in items if i.strip()]
        return 'combine', {'items': items, 'reasoning': reasoning}

    # ── eat / drink ──
    if action_type in ('eat', 'drink'):
        return action_type, {'target': rest, 'action_type': action_type}

    # ── rest ──
    if action_type == 'rest':
        return 'rest', {}

    # ── inventory ──
    if action_type == 'inventory':
        return 'inventory', {}

    # ── help ──
    if action_type == 'help':
        return 'help', {}

    # ── recipes ──
    if action_type == 'recipes':
        return 'recipes', {}

    # ── note (小本本) ──
    if action_type == 'note':
        return 'note', {'content': rest}

    # ── free_action (try) ──
    if action_type == 'free_action':
        # 去掉可能的引号
        target = rest.strip('""\u201c\u201d')
        return 'free_action', {'target': target}

    # ── 直接输入中文的容错处理 ──
    # 如果第一个字就是方位词，当作移动
    directions = ['北', '南', '东', '西', '上', '下', '深处', '外面', '东北', '西南']
    if cmd in directions or raw in directions:
        return 'move', {'target': raw}

    # 未识别
    return 'unknown', {'raw': raw}
