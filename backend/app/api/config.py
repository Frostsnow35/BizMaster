"""
@brief 配置管理 API

GET  /api/config — 读取当前 LLM 配置（API Key 脱敏）
POST /api/config — 保存 LLM 配置并持久化到 settings.yaml
"""

import os
import yaml
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.config import config as app_config, encrypt_api_key, decrypt_api_key
from app.core.llm import reset_llm

router = APIRouter(prefix="/api", tags=["config"])


class ConfigResponse(BaseModel):
    """配置读取响应"""
    provider: str
    model: str
    api_key_masked: str  # 脱敏的 API Key
    configured: bool  # 是否已配置可用的 API Key


class ConfigSaveRequest(BaseModel):
    """配置保存请求"""
    provider: str | None = Field(default=None, description="LLM Provider 名称")
    model: str | None = Field(default=None, description="模型名称")
    api_key: str | None = Field(default=None, description="API Key")


def _mask_api_key(key: str) -> str:
    """对 API Key 进行脱敏处理"""
    if not key:
        return "(未配置)"
    if len(key) <= 8:
        return key[:3] + "***"
    return key[:3] + "***" + key[-3:]


def _get_settings_path() -> str:
    """获取 settings.yaml 的绝对路径"""
    api_dir = os.path.dirname(os.path.abspath(__file__))  # .../backend/app/api
    backend_dir = os.path.dirname(os.path.dirname(api_dir))  # .../backend
    return os.path.join(backend_dir, "config", "settings.yaml")


@router.get("/config")
async def get_config():
    """
    @brief 读取当前配置（API Key 脱敏，密文存储不解密）
    """
    provider_name = app_config.llm.provider
    model = app_config.llm.default_model

    raw_config = _load_yaml()
    provider_cfg = raw_config.get(provider_name, {})

    # 尝试从 YAML 读取加密后的 key，解密后脱敏
    encrypted_key = provider_cfg.get("api_key", "")
    plain_key = decrypt_api_key(encrypted_key) if encrypted_key else ""
    if not plain_key:
        plain_key = os.environ.get(f"{provider_name.upper()}_API_KEY", "")
    api_key_masked = _mask_api_key(plain_key)

    return ConfigResponse(
        provider=provider_name,
        model=model,
        api_key_masked=api_key_masked,
        configured=bool(plain_key),
    )


@router.post("/config")
async def save_config(req: ConfigSaveRequest):
    """
    @brief 保存配置并持久化（API Key 加密存储）
    """
    yaml_path = _get_settings_path()
    raw_config = _load_yaml()

    provider_name = req.provider or app_config.llm.provider

    if req.model:
        raw_config["llm"]["default_model"] = req.model

    if req.provider:
        raw_config["llm"]["provider"] = req.provider

    if req.api_key is not None:
        if provider_name not in raw_config:
            raw_config[provider_name] = {}
        # 加密存储
        raw_config[provider_name]["api_key"] = encrypt_api_key(req.api_key)

    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(raw_config, f, allow_unicode=True, default_flow_style=False)

    app_config.reload()
    reset_llm()

    return {"message": "配置已保存（API Key 已加密存储）"}


def _load_yaml() -> dict:
    """加载 settings.yaml 原始内容"""
    with open(_get_settings_path(), "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
