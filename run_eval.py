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

SEED = 42                    # 随机种子（控制运行时随机）
MAX_PARALLEL = 4             # 最大并行数（OpenRouter 付费账户 $1=1RPS，4并行较安全）

# 模型列表：每项为 (provider/model, thinking, player_tag)
# thinking: None=关闭, "high"/"medium"/"low"=对应级别
MODELS = [
    # ── Gemini (官方API) ──
    ("gemini/3-Pro",         "high", "gemini_3pro_high"),
    ("gemini/3-Pro",         None,   "gemini_3pro_off"),
    ("gemini/3-Flash",       "high", "gemini_3flash_high"),
    ("gemini/3-Flash",       None,   "gemini_3flash_off"),

    # ── Claude (官方API) ──
    # ("anthropic/claude-46-big",  "high", "claude_opus_on"),
    # ("anthropic/claude-46-big",  None,   "claude_opus_off"),
    # ("anthropic/claude-45-mid",  "high", "claude_sonnet_on"),
    # ("anthropic/claude-45-mid",  None,   "claude_sonnet_off"),

    # ── Claude (OpenRouter) ──
    ("openrouter/anthropic/claude-opus-4.6",    "high", "claude_opus_on"),
    ("openrouter/anthropic/claude-opus-4.6",    None,   "claude_opus_off"),
    ("openrouter/anthropic/claude-sonnet-4.5",  "high", "claude_sonnet_on"),
    ("openrouter/anthropic/claude-sonnet-4.5",  None,   "claude_sonnet_off"),

    # ── GPT (官方API) ──
    # ("openai/gpt-5.2",       "high",   "gpt52_on"),
    # ("openai/gpt-5.2",       None,     "gpt52_off"),
    # ("openai/gpt-5.2-chat",  "medium", "gpt52chat_on"),
    # ("openai/gpt-5.2-chat",  None,     "gpt52chat_off"),

    # ── GPT (OpenRouter) ──
    ("openrouter/openai/gpt-5.2",       "high",   "gpt52_on"),
    ("openrouter/openai/gpt-5.2",       None,     "gpt52_off"),
    ("openrouter/openai/gpt-5.2-chat",  "medium", "gpt52chat_on"),
    ("openrouter/openai/gpt-5.2-chat",  None,     "gpt52chat_off"),

    # ── DeepSeek (官方API) ──
    ("deepseek/v3",          "high", "deepseek_on"),
    ("deepseek/v3",          None,   "deepseek_off"),

    # ── Doubao (官方API) ──
    ("doubao/seed-1.8",      "high", "doubao_on"),
    ("doubao/seed-1.8",      None,   "doubao_off"),

    # ── Kimi (官方API) ──
    ("moonshot/k2.5",        "high", "kimi_on"),
    ("moonshot/k2.5",        None,   "kimi_off"),

    # ── OpenRouter 渠道 ──
    ("openrouter/z-ai/glm-5",                    "high", "glm5_on"),
    ("openrouter/z-ai/glm-5",                    None,   "glm5_off"),
    ("openrouter/qwen/qwen3-max-thinking",       "high", "qwen3max_on"),
    ("openrouter/qwen/qwen3-max-thinking",       None,   "qwen3max_off"),
    ("openrouter/stepfun/step-3.5-flash:free",   "high", "step35flash_on"),
    ("openrouter/stepfun/step-3.5-flash:free",   None,   "step35flash_off"),
]

# ╔══════════════════════════════════════════════════════════════╗
# ║                    以下不需要改                               ║
# ╚══════════════════════════════════════════════════════════════╝

ROOT = Path(__file__).parent
LOG_DIR = ROOT / "eval_logs"


def build_cmd(agent: str, thinking: str | None, player: str) -> list[str]:
    cmd = [
        sys.executable, str(ROOT / "main.py"),
        "--agent", agent,
        "--seed", str(SEED),
        "--player", player,
    ]
    if thinking:
        cmd += ["--thinking", thinking]
    return cmd


def run():
    LOG_DIR.mkdir(exist_ok=True)
    (ROOT / "sessions").mkdir(exist_ok=True)

    total = len(MODELS)
    print(f"=== 批量评测：{total} 个配置，seed={SEED}，并行={MAX_PARALLEL} ===")
    print(f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    active: list[tuple[subprocess.Popen, str, Path]] = []
    pending = list(MODELS)
    completed = 0
    failed = []

    while pending or active:
        # 启动新进程（不超过并行上限）
        while pending and len(active) < MAX_PARALLEL:
            agent, thinking, player = pending.pop(0)
            log_file = LOG_DIR / f"{player}.log"
            cmd = build_cmd(agent, thinking, player)

            think_tag = f"think={thinking}" if thinking else "no-think"
            print(f"  启动 [{completed + len(active) + 1}/{total}] {player} ({think_tag})")

            fp = open(log_file, "w", encoding="utf-8")
            proc = subprocess.Popen(cmd, stdout=fp, stderr=subprocess.STDOUT)
            active.append((proc, player, fp))

        # 检查已完成的进程
        still_active = []
        for proc, player, fp in active:
            ret = proc.poll()
            if ret is None:
                still_active.append((proc, player, fp))
            else:
                fp.close()
                completed += 1
                if ret == 0:
                    print(f"  ✓ [{completed}/{total}] {player} 完成")
                else:
                    print(f"  ✗ [{completed}/{total}] {player} 失败 (exit={ret})")
                    failed.append(player)
        active = still_active

        if active:
            time.sleep(2)

    print()
    print(f"=== 评测完成 ===")
    print(f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"成功: {completed - len(failed)}/{total}  失败: {len(failed)}/{total}")
    if failed:
        print(f"失败列表: {', '.join(failed)}")

    session_count = len(list((ROOT / "sessions").glob("*.jsonl")))
    print(f"Session 文件: {session_count} 个")


if __name__ == "__main__":
    run()
