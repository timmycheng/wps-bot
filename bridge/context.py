# encoding:utf-8
"""
上下文类型定义
"""

from enum import Enum
from typing import Any, Dict


class ContextType(Enum):
    """消息类型"""
    TEXT = 1          # 文本消息
    VOICE = 2         # 语音消息
    IMAGE = 3         # 图片消息
    FILE = 4          # 文件消息
    VIDEO = 5         # 视频消息
    
    IMAGE_CREATE = 10  # 创建图片命令
    JOIN_GROUP = 20    # 加入群聊


class Context:
    """
    消息上下文
    封装消息类型、内容和附加信息
    """
    
    def __init__(self, type: ContextType = None, content: str = None, kwargs: Dict = None):
        self.type = type
        self.content = content
        self.kwargs = kwargs or {}
    
    def __contains__(self, key):
        if key == "type":
            return self.type is not None
        elif key == "content":
            return self.content is not None
        return key in self.kwargs
    
    def __getitem__(self, key):
        if key == "type":
            return self.type
        elif key == "content":
            return self.content
        return self.kwargs[key]
    
    def __setitem__(self, key, value):
        if key == "type":
            self.type = value
        elif key == "content":
            self.content = value
        else:
            self.kwargs[key] = value
    
    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default
    
    def __str__(self):
        return f"Context(type={self.type}, content={self.content}, kwargs={self.kwargs})"
