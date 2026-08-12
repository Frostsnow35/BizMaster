import os
import hashlib
import base64
from cryptography.fernet import Fernet

import yaml


class _ConfigDict(dict):
    """支持点号访问的字典包装器。"""

    def __getattr__(self, name: str):
        try:
            value = self[name]
        except KeyError:
            raise AttributeError(f"配置项 '{name}' 不存在")
        if isinstance(value, dict):
            value = _ConfigDict(value)
            self[name] = value
        return value

    def __setattr__(self, name: str, value) -> None:
        self[name] = value

    def __delattr__(self, name: str) -> None:
        try:
            del self[name]
        except KeyError:
            raise AttributeError(f"配置项 '{name}' 不存在")


class Config:
    """应用配置单例类。

    加载 config/settings.yaml 并通过环境变量覆盖。
    环境变量名映射规则: 嵌套 key 的 UPPER_CASE 形式，如 APP_DEBUG、DEEPSEEK_API_KEY。
    """

    _instance = None
    _initialized = False

    def __new__(cls) -> "Config":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if Config._initialized:
            return
        Config._initialized = True
        self._load()

    def reload(self) -> None:
        """重新加载 YAML 配置（用于配置热更新，如 API Key 变更后）"""
        self._load()

    def _load(self) -> None:
        """加载 YAML 并构建 _ConfigDict"""
        self._raw = self._load_yaml()
        self._apply_env_overrides(self._raw)
        self._data = _ConfigDict(self._raw)

    def _load_yaml(self) -> dict:
        """从 YAML 文件加载原始配置。"""
        # core/config.py -> app/ -> backend/ -> config/settings.yaml
        config_dir = os.path.dirname(os.path.abspath(__file__))  # .../backend/app/core
        backend_dir = os.path.dirname(os.path.dirname(config_dir))  # .../backend
        yaml_path = os.path.join(backend_dir, "config", "settings.yaml")

        with open(yaml_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _apply_env_overrides(self, data: dict, prefix: str = "") -> None:
        """递归遍历配置，用环境变量覆盖值。"""
        for key, value in data.items():
            env_key = f"{prefix}{key}".upper() if prefix else key.upper()
            if isinstance(value, dict):
                self._apply_env_overrides(value, f"{env_key}_")
            elif isinstance(value, bool):
                env_val = os.environ.get(env_key)
                if env_val is not None:
                    data[key] = env_val.lower() in ("1", "true", "yes")
            elif isinstance(value, int):
                env_val = os.environ.get(env_key)
                if env_val is not None:
                    data[key] = int(env_val)
            elif isinstance(value, float):
                env_val = os.environ.get(env_key)
                if env_val is not None:
                    data[key] = float(env_val)
            elif isinstance(value, list):
                env_val = os.environ.get(env_key)
                if env_val is not None:
                    data[key] = [item.strip() for item in env_val.split(",") if item.strip()]
            else:
                env_val = os.environ.get(env_key)
                if env_val is not None:
                    data[key] = env_val

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(f"'{type(self).__name__}' 没有属性 '{name}'")
        try:
            return getattr(self._data, name)
        except AttributeError:
            raise AttributeError(f"配置项 '{name}' 不存在")


# 全局单例实例
config = Config()


# ── API Key 加密/解密 ──

def _get_cipher() -> Fernet:
    """基于机器标识生成确定性加密密钥"""
    machine_id = os.environ.get("COMPUTERNAME", os.environ.get("USERNAME", "default"))
    key_material = hashlib.sha256(f"ecom-agent-salt-{machine_id}".encode()).digest()
    key = base64.urlsafe_b64encode(key_material)
    return Fernet(key)


def encrypt_api_key(plain_text: str) -> str:
    """加密 API Key，返回 Base64 密文"""
    if not plain_text:
        return ""
    cipher = _get_cipher()
    encrypted = cipher.encrypt(plain_text.encode("utf-8"))
    return base64.urlsafe_b64encode(encrypted).decode()


def decrypt_api_key(encrypted_b64: str) -> str:
    """解密 API Key，返回明文"""
    if not encrypted_b64:
        return ""
    try:
        cipher = _get_cipher()
        encrypted = base64.urlsafe_b64decode(encrypted_b64.encode())
        return cipher.decrypt(encrypted).decode("utf-8")
    except Exception:
        # 解密失败（旧数据未加密等），返回原文
        return encrypted_b64
