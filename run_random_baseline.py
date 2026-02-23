#!/usr/bin/env python3
"""随机基准 Agent 批量运行脚本

运行两种基准各 NUM_RUNS 局，建立 benchmark 零点：
  random   —— 从所有合法动作中均匀随机选择（纯随机）
  reactive —— 危机阈值时才干预，其余随机（最小规则基线）

结果保存到 eval_results/seed_{SEED}/random_XXX/
"""

import subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).parent
RESULTS_DIR = ROOT / "eval_results"
SEED = 217
NUM_RUNS = 10

BASELINES = [
    ("random",   "random_baseline"),
    ("reactive", "reactive_baseline"),
]

tasks = []
for mode, player_tag in BASELINES:
    out_dir = RESULTS_DIR / f"seed_{SEED}" / player_tag
    out_dir.mkdir(parents=True, exist_ok=True)
    for run_idx in range(1, NUM_RUNS + 1):
        session_file = out_dir / f"run_{run_idx}.jsonl"
        if session_file.exists():
            print(f"  跳过（已存在）: {player_tag} run#{run_idx}")
            continue
        tasks.append((mode, player_tag, run_idx, out_dir))

print(f"=== 随机基准：共 {len(tasks)} 局 ===")

# 随机 agent 很快（无 LLM），可以高并发
MAX_PARALLEL = 20

active = []
pending = list(tasks)
completed = 0
failed = []

while pending or active:
    while pending and len(active) < MAX_PARALLEL:
        mode, player_tag, run_idx, out_dir = pending.pop(0)
        session_file = out_dir / f"run_{run_idx}.jsonl"
        log_file = out_dir / f"run_{run_idx}.log"
        cmd = [
            sys.executable, str(ROOT / "main.py"),
            "--random-agent", mode,
            "--seed", str(SEED),
            "--player", player_tag,
            "--session-file", str(session_file),
        ]
        print(f"  启动 [{completed + len(active) + 1}/{len(tasks)}] {player_tag} run#{run_idx} ({mode})")
        fp = open(log_file, "w", encoding="utf-8")
        proc = subprocess.Popen(cmd, stdout=fp, stderr=subprocess.STDOUT)
        active.append((proc, player_tag, run_idx, fp))

    still_active = []
    for proc, player_tag, run_idx, fp in active:
        ret = proc.poll()
        if ret is None:
            still_active.append((proc, player_tag, run_idx, fp))
        else:
            fp.close()
            completed += 1
            tag = f"{player_tag} run#{run_idx}"
            if ret == 0:
                print(f"  ✓ [{completed}/{len(tasks)}] {tag}")
            else:
                print(f"  ✗ [{completed}/{len(tasks)}] {tag} (exit={ret})")
                failed.append(tag)
    active = still_active
    if active:
        time.sleep(0.5)

print(f"\n=== 完成: {completed - len(failed)}/{len(tasks)} 成功, {len(failed)} 失败 ===")
if failed:
    for t in failed:
        print(f"  - {t}")
