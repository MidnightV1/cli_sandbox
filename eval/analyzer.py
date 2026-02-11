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
    return results


def print_table(results: list[dict]):
    """打印结果汇总表"""
    if not results:
        print("没有找到有效的 session 数据。")
        return

    # 表头
    header = (
        f"{'模型':<28s} {'存活':>6s} {'动作':>4s} {'有效%':>5s} "
        f"{'探索':>5s} {'科技':>10s} {'发明':>4s} {'费用':>8s} "
        f"│ {'耗时':>6s} {'输出tk':>8s} {'tk效率':>6s} "
        f"{'尝试':>7s} {'创造':>5s} {'重复%':>5s} {'首制':>4s}"
    )
    sep = "─" * len(header)

    print(f"\n{sep}")
    print(header)
    print(sep)

    for r in results:
        tech = f"{r['tech_level']}({r['tech_points']}pt)"
        cost = f"¥{r['cost_cny']:.2f}"
        wall = f"{r['wall_clock_min']}m"
        tk = r['total_output_tokens']
        out_tk = f"{tk / 1000:.1f}K" if tk >= 1000 else (str(tk) if tk else '-')
        tk_eff = f"{r['token_efficiency']:.2f}" if r['token_efficiency'] and tk >= 1000 else '-'
        first = str(r['first_craft_tick']) if r['first_craft_tick'] else '-'

        print(
            f"{r['player_type']:<28s} {r['hours_survived']:>5.1f}h {r['actions_taken']:>4d} "
            f"{r['valid_rate']:>4d}% {r['exploration']:>5s} {tech:>10s} "
            f"{r['inventions']:>4d} {cost:>8s} "
            f"│ {wall:>6s} {out_tk:>8s} {tk_eff:>6s} "
            f"{r['attempt_success']:>7s} {r['craft_success']:>5s} "
            f"{r['repeat_rate']:>4.1f}% {first:>4s}"
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
