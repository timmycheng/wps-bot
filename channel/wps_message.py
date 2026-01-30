# encoding:utf-8
"""
WPS 消息类
封装WPS协作平台的消息格式
"""

from typing import Any, Dict, List, Optional

from bridge.context import ContextType


class WPSMessage:
    """WPS消息"""
    
    def __init__(self, msg_data: Dict[str, Any]):
        """
        初始化WPS消息
        
        :param msg_data: 原始消息数据
        """
        self.raw_data = msg_data
        
        # 基本信息
        self.msg_id = msg_data.get("msg_id", "")
        self.msg_type = msg_data.get("msg_type", "")
        self.create_time = msg_data.get("create_time", 0)
        
        # 聊天信息
        self.chat_id = msg_data.get("chat_id", "")
        self.chat_type = msg_data.get("chat_type", "")  # "single" 或 "group"
        
        # 发送者信息
        self.from_user_id = msg_data.get("from_user_id", "")
        self.from_user_name = msg_data.get("from_user_name", "")
        
        # 消息内容
        self.content = self._parse_content(msg_data)
        
        # @信息
        self.at_list: List[Dict] = msg_data.get("at_list", [])
        self.is_at = len(self.at_list) > 0
        
        # 判断消息类型
        self.ctype = self._get_context_type()
        self.is_group = self.chat_type == "group"
    
    def _parse_content(self, msg_data: Dict) -> str:
        """解析消息内容"""
        msg_type = msg_data.get("msg_type", "")
        
        if msg_type == "text":
            return msg_data.get("content", "")
        
        elif msg_type == "markdown":
            return msg_data.get("markdown", {}).get("content", "")
        
        elif msg_type == "image":
            return "[图片]"
        
        elif msg_type == "file":
            return f"[文件] {msg_data.get('file_name', '')}"
        
        else:
            return str(msg_data.get("content", ""))
    
    def _get_context_type(self) -> ContextType:
        """获取上下文类型"""
        msg_type = self.msg_type
        
        if msg_type == "text" or msg_type == "markdown":
            return ContextType.TEXT
        elif msg_type == "image":
            return ContextType.IMAGE
        elif msg_type == "file":
            return ContextType.FILE
        else:
            return ContextType.TEXT
    
    def get_at_users(self) -> List[str]:
        """获取被@的用户列表"""
        return [at.get("user_id", "") for at in self.at_list]
    
    def is_at_user(self, user_id: str) -> bool:
        """是否@了指定用户"""
        return user_id in self.get_at_users()
    
    def __str__(self):
        return (f"WPSMessage(id={self.msg_id}, type={self.msg_type}, "
                f"from={self.from_user_name}, content={self.content[:50]}...)")
