"""
@brief LLM Provider 抽象基类

定义统一的 LLM 调用接口，所有 Provider 实现必须继承此类。
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, AsyncIterator


class BaseLLMProvider(ABC):
    """LLM Provider 抽象基类"""

    @abstractmethod
    async def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        @brief 同步对话（非流式）
        @param messages 消息列表 [{"role": "user", "content": "..."}, ...]
        @param kwargs 额外参数（temperature, max_tokens 等）
        @return LLM 回复文本
        """
        ...

    @abstractmethod
    async def chat_with_tools(
        self, messages: List[Dict[str, str]], tools: List[Dict[str, Any]], **kwargs
    ) -> Dict[str, Any]:
        """
        @brief 带工具调用的对话
        @param messages 消息列表
        @param tools 工具定义列表（OpenAI Function Calling 格式）
        @param kwargs 额外参数
        @return {"content": "...", "tool_calls": [...]} 或纯文本回复
        """
        ...

    @abstractmethod
    async def stream_chat(
        self, messages: List[Dict[str, str]], **kwargs
    ) -> AsyncIterator[str]:
        """
        @brief 流式对话
        @param messages 消息列表
        @param kwargs 额外参数
        @yield 增量文本片段
        """
        ...
