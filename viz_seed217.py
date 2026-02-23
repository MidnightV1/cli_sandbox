"""
seed=217 Phase 2 可视化脚本
生成图表到 figures/ 目录

图表清单：
  fig_3_1_isi_ranking_bar.png      — ISI 排名条形图（按 Tier 着色）
  fig_3_1_asd_tci_scatter.png      — ASD × TCI 二维散点图（ISI 等值线 + 四象限）
  fig_3_3_thinking_delta.png       — 思维模式 ΔISI 瀑布图
  fig_4_1_behavioral_archetypes.png — 行为原型：早期/末期动作分布对比
  fig_4_2_inventions_style.png     — 创造力风格：发明数 vs TCI
"""

import json, glob, os
from collections import defaultdict
import numpy as np

# ── matplotlib 配置 ──
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# 中文字体（macOS）
matplotlib.rcParams['font.sans-serif'] = ['Hiragino Sans GB', 'Heiti TC', 'Arial Unicode MS', 'STHeiti', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False
# 清除字体缓存确保生效
matplotlib.font_manager._load_fontmanager(try_read_cache=False)

# Tier 颜色
TIER_COLORS = {'S': '#e74c3c', 'A': '#e67e22', 'B': '#3498db', 'C': '#95a5a6', 'D': '#bdc3c7'}

# 标签美化
def short_label(tag):
    """player_tag → 短标签（配置命名规范：thinking 模式加 ' - T'，标准模式无后缀）"""
    name_map = {
        'claude_opus': 'Opus 4.6', 'claude_sonnet': 'Sonnet 4.5', 'claude_sonnet46': 'Sonnet 4.6',
        'deepseek_v32': 'DS V3.2', 'doubao_v15pro': 'Db v1.5P', 'doubao_v16': 'Db v1.6',
        'doubao_v18': 'Db v1.8', 'doubao_v20pro': 'Db v2.0P',
        'gemini_25_flash': 'Gm 2.5F', 'gemini_25_pro': 'Gm 2.5P',
        'gemini_3_flash': 'Gm 3F', 'gemini_3_pro': 'Gm 3P', 'gemini_31_pro': 'Gm 3.1P',
        'glm_5': 'GLM-5', 'gpt52': 'GPT-5.2', 'gpt52_chat': 'GPT-5.2C',
        'kimi_25': 'Kimi', 'qwen3_max': 'Qwen3M', 'qwen35_plus': 'Qw3.5+',
        'qwen35_397b': 'Qw397B', 'step_35_flash': 'Step 3.5F',
        'random_baseline': 'Random', 'reactive_baseline': 'Reactive',
    }
    if tag in ('random_baseline', 'reactive_baseline'):
        return name_map.get(tag, tag)
    if tag.endswith('_on'):
        base = tag[:-3]
        suffix = ' - T'  # thinking
    elif tag.endswith('_off'):
        base = tag[:-4]
        suffix = ''
    else:
        return tag
    return f"{name_map.get(base, base)}{suffix}"


# ── 数据加载 ──
def load_seed217_data():
    """从 JSONL 加载 seed=217 全量数据"""
    base = os.path.join(os.path.dirname(__file__), 'eval_results', 'seed_217')
    results = defaultdict(lambda: {
        'asd_list': [], 'tci_list': [], 'isi_list': [],
        'inv_list': [], 'cost_list': [],
        'early_actions': defaultdict(int), 'late_actions': defaultdict(int),
        'notebook_sessions': 0, 'sessions': 0
    })

    for path in sorted(glob.glob(os.path.join(base, '*', 'run_*.jsonl'))):
        tag = os.path.basename(os.path.dirname(path))
        lines = open(path).readlines()
        ticks = [json.loads(l) for l in lines]

        last = ticks[-1]
        if last.get('type') != 'final_score':
            continue

        r = results[tag]
        r['sessions'] += 1

        # ASD
        asd = last['scores']['hours_survived']
        r['asd_list'].append(asd)

        # Cost
        cost = last['scores'].get('cost', {}).get('total_cost_cny', 0)
        r['cost_list'].append(cost)

        # Inventions
        inv = last['scores'].get('inventions', 0)
        r['inv_list'].append(inv)

        # TCI: craft/combine success tracking
        craft_ok = craft_att = combine_ok = 0
        used_notebook = False
        action_ticks = [t for t in ticks if t.get('type') != 'final_score' and 'action_type' in t]

        for t in action_ticks:
            at = t.get('action_type', '')
            ok = t.get('success', False)
            if at == 'craft':
                craft_att += 1
                if ok:
                    craft_ok += 1
            elif at == 'combine' and ok:
                combine_ok += 1
            if at == 'note':
                used_notebook = True

        denom = craft_att + combine_ok
        tci = (craft_ok + combine_ok) / denom if denom > 0 else 0
        r['tci_list'].append(tci)

        # ISI
        isi = max(0, asd - 29.2) * (0.5 + 0.5 * tci)
        r['isi_list'].append(isi)

        if used_notebook:
            r['notebook_sessions'] += 1

        # Early/late actions
        for t in action_ticks[:10]:
            r['early_actions'][t['action_type']] += 1
        for t in action_ticks[-10:]:
            r['late_actions'][t['action_type']] += 1

    # Aggregate
    configs = {}
    for tag, r in results.items():
        n = r['sessions']
        if n == 0:
            continue
        configs[tag] = {
            'asd': np.mean(r['asd_list']),
            'asd_std': np.std(r['asd_list']),
            'tci': np.mean(r['tci_list']),
            'isi': np.mean(r['isi_list']),
            'isi_std': np.std(r['isi_list']),
            'inv': np.mean(r['inv_list']),
            'cost': np.mean(r['cost_list']),
            'n': n,
            'tier': get_tier(np.mean(r['isi_list'])),
            'early_actions': dict(r['early_actions']),
            'late_actions': dict(r['late_actions']),
            'notebook_rate': r['notebook_sessions'] / n,
        }
    return configs


def get_tier(isi):
    if isi >= 15: return 'S'
    if isi >= 10: return 'A'
    if isi >= 6: return 'B'
    if isi >= 2: return 'C'
    return 'D'


def ensure_figures_dir():
    d = os.path.join(os.path.dirname(__file__), 'figures')
    os.makedirs(d, exist_ok=True)
    return d


# ── 图 3.1a: ISI 排名条形图 ──
def plot_isi_ranking(configs, figdir):
    # 排序（排除基线）
    items = [(tag, c) for tag, c in configs.items()]
    items.sort(key=lambda x: -x[1]['isi'])

    tags = [t for t, _ in items]
    isis = [c['isi'] for _, c in items]
    colors = [TIER_COLORS[c['tier']] for _, c in items]
    labels = [short_label(t) for t in tags]

    fig, ax = plt.subplots(figsize=(18, 7))
    bars = ax.barh(range(len(tags)), isis, color=colors, edgecolor='white', linewidth=0.5)
    ax.set_yticks(range(len(tags)))
    ax.set_yticklabels(labels, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel('ISI (智能生存小时)', fontsize=12)
    ax.set_title('ISI 排名 — seed=217 (43 配置)', fontsize=14)

    # Tier 分界线
    for threshold, label in [(15, 'S≥15'), (10, 'A≥10'), (6, 'B≥6'), (2, 'C≥2')]:
        ax.axvline(x=threshold, color='gray', linestyle='--', alpha=0.5, linewidth=0.8)
        ax.text(threshold + 0.2, len(tags) - 1, label, fontsize=8, color='gray', va='bottom')

    # 图例
    legend_patches = [mpatches.Patch(color=TIER_COLORS[t], label=f'Tier {t}') for t in 'SABCD']
    ax.legend(handles=legend_patches, loc='lower right', fontsize=9)

    plt.tight_layout()
    path = os.path.join(figdir, 'fig_3_1_isi_ranking_bar.png')
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f'  ✓ {path}')


# ── 图 3.1b: ASD × TCI 散点图（核心图） ──
def plot_asd_tci_scatter(configs, figdir):
    fig, ax = plt.subplots(figsize=(12, 9))

    # ISI 等值线
    asd_range = np.linspace(29.2, 55, 200)
    tci_range = np.linspace(0, 1, 200)
    ASD_grid, TCI_grid = np.meshgrid(asd_range, tci_range)
    ISI_grid = np.maximum(0, ASD_grid - 29.2) * (0.5 + 0.5 * TCI_grid)

    contour = ax.contour(ASD_grid, TCI_grid, ISI_grid,
                         levels=[2, 6, 10, 15, 20],
                         colors='lightgray', linewidths=0.8, linestyles='--')
    ax.clabel(contour, fmt='ISI=%g', fontsize=8, colors='gray')

    # 四象限分界
    asd_mid = 39.0  # 中位数附近
    tci_mid = 0.50
    ax.axhline(y=tci_mid, color='lightgray', linestyle='-', alpha=0.3)
    ax.axvline(x=asd_mid, color='lightgray', linestyle='-', alpha=0.3)

    # 象限标签
    ax.text(52, 0.95, '聪明型\n高存活 + 高工具', fontsize=9, color='#27ae60',
            ha='center', va='top', alpha=0.6, style='italic')
    ax.text(32, 0.95, '理解型\n低存活 + 高工具', fontsize=9, color='#2980b9',
            ha='center', va='top', alpha=0.6, style='italic')
    ax.text(52, 0.05, '苟活型\n高存活 + 低工具', fontsize=9, color='#e67e22',
            ha='center', va='bottom', alpha=0.6, style='italic')
    ax.text(32, 0.05, '基线附近\n低存活 + 低工具', fontsize=9, color='#95a5a6',
            ha='center', va='bottom', alpha=0.6, style='italic')

    # 散点
    for tag, c in configs.items():
        if tag in ('random_baseline', 'reactive_baseline'):
            # 基线用 × 标记
            ax.scatter(c['asd'], c['tci'], marker='x', s=80, c='black', zorder=5)
            ax.annotate(short_label(tag), (c['asd'], c['tci']),
                       fontsize=7, ha='center', va='bottom',
                       xytext=(0, 5), textcoords='offset points', color='black')
            continue

        color = TIER_COLORS[c['tier']]
        is_on = tag.endswith('_on')
        marker = 'o' if is_on else 's'  # ● ON, ■ OFF
        size = 100 if c['tier'] in ('S', 'A') else 60

        ax.scatter(c['asd'], c['tci'], marker=marker, s=size, c=color,
                  edgecolors='white', linewidths=0.5, zorder=5, alpha=0.85)

        # 标签（只标注 S/A 级 + 有趣的 case）
        label_tags = {
            'claude_opus_on', 'claude_opus_off', 'qwen3_max_on', 'qwen3_max_off',
            'gpt52_on', 'gpt52_off', 'doubao_v18_on', 'deepseek_v32_on', 'deepseek_v32_off',
            'glm_5_on', 'gemini_3_flash_off', 'claude_sonnet_off',
            'gpt52_chat_off', 'doubao_v18_off', 'gemini_3_flash_on',
            'gemini_31_pro_on', 'gemini_31_pro_off',
            'claude_sonnet46_on', 'claude_sonnet46_off',
        }
        if tag in label_tags:
            ax.annotate(short_label(tag), (c['asd'], c['tci']),
                       fontsize=7, ha='left', va='bottom',
                       xytext=(4, 3), textcoords='offset points', color=color)

    # 思维模式连线（ON→OFF 同模型）
    drawn_pairs = set()
    for tag, c in configs.items():
        if not tag.endswith('_on'):
            continue
        base = tag[:-3]
        off_tag = base + '_off'
        if off_tag in configs and base not in drawn_pairs:
            drawn_pairs.add(base)
            off_c = configs[off_tag]
            ax.annotate('', xy=(c['asd'], c['tci']), xytext=(off_c['asd'], off_c['tci']),
                       arrowprops=dict(arrowstyle='->', color='gray', alpha=0.3, lw=0.8))

    # Reactive 基线垂直线
    ax.axvline(x=29.2, color='red', linestyle=':', alpha=0.4, linewidth=1)
    ax.text(29.5, 0.98, 'Reactive\n基线', fontsize=8, color='red', alpha=0.5, va='top')

    ax.set_xlabel('ASD — 平均存活时长 (h)', fontsize=12)
    ax.set_ylabel('TCI — 工具创造准确率', fontsize=12)
    ax.set_title('ASD × TCI 智能结构分布 — seed=217', fontsize=14)
    ax.set_xlim(14, 54)
    ax.set_ylim(-0.05, 1.08)

    # 图例
    legend_elements = [
        plt.scatter([], [], marker='o', c='gray', s=60, label='thinking'),
        plt.scatter([], [], marker='s', c='gray', s=60, label='标准'),
        plt.scatter([], [], marker='x', c='black', s=60, label='基线'),
    ]
    for t in 'SABCD':
        legend_elements.append(mpatches.Patch(color=TIER_COLORS[t], label=f'Tier {t}'))
    ax.legend(handles=legend_elements, loc='upper left', fontsize=8, ncol=2)

    plt.tight_layout()
    path = os.path.join(figdir, 'fig_3_1_asd_tci_scatter.png')
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f'  ✓ {path}')


# ── 图 3.3: 思维模式 ΔISI 瀑布图 ──
def plot_thinking_delta(configs, figdir):
    pairs = []
    for tag, c in configs.items():
        if not tag.endswith('_on'):
            continue
        base = tag[:-3]
        off_tag = base + '_off'
        if off_tag not in configs:
            continue
        off_c = configs[off_tag]
        delta_isi = c['isi'] - off_c['isi']
        delta_asd = c['asd'] - off_c['asd']
        delta_tci = c['tci'] - off_c['tci']
        pairs.append((base, delta_isi, delta_asd, delta_tci, c['isi'], off_c['isi']))

    pairs.sort(key=lambda x: -x[1])

    fig, ax = plt.subplots(figsize=(14, 7))
    labels = [short_label(p[0] + '_on').replace(' ●', '') for p in pairs]
    deltas = [p[1] for p in pairs]
    colors = ['#27ae60' if d > 0 else '#e74c3c' for d in deltas]

    bars = ax.barh(range(len(pairs)), deltas, color=colors, edgecolor='white', linewidth=0.5)
    ax.set_yticks(range(len(pairs)))
    ax.set_yticklabels(labels, fontsize=10)
    ax.invert_yaxis()
    ax.axvline(x=0, color='black', linewidth=0.8)
    ax.set_xlabel('ΔISI (thinking - 标准)', fontsize=12)
    ax.set_title('思维模式效应 — ISI 增益', fontsize=14)

    # 数值标签
    for i, (_, delta, d_asd, d_tci, _, _) in enumerate(pairs):
        x_pos = delta + (0.3 if delta >= 0 else -0.3)
        ha = 'left' if delta >= 0 else 'right'
        detail = f'{delta:+.1f}  (ASD{d_asd:+.1f}h, TCI{d_tci:+.2f})'
        ax.text(x_pos, i, detail, va='center', ha=ha, fontsize=8, color='#333')

    plt.tight_layout()
    path = os.path.join(figdir, 'fig_3_3_thinking_delta.png')
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f'  ✓ {path}')


# ── 图 4.1: 行为原型对比 ──
def plot_behavioral_archetypes(configs, figdir):
    # 选取代表性模型
    archetypes = {
        'claude_opus_on': '全栈玩家',
        'deepseek_v32_off': '观察瘫痪',
        'deepseek_v32_on': '思维解锁',
        'qwen3_max_on': '创造力爆发',
        'qwen3_max_off': '空背包制作',
        'gpt52_off': '稳定执行',
    }

    action_order = ['gather', 'look', 'move', 'rest', 'drink', 'eat', 'craft',
                    'free_action', 'use', 'combine', 'note', 'empty', 'unknown']
    action_colors = {
        'gather': '#27ae60', 'look': '#3498db', 'move': '#9b59b6', 'rest': '#f39c12',
        'drink': '#1abc9c', 'eat': '#e67e22', 'craft': '#e74c3c', 'free_action': '#c0392b',
        'use': '#2ecc71', 'combine': '#d35400', 'note': '#7f8c8d', 'empty': '#bdc3c7',
        'unknown': '#95a5a6',
    }

    fig, axes = plt.subplots(len(archetypes), 2, figsize=(14, 3 * len(archetypes)))
    fig.suptitle('行为原型：早期 vs 末期动作分布', fontsize=14, y=1.01)

    for idx, (tag, archetype_name) in enumerate(archetypes.items()):
        c = configs[tag]
        for col, (phase, actions_dict) in enumerate([('早期 (前10 tick)', c['early_actions']),
                                                      ('末期 (后10 tick)', c['late_actions'])]):
            ax = axes[idx][col]
            total = sum(actions_dict.values())
            if total == 0:
                ax.set_visible(False)
                continue

            # 筛选 > 3% 的动作
            action_pcts = {a: actions_dict.get(a, 0) / total * 100 for a in action_order
                          if actions_dict.get(a, 0) / total > 0.03}
            other = 100 - sum(action_pcts.values())
            if other > 1:
                action_pcts['other'] = other

            acts = list(action_pcts.keys())
            pcts = list(action_pcts.values())
            colors_list = [action_colors.get(a, '#bdc3c7') for a in acts]

            ax.barh(acts, pcts, color=colors_list, edgecolor='white', linewidth=0.5)
            ax.set_xlim(0, 75)

            if col == 0:
                ax.set_ylabel(f'{short_label(tag)}\n「{archetype_name}」', fontsize=9, fontweight='bold')
            if idx == 0:
                ax.set_title(phase, fontsize=11)
            if idx == len(archetypes) - 1:
                ax.set_xlabel('%', fontsize=10)

            # 百分比标签
            for j, (act, pct) in enumerate(zip(acts, pcts)):
                if pct > 5:
                    ax.text(pct + 0.5, j, f'{pct:.0f}%', va='center', fontsize=8)

    plt.tight_layout()
    path = os.path.join(figdir, 'fig_4_1_behavioral_archetypes.png')
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f'  ✓ {path}')


# ── 图 4.2: 创造力风格（发明数 vs TCI）──
def plot_inventions_style(configs, figdir):
    fig, ax = plt.subplots(figsize=(11, 8))

    for tag, c in configs.items():
        if tag in ('random_baseline', 'reactive_baseline'):
            continue

        color = TIER_COLORS[c['tier']]
        is_on = tag.endswith('_on')
        marker = 'o' if is_on else 's'

        ax.scatter(c['tci'], c['inv'], marker=marker, s=80, c=color,
                  edgecolors='white', linewidths=0.5, alpha=0.85, zorder=5)

        # 标注高发明数或极端 case
        if c['inv'] >= 1.4 or c['inv'] == 0 or (c['tci'] > 0.8 and c['inv'] < 0.5):
            ax.annotate(short_label(tag), (c['tci'], c['inv']),
                       fontsize=7, ha='left', va='bottom',
                       xytext=(4, 3), textcoords='offset points', color=color)

    ax.set_xlabel('TCI — 工具创造准确率', fontsize=12)
    ax.set_ylabel('INV — 平均发明数/轮', fontsize=12)
    ax.set_title('创造力风格：发明数量 vs 工具使用能力', fontsize=14)
    ax.set_xlim(-0.05, 1.08)

    # 象限标签
    ax.text(0.95, ax.get_ylim()[1] * 0.9, '高执行 + 高创造', fontsize=9,
            ha='right', color='#27ae60', alpha=0.5, style='italic')
    ax.text(0.05, ax.get_ylim()[1] * 0.9, '低执行 + 高创造', fontsize=9,
            ha='left', color='#2980b9', alpha=0.5, style='italic')
    ax.text(0.95, 0.05, '高执行 + 零创造', fontsize=9,
            ha='right', color='#e67e22', alpha=0.5, style='italic')

    legend_elements = [
        plt.scatter([], [], marker='o', c='gray', s=60, label='thinking'),
        plt.scatter([], [], marker='s', c='gray', s=60, label='标准'),
    ]
    for t in 'SABCD':
        legend_elements.append(mpatches.Patch(color=TIER_COLORS[t], label=f'Tier {t}'))
    ax.legend(handles=legend_elements, loc='upper left', fontsize=8)

    plt.tight_layout()
    path = os.path.join(figdir, 'fig_4_2_inventions_style.png')
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f'  ✓ {path}')


# ── 主入口 ──
if __name__ == '__main__':
    print('Loading seed=217 data...')
    configs = load_seed217_data()
    print(f'  Loaded {len(configs)} configs, {sum(c["n"] for c in configs.values())} sessions')

    figdir = ensure_figures_dir()
    print('\nGenerating figures:')

    plot_isi_ranking(configs, figdir)
    plot_asd_tci_scatter(configs, figdir)
    plot_thinking_delta(configs, figdir)
    plot_behavioral_archetypes(configs, figdir)
    plot_inventions_style(configs, figdir)

    print('\nDone.')
