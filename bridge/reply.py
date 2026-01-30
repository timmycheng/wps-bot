# encoding:utf-8
"""
回复类型定义
"""

from enum import Enum


class ReplyType(Enum):
    """回复类型"""
    TEXT = 1         # 文本回复
    VOICE = 2        # 语音回复
    IMAGE = 3        # 图片回复
    IMAGE_URL = 4    # 图片URL
    ERROR = 5        # 错误信息
    INFO = 6         # 提示信息


class Reply:
    """
    回复消息
    """
    
    def __init__(self, type: ReplyType = None, content: str = None):
        self.type = type
        self.content = content
    
    def __str__(self):
        return f"Reply(type={self.type}, content={self.content})"
