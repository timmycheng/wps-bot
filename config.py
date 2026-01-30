# encoding:utf-8
"""
WPS Bot 配置管理模块
"""

import json
import logging
import os
from typing import Any, Dict


# 默认配置
DEFAULT_CONFIG = {
    # WPS 协作平台配置
    "wps_app_id": "",  # WPS应用ID
    "wps_app_secret": "",  # WPS应用Secret
    "wps_encrypt_key": "",  # WPS消息加密密钥（可选，如开启消息加密则必填）
    "wps_base_url": "https://openapi.wps.cn",  # WPS协作平台基础URL（私有化部署可修改）
    
    # 事件订阅配置
    "event_callback_url": "",  # 事件回调URL（用于接收WPS推送的消息）
    
    # 服务配置
    "port": 8080,  # 服务端口
    "host": "0.0.0.0",  # 服务监听地址
    
    # LLM 配置 (OpenAI 标准接口)
    "llm_api_key": "",  # LLM API Key
    "llm_api_base": "http://localhost:8000/v1",  # LLM API Base URL (私有化网关地址)
    "llm_model": "gpt-3.5-turbo",  # 默认模型
    
    # 对话配置
    "single_chat_prefix": [""],  # 私聊触发前缀，默认无前缀
    "single_chat_reply_prefix": "",  # 私聊回复前缀
    "group_chat_prefix": ["@机器人"],  # 群聊触发前缀
    "group_at_off": False,  # 是否关闭群聊@触发
    "group_name_white_list": ["ALL_GROUP"],  # 群聊白名单
    "conversation_max_tokens": 4000,  # 最大上下文token数
    "expires_in_seconds": 3600,  # 会话过期时间
    
    # 人格描述
    "character_desc": "你是WPS智能助手，一个由大型语言模型驱动的AI助手，可以帮助用户解答问题、处理文档、编写代码等。",
    
    # LLM 参数
    "temperature": 0.7,
    "top_p": 1.0,
    "frequency_penalty": 0.0,
    "presence_penalty": 0.0,
    "request_timeout": 120,  # 请求超时时间
    "max_tokens": 2048,  # 最大生成token数
    
    # 日志配置
    "debug": False,
    "log_level": "INFO",
}


class Config(dict):
    """配置类，支持字典式访问"""
    
    def __init__(self, d: Dict[str, Any] = None):
        super().__init__()
        if d is None:
            d = {}
        # 使用默认配置初始化
        for k, v in DEFAULT_CONFIG.items():
            self[k] = v
        # 覆盖用户配置
        for k, v in d.items():
            if k in DEFAULT_CONFIG:
                self[k] = v
            else:
                logging.warning(f"[Config] Unknown config key: {k}")
    
    def __getitem__(self, key):
        return super().__getitem__(key)
    
    def __setitem__(self, key, value):
        super().__setitem__(key, value)
    
    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default


# 全局配置实例
_config = Config()


def load_config(config_path: str = "config.json") -> Config:
    """加载配置文件"""
    global _config
    
    # 1. 尝试从配置文件加载
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                file_config = json.load(f)
                _config = Config(file_config)
            logging.info(f"[Config] Loaded from {config_path}")
        except Exception as e:
            logging.error(f"[Config] Error loading {config_path}: {e}")
    else:
        logging.warning(f"[Config] {config_path} not found, using default config")
    
    # 2. 环境变量覆盖（便于Docker部署）
    env_mappings = {
        "WPS_APP_ID": "wps_app_id",
        "WPS_APP_SECRET": "wps_app_secret",
        "WPS_ENCRYPT_KEY": "wps_encrypt_key",
        "WPS_BASE_URL": "wps_base_url",
        "EVENT_CALLBACK_URL": "event_callback_url",
        "LLM_API_KEY": "llm_api_key",
        "LLM_API_BASE": "llm_api_base",
        "LLM_MODEL": "llm_model",
        "PORT": "port",
        "HOST": "host",
        "DEBUG": "debug",
        "LOG_LEVEL": "log_level",
    }
    
    for env_key, config_key in env_mappings.items():
        value = os.environ.get(env_key)
        if value is not None:
            # 类型转换
            if config_key in ["port"]:
                value = int(value)
            elif config_key in ["debug"]:
                value = value.lower() in ["true", "1", "yes"]
            elif config_key in ["temperature", "top_p", "frequency_penalty", "presence_penalty"]:
                value = float(value)
            _config[config_key] = value
            logging.info(f"[Config] Override {config_key} from environment variable {env_key}")
    
    # 3. 设置日志级别
    if _config.get("debug"):
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        log_level = _config.get("log_level", "INFO")
        logging.getLogger().setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    # 4. 验证必要配置
    required_configs = ["wps_app_id", "wps_app_secret"]
    for key in required_configs:
        if not _config.get(key):
            logging.warning(f"[Config] Required config '{key}' is not set!")
    
    return _config


def get_config() -> Config:
    """获取全局配置实例"""
    global _config
    return _config


def save_config(config: Config, config_path: str = "config.json"):
    """保存配置到文件"""
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(dict(config), f, ensure_ascii=False, indent=2)
        logging.info(f"[Config] Saved to {config_path}")
    except Exception as e:
        logging.error(f"[Config] Error saving config: {e}")
