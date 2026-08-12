"""
@brief LLM 调用入口封装

从配置读取 Provider 类型，提供统一的 LLM 调用接口。
"""

from typing import AsyncIterator
from app.core.config import config
from app.llm_providers.registry import ProviderRegistry
from app.llm_providers.base import BaseLLMProvider


_llm_instance: BaseLLMProvider | None = None


def get_llm() -> BaseLLMProvider:
    """
    @brief 获取当前配置的 LLM Provider 实例（懒加载单例）
    @return Provider 实例
    """
    global _llm_instance
    if _llm_instance is None:
        provider_name = config.llm.provider
        _llm_instance = ProviderRegistry.get(provider_name)
    return _llm_instance


def reset_llm() -> None:
    """
    @brief 重置 LLM 实例（切换 Provider 后调用）
    """
    global _llm_instance
    _llm_instance = None
