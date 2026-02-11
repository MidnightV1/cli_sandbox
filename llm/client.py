# -*- coding: utf-8 -*-
"""统一LLM客户端 —— 基于 work_functions.py 的调用封装"""

import os
from dotenv import load_dotenv

# 加载 .env
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))


# ═══ 计费系统 ═══
# 价格：美元 / 百万 token
PRICING = {
    # Anthropic
    'claude-3-big': {'input': 15, 'output': 75},
    'claude-4-big': {'input': 15, 'output': 75},
    'claude-35-mid': {'input': 3, 'output': 15},
    'claude-4-mid': {'input': 3, 'output': 15},
    'claude-37': {'input': 3, 'output': 15},
    'claude-35-small': {'input': 0.8, 'output': 4},
    # OpenAI
    'gpt-4.1': {'input': 2, 'output': 8},
    'gpt-4.1-mini': {'input': 0.4, 'output': 1.6},
    # Gemini
    '2.5-Flash': {'input': 0.3, 'output': 2.5},
    '2.5-Pro': {'input': 1.25, 'output': 10},
    '3-Pro': {'input': 2.0, 'output': 12},
    '3-Flash': {'input': 0.5, 'output': 3},
    # DeepSeek (V3.2, thinking/non-thinking同价)
    'v3': {'input': 0.28, 'output': 0.42},
    # Moonshot Kimi (价格: ¥4/¥21 per M tokens → USD)
    'k2.5': {'input': 0.55, 'output': 2.88},
}
EX_RATE = 7.3  # 美元→人民币


class CostTracker:
    """LLM调用计费追踪"""

    def __init__(self):
        self.calls: list[dict] = []
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost_cny = 0.0

    def record(self, model: str, input_tokens: int, output_tokens: int):
        pricing = PRICING.get(model, {'input': 3, 'output': 15})
        input_cost = pricing['input'] * input_tokens / 1_000_000 * EX_RATE
        output_cost = pricing['output'] * output_tokens / 1_000_000 * EX_RATE
        cost = input_cost + output_cost
        self.calls.append({
            'model': model,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'cost_cny': round(cost, 6),
        })
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost_cny += cost

    def summary(self) -> dict:
        by_model = {}
        for c in self.calls:
            m = c['model']
            if m not in by_model:
                by_model[m] = {'calls': 0, 'input_tokens': 0, 'output_tokens': 0, 'cost_cny': 0.0}
            by_model[m]['calls'] += 1
            by_model[m]['input_tokens'] += c['input_tokens']
            by_model[m]['output_tokens'] += c['output_tokens']
            by_model[m]['cost_cny'] += c['cost_cny']
        return {
            'total_calls': len(self.calls),
            'total_input_tokens': self.total_input_tokens,
            'total_output_tokens': self.total_output_tokens,
            'total_cost_cny': round(self.total_cost_cny, 4),
            'by_model': {k: {**v, 'cost_cny': round(v['cost_cny'], 4)} for k, v in by_model.items()},
        }


class LLMClient:
    """统一接口调用各家LLM"""

    PROVIDER_MODELS = {
        'anthropic': {
            'claude-37': 'claude-3-7-sonnet-20250219',
            'claude-4-mid': 'claude-4-sonnet-20250514',
            'claude-4-big': 'claude-opus-4-20250514',
        },
        'openai': {
            'gpt-4.1': 'gpt-4.1-2025-04-14',
            'gpt-4.1-mini': 'gpt-4.1-mini-2025-04-14',
        },
        'gemini': {
            '2.5-Flash': 'gemini-2.5-flash',
            '2.5-Pro': 'gemini-2.5-pro',
            '3-Pro': 'gemini-3-pro-preview',
            '3-Flash': 'gemini-3-flash-preview',
        },
        'deepseek': {
            'v3': 'deepseek-chat',
        },
        'moonshot': {
            'k2.5': 'kimi-k2.5',
        },
    }

    def __init__(self):
        self._clients = {}
        self.cost_tracker = CostTracker()

    def call(self, system_prompt: str, user_prompt: str,
             provider: str = 'anthropic', model: str = 'claude-37',
             temperature: float = 0.3, thinking=None) -> dict:
        """
        统一调用接口。返回标准化结果：
        {model, content, input_tokens, output_tokens}
        thinking: str级别(high/medium/low) 或 True(=high) 或 None/False(关闭)
        """
        if provider == 'anthropic':
            result = self._call_anthropic(system_prompt, user_prompt, model, temperature)
        elif provider == 'openai':
            result = self._call_openai(system_prompt, user_prompt, model, temperature)
        elif provider == 'gemini':
            result = self._call_gemini(system_prompt, user_prompt, model, temperature, thinking)
        elif provider == 'deepseek':
            result = self._call_deepseek(system_prompt, user_prompt, model, temperature, thinking)
        elif provider == 'moonshot':
            result = self._call_moonshot(system_prompt, user_prompt, model, temperature, thinking)
        else:
            raise ValueError(f"未知的LLM提供商：{provider}")

        # 记录计费
        self.cost_tracker.record(
            model=result['model'],
            input_tokens=result['input_tokens'],
            output_tokens=result['output_tokens'],
        )
        return result

    def _call_anthropic(self, system_prompt, user_prompt, model_name, temperature):
        import anthropic
        if 'anthropic' not in self._clients:
            api_key = os.getenv('ANTHROPIC_API_KEY')
            if not api_key:
                raise ValueError("缺少 ANTHROPIC_API_KEY 环境变量")
            self._clients['anthropic'] = anthropic.Anthropic(api_key=api_key)

        client = self._clients['anthropic']
        model_id = self.PROVIDER_MODELS['anthropic'].get(model_name, model_name)

        message = client.messages.create(
            model=model_id,
            max_tokens=4096,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        return {
            'model': model_name,
            'content': message.content[0].text,
            'input_tokens': message.usage.input_tokens,
            'output_tokens': message.usage.output_tokens,
        }

    def _call_openai(self, system_prompt, user_prompt, model_name, temperature):
        from openai import OpenAI
        if 'openai' not in self._clients:
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                raise ValueError("缺少 OPENAI_API_KEY 环境变量")
            self._clients['openai'] = OpenAI(api_key=api_key)

        client = self._clients['openai']
        model_id = self.PROVIDER_MODELS['openai'].get(model_name, model_name)

        response = client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=4096,
        )

        return {
            'model': model_name,
            'content': response.choices[0].message.content,
            'input_tokens': response.usage.prompt_tokens,
            'output_tokens': response.usage.completion_tokens,
        }

    def _call_gemini(self, system_prompt, user_prompt, model_name, temperature, thinking=False):
        from google import genai
        from google.genai import types
        if 'gemini' not in self._clients:
            api_key = os.getenv('GEMINI_API_KEY')
            if not api_key:
                raise ValueError("缺少 GEMINI_API_KEY 环境变量")
            self._clients['gemini'] = genai.Client(api_key=api_key)

        client = self._clients['gemini']
        model_id = self.PROVIDER_MODELS['gemini'].get(model_name, model_name)

        # thinking配置
        thinking_config = None
        if thinking:
            level = thinking if isinstance(thinking, str) else "high"
            if model_name.startswith('3-'):
                thinking_config = types.ThinkingConfig(thinking_level=level)
            else:
                thinking_config = types.ThinkingConfig(thinking_budget=-1)

        response = client.models.generate_content(
            model=model_id,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=temperature,
                max_output_tokens=8192,
                thinking_config=thinking_config,
            ),
            contents=user_prompt,
        )

        return {
            'model': model_name,
            'content': response.text,
            'input_tokens': response.usage_metadata.prompt_token_count,
            'output_tokens': response.usage_metadata.candidates_token_count,
        }

    def _call_deepseek(self, system_prompt, user_prompt, model_name, temperature, thinking=False):
        from openai import OpenAI
        if 'deepseek' not in self._clients:
            api_key = os.getenv('DEEPSEEK_API_KEY')
            if not api_key:
                raise ValueError("缺少 DEEPSEEK_API_KEY 环境变量")
            self._clients['deepseek'] = OpenAI(
                api_key=api_key,
                base_url="https://api.deepseek.com",
            )

        client = self._clients['deepseek']
        model_id = self.PROVIDER_MODELS['deepseek'].get(model_name, model_name)

        # thinking模式：V3.2通过extra_body开关，thinking时temperature无效
        extra = {}
        if thinking:
            extra['extra_body'] = {"thinking": {"type": "enabled"}}

        response = client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature if not thinking else None,
            max_tokens=8192,
            **extra,
        )

        return {
            'model': model_name,
            'content': response.choices[0].message.content,
            'input_tokens': response.usage.prompt_tokens,
            'output_tokens': response.usage.completion_tokens,
        }

    def _call_moonshot(self, system_prompt, user_prompt, model_name, temperature, thinking=True):
        from openai import OpenAI
        if 'moonshot' not in self._clients:
            api_key = os.getenv('MOONSHOT_API_KEY')
            if not api_key:
                raise ValueError("缺少 MOONSHOT_API_KEY 环境变量")
            self._clients['moonshot'] = OpenAI(
                api_key=api_key,
                base_url="https://api.moonshot.cn/v1",
            )

        client = self._clients['moonshot']
        model_id = self.PROVIDER_MODELS['moonshot'].get(model_name, model_name)

        # Kimi K2.5: thinking默认开启，通过extra_body关闭
        # temperature限制：thinking=on → 只允许1，thinking=off → 只允许0.6
        extra = {}
        if thinking:
            temp = 1
        else:
            extra['extra_body'] = {"thinking": {"type": "disabled"}}
            temp = 0.6

        response = client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temp,
            max_tokens=8192,
            **extra,
        )

        return {
            'model': model_name,
            'content': response.choices[0].message.content,
            'input_tokens': response.usage.prompt_tokens,
            'output_tokens': response.usage.completion_tokens,
        }
