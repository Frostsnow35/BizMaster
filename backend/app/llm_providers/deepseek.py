"""
@brief DeepSeek Provider 实现

基于 OpenAI 兼容接口调用 DeepSeek API。
"""

from typing import List, Dict, Any, AsyncIterator
from openai import AsyncOpenAI
from app.llm_providers.base import BaseLLMProvider
from app.core.config import config, decrypt_api_key


class DeepSeekProvider(BaseLLMProvider):
    """DeepSeek API Provider"""

    def __init__(self):
        api_key = decrypt_api_key(config.deepseek.api_key)
        if not api_key:
            raise ValueError("DeepSeek API Key 未配置，请在设置页面填写或设置环境变量 DEEPSEEK_API_KEY")

        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=config.deepseek.base_url,
        )
        self._default_model = config.llm.default_model

    async def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        model = kwargs.pop("model", self._default_model)
        temperature = kwargs.pop("temperature", config.llm.temperature)
        max_tokens = kwargs.pop("max_tokens", config.llm.max_tokens)

        response = await self._client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        return response.choices[0].message.content or ""

    async def chat_with_tools(
        self, messages: List[Dict[str, str]], tools: List[Dict[str, Any]], **kwargs
    ) -> Dict[str, Any]:
        model = kwargs.pop("model", self._default_model)
        temperature = kwargs.pop("temperature", config.llm.temperature)

        response = await self._client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            temperature=temperature,
            **kwargs,
        )

        choice = response.choices[0]
        message = choice.message

        result = {"content": message.content}

        if message.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                }
                for tc in message.tool_calls
            ]

        return result

    async def stream_chat(
        self, messages: List[Dict[str, str]], **kwargs
    ) -> AsyncIterator[str]:
        model = kwargs.pop("model", self._default_model)
        temperature = kwargs.pop("temperature", config.llm.temperature)
        max_tokens = kwargs.pop("max_tokens", config.llm.max_tokens)

        stream = await self._client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            **kwargs,
        )

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
