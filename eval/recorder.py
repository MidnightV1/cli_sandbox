# -*- coding: utf-8 -*-
"""会话录制器 —— 完整记录游戏过程"""

import json
import os
import time
from models.state import TickResult


class Recorder:
    def __init__(self, session_dir: str = None, player_type: str = None,
                 thinking: str = None, session_file: str = None):
        # 外部指定路径（run_eval 批量模式）
        if session_file:
            os.makedirs(os.path.dirname(session_file), exist_ok=True)
            self.session_file = session_file
            self.metadata = {}
            return

        # 自动生成路径（人类玩家 / 单次调试）
        if session_dir is None:
            session_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'sessions'
            )
        os.makedirs(session_dir, exist_ok=True)

        timestamp = time.strftime("%Y%m%d_%H%M%S")

        model_name = 'unknown'
        if player_type:
            if '/' in player_type:
                model_name = player_type.lower().replace('/', '-').replace(' ', '-')
            else:
                model_name = player_type.lower()

        think_suffix = ''
        if thinking:
            think_suffix = f"_{thinking}"
        elif player_type and '/' in player_type:
            think_suffix = '_off'

        filename = f"{model_name}{think_suffix}_{timestamp}.jsonl"
        self.session_file = os.path.join(session_dir, filename)
        self.metadata = {}

    def set_metadata(self, **kwargs):
        """设置会话元数据（玩家类型、场景等）"""
        self.metadata.update(kwargs)

    def record_tick(self, tick: int, raw_input: str, action_type: str,
                    tick_result: TickResult, tech_points: int = 0, notebook: list = None,
                    llm_raw_output: str = None, thinking: str = None):
        """记录一个tick"""
        record = {
            'tick': tick,                          # 决策序号（连续递增，从1开始）
            'turn': tick_result.action_count,      # 游戏回合（仅成功推进时递增）
            'timestamp': time.time(),
            'raw_input': raw_input,
            'llm_raw_output': llm_raw_output,  # 模型的原始输出（XML格式）
            'thinking': thinking,  # 模型的思考过程（思维链）
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
