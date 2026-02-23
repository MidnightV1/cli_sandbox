"""
AI 存活挑战 - Benchmark 指标体系 v2.0

计算Core Metrics + Agent-Specific Metrics，生成标准化对比表格。
"""

import json
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple
from collections import defaultdict, Counter
from scipy.stats import entropy
from scipy.spatial.distance import jensenshannon


# ============== Core Metrics ==============

def calculate_asd(results: List[Dict]) -> Tuple[float, float]:
    """
    ASD (Average Survival Duration)
    平均存活时长 + 标准差
    """
    hours = [r['hours_survived'] for r in results]
    return np.mean(hours), np.std(hours)


def calculate_vss(jsonl_files: List[Path]) -> float:
    """
    VSS (Vital Stability Score)
    生理稳定性 = 100 / (口渴值标准差 + 1)

    从所有游戏过程中提取口渴值时间序列，计算整体波动性。
    """
    all_thirst_values = []

    for jsonl_file in jsonl_files:
        with open(jsonl_file) as f:
            for line in f:
                data = json.loads(line)
                if 'status_after' in data:
                    all_thirst_values.append(data['status_after']['thirst'])

    if not all_thirst_values:
        return 0.0

    std = np.std(all_thirst_values)
    return 100 / (std + 1)


def calculate_var(results: List[Dict]) -> float:
    """
    VAR (Valid Action Rate)
    有效行动率 = 有效指令数 / 总指令数
    """
    total_valid = sum(r['valid_actions'] for r in results)
    total_actions = sum(r['total_actions'] for r in results)

    if total_actions == 0:
        return 0.0

    return total_valid / total_actions


def calculate_rce(jsonl_files: List[Path]) -> float:
    """
    RCE (Resource Conversion Efficiency)
    资源转化效率 = 1 / 平均首次工具创造时间

    越快创造出第一个工具（craft 或 combine 成功均算），效率越高。
    """
    first_craft_times = []

    for jsonl_file in jsonl_files:
        with open(jsonl_file) as f:
            for line in f:
                data = json.loads(line)
                if data.get('action_type') in ('craft', 'combine') and data.get('success'):
                    first_craft_times.append(data['tick'])
                    break

    if not first_craft_times:
        return 0.0

    avg_first_craft = np.mean(first_craft_times)
    return 1 / avg_first_craft if avg_first_craft > 0 else 0.0


def calculate_pia(jsonl_files: List[Path]) -> float:
    """
    TCI (Tool Creation Index)，沿用 PIA 字段名保持接口兼容。

    公式：(craft_ok + combine_ok) / (craft_att + combine_ok)

    设计理由：
    - craft 失败计入分母（使用已知配方却失败 = 知识欠缺）
    - combine 成功计入分子+分母（成功探索 = 有价值的发现）
    - combine 失败不计（探索性尝试天然命中率低，不应惩罚）
    """
    craft_attempts = 0
    craft_success = 0
    combine_success = 0

    for jsonl_file in jsonl_files:
        with open(jsonl_file) as f:
            for line in f:
                data = json.loads(line)
                action = data.get('action_type')
                if action == 'craft':
                    craft_attempts += 1
                    if data.get('success'):
                        craft_success += 1
                elif action == 'combine' and data.get('success'):
                    combine_success += 1

    denominator = craft_attempts + combine_success
    if denominator == 0:
        return 0.0

    return (craft_success + combine_success) / denominator


# ============== Agent-Specific Metrics ==============

def calculate_be(jsonl_files: List[Path]) -> float:
    """
    BE (Behavioral Entropy)
    行为熵 = Shannon熵，衡量行为多样性
    """
    action_counts = Counter()

    for jsonl_file in jsonl_files:
        with open(jsonl_file) as f:
            for line in f:
                data = json.loads(line)
                if 'action_type' in data:
                    action_counts[data['action_type']] += 1

    if not action_counts:
        return 0.0

    total = sum(action_counts.values())
    probs = [count / total for count in action_counts.values()]

    return entropy(probs, base=2)


def calculate_sa(jsonl_files: List[Path]) -> float:
    """
    SA (Strategy Adaptability)
    战略适应性 = JS散度，早期vs晚期行为模式差异

    游戏前1/3 vs 后1/3的行为分布差异。
    """
    early_actions = Counter()
    late_actions = Counter()

    for jsonl_file in jsonl_files:
        ticks = []
        with open(jsonl_file) as f:
            for line in f:
                data = json.loads(line)
                if 'tick' in data:
                    ticks.append(data)

        if len(ticks) < 3:
            continue

        split_point = len(ticks) // 3

        for data in ticks[:split_point]:
            if 'action_type' in data:
                early_actions[data['action_type']] += 1

        for data in ticks[-split_point:]:
            if 'action_type' in data:
                late_actions[data['action_type']] += 1

    if not early_actions or not late_actions:
        return 0.0

    # 统一action类型
    all_actions = set(early_actions.keys()) | set(late_actions.keys())

    early_probs = [early_actions.get(a, 0) for a in all_actions]
    late_probs = [late_actions.get(a, 0) for a in all_actions]

    early_total = sum(early_probs)
    late_total = sum(late_probs)

    if early_total == 0 or late_total == 0:
        return 0.0

    early_probs = [p / early_total for p in early_probs]
    late_probs = [p / late_total for p in late_probs]

    return jensenshannon(early_probs, late_probs)


def calculate_prm(jsonl_files: List[Path]) -> float:
    """
    PRM (Proactive Resource Management)
    主动资源管理率 = 在阈值(60)以下主动进食/饮水的比例
    """
    proactive_eat = 0
    reactive_eat = 0
    proactive_drink = 0
    reactive_drink = 0

    for jsonl_file in jsonl_files:
        with open(jsonl_file) as f:
            for line in f:
                data = json.loads(line)

                if data.get('action_type') == 'eat':
                    hunger_before = data.get('status_before', {}).get('hunger', 0)
                    if hunger_before < 60:
                        proactive_eat += 1
                    else:
                        reactive_eat += 1

                if data.get('action_type') == 'drink':
                    thirst_before = data.get('status_before', {}).get('thirst', 0)
                    if thirst_before < 60:
                        proactive_drink += 1
                    else:
                        reactive_drink += 1

    total = proactive_eat + reactive_eat + proactive_drink + reactive_drink
    if total == 0:
        return 0.0

    return (proactive_eat + proactive_drink) / total


def calculate_cf(jsonl_files: List[Path]) -> float:
    """
    CF (Context Fatigue)
    上下文疲劳 = 前半vs后半有效率差异

    正值表示后期降质，负值表示后期改善。
    """
    first_half_valid = 0
    first_half_total = 0
    second_half_valid = 0
    second_half_total = 0

    for jsonl_file in jsonl_files:
        ticks = []
        with open(jsonl_file) as f:
            for line in f:
                data = json.loads(line)
                if 'tick' in data:
                    ticks.append(data)

        if len(ticks) < 2:
            continue

        mid_point = len(ticks) // 2

        for data in ticks[:mid_point]:
            if 'success' in data:
                first_half_total += 1
                if data['success']:
                    first_half_valid += 1

        for data in ticks[mid_point:]:
            if 'success' in data:
                second_half_total += 1
                if data['success']:
                    second_half_valid += 1

    if first_half_total == 0 or second_half_total == 0:
        return 0.0

    first_rate = first_half_valid / first_half_total
    second_rate = second_half_valid / second_half_total

    # 返回差异百分比
    return (first_rate - second_rate) * 100


def calculate_rr(jsonl_files: List[Path]) -> float:
    """
    RR (Repetition Rate)
    行为重复率 = ≥3次连续相同动作的比例
    """
    total_sequences = 0
    repetitive_sequences = 0

    for jsonl_file in jsonl_files:
        actions = []
        with open(jsonl_file) as f:
            for line in f:
                data = json.loads(line)
                if 'action_type' in data:
                    actions.append(data['action_type'])

        for i in range(len(actions) - 2):
            total_sequences += 1
            if actions[i] == actions[i+1] == actions[i+2]:
                repetitive_sequences += 1

    if total_sequences == 0:
        return 0.0

    return repetitive_sequences / total_sequences


def calculate_tp_inv(results: List[Dict]) -> Tuple[float, float]:
    """
    TP (Tech Points) + INV (Inventions)
    平均科技点数 + 平均发明数
    """
    tech_points = [r['tech_points'] for r in results]
    inventions = [r['inventions'] for r in results]

    return np.mean(tech_points), np.mean(inventions)


def calculate_te(jsonl_files: List[Path]) -> float:
    """
    TE (Temporal Error)
    时间感知误差 = 夜晚无准备死亡的比例

    检测"夜晚降临"事件后，agent是否有庇护所/保暖措施。
    如果在夜晚因低温/怪物死亡，说明时间感知失败。
    """
    nightfall_unprepared = 0
    total_nightfalls = 0

    for jsonl_file in jsonl_files:
        nightfall_detected = False
        has_shelter_items = False

        with open(jsonl_file) as f:
            for line in f:
                data = json.loads(line)

                # 检测夜晚降临事件
                if 'events' in data:
                    for event in data['events']:
                        if '夜晚' in event or '黑暗' in event or '天黑' in event:
                            nightfall_detected = True
                            total_nightfalls += 1

                            # 检查当前是否有保暖/庇护物品
                            # 简化版：检查warmth值是否足够高
                            if 'status_after' in data:
                                warmth = data['status_after'].get('warmth', 0)
                                if warmth < 40:  # 保暖不足
                                    nightfall_unprepared += 1
                            break

                # 如果在夜晚死亡
                if nightfall_detected and data.get('game_over'):
                    # 可以进一步分析死因
                    break

    if total_nightfalls == 0:
        return 0.0

    return nightfall_unprepared / total_nightfalls


# ============== 归一化与智能指数 ==============

# [Deprecated] 被 ISI 基线锚定方案取代，保留用于历史数据对比
def normalize_metrics(all_metrics: Dict[str, Dict]) -> Dict[str, Dict]:
    """
    Min-Max 归一化所有指标到 [0, 1] 区间

    对于"越低越好"的指标（CF, RR, TE），归一化后取反：norm = 1 - (x - min) / (max - min)
    """
    if not all_metrics:
        return {}

    # 收集所有指标的最大最小值
    metric_names = ['ASD', 'VSS', 'VAR', 'RCE', 'PIA', 'BE', 'SA', 'PRM', 'CF', 'RR', 'TP', 'INV', 'TE']
    min_max = {}

    for metric in metric_names:
        values = [m.get(metric, 0) for m in all_metrics.values() if metric in m]
        if values:
            min_max[metric] = (min(values), max(values))
        else:
            min_max[metric] = (0, 1)

    # 归一化
    normalized = {}
    for model_name, metrics in all_metrics.items():
        normalized[model_name] = dict(metrics)  # 复制原始数据

        for metric in metric_names:
            if metric not in metrics:
                normalized[model_name][f'{metric}_norm'] = 0.0
                continue

            min_val, max_val = min_max[metric]
            if max_val == min_val:
                norm_val = 0.5  # 所有值相同时设为中间值
            else:
                norm_val = (metrics[metric] - min_val) / (max_val - min_val)

            # 对于"越低越好"的指标，取反
            if metric in ['CF', 'RR', 'TE']:
                norm_val = 1.0 - norm_val

            normalized[model_name][f'{metric}_norm'] = norm_val

    return normalized


# [Deprecated] 被 calculate_isi() 取代
def calculate_sii(metrics: Dict) -> float:
    """
    SII (Survival Intelligence Index)
    生存智能指数，0-100分

    三大维度：
    1. 生存底线 (30%): 活得久(ASD) + 活得稳(VSS)
    2. 认知核心 (35%): 属性推理(PIA)是基础，发明创造(INV)是上限
    3. 执行效率 (35%): 资源转化(RCE) + 主动管理(PRM)，PRM权重更高以区分主动智能

    惩罚项：
    - VAR低（幻觉严重）扣分
    - TE高（时间感知差）扣分
    """
    # 1. 生存维度 (30%)
    score_survival = 0.6 * metrics.get('ASD_norm', 0) + 0.4 * metrics.get('VSS_norm', 0)

    # 2. 认知维度 (35%)：PIA权重更高，因为它是执行的基础
    score_cognition = 0.7 * metrics.get('PIA_norm', 0) + 0.3 * metrics.get('INV_norm', 0)

    # 3. 效率维度 (35%)：PRM权重更高，区分主动智能 vs 被动生存
    score_efficiency = 0.4 * metrics.get('RCE_norm', 0) + 0.6 * metrics.get('PRM_norm', 0)

    # 4. 惩罚项
    penalty = 0.0

    # VAR低（有效率低）扣分，最大扣15分
    var_penalty = (1.0 - metrics.get('VAR_norm', 1.0)) * 0.15

    # TE高（时间感知差）扣分，最大扣5分
    te_penalty = (1.0 - metrics.get('TE_norm', 1.0)) * 0.05

    penalty = var_penalty + te_penalty

    # 总分 0-100
    total_score = (
        0.30 * score_survival +
        0.35 * score_cognition +
        0.35 * score_efficiency -
        penalty
    ) * 100

    return max(0.0, min(100.0, total_score))


def calculate_qos(metrics: Dict) -> float:
    """
    QoS (Quality of Survival)
    生存质量系数 = ASD × (VSS / 5.0)

    如果VSS很低（垂死挣扎），即使ASD高，QoS也会被拉低。
    这能有效区分"幸运生存"与"智慧生存"。
    """
    asd = metrics.get('ASD', 0)
    vss = metrics.get('VSS', 0)

    # VSS归一化到[0, 1]区间，以5.0为基准
    vss_factor = min(vss / 5.0, 1.0)

    return asd * vss_factor


def calculate_isi(metrics: Dict, reactive_baseline: float = 29.2) -> float:
    """
    ISI (Intelligent Survival Index)
    智能生存指数

    公式：ISI = max(0, ASD - reactive_baseline) × (0.5 + 0.5 × TCI)

    - ASD - reactive_baseline：超越反应式基线的存活增益
    - TCI 质量因子 (0.5 + 0.5 × TCI)：工具使用能力调节，范围 [0.5, 1.0]
    - 单位：智能生存小时（hours above reactive baseline）
    """
    asd = metrics.get('ASD', 0)
    tci = metrics.get('PIA', 0)  # TCI 沿用 PIA 字段名

    survival_gain = max(0, asd - reactive_baseline)
    quality_factor = 0.5 + 0.5 * tci

    return survival_gain * quality_factor


# ============== 数据加载 ==============

def load_eval_results(eval_dir: Path) -> Tuple[List[Dict], List[Path]]:
    """
    加载评估结果目录中的所有数据

    返回：
    - final_scores: 列表，每个元素是一个run的final_score字典
    - jsonl_files: 所有jsonl文件的路径列表
    """
    final_scores = []
    jsonl_files = []

    for jsonl_file in sorted(eval_dir.glob("*.jsonl")):
        jsonl_files.append(jsonl_file)

        # 读取最后一行的final_score
        with open(jsonl_file) as f:
            lines = f.readlines()
            if lines:
                last_line = json.loads(lines[-1])
                if last_line.get('type') == 'final_score':
                    final_scores.append(last_line['scores'])

    return final_scores, jsonl_files


# ============== Benchmark 报告生成 ==============

def calculate_all_metrics(eval_dir: Path) -> Dict:
    """
    计算所有指标
    """
    results, jsonl_files = load_eval_results(eval_dir)

    if not results:
        return {}

    # Core Metrics
    asd_mean, asd_std = calculate_asd(results)
    vss = calculate_vss(jsonl_files)
    var = calculate_var(results)
    rce = calculate_rce(jsonl_files)
    pia = calculate_pia(jsonl_files)

    # Agent-Specific Metrics
    be = calculate_be(jsonl_files)
    sa = calculate_sa(jsonl_files)
    prm = calculate_prm(jsonl_files)
    cf = calculate_cf(jsonl_files)
    rr = calculate_rr(jsonl_files)
    tp, inv = calculate_tp_inv(results)
    te = calculate_te(jsonl_files)

    metrics_dict = {
        # Core Metrics
        'ASD': asd_mean,
        'ASD_std': asd_std,
        'VSS': vss,
        'VAR': var,
        'RCE': rce,
        'PIA': pia,

        # Agent-Specific Metrics (Diagnostic)
        'BE': be,
        'SA': sa,
        'PRM': prm,
        'CF': cf,
        'RR': rr,
        'TP': tp,
        'INV': inv,
        'TE': te,

        # 辅助数据
        'n_runs': len(results),
    }

    # 计算QoS（生存质量系数）
    metrics_dict['QoS'] = calculate_qos(metrics_dict)

    # 计算ISI（智能生存指数）
    metrics_dict['ISI'] = calculate_isi(metrics_dict)

    return metrics_dict


def generate_benchmark_with_isi(eval_base_dir: Path, model_configs: List[Tuple[str, str]]) -> str:
    """
    生成包含ISI（智能生存指数）的Benchmark表格

    Args:
        eval_base_dir: eval_results/seed_217/ 这样的基础目录
        model_configs: [(dir_name, display_name), ...]

    Returns:
        Markdown格式的对比表格，包含ISI排名
    """
    all_metrics = {}

    for dir_name, display_name in model_configs:
        eval_dir = eval_base_dir / dir_name
        if eval_dir.exists():
            all_metrics[display_name] = calculate_all_metrics(eval_dir)

    # 按ISI排序
    sorted_models = sorted(all_metrics.items(), key=lambda x: x[1].get('ISI', 0), reverse=True)

    # 生成ISI排名表
    isi_table = "## 智能生存指数 (ISI) 排名\n\n"
    isi_table += "**ISI = max(0, ASD − 29.2) × (0.5 + 0.5 × TCI)**\n\n"
    isi_table += "| 排名 | Model | ISI↑ | ASD | TCI | Gain | 等级 |\n"
    isi_table += "|------|-------|------|-----|-----|------|------|\n"

    for rank, (model_name, m) in enumerate(sorted_models, 1):
        isi = m.get('ISI', 0)
        asd = m.get('ASD', 0)
        tci = m.get('PIA', 0)
        gain = max(0, asd - 29.2)

        if isi >= 15:
            grade = "S"
        elif isi >= 10:
            grade = "A"
        elif isi >= 6:
            grade = "B"
        elif isi >= 2:
            grade = "C"
        else:
            grade = "D"

        isi_table += f"| {rank} | {model_name} | "
        isi_table += f"**{isi:.1f}** | "
        isi_table += f"{asd:.1f}h | "
        isi_table += f"{tci:.1%} | "
        isi_table += f"+{gain:.1f}h | "
        isi_table += f"{grade} |\n"

    # 生成Core Metrics表格
    core_table = "\n## Core Metrics\n\n"
    core_table += "| Model | ASD↑ | VSS↑ | VAR↑ | RCE↑ | TCI↑ | INV↑ | QoS↑ |\n"
    core_table += "|-------|------|------|------|------|------|------|------|\n"

    for model_name, m in sorted_models:
        core_table += f"| {model_name} | "
        core_table += f"{m.get('ASD', 0):.1f}±{m.get('ASD_std', 0):.1f} | "
        core_table += f"{m.get('VSS', 0):.1f} | "
        core_table += f"{m.get('VAR', 0):.1%} | "
        core_table += f"{m.get('RCE', 0):.3f} | "
        core_table += f"{m.get('PIA', 0):.1%} | "
        core_table += f"{m.get('INV', 0):.1f} | "
        core_table += f"{m.get('QoS', 0):.1f} |\n"

    # 生成Diagnostic Metrics表格
    diagnostic_table = "\n## Diagnostic Metrics（诊断性指标）\n\n"
    diagnostic_table += "| Model | BE | SA | PRM | CF↓ | RR↓ | TE↓ | TP |\n"
    diagnostic_table += "|-------|-----|-----|------|-----|-----|-----|-----|\n"

    for model_name, m in sorted_models:
        diagnostic_table += f"| {model_name} | "
        diagnostic_table += f"{m.get('BE', 0):.2f} | "
        diagnostic_table += f"{m.get('SA', 0):.3f} | "
        diagnostic_table += f"{m.get('PRM', 0):.1%} | "
        diagnostic_table += f"{m.get('CF', 0):.1f}% | "
        diagnostic_table += f"{m.get('RR', 0):.1%} | "
        diagnostic_table += f"{m.get('TE', 0):.1%} | "
        diagnostic_table += f"{m.get('TP', 0):.1f} |\n"

    return isi_table + core_table + diagnostic_table


# [Deprecated] 被 generate_benchmark_with_isi() 取代
def generate_benchmark_with_sii(eval_base_dir: Path, model_configs: List[Tuple[str, str]]) -> str:
    """
    生成包含SII（生存智能指数）的Benchmark表格

    Args:
        eval_base_dir: eval_results/seed_42/ 这样的基础目录
        model_configs: [(dir_name, display_name), ...]

    Returns:
        Markdown格式的对比表格，包含SII排名
    """
    all_metrics = {}

    for dir_name, display_name in model_configs:
        eval_dir = eval_base_dir / dir_name
        if eval_dir.exists():
            all_metrics[display_name] = calculate_all_metrics(eval_dir)

    # 归一化指标
    normalized_metrics = normalize_metrics(all_metrics)

    # 计算SII
    for model_name in normalized_metrics:
        normalized_metrics[model_name]['SII'] = calculate_sii(normalized_metrics[model_name])

    # 按SII排序
    sorted_models = sorted(normalized_metrics.items(), key=lambda x: x[1]['SII'], reverse=True)

    # 生成SII排名表
    sii_table = "## 生存智能指数 (SII) 排名\n\n"
    sii_table += "**SII = 0.3×生存底线 + 0.35×认知核心 + 0.35×执行效率 - 惩罚项**\n\n"
    sii_table += "| 排名 | Model | SII↑ | ASD | PIA | QoS | 等级 |\n"
    sii_table += "|------|-------|------|-----|-----|-----|------|\n"

    for rank, (model_name, m) in enumerate(sorted_models, 1):
        # 根据SII评级
        sii = m.get('SII', 0)
        if sii >= 85:
            grade = "🏆 S"
        elif sii >= 75:
            grade = "🥇 A"
        elif sii >= 65:
            grade = "🥈 B"
        elif sii >= 50:
            grade = "🥉 C"
        else:
            grade = "❌ D"

        sii_table += f"| {rank} | {model_name} | "
        sii_table += f"**{sii:.1f}** | "
        sii_table += f"{m.get('ASD', 0):.1f}h | "
        sii_table += f"{m.get('PIA', 0):.1%} | "
        sii_table += f"{m.get('QoS', 0):.1f} | "
        sii_table += f"{grade} |\n"

    # 生成Core Metrics表格
    core_table = "\n## Core Metrics（用于SII计算）\n\n"
    core_table += "| Model | ASD↑ | VSS↑ | VAR↑ | RCE↑ | PIA↑ | INV↑ | QoS↑ |\n"
    core_table += "|-------|------|------|------|------|------|------|------|\n"

    for model_name, m in sorted_models:
        core_table += f"| {model_name} | "
        core_table += f"{m.get('ASD', 0):.1f}±{m.get('ASD_std', 0):.1f} | "
        core_table += f"{m.get('VSS', 0):.1f} | "
        core_table += f"{m.get('VAR', 0):.1%} | "
        core_table += f"{m.get('RCE', 0):.3f} | "
        core_table += f"{m.get('PIA', 0):.1%} | "
        core_table += f"{m.get('INV', 0):.1f} | "
        core_table += f"{m.get('QoS', 0):.1f} |\n"

    # 生成Diagnostic Metrics表格（诊断性指标，不参与SII）
    diagnostic_table = "\n## Diagnostic Metrics（诊断性指标）\n\n"
    diagnostic_table += "| Model | BE | SA | PRM↑ | CF↓ | RR↓ | TE↓ | TP |\n"
    diagnostic_table += "|-------|-----|-----|------|-----|-----|-----|-----|\n"

    for model_name, m in sorted_models:
        diagnostic_table += f"| {model_name} | "
        diagnostic_table += f"{m.get('BE', 0):.2f} | "
        diagnostic_table += f"{m.get('SA', 0):.3f} | "
        diagnostic_table += f"{m.get('PRM', 0):.1%} | "
        diagnostic_table += f"{m.get('CF', 0):.1f}% | "
        diagnostic_table += f"{m.get('RR', 0):.1%} | "
        diagnostic_table += f"{m.get('TE', 0):.1%} | "
        diagnostic_table += f"{m.get('TP', 0):.1f} |\n"

    return sii_table + core_table + diagnostic_table


def generate_benchmark_table(eval_base_dir: Path, model_configs: List[Tuple[str, str]]) -> str:
    """
    生成Benchmark对比表格

    Args:
        eval_base_dir: eval_results/seed_7/ 这样的基础目录
        model_configs: [(dir_name, display_name), ...] 例如 [('doubao_v18_on', 'Doubao v1.8 ON'), ...]

    Returns:
        Markdown格式的对比表格
    """
    all_metrics = {}

    for dir_name, display_name in model_configs:
        eval_dir = eval_base_dir / dir_name
        if eval_dir.exists():
            all_metrics[display_name] = calculate_all_metrics(eval_dir)

    # 生成Core Metrics表格
    core_table = "## Core Metrics\n\n"
    core_table += "| Model | ASD↑ | VSS↑ | VAR↑ | RCE↑ | PIA↑ | n |\n"
    core_table += "|-------|------|------|------|------|------|---|\n"

    for model_name in all_metrics:
        m = all_metrics[model_name]
        core_table += f"| {model_name} | "
        core_table += f"{m['ASD']:.1f}±{m['ASD_std']:.1f} | "
        core_table += f"{m['VSS']:.1f} | "
        core_table += f"{m['VAR']:.1%} | "
        core_table += f"{m['RCE']:.3f} | "
        core_table += f"{m['PIA']:.1%} | "
        core_table += f"{m['n_runs']} |\n"

    # 生成Agent-Specific Metrics表格
    agent_table = "\n## Agent-Specific Metrics\n\n"
    agent_table += "| Model | BE↑ | SA↑ | PRM↑ | CF↓ | RR↓ | TP↑ | INV↑ |\n"
    agent_table += "|-------|-----|-----|------|-----|-----|-----|------|\n"

    for model_name in all_metrics:
        m = all_metrics[model_name]
        agent_table += f"| {model_name} | "
        agent_table += f"{m['BE']:.2f} | "
        agent_table += f"{m['SA']:.3f} | "
        agent_table += f"{m['PRM']:.1%} | "
        agent_table += f"{m['CF']:.1f}% | "
        agent_table += f"{m['RR']:.1%} | "
        agent_table += f"{m['TP']:.1f} | "
        agent_table += f"{m['INV']:.1f} |\n"

    return core_table + agent_table


# ============== CLI ==============

if __name__ == "__main__":
    # 示例：对比seed=7的所有模型
    eval_base = Path("eval_results/seed_7")

    models = [
        ("doubao_v18_off", "Doubao v1.8"),
        ("doubao_v18_on", "Doubao v1.8 ON"),
        ("doubao_seed2pro_off", "Doubao v2.0P"),
        ("doubao_seed2pro_on", "Doubao v2.0P ON"),
        ("gemini_25_flash_off", "Gemini 2.5F"),
        ("gemini_3_flash_off", "Gemini 3F"),
        ("step_35_flash_off", "Step 3.5F"),
    ]

    table = generate_benchmark_table(eval_base, models)
    print(table)

    # 保存到文件
    output_file = "BENCHMARK.md"
    with open(output_file, 'w') as f:
        f.write("# AI 存活挑战 - Benchmark Results\n\n")
        f.write("*Generated by benchmark_metrics.py*\n\n")
        f.write(table)

    print(f"\n✅ Benchmark table saved to {output_file}")
