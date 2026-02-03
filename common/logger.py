# encoding:utf-8
"""
日志模块
"""

import logging
import sys
from logging.handlers import RotatingFileHandler

# 标记是否已经初始化（避免重复设置）
_logger_initialized = False


def setup_logger(name: str = "wps_bot", level: int = logging.INFO) -> logging.Logger:
    """
    设置日志
    :param name: logger名称
    :param level: 日志级别
    :return: logger实例
    """
    global _logger_initialized
    
    logger = logging.getLogger(name)
    
    # 如果已经初始化过，只更新日志级别
    if _logger_initialized:
        logger.setLevel(level)
        for handler in logger.handlers:
            handler.setLevel(level)
        return logger
    
    # 首次初始化
    _logger_initialized = True
    
    # 清除已有处理器（防止重复）
    logger.handlers.clear()
    
    # 设置日志级别
    logger.setLevel(level)
    
    # 防止日志消息传播到父logger（避免重复打印）
    logger.propagate = False
    
    # 日志格式
    formatter = logging.Formatter(
        "[%(levelname)s][%(asctime)s][%(filename)s:%(lineno)d] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 文件处理器 (轮转日志，最大10MB，保留5个备份)
    file_handler = RotatingFileHandler(
        "wps_bot.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger


# 全局logger实例（使用默认INFO级别初始化）
logger = setup_logger()
