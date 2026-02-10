# -*- coding: utf-8 -*-
"""会话录制器 —— 完整记录游戏过程"""

import json
import os
import time
from models.state import TickResult


class Recorder:
    def __init__(self, session_dir: str = None):
        if session_dir is None:
            session_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'sessions'
            )
        os.makedirs(session_dir, exist_ok=True)

        self.session_id = time.strftime("%Y%m%d_%H%M%S")
        self.session_file = os.path.join(session_dir, f"session_{self.session_id}.jsonl")
        self.metadata = {}

    def set_metadata(self, **kwargs):
        """设置会话元数据（玩家类型、场景等）"""
        self.metadata.update(kwargs)

    def record_tick(self, tick: int, raw_input: str, action_type: str,
                    tick_result: TickResult, tech_points: int = 0):
        """记录一个tick"""
        record = {
            'tick': tick,
            'timestamp': time.time(),
            'raw_input': raw_input,
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
            'game_over': tick_result.game_over,
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
