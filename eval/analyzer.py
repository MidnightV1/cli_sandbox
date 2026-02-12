# -*- coding: utf-8 -*-
"""Session 分析器 —— 从 JSONL 提取完整评测指标"""

import json
import glob
import os
import sys
import io

# Windows 控制台强制 UTF-8
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# 科技等级映射（兜底解码失败的 tech_level）
TECH_NAMES = {0: '原始', 1: '石器', 2: '工匠', 3: '工程师', 4: '创造者'}


def calculate_risk_awareness(ticks: list[dict]) -> dict:
    """计算风险意识指标 - 口渴≥70后的动作分布（0-100范围）"""
    high_thirst_ticks = []

    for tick in ticks:
        thirst_before = tick.get('status_before', {}).get('thirst', 0)
        if thirst_before >= 70:
            high_thirst_ticks.append(tick)

    distribution = {'explore': 0, 'craft': 0, 'survival': 0}
    for tick in high_thirst_ticks:
        action_type = tick.get('action_type')
        if action_type == 'move':
            distribution['explore'] += 1
        elif action_type in ('craft', 'combine'):
            distribution['craft'] += 1
        elif action_type in ('drink', 'eat', 'rest', 'use'):
            distribution['survival'] += 1

    total = len(high_thirst_ticks)
    risk_score = distribution['survival'] / total if total > 0 else 0

    # 死亡前口渴值
    death_before_thirst = ticks[-1].get('status_before', {}).get('thirst', 0) if ticks else 0

    return {
        'high_thirst_ticks': total,
        'action_distribution': distribution,
        'risk_score': round(risk_score, 2),
        'death_before_thirst': death_before_thirst
    }


def calculate_resource_efficiency(ticks: list[dict]) -> dict:
    """计算资源利用率 - 使用的物品数 / 采集的物品数"""
    collected_items = []
    used_items = []

    for tick in ticks:
        # 采集和制作获得的物品
        gained = tick.get('items_gained', [])
        collected_items.extend(gained)

        # 消耗的物品
        consumed = tick.get('items_consumed', [])
        used_items.extend(consumed)

    total_collected = len(collected_items)
    total_used = len(used_items)

    utilization_rate = total_used / total_collected if total_collected > 0 else 0

    return {
        'items_collected': total_collected,
        'items_used': total_used,
        'utilization_rate': round(utilization_rate, 2),
        'unique_items_collected': len(set(collected_items)) if collected_items else 0,
        'unique_items_used': len(set(used_items)) if used_items else 0
    }


def detect_loop_patterns(ticks: list[dict]) -> dict:
    """检测循环模式 - A-A, A-B-A-B, A-B-C-A-B-C"""
    actions = [t.get('raw_input', '') for t in ticks if t.get('action_type')]

    if len(actions) < 2:
        return {
            'consecutive_repeats': 0,
            'loop_2_count': 0,
            'loop_3_count': 0,
            'total_loop_ticks': 0,
            'loop_rate': 0
        }

    # 1. 连续重复（A-A）
    consecutive = sum(1 for i in range(1, len(actions)) if actions[i] == actions[i-1])

    # 2. 2-动作循环（A-B-A-B）
    loop_2 = 0
    if len(actions) >= 4:
        for i in range(3, len(actions)):
            pattern = (actions[i-3], actions[i-2])
            current = (actions[i-1], actions[i])
            if pattern == current and pattern[0] != pattern[1]:
                loop_2 += 1

    # 3. 3-动作循环（A-B-C-A-B-C）
    loop_3 = 0
    if len(actions) >= 6:
        for i in range(5, len(actions)):
            pattern = (actions[i-5], actions[i-4], actions[i-3])
            current = (actions[i-2], actions[i-1], actions[i])
            if pattern == current and len(set(pattern)) == 3:
                loop_3 += 1

    total_loop_ticks = consecutive + loop_2 + loop_3
    loop_rate = total_loop_ticks / len(actions) if actions else 0

    return {
        'consecutive_repeats': consecutive,
        'loop_2_count': loop_2,
        'loop_3_count': loop_3,
        'total_loop_ticks': total_loop_ticks,
        'loop_rate': round(loop_rate, 2)
    }


def calculate_learning_curve(ticks: list[dict]) -> dict:
    """计算学习曲线 - 前10轮 vs 后10轮成功率"""
    attempt_ticks = [t for t in ticks if t.get('action_type')]

    if len(attempt_ticks) < 20:
        return {
            'early_success_rate': 0,
            'late_success_rate': 0,
            'improvement': 0,
            'is_improving': False
        }

    # 前10轮
    early_ticks = attempt_ticks[:10]
    early_success = sum(1 for t in early_ticks if t.get('success'))
    early_rate = early_success / len(early_ticks)

    # 后10轮
    late_ticks = attempt_ticks[-10:]
    late_success = sum(1 for t in late_ticks if t.get('success'))
    late_rate = late_success / len(late_ticks)

    improvement = late_rate - early_rate

    return {
        'early_success_rate': round(early_rate, 2),
        'late_success_rate': round(late_rate, 2),
        'improvement': round(improvement, 2),
        'is_improving': improvement > 0
    }


def calculate_normalized_cost_performance(all_results: list[dict]) -> list[dict]:
    """计算归一化性价比（需要所有结果作为上下文）"""
    if not all_results:
        return all_results

    # 提取各维度值
    survivals = [r['hours_survived'] for r in all_results]
    tech_points = [r['tech_points'] for r in all_results]
    inventions = [r['inventions'] for r in all_results]
    valid_rates = [r['valid_rate'] for r in all_results]

    # 标准化函数
    def normalize(value, min_val, max_val):
        if max_val == min_val:
            return 0.5
        return (value - min_val) / (max_val - min_val)

    for r in all_results:
        survival_norm = normalize(r['hours_survived'], min(survivals), max(survivals))
        tech_norm = normalize(r['tech_points'], min(tech_points), max(tech_points))
        invention_norm = normalize(r['inventions'], min(inventions), max(inventions))
        valid_norm = normalize(r['valid_rate'], min(valid_rates), max(valid_rates))

        # 加权求和
        composite_score = (
            survival_norm * 0.3 +
            tech_norm * 0.3 +
            invention_norm * 0.2 +
            valid_norm * 0.2
        )

        # 除以费用（避免除0）
        cost_cny = r['cost_cny']
        cost_performance = composite_score / cost_cny if cost_cny > 0.01 else composite_score / 0.01

        r['cost_performance_normalized'] = round(cost_performance, 1)

    return all_results


def analyze_session(filepath: str) -> dict | None:
    """分析单个 session JSONL，返回完整指标 dict（无 final_score 返回 None）"""
    ticks = []
    final = None

    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            record = json.loads(line.strip())
            if record.get('type') == 'final_score':
                final = record
            else:
                ticks.append(record)

    if not final or not ticks:
        return None

    scores = final['scores']
    meta = final['metadata']

    # ── 基础指标（已有）──
    hours_survived = scores['hours_survived']
    actions_taken = scores['actions_taken']
    valid_actions = scores['valid_actions']
    total_actions = scores['total_actions']
    invalid_rate = scores['invalid_rate']

    cost_data = scores.get('cost') or {}
    total_output_tokens = cost_data.get('total_output_tokens', 0)
    total_input_tokens = cost_data.get('total_input_tokens', 0)
    total_cost_cny = cost_data.get('total_cost_cny', 0)
    total_calls = cost_data.get('total_calls', 0)

    # ── 新指标 1: 运行耗时（wall-clock） ──
    wall_clock = ticks[-1]['timestamp'] - ticks[0]['timestamp']

    # ── 新指标 2: Token 效率 ──
    token_efficiency = (hours_survived / (total_output_tokens / 1000)
                        if total_output_tokens > 0 else 0)

    # ── 新指标 3: 尝试成功率 ──
    # 统计所有有 action_type 的 tick（排除引擎跳过的空行）
    attempt_ticks = [t for t in ticks if t.get('action_type')]
    success_count = sum(1 for t in attempt_ticks if t.get('success'))
    attempt_total = len(attempt_ticks)

    # ── 新指标 4: 创造成功率（craft + combine） ──
    craft_ticks = [t for t in ticks if t.get('action_type') in ('craft', 'combine')]
    craft_success = sum(1 for t in craft_ticks if t.get('success'))
    craft_total = len(craft_ticks)

    # ── 新指标 5: 重复动作率 ──
    consecutive_repeats = 0
    for i in range(1, len(ticks)):
        if ticks[i].get('raw_input') == ticks[i - 1].get('raw_input'):
            consecutive_repeats += 1
    repeat_rate = consecutive_repeats / len(ticks) if ticks else 0

    # ── 新指标 6: 首次制作 tick ──
    first_craft_tick = None
    for t in ticks:
        if t.get('action_type') in ('craft', 'combine') and t.get('success'):
            first_craft_tick = t['tick']
            break

    # ── 新指标 7-11: 高级指标 ──
    risk_data = calculate_risk_awareness(ticks)
    resource_data = calculate_resource_efficiency(ticks)
    loop_data = detect_loop_patterns(ticks)
    learning_data = calculate_learning_curve(ticks)

    # 完整 Token 效率（输入+输出）
    total_tokens = total_input_tokens + total_output_tokens
    full_token_efficiency = (hours_survived / (total_tokens / 1000)
                             if total_tokens > 0 else 0)

    return {
        # 元数据
        'file': os.path.basename(filepath),
        'player_type': meta.get('player_type', '?'),
        'scenario': meta.get('scenario', '?'),
        'seed': meta.get('seed'),
        'llm_enabled': meta.get('llm_enabled'),

        # 已有指标
        'days_survived': scores['days_survived'],
        'hours_survived': hours_survived,
        'actions_taken': actions_taken,
        'valid_rate': round((1 - invalid_rate) * 100),
        'exploration': scores['exploration'],
        'tech_points': scores['tech_points'],
        'tech_level': TECH_NAMES.get(scores.get('tech_level_num', 0),
                                     scores.get('tech_level', '?')),
        'inventions': scores['inventions'],
        'cost_cny': total_cost_cny,

        # 新指标
        'wall_clock_sec': round(wall_clock, 1),
        'wall_clock_min': round(wall_clock / 60, 1),
        'total_output_tokens': total_output_tokens,
        'total_input_tokens': total_input_tokens,
        'token_efficiency': round(token_efficiency, 2),
        'attempt_success': f"{success_count}/{attempt_total}",
        'attempt_success_rate': round(success_count / attempt_total * 100) if attempt_total else 0,
        'craft_success': f"{craft_success}/{craft_total}",
        'craft_success_rate': round(craft_success / craft_total * 100) if craft_total else 0,
        'repeat_rate': round(repeat_rate * 100, 1),
        'first_craft_tick': first_craft_tick,

        # 高级指标
        'risk_awareness_score': risk_data['risk_score'],
        'high_thirst_ticks': risk_data['high_thirst_ticks'],
        'death_before_thirst': risk_data['death_before_thirst'],
        'resource_utilization_rate': resource_data['utilization_rate'],
        'items_collected': resource_data['items_collected'],
        'items_used': resource_data['items_used'],
        'loop_rate': loop_data['loop_rate'],
        'loop_2_count': loop_data['loop_2_count'],
        'loop_3_count': loop_data['loop_3_count'],
        'early_success_rate': learning_data['early_success_rate'],
        'late_success_rate': learning_data['late_success_rate'],
        'is_improving': learning_data['is_improving'],
        'total_tokens': total_tokens,
        'full_token_efficiency': round(full_token_efficiency, 2),
    }


def analyze_all(session_dir: str = None, seed_filter: int = None) -> list[dict]:
    """分析目录下所有 session，返回结果列表（按存活时间降序）"""
    if session_dir is None:
        session_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'sessions'
        )

    results = []
    for filepath in glob.glob(os.path.join(session_dir, '*.jsonl')):
        r = analyze_session(filepath)
        if r is None:
            continue
        if seed_filter is not None and r['seed'] != seed_filter:
            continue
        results.append(r)

    results.sort(key=lambda x: x['hours_survived'], reverse=True)

    # 计算归一化性价比
    results = calculate_normalized_cost_performance(results)

    return results


def print_table(results: list[dict]):
    """打印结果汇总表（扩展版）"""
    if not results:
        print("没有找到有效的 session 数据。")
        return

    # 表头（添加新指标）
    header = (
        f"{'模型':<28s} {'存活':>6s} {'动作':>4s} {'有效%':>5s} "
        f"{'探索':>5s} {'科技':>10s} {'发明':>4s} {'费用':>8s} "
        f"│ {'风险':>4s} {'资源%':>5s} {'循环%':>5s} {'学习':>5s} "
        f"│ {'耗时':>6s} {'全tk':>8s} {'tk效率':>6s} {'性价比':>6s}"
    )
    sep = "─" * len(header)

    print(f"\n{sep}")
    print(header)
    print(sep)

    for r in results:
        tech = f"{r['tech_level']}({r['tech_points']}pt)"
        cost = f"¥{r['cost_cny']:.2f}"

        # 新指标显示
        risk = f"{r.get('risk_awareness_score', 0):.2f}"
        resource = f"{int(r.get('resource_utilization_rate', 0) * 100)}%"
        loop = f"{int(r.get('loop_rate', 0) * 100)}%"
        learning = "↑" if r.get('is_improving', False) else "→"

        wall = f"{r['wall_clock_min']}m"
        total_tk = r.get('total_tokens', 0)
        tk_str = f"{total_tk / 1000:.1f}K" if total_tk >= 1000 else (str(total_tk) if total_tk else '-')
        tk_eff = f"{r.get('full_token_efficiency', 0):.2f}" if r.get('full_token_efficiency', 0) > 0 else '-'
        cost_perf = f"{r.get('cost_performance_normalized', 0):.1f}"

        print(
            f"{r['player_type']:<28s} {r['hours_survived']:>5.1f}h {r['actions_taken']:>4d} "
            f"{r['valid_rate']:>4d}% {r['exploration']:>5s} {tech:>10s} "
            f"{r['inventions']:>4d} {cost:>8s} "
            f"│ {risk:>4s} {resource:>5s} {loop:>5s} {learning:>5s} "
            f"│ {wall:>6s} {tk_str:>8s} {tk_eff:>6s} {cost_perf:>6s}"
        )

    print(sep)
    print(f"共 {len(results)} 个 session\n")


def print_markdown(results: list[dict]):
    """输出 Markdown 格式表格"""
    print("\n| 模型 | Think | 存活 | 动作 | 有效率 | 探索 | 科技 | 发明 | 费用 "
          "| 耗时 | 输出Token | Token效率 | 尝试成功 | 创造成功 | 重复率 | 首制 |")
    print("|------|-------|------|------|--------|------|------|------|------"
          "|------|-----------|-----------|----------|----------|--------|------|")

    for r in results:
        # 解析 player_type 提取 thinking 标记
        pt = r['player_type']
        tech = f"{r['tech_level']}({r['tech_points']}pt)"
        cost = f"¥{r['cost_cny']:.2f}"
        wall = f"{r['wall_clock_min']}m"
        tk = r['total_output_tokens']
        out_tk = f"{tk / 1000:.1f}K" if tk >= 1000 else (str(tk) if tk else '-')
        tk_eff = f"{r['token_efficiency']:.2f}" if r['token_efficiency'] and tk >= 1000 else '-'
        first = str(r['first_craft_tick']) if r['first_craft_tick'] else '-'

        print(
            f"| {pt} | - | {r['hours_survived']}h | {r['actions_taken']} | "
            f"{r['valid_rate']}% | {r['exploration']} | {tech} | {r['inventions']} | {cost} "
            f"| {wall} | {out_tk} | {tk_eff} | {r['attempt_success']} | "
            f"{r['craft_success']} | {r['repeat_rate']}% | {first} |"
        )


if __name__ == '__main__':
    seed = None
    fmt = 'table'
    for arg in sys.argv[1:]:
        if arg.startswith('--seed='):
            seed = int(arg.split('=')[1])
        elif arg == '--md':
            fmt = 'markdown'

    results = analyze_all(seed_filter=seed)
    if fmt == 'markdown':
        print_markdown(results)
    else:
        print_table(results)
