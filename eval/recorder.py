# -*- coding: utf-8 -*-
"""会话录制器 —— 完整记录游戏过程"""

import json
import os
import time
from models.state import TickResult


class Recorder:
    def __init__(self, session_dir: str = None, player_type: str = None, thinking: str = None):
        if session_dir is None:
            session_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'sessions'
            )
        os.makedirs(session_dir, exist_ok=True)

        # 构建文件名：模型名_thinking状态_时间戳
        timestamp = time.strftime("%Y%m%d_%H%M%S")

        # 清理模型名（保留完整 provider/model，替换斜杠为连字符）
        model_name = 'unknown'
        if player_type:
            # 格式可能是 "gemini/3-Flash" 或 "human" 或 "ai"
            if '/' in player_type:
                # 保留完整名称，如 "gemini/3-Flash" -> "gemini-3-flash"
                model_name = player_type.lower().replace('/', '-').replace(' ', '-')
            else:
                model_name = player_type.lower()

        # thinking 状态
        think_suffix = ''
        if thinking:
            think_suffix = f"_{thinking}"
        elif player_type and '/' in player_type:
            # AI agent 但未指定 thinking，默认标记为 off
            think_suffix = '_off'

        # 最终文件名：模型名_thinking_时间戳.jsonl
        filename = f"{model_name}{think_suffix}_{timestamp}.jsonl"
        self.session_file = os.path.join(session_dir, filename)
        self.metadata = {}

    def set_metadata(self, **kwargs):
        """设置会话元数据（玩家类型、场景等）"""
        self.metadata.update(kwargs)

    def record_tick(self, tick: int, raw_input: str, action_type: str,
                    tick_result: TickResult, tech_points: int = 0, notebook: list = None,
                    llm_raw_output: str = None):
        """记录一个tick"""
        record = {
            'tick': tick,
            'timestamp': time.time(),
            'raw_input': raw_input,
            'llm_raw_output': llm_raw_output,  # 模型的原始输出（XML格式）
            'action_type': action_type,
            'success': tick_result.action_result.success,
            'message': tick_result.action_result.message,
            'hours_elapsed': tick_result.hours_elapsed,
            'events': tick_result.events,
            'status_before': tick_result.status_before,
            'status_after': tick_result.status_after,
            'items_consumed': tick_result.action_result.items_consumed,
            'items_gained': [str(i) for i in tick_result.action_result.items_gained],
            'energy_cost': tick_result.action_result.energy_cost,
            'needs_llm': tick_result.action_result.needs_llm,
            'tech_points': tech_points,
            'notebook': notebook if notebook else [],
            'game_over': tick_result.game_over,
        }

        with open(self.session_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')

    def record_error(self, tick: int, raw_input: str, error_type: str,
                     message: str, llm_raw_output: str = None, world=None):
        """记录格式错误 / 未知指令（不需要 TickResult）"""
        record = {
            'tick': tick,
            'timestamp': time.time(),
            'raw_input': raw_input,
            'llm_raw_output': llm_raw_output,
            'action_type': error_type,
            'success': False,
            'message': message,
            'hours_elapsed': 0,
            'events': [],
            'game_over': world.game_over if world else False,
        }
        if world:
            s = world.player.status
            record['status_snapshot'] = {
                'health': s.health, 'hunger': s.hunger,
                'thirst': s.thirst, 'warmth': s.warmth, 'energy': s.energy,
            }
        with open(self.session_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')

    def record_final(self, scores: dict):
        """记录最终得分"""
        record = {
            'type': 'final_score',
            'timestamp': time.time(),
            'metadata': self.metadata,
            'scores': scores,
        }
        with open(self.session_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
