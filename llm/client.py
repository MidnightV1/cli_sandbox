# -*- coding: utf-8 -*-
"""统一LLM客户端 —— 基于 work_functions.py 的调用封装"""

import os
import requests
from dotenv import load_dotenv

# 加载 .env
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))


# ═══ 计费系统 ═══
# 价格：百万 token，默认 USD，cny=True 表示人民币
EX_RATE = 7.3  # USD → CNY
PRICING = {
    # Anthropic (USD)
    'claude-45-mid': {'input': 3, 'output': 15},
    'claude-46-big': {'input': 5, 'output': 25},
    'anthropic/claude-sonnet-4.6': {'input': 3, 'output': 15},  # ≤200K档
    # OpenAI (USD)
    'gpt-4.1': {'input': 2, 'output': 8},
    'gpt-4.1-mini': {'input': 0.4, 'output': 1.6},
    'gpt-5.2': {'input': 1.75, 'output': 14},
    'gpt-5.2-chat': {'input': 1.75, 'output': 14},
    # Gemini (USD)
    '2.5-Flash': {'input': 0.3, 'output': 2.5},
    '2.5-Pro': {'input': 1.25, 'output': 10},
    '3-Pro': {'input': 2.0, 'output': 12},
    '3.1-Pro': {'input': 2.0, 'output': 12},
    '3-Flash': {'input': 0.5, 'output': 3},
    # DeepSeek V3.2 (CNY, thinking/non-thinking 同价, 缓存未命中)
    'v3': {'input': 2, 'output': 3, 'cny': True},
    # Moonshot Kimi (CNY, input≤128K 档)
    'k2.5': {'input': 4, 'output': 21, 'cny': True},
    # Doubao Seed (CNY, input≤32K 档)
    'seed-1.5-pro': {'input': 0.8, 'output': 8, 'cny': True},
    'seed-1.6': {'input': 0.8, 'output': 8, 'cny': True},
    'seed-1.8': {'input': 0.8, 'output': 8, 'cny': True},
    'seed-2.0-pro': {'input': 3.2, 'output': 16, 'cny': True},
    # Qwen (CNY, 0-128K 档)
    'qwen3-max': {'input': 2.5, 'output': 10, 'cny': True},
    'qwen3.5-plus': {'input': 0.8, 'output': 4.8, 'cny': True},
    'qwen3.5-397b': {'input': 0.8, 'output': 4.8, 'cny': True},  # 开源版，与 plus 同价
    # Longcat (美团) —— 价格暂设 0
    'flash-chat':          {'input': 0, 'output': 0, 'cny': True},
    'flash-thinking':      {'input': 0, 'output': 0, 'cny': True},
    'flash-thinking-2601': {'input': 0, 'output': 0, 'cny': True},
    'flash-lite':          {'input': 0, 'output': 0, 'cny': True},
}

# OpenRouter 价格缓存（内存级，进程结束即释放）
_openrouter_pricing_cache = {}


def _fetch_openrouter_pricing():
    """从 OpenRouter API 拉取所有模型价格，缓存到内存"""
    if _openrouter_pricing_cache:
        return
    try:
        resp = requests.get("https://openrouter.ai/api/v1/models", timeout=10)
        for m in resp.json().get("data", []):
            p = m.get("pricing", {})
            if p.get("prompt") and p.get("completion"):
                _openrouter_pricing_cache[m["id"]] = {
                    'input': float(p["prompt"]) * 1_000_000,
                    'output': float(p["completion"]) * 1_000_000,
                }
    except Exception:
        pass


class CostTracker:
    """LLM调用计费追踪"""

    def __init__(self):
        self.calls: list[dict] = []
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost_cny = 0.0

    def record(self, model: str, input_tokens: int, output_tokens: int):
        pricing = PRICING.get(model) or _openrouter_pricing_cache.get(model)
        if not pricing:
            return  # 无价格信息则跳过计费
        rate = 1 if pricing.get('cny') else EX_RATE
        input_cost = pricing['input'] * input_tokens / 1_000_000 * rate
        output_cost = pricing['output'] * output_tokens / 1_000_000 * rate
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
            'claude-45-mid': 'claude-sonnet-4-5-20250929',
            'claude-46-big': 'claude-opus-4-6',
        },
        'openai': {
            'gpt-4.1': 'gpt-4.1-2025-04-14',
            'gpt-4.1-mini': 'gpt-4.1-mini-2025-04-14',
            'gpt-5.2': 'gpt-5.2',
            'gpt-5.2-chat': 'gpt-5.2-chat-latest',
        },
        'gemini': {
            '2.5-Flash': 'gemini-2.5-flash',
            '2.5-Pro': 'gemini-2.5-pro',
            '3-Pro': 'gemini-3-pro-preview',
            '3.1-Pro': 'gemini-3.1-pro-preview',
            '3-Flash': 'gemini-3-flash-preview',
        },
        'deepseek': {
            'v3': 'deepseek-chat',
        },
        'moonshot': {
            'k2.5': 'kimi-k2.5',
        },
        'doubao': {
            'seed-1.5-pro': 'doubao-1-5-pro-32k-250115',
            'seed-1.6': 'doubao-seed-1-6-251015',
            'seed-1.8': 'doubao-seed-1-8-251228',
            'seed-2.0-pro': 'doubao-seed-2-0-pro-260215',
        },
        'qwen': {
            'qwen3-max': 'qwen3-max',
            'qwen3.5-plus': 'qwen3.5-plus',
            'qwen3.5-397b': 'qwen3.5-397b-a17b',
        },
        'longcat': {
            'flash-chat':          'LongCat-Flash-Chat',
            'flash-thinking':      'LongCat-Flash-Thinking',
            'flash-thinking-2601': 'LongCat-Flash-Thinking-2601',
            'flash-lite':          'LongCat-Flash-Lite',
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
            result = self._call_anthropic(system_prompt, user_prompt, model, temperature, thinking)
        elif provider == 'openai':
            result = self._call_openai(system_prompt, user_prompt, model, temperature, thinking)
        elif provider == 'gemini':
            result = self._call_gemini(system_prompt, user_prompt, model, temperature, thinking)
        elif provider == 'deepseek':
            result = self._call_deepseek(system_prompt, user_prompt, model, temperature, thinking)
        elif provider == 'moonshot':
            result = self._call_moonshot(system_prompt, user_prompt, model, temperature, thinking)
        elif provider == 'doubao':
            result = self._call_doubao(system_prompt, user_prompt, model, temperature, thinking)
        elif provider == 'qwen':
            result = self._call_qwen(system_prompt, user_prompt, model, temperature, thinking)
        elif provider == 'openrouter':
            result = self._call_openrouter(system_prompt, user_prompt, model, temperature, thinking)
        elif provider == 'longcat':
            result = self._call_longcat(system_prompt, user_prompt, model, temperature, thinking)
        else:
            raise ValueError(f"未知的LLM提供商：{provider}")

        # 记录计费
        self.cost_tracker.record(
            model=result['model'],
            input_tokens=result['input_tokens'],
            output_tokens=result['output_tokens'],
        )
        return result

    def _call_anthropic(self, system_prompt, user_prompt, model_name, temperature, thinking=False):
        import anthropic
        if 'anthropic' not in self._clients:
            api_key = os.getenv('ANTHROPIC_API_KEY')
            if not api_key:
                raise ValueError("缺少 ANTHROPIC_API_KEY 环境变量")
            self._clients['anthropic'] = anthropic.Anthropic(api_key=api_key)

        client = self._clients['anthropic']
        model_id = self.PROVIDER_MODELS['anthropic'].get(model_name, model_name)

        kwargs = {
            'model': model_id,
            'max_tokens': 8192,
            'system': system_prompt,
            'messages': [{"role": "user", "content": user_prompt}],
        }

        if thinking:
            # extended thinking模式：temperature必须为1，budget_tokens < max_tokens
            kwargs['max_tokens'] = 16000
            kwargs['temperature'] = 1
            kwargs['thinking'] = {"type": "enabled", "budget_tokens": 8000}
        else:
            kwargs['temperature'] = temperature

        message = client.messages.create(**kwargs)

        # extended thinking时content可能包含thinking block，取最后的text block
        content = ''
        thinking_text = ''
        for block in message.content:
            if block.type == 'thinking':
                thinking_text = block.thinking
            elif block.type == 'text':
                content = block.text

        return {
            'model': model_name,
            'content': content,
            'thinking': thinking_text,
            'input_tokens': message.usage.input_tokens,
            'output_tokens': message.usage.output_tokens,
        }

    def _call_openai(self, system_prompt, user_prompt, model_name, temperature, thinking=False):
        from openai import OpenAI
        if 'openai' not in self._clients:
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                raise ValueError("缺少 OPENAI_API_KEY 环境变量")
            self._clients['openai'] = OpenAI(api_key=api_key)

        client = self._clients['openai']
        model_id = self.PROVIDER_MODELS['openai'].get(model_name, model_name)

        kwargs = {
            'model': model_id,
            'messages': [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        if model_name.startswith('gpt-5'):
            # GPT-5.x 系列：必须用 max_completion_tokens，temperature 只支持默认值1
            kwargs['max_completion_tokens'] = 8192
            if thinking:
                # GPT-5.2-chat 只支持 medium，GPT-5.2 支持 high/medium/low
                if isinstance(thinking, str):
                    effort = thinking
                else:
                    effort = 'medium' if model_name == 'gpt-5.2-chat' else 'high'
                kwargs['reasoning_effort'] = effort
        else:
            kwargs['temperature'] = temperature
            kwargs['max_tokens'] = 4096

        response = client.chat.completions.create(**kwargs)

        return {
            'model': model_name,
            'content': response.choices[0].message.content,
            'thinking': '',  # GPT-5 reasoning 不对外暴露
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
        if model_name.startswith('3-') or model_name.startswith('3.'):
            # 3/3.1系列只支持thinking_level，不能完全关闭
            # 3-Flash: minimal/low/medium/high, 3-Pro/3.1-Pro: low/high
            if isinstance(thinking, str):
                level = thinking
            elif thinking:
                level = 'high'
            else:
                level = 'minimal' if 'Flash' in model_name else 'low'
            # include_thoughts=True 才会在 parts 中返回思考块
            thinking_config = types.ThinkingConfig(thinking_level=level, include_thoughts=bool(thinking))
        else:
            if thinking:
                thinking_config = types.ThinkingConfig(
                    thinking_budget=-1, include_thoughts=True,
                )

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

        # candidates_token_count 不含 thinking tokens，需额外加上
        thoughts = response.usage_metadata.thoughts_token_count or 0
        output_tokens = response.usage_metadata.candidates_token_count or 0
        output_tokens += thoughts

        # 提取 thinking 内容（part.thought 为 truthy 时表示思考块）
        thinking_text = ''
        try:
            parts = response.candidates[0].content.parts or []
            for part in parts:
                if getattr(part, 'thought', False):
                    thinking_text = part.text or ''
                    break
        except (AttributeError, IndexError):
            pass

        return {
            'model': model_name,
            'content': response.text or '',
            'thinking': thinking_text,
            'input_tokens': response.usage_metadata.prompt_token_count,
            'output_tokens': output_tokens,
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

        msg = response.choices[0].message
        return {
            'model': model_name,
            'content': msg.content,
            'thinking': getattr(msg, 'reasoning_content', '') or '',
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

        msg = response.choices[0].message
        return {
            'model': model_name,
            'content': msg.content,
            'thinking': getattr(msg, 'reasoning_content', '') or '',
            'input_tokens': response.usage.prompt_tokens,
            'output_tokens': response.usage.completion_tokens,
        }

    def _call_doubao(self, system_prompt, user_prompt, model_name, temperature, thinking=False):
        from openai import OpenAI
        if 'doubao' not in self._clients:
            api_key = os.getenv('ARK_API_KEY')
            if not api_key:
                raise ValueError("缺少 ARK_API_KEY 环境变量")
            self._clients['doubao'] = OpenAI(
                api_key=api_key,
                base_url="https://ark.cn-beijing.volces.com/api/v3",
            )

        client = self._clients['doubao']
        model_id = self.PROVIDER_MODELS['doubao'].get(model_name, model_name)

        # thinking模式：通过extra_body传递
        extra = {}
        if thinking:
            extra['extra_body'] = {"thinking": {"type": "enabled"}}

        response = client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=8192,
            **extra,
        )

        msg = response.choices[0].message
        content = msg.content or ''
        thinking = ''

        # 豆包的thinking内容可能在content中用<think>标签包裹
        if content and '<think>' in content and '</think>' in content:
            import re
            think_match = re.search(r'<think>(.*?)</think>', content, re.DOTALL)
            if think_match:
                thinking = think_match.group(1).strip()
                # 移除thinking部分，只保留实际回复
                content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()

        # 备用：尝试从reasoning_content获取
        if not thinking:
            thinking = getattr(msg, 'reasoning_content', '') or ''

        return {
            'model': model_name,
            'content': content,
            'thinking': thinking,
            'input_tokens': response.usage.prompt_tokens,
            'output_tokens': response.usage.completion_tokens,
        }

    def _call_qwen(self, system_prompt, user_prompt, model_name, temperature, thinking=False):
        from openai import OpenAI
        if 'qwen' not in self._clients:
            api_key = os.getenv('DASHSCOPE_API_KEY')
            if not api_key:
                raise ValueError("缺少 DASHSCOPE_API_KEY 环境变量")
            self._clients['qwen'] = OpenAI(
                api_key=api_key,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            )

        client = self._clients['qwen']
        model_id = self.PROVIDER_MODELS['qwen'].get(model_name, model_name)

        extra = {}
        if thinking:
            extra['extra_body'] = {"enable_thinking": True}
        else:
            extra['extra_body'] = {"enable_thinking": False}

        # thinking 模式必须用 stream，否则 Qwen API 会因生成时间过长返回 400 超时
        if thinking:
            stream = client.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=8192,
                stream=True,
                stream_options={"include_usage": True},
                **extra,
            )
            content_parts = []
            thinking_parts = []
            input_tokens = 0
            output_tokens = 0
            for chunk in stream:
                if chunk.usage:
                    input_tokens = chunk.usage.prompt_tokens or 0
                    output_tokens = chunk.usage.completion_tokens or 0
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if getattr(delta, 'reasoning_content', None):
                    thinking_parts.append(delta.reasoning_content)
                if delta.content:
                    content_parts.append(delta.content)
            return {
                'model': model_name,
                'content': ''.join(content_parts),
                'thinking': ''.join(thinking_parts),
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
            }

        response = client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=8192,
            **extra,
        )

        msg = response.choices[0].message
        return {
            'model': model_name,
            'content': msg.content or '',
            'thinking': getattr(msg, 'reasoning_content', '') or '',
            'input_tokens': response.usage.prompt_tokens,
            'output_tokens': response.usage.completion_tokens,
        }

    def _call_openrouter(self, system_prompt, user_prompt, model_name, temperature, thinking=False):
        import time as _time
        from openai import OpenAI, RateLimitError, APIConnectionError
        if 'openrouter' not in self._clients:
            api_key = os.getenv('OPENROUTER_API_KEY')
            if not api_key:
                raise ValueError("缺少 OPENROUTER_API_KEY 环境变量")
            self._clients['openrouter'] = OpenAI(
                api_key=api_key,
                base_url="https://openrouter.ai/api/v1",
            )

        # 首次调用拉取价格缓存
        _fetch_openrouter_pricing()

        client = self._clients['openrouter']
        # model_name 直接透传（如 google/gemini-2.5-flash）
        extra = {}
        if thinking:
            # reasoning: 启用推理模式
            # include_reasoning: true 返回思考过程，通过 reasoning_content 字段获取
            extra['extra_body'] = {"reasoning": {"enabled": True}, "include_reasoning": True}

        # 重试机制：429/连接错误 → 指数退避重试
        max_retries = 5
        for attempt in range(max_retries):
            try:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=temperature,
                    max_tokens=8192,
                    **extra,
                )
                msg = response.choices[0].message
                content = msg.content or ''
                extras = getattr(msg, 'model_extra', None) or {}

                # 1) reasoning_content 属性（部分 SDK 版本直接暴露）
                thinking = getattr(msg, 'reasoning_content', '') or ''

                # 2) model_extra['reasoning']（Claude/GPT/Step 等通过此字段返回）
                if not thinking:
                    thinking = extras.get('reasoning', '') or ''

                # 3) reasoning_details 结构化字段（更可靠的 fallback）
                if not thinking:
                    details = extras.get('reasoning_details') or []
                    for d in details:
                        text = (d.get('text') or d.get('summary') or '') if isinstance(d, dict) else ''
                        if text:
                            thinking = text
                            break

                # 4) <think> 标签混入 content（Qwen3 等模型）
                if not thinking and content and '<think>' in content and '</think>' in content:
                    import re
                    think_match = re.search(r'<think>(.*?)</think>', content, re.DOTALL)
                    if think_match:
                        thinking = think_match.group(1).strip()
                        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()

                return {
                    'model': model_name,
                    'content': content,
                    'thinking': thinking,
                    'input_tokens': response.usage.prompt_tokens,
                    'output_tokens': response.usage.completion_tokens,
                }
            except (RateLimitError, APIConnectionError) as e:
                if attempt == max_retries - 1:
                    raise
                wait = 2 ** attempt + 1  # 2, 3, 5, 9, 17s
                _time.sleep(wait)

    def _call_longcat(self, system_prompt, user_prompt, model_name, temperature, thinking=False):
        from openai import OpenAI
        if 'longcat' not in self._clients:
            api_key = os.getenv('LONGCAT_API_KEY')
            if not api_key:
                raise ValueError("缺少 LONGCAT_API_KEY 环境变量")
            self._clients['longcat'] = OpenAI(
                api_key=api_key,
                base_url="https://api.longcat.chat/openai",
            )

        client = self._clients['longcat']
        model_id = self.PROVIDER_MODELS['longcat'].get(model_name, model_name)

        extra = {}
        if thinking:
            extra['extra_body'] = {"enable_thinking": True}

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

        msg = response.choices[0].message
        content = msg.content or ''

        # 提取 thinking：先尝试 reasoning_content，再尝试 <think> 标签
        thinking_text = getattr(msg, 'reasoning_content', '') or ''
        if not thinking_text and '<think>' in content and '</think>' in content:
            import re
            m = re.search(r'<think>(.*?)</think>', content, re.DOTALL)
            if m:
                thinking_text = m.group(1).strip()
                content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()

        return {
            'model': model_name,
            'content': content,
            'thinking': thinking_text,
            'input_tokens': response.usage.prompt_tokens,
            'output_tokens': response.usage.completion_tokens,
        }
