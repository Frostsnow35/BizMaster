"""
@brief Provider 注册与工厂模块

支持动态注册和获取 LLM Provider 实例。
"""

from typing import Dict, Type
from app.llm_providers.base import BaseLLMProvider
from app.llm_providers.deepseek import DeepSeekProvider


class ProviderRegistry:
    """LLM Provider 注册表"""

    _providers: Dict[str, Type[BaseLLMProvider]] = {
        "deepseek": DeepSeekProvider,
    }

    @classmethod
    def register(cls, name: str, provider_cls: Type[BaseLLMProvider]) -> None:
        """
        @brief 注册新的 Provider
        @param name Provider 名称
        @param provider_cls Provider 类
        """
        cls._providers[name] = provider_cls

    @classmethod
    def get(cls, name: str) -> BaseLLMProvider:
        """
        @brief 获取 Provider 实例
        @param name Provider 名称
        @return Provider 实例
        @throws ValueError 如果 Provider 不存在
        """
        provider_cls = cls._providers.get(name)
        if provider_cls is None:
            available = ", ".join(cls._providers.keys())
            raise ValueError(f"未知的 LLM Provider: {name}，可用: {available}")
        return provider_cls()

    @classmethod
    def list_providers(cls) -> list:
        """列出所有已注册的 Provider 名称"""
        return list(cls._providers.keys())
