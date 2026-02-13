# -*- coding: utf-8 -*-
"""异星求生 CLI沙盒 —— 主入口"""

import sys
import os
import argparse
import time as _time

# 确保项目根目录在 sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.world import GameEngine
from interface.parser import parse_action
from interface.cli import CLIRenderer
from eval.recorder import Recorder


def main():
    parser = argparse.ArgumentParser(description='LLM Agent 生存沙盒')
    parser.add_argument('--scene', default=None, help='场景目录路径（如 data/scenes/crash_site_42）')
    parser.add_argument('--no-llm', action='store_true', help='禁用LLM裁判（仅使用确定性规则引擎）')
    parser.add_argument('--player', default=None, help='玩家类型标记（human/ai/model_name），用于录制')
    parser.add_argument('--seed', type=int, default=None, help='随机种子（控制日长、天气等运行时随机）')
    parser.add_argument('--agent', type=str, default=None,
                        help='AI agent模式（格式：provider/model，如 gemini/3-Pro）')
    parser.add_argument('--thinking', type=str, nargs='?', const='high', default=None,
                        help='思考级别：high/medium/low（默认high）')
    parser.add_argument('--session-file', type=str, default=None,
                        help='指定session录制文件路径（批量评测用）')
    args = parser.parse_args()

    # 随机种子
    if args.seed is not None:
        import random
        random.seed(args.seed)

    # 解析agent配置
    agent_provider = agent_model = None
    if args.agent:
        parts = args.agent.split('/', 1)
        if len(parts) != 2:
            print("[错误] --agent 格式应为 provider/model，如 gemini/3-Pro")
            sys.exit(1)
        agent_provider, agent_model = parts

    # LLM客户端（agent模式强制启用）
    llm_client = None
    if not args.no_llm or args.agent:
        try:
            from llm.client import LLMClient
            llm_client = LLMClient()
        except Exception as e:
            print(f"[警告] LLM客户端初始化失败：{e}")
            if args.agent:
                print("[错误] Agent模式需要LLM客户端。")
                sys.exit(1)
            print("[提示] 将以纯规则引擎模式运行。\n")

    # 初始化引擎
    engine = GameEngine(scene_dir=args.scene, llm_client=llm_client)

    # agent模式：裁判统一用 Gemini 3-Pro（推理能力强，判断准确）
    if args.agent and llm_client:
        from engine.judge import LLMJudge
        world_rules = engine._load_world_rules()
        engine.judge = LLMJudge(llm_client, world_rules, provider='gemini', model='3-Pro')

    # AI玩家
    ai_player = None
    if args.agent and llm_client:
        from agent.player import AIPlayer
        ai_player = AIPlayer(
            llm_client, agent_provider, agent_model,
            thinking=args.thinking,
            materials_db=engine.materials,
            recipes_db=engine.recipes,
        )

    # 录制
    renderer = CLIRenderer()
    player_type = args.player or (f"{agent_provider}/{agent_model}" if args.agent else 'human')
    recorder = Recorder(player_type=player_type, thinking=args.thinking,
                        session_file=args.session_file)
    recorder.set_metadata(
        player_type=player_type,
        scenario=engine.world.scenario_name,
        llm_enabled=True if args.agent else not args.no_llm,
        seed=args.seed,
    )

    # 开场
    renderer.render_intro(engine.world)
    renderer.render_world(engine.world)

    if ai_player:
        renderer.render_message(
            f"\n[Agent] {agent_provider}/{agent_model}"
            f"{' (thinking)' if args.thinking else ''} 开始自动游戏...\n",
            "bold blue"
        )

    # 主循环
    last_tick = None

    while not engine.world.game_over:
        # ── 获取输入 ──
        if ai_player:
            try:
                game_state = ai_player.build_state_text(engine.world, last_tick)
                raw_input_str = ai_player.decide(game_state)
            except Exception as e:
                renderer.render_message(f"[Agent异常] {e}", "red")
                raise  # 直接抛出异常，不兜底
            renderer.render_message(f"\n[AI] {raw_input_str}", "bold blue")
            _time.sleep(0.2)
        else:
            raw_input_str = renderer.get_input()

        # 退出检查（仅人类模式）
        if not ai_player and raw_input_str.lower() in ('quit', 'exit', '退出', 'q'):
            renderer.render_message("\n你选择了放弃...", "dim")
            engine.world.game_over = True
            engine.world.game_over_reason = "玩家主动退出。"
            break

        if not raw_input_str:
            if ai_player:
                raw_out = getattr(ai_player, 'last_raw_response', '') or ''
                snippet = raw_out.replace('\n', ' ').strip()[:80]
                renderer.render_message(f"格式错误：未能提取有效指令", "yellow")
                # 走 engine 标准流程（统一处理体力扣除、tick递增、时间推进）
                tick_result = engine.process_action('empty', {'raw': ''})
                last_tick = tick_result
                feedback = f"格式错误，你的输出不符合XML格式（-2体力, -0.25h）。你的原始输出：「{snippet}」"
                ai_player.record_action("格式错误", engine.world, result_msg=feedback, success=False)
                recorder.record_tick(
                    engine.world.decision_count, '', 'empty', tick_result,
                    tech_points=engine.world.tech_points,
                    notebook=engine.world.player.notebook if hasattr(engine.world.player, 'notebook') else [],
                    llm_raw_output=raw_out,
                )
                if tick_result.hours_elapsed > 0:
                    renderer.render_world(engine.world)
            continue

        # ── 解析 ──
        action_type, action_args = parse_action(raw_input_str)

        if action_type == 'unknown':
            renderer.render_message(f"无法理解指令「{raw_input_str}」。输入 help 查看可用指令。", "yellow")
            if ai_player:
                raw_out = getattr(ai_player, 'last_raw_response', '') or ''
                # 走 engine 标准流程
                tick_result = engine.process_action('unknown', {'raw': raw_input_str})
                last_tick = tick_result
                feedback = f"无法理解的指令「{raw_input_str}」（-2体力, -0.25h），合法指令：观察/移动/采集/制作/组合/使用/吃/喝/休息/尝试/记录"
                ai_player.record_action(raw_input_str, engine.world, result_msg=feedback, success=False)
                recorder.record_tick(
                    engine.world.decision_count, raw_input_str, 'unknown', tick_result,
                    tech_points=engine.world.tech_points,
                    notebook=engine.world.player.notebook if hasattr(engine.world.player, 'notebook') else [],
                    llm_raw_output=raw_out,
                )
                if tick_result.hours_elapsed > 0:
                    renderer.render_world(engine.world)
            continue

        if action_type == 'empty':
            continue

        # ── combine 推理 ──
        if action_type == 'combine' and not action_args.get('reasoning'):
            test_result = engine.rules.resolve('combine', action_args, engine.world)
            if test_result.needs_llm and not test_result.success:
                if ai_player:
                    try:
                        game_state = ai_player.build_state_text(engine.world)
                        reasoning = ai_player.provide_reasoning(
                            action_args.get('items', []), game_state
                        )
                        renderer.render_message(f"  [AI推理] {reasoning}", "blue")
                        action_args['reasoning'] = reasoning
                    except Exception as e:
                        renderer.render_message(f"  [推理异常] {e}", "red")
                        action_args['reasoning'] = "尝试利用材料属性组合出有用的工具"
                else:
                    items_str = "、".join(action_args.get('items', []))
                    renderer.render_message(
                        f"这不是已知配方。你想把 {items_str} 组合成什么？请描述你的思路：",
                        "cyan"
                    )
                    reasoning = renderer.get_input()
                    if reasoning.lower() in ('cancel', '取消', 'q'):
                        renderer.render_message("取消组合。", "dim")
                        continue
                    action_args['reasoning'] = reasoning

        # ── 执行 ──
        tick_result = engine.process_action(action_type, action_args)
        last_tick = tick_result

        # 渲染结果
        renderer.render_result(tick_result)

        # agent记录上下文
        if ai_player:
            ai_player.record_action(
                raw_input_str, engine.world,
                result_msg=tick_result.action_result.message,
                success=tick_result.action_result.success,
                events=tick_result.events,
            )

        # 录制
        recorder.record_tick(
            engine.world.decision_count,
            raw_input_str,
            action_type,
            tick_result,
            tech_points=engine.world.tech_points,
            notebook=engine.world.player.notebook if hasattr(engine.world.player, 'notebook') else [],
            llm_raw_output=ai_player.last_raw_response if ai_player and hasattr(ai_player, 'last_raw_response') else None,
        )

        # 状态栏（消耗时间的成功动作才刷新）
        if tick_result.hours_elapsed > 0:
            renderer.render_world(engine.world)

        # ── 检查点 ──
        if engine.world.checkpoint_reached and not engine.world.game_over:
            checkpoint_scores = engine.get_score()
            if ai_player:
                # agent模式：显示报告，自动继续
                renderer.render_message(f"\n{'═' * 50}", "bold yellow")
                renderer.render_message(
                    f"检查点 —— 第{engine.world.checkpoints_passed + 1}阶段"
                    f"（第{engine.world.current_day}天）",
                    "bold yellow"
                )
                _, tech_name = engine.world.tech_level
                renderer.render_message(
                    f"  科技：{tech_name}（{checkpoint_scores['tech_points']}点）| "
                    f"发明：{checkpoint_scores['inventions']} | "
                    f"有效率：{(1 - checkpoint_scores['invalid_rate']) * 100:.0f}%",
                    "white"
                )
                cost = checkpoint_scores.get('cost')
                if cost and cost['total_calls'] > 0:
                    renderer.render_message(
                        f"  LLM调用：{cost['total_calls']}次 | 费用：¥{cost['total_cost_cny']:.4f}",
                        "yellow"
                    )
                engine.world.checkpoint_reached = False
                engine.world.checkpoints_passed += 1
                renderer.render_message(
                    f"\n[Agent] 自动进入第{engine.world.checkpoints_passed + 1}阶段"
                    f"（目标：第{engine.world.next_checkpoint_day}天）",
                    "bold cyan"
                )
                renderer.render_world(engine.world)
            else:
                should_continue = renderer.render_checkpoint(engine.world, checkpoint_scores)
                engine.world.checkpoint_reached = False
                if should_continue:
                    engine.world.checkpoints_passed += 1
                    renderer.render_message(
                        f"\n进入第{engine.world.checkpoints_passed + 1}阶段"
                        f"（目标：第{engine.world.next_checkpoint_day}天）",
                        "bold cyan"
                    )
                    renderer.render_world(engine.world)
                else:
                    engine.world.game_over = True
                    engine.world.game_over_reason = (
                        f"在第{engine.world.checkpoints_passed + 1}阶段检查点选择结束实验。"
                    )

    # 游戏结束
    scores = engine.get_score()
    renderer.render_game_over(engine.world, scores)
    recorder.record_final(scores)

    renderer.render_message(f"会话已录制到：{recorder.session_file}", "dim")


if __name__ == '__main__':
    main()
