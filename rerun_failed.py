#!/usr/bin/env python3
"""补跑失败 session — 只跑缺失的 run_N，跳过已有文件"""
import subprocess, sys, time, os
from pathlib import Path

ROOT = Path(__file__).parent
RESULTS_DIR = ROOT / "eval_results"
SEED = 217

# 需要补跑的配置: (agent, thinking, player_tag, runs需要的总数)
RERUN_CONFIGS = [
    ("gemini/2.5-Pro",                          "high", "gemini_25_pro_on",     10),
    ("gemini/2.5-Pro",                          None,   "gemini_25_pro_off",    10),
    ("gemini/3-Pro",                             "high", "gemini_3_pro_on",      10),
    ("openrouter/anthropic/claude-opus-4.6",    "high", "claude_opus_on",       10),
    ("openrouter/openai/gpt-5.2-chat",          None,   "gpt52_chat_off",       10),
    ("openrouter/z-ai/glm-5",                   "high", "glm_5_on",            10),
    ("openrouter/z-ai/glm-5",                   None,   "glm_5_off",           10),
    ("qwen/qwen3-max",                           "high", "qwen3_max_on",        10),
    # 新增 claude-sonnet-4.6（从未跑过）
    ("openrouter/anthropic/claude-sonnet-4.6",  "high", "claude_sonnet46_on",  10),
    ("openrouter/anthropic/claude-sonnet-4.6",  None,   "claude_sonnet46_off", 10),
]

PROVIDER_PARALLEL = {
    'gemini':     10,
    'openrouter':  3,
    'qwen':       10,
}
MAX_PARALLEL = 16

def provider_of(agent):
    return agent.split('/')[0]

def provider_active(active, prov):
    return sum(1 for _, p, *_ in active if p == prov)

tasks = []
for agent, thinking, player, total in RERUN_CONFIGS:
    out_dir = RESULTS_DIR / f"seed_{SEED}" / player
    out_dir.mkdir(parents=True, exist_ok=True)
    for run_idx in range(1, total + 1):
        session_file = out_dir / f"run_{run_idx}.jsonl"
        if session_file.exists():
            continue  # 已有，跳过
        tasks.append((agent, thinking, player, run_idx, out_dir))

print(f"=== 补跑 {len(tasks)} 局 ===")

active = []
pending = list(tasks)
completed = 0
failed = []

while pending or active:
    while pending and len(active) < MAX_PARALLEL:
        launched = False
        for i, task in enumerate(pending):
            agent, thinking, player, run_idx, out_dir = task
            prov = provider_of(agent)
            limit = PROVIDER_PARALLEL.get(prov, MAX_PARALLEL)
            if provider_active(active, prov) >= limit:
                continue
            pending.pop(i)
            session_file = out_dir / f"run_{run_idx}.jsonl"
            log_file = out_dir / f"run_{run_idx}.log"
            cmd = [sys.executable, str(ROOT / "main.py"),
                   "--agent", agent, "--seed", str(SEED),
                   "--player", player, "--session-file", str(session_file)]
            if thinking:
                cmd += ["--thinking", thinking]
            think_tag = f"think={thinking}" if thinking else "no-think"
            print(f"  启动 [{completed+len(active)+1}/{len(tasks)}] {player} run#{run_idx} ({think_tag})")
            fp = open(log_file, "w", encoding="utf-8")
            proc = subprocess.Popen(cmd, stdout=fp, stderr=subprocess.STDOUT)
            active.append((proc, prov, player, run_idx, fp))
            launched = True
            break
        if not launched:
            break

    still_active = []
    for proc, prov, player, run_idx, fp in active:
        ret = proc.poll()
        if ret is None:
            still_active.append((proc, prov, player, run_idx, fp))
        else:
            fp.close(); completed += 1
            tag = f"{player} run#{run_idx}"
            if ret == 0:
                print(f"  ✓ [{completed}/{len(tasks)}] {tag}")
            else:
                print(f"  ✗ [{completed}/{len(tasks)}] {tag} (exit={ret})")
                failed.append(tag)
    active = still_active
    if active:
        time.sleep(2)

print(f"\n=== 完成: {completed-len(failed)}/{len(tasks)} 成功, {len(failed)} 失败 ===")
if failed:
    for t in failed: print(f"  - {t}")
