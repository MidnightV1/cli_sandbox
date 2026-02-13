#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量评测启动器 —— 在顶部配置模型，一键跑批"""

import subprocess
import os
import sys
import time
from pathlib import Path

# ╔══════════════════════════════════════════════════════════════╗
# ║                    评测配置（改这里）                         ║
# ╚══════════════════════════════════════════════════════════════╝

SEEDS = [7, 233, 999]        # Phase 1 新 seeds（与已有 121/666 交叉对比）
NUM_RUNS = 100               # Phase 1: 大规模验证（验证 n=10 的采样充分性）
MAX_PARALLEL = 50            # 全局最大并行数

# 限速 provider 的最大并发数（provider 前缀匹配）
# OpenRouter 免费模型限 50 RPM，每局 ~35 次请求，5 并发 ≈ 40 RPM
PROVIDER_PARALLEL = {
    'openrouter': 5,
}

# 模型列表：每项为 (provider/model, thinking, player_tag)
# thinking: None=关闭, "high"/"medium"/"low"=对应级别
MODELS = [
    # ═══ Phase 1：大规模采样验证（3个便宜模型 × 100轮 × 2seeds） ═══

    # ── Gemini (官方API) ──
    ("gemini/3-Flash",       None,   "gemini_3_flash_off"),

    # ── Doubao (官方API) ──
    ("doubao/seed-1.8",      None,   "doubao_v18_off"),

    # ── Step (OpenRouter) ──  暂停：免费版 50 RPM 限速
    # ("openrouter/stepfun/step-3.5-flash:free",   None,   "step_35_flash_off"),

    # ═══ Phase 2：全模型对比（等 Phase 1 验证后再启用） ═══

    # ── Gemini (官方API) ──
    # ("gemini/3-Pro",         "high", "gemini_3_pro_high"),
    # ("gemini/3-Pro",         None,   "gemini_3_pro_off"),
    # ("gemini/3-Flash",       "high", "gemini_3_flash_high"),

    # ── Claude (官方API) ──
    # ("anthropic/claude-46-big",  "high", "claude_opus_on"),
    # ("anthropic/claude-46-big",  None,   "claude_opus_off"),
    # ("anthropic/claude-45-mid",  "high", "claude_sonnet_on"),
    # ("anthropic/claude-45-mid",  None,   "claude_sonnet_off"),

    # ── Claude (OpenRouter) ──
    # ("openrouter/anthropic/claude-opus-4.6",    "high", "claude_opus_on"),
    # ("openrouter/anthropic/claude-opus-4.6",    None,   "claude_opus_off"),
    # ("openrouter/anthropic/claude-sonnet-4.5",  "high", "claude_sonnet_on"),
    # ("openrouter/anthropic/claude-sonnet-4.5",  None,   "claude_sonnet_off"),

    # ── GPT (官方API) ──
    # ("openai/gpt-5.2",       "high",   "gpt52_on"),
    # ("openai/gpt-5.2",       None,     "gpt52_off"),
    # ("openai/gpt-5.2-chat",  "medium", "gpt52_chat_on"),
    # ("openai/gpt-5.2-chat",  None,     "gpt52_chat_off"),

    # ── GPT (OpenRouter) ──
    # ("openrouter/openai/gpt-5.2",       "high",   "gpt52_on"),
    # ("openrouter/openai/gpt-5.2",       None,     "gpt52_off"),
    # ("openrouter/openai/gpt-5.2-chat",  "medium", "gpt52_chat_on"),
    # ("openrouter/openai/gpt-5.2-chat",  None,     "gpt52_chat_off"),

    # ── DeepSeek (官方API) ──
    # ("deepseek/v3",          "high", "deepseek_v32_on"),
    # ("deepseek/v3",          None,   "deepseek_v32_off"),

    # ── Doubao (官方API) ──
    # ("doubao/seed-1.8",      "high", "doubao_v18_on"),

    # ── Kimi (官方API) ──
    # ("moonshot/k2.5",        "high", "kimi_25_on"),
    # ("moonshot/k2.5",        None,   "kimi_25_off"),

    # ── OpenRouter 渠道 ──
    # ("openrouter/z-ai/glm-5",                    "high", "glm_5_on"),
    # ("openrouter/z-ai/glm-5",                    None,   "glm_5_off"),
    # ("openrouter/qwen/qwen3-max-thinking",       "high", "qwen3_max_on"),
    # ("openrouter/qwen/qwen3-max-thinking",       None,   "qwen3_max_off"),
    # ("openrouter/stepfun/step-3.5-flash:free",   "high", "step_35_flash_on"),
]

# ╔══════════════════════════════════════════════════════════════╗
# ║                    以下不需要改                               ║
# ╚══════════════════════════════════════════════════════════════╝

ROOT = Path(__file__).parent
RESULTS_DIR = ROOT / "eval_results"


def build_cmd(agent: str, thinking: str | None, player: str,
              seed: int, run_idx: int, out_dir: Path) -> list[str]:
    """构建单次运行的命令行"""
    session_file = out_dir / f"run_{run_idx}.jsonl"
    cmd = [
        sys.executable, str(ROOT / "main.py"),
        "--agent", agent,
        "--seed", str(seed),
        "--player", player,
        "--session-file", str(session_file),
    ]
    if thinking:
        cmd += ["--thinking", thinking]
    return cmd


def run():
    total_configs = len(MODELS)
    total_runs = total_configs * NUM_RUNS * len(SEEDS)

    print(f"=== 批量评测 ===")
    print(f"配置: {total_configs} 个 × {NUM_RUNS} 轮 × {len(SEEDS)} seeds = {total_runs} 局")
    print(f"seeds={SEEDS}  并行={MAX_PARALLEL}")
    print(f"输出: {RESULTS_DIR}/")
    print(f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # 展开所有任务：(agent, thinking, player, seed, run_idx, out_dir)
    tasks = []
    for seed in SEEDS:
        for agent, thinking, player in MODELS:
            out_dir = RESULTS_DIR / f"seed_{seed}" / player
            out_dir.mkdir(parents=True, exist_ok=True)
            for run_idx in range(1, NUM_RUNS + 1):
                tasks.append((agent, thinking, player, seed, run_idx, out_dir))

    active: list[tuple] = []  # (proc, provider, player, seed, run_idx, log_fp)
    pending = list(tasks)
    completed = 0
    failed = []

    def _provider_of(agent_str: str) -> str:
        return agent_str.split('/')[0]

    def _provider_active_count(prov: str) -> int:
        return sum(1 for _, p, *_ in active if p == prov)

    while pending or active:
        # 启动新进程
        while pending and len(active) < MAX_PARALLEL:
            # 找到第一个不超限的任务
            launched = False
            for i, task in enumerate(pending):
                agent = task[0]
                prov = _provider_of(agent)
                limit = PROVIDER_PARALLEL.get(prov, MAX_PARALLEL)
                if _provider_active_count(prov) >= limit:
                    continue
                # 可以启动
                pending.pop(i)
                agent, thinking, player, seed, run_idx, out_dir = task
                log_file = out_dir / f"run_{run_idx}.log"
                cmd = build_cmd(agent, thinking, player, seed, run_idx, out_dir)

                think_tag = f"think={thinking}" if thinking else "no-think"
                print(f"  启动 [{completed + len(active) + 1}/{total_runs}]"
                      f" {player} seed={seed} run#{run_idx} ({think_tag})")

                fp = open(log_file, "w", encoding="utf-8")
                proc = subprocess.Popen(cmd, stdout=fp, stderr=subprocess.STDOUT)
                active.append((proc, prov, player, seed, run_idx, fp))
                launched = True
                break
            if not launched:
                break  # 所有 pending 任务都受限，等完成后再试

        # 检查完成
        still_active = []
        for proc, prov, player, seed, run_idx, fp in active:
            ret = proc.poll()
            if ret is None:
                still_active.append((proc, prov, player, seed, run_idx, fp))
            else:
                fp.close()
                completed += 1
                tag = f"{player} seed={seed} run#{run_idx}"
                if ret == 0:
                    print(f"  ✓ [{completed}/{total_runs}] {tag} 完成")
                else:
                    print(f"  ✗ [{completed}/{total_runs}] {tag} 失败 (exit={ret})")
                    failed.append(tag)
        active = still_active

        if active:
            time.sleep(2)

    # 汇总
    print()
    print(f"=== 评测完成 ===")
    print(f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"成功: {completed - len(failed)}/{total_runs}  失败: {len(failed)}/{total_runs}")
    if failed:
        print(f"失败列表:")
        for tag in failed:
            print(f"  - {tag}")

    # 统计 session 文件
    for seed in SEEDS:
        seed_dir = RESULTS_DIR / f"seed_{seed}"
        session_count = len(list(seed_dir.rglob("*.jsonl"))) if seed_dir.exists() else 0
        print(f"Session 文件: {session_count} 个 → {seed_dir}")


if __name__ == "__main__":
    run()
