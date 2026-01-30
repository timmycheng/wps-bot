# encoding:utf-8
"""
日志模块
"""

import logging
import sys
from logging.handlers import RotatingFileHandler


def setup_logger(name: str = "wps_bot", level: int = logging.INFO) -> logging.Logger:
    """
    设置日志
    :param name: logger名称
    :param level: 日志级别
    :return: logger实例
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 清除已有处理器
    logger.handlers.clear()
    
    # 日志格式
    formatter = logging.Formatter(
        "[%(levelname)s][%(asctime)s][%(filename)s:%(lineno)d] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 文件处理器 (轮转日志，最大10MB，保留5个备份)
    file_handler = RotatingFileHandler(
        "wps_bot.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger


# 全局logger实例
logger = setup_logger()
