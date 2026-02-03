# encoding:utf-8
"""
WPS 消息类
封装WPS协作平台的消息格式

文档：https://365.kdocs.cn/3rd/open/documents/app-integration-dev/wps365/server/im/event/receive-msg
"""

from typing import Any, Dict, List, Optional

from bridge.context import ContextType
from common.logger import logger


class WPSMessage:
    """WPS消息"""
    
    def __init__(self, event_data: Dict[str, Any]):
        """
        初始化WPS消息
        
        解密后的事件数据结构:
        {
            "chat": {"id": "xxx", "type": "p2p/group"},
            "company_id": "xxx",
            "message": {"id": "xxx", "type": "text", "content": {...}},
            "send_time": 1234567890,
            "sender": {"id": "xxx", "type": "user"},
            "mentions": [...]  // 可选
        }
        
        :param event_data: 解密后的事件数据（包含 chat, message, sender）
        """
        self.raw_data = event_data
        
        logger.debug(f"[WPSMessage] Raw event data: {event_data}")
        
        # 提取嵌套的 message 对象
        msg_data = event_data.get("message", {})
        if not isinstance(msg_data, dict):
            msg_data = {}
        
        # 提取 chat 对象
        chat_data = event_data.get("chat", {})
        if not isinstance(chat_data, dict):
            chat_data = {}
        
        # 提取 sender 对象
        sender_data = event_data.get("sender", {})
        if not isinstance(sender_data, dict):
            sender_data = {}
        
        # 消息基本信息（从 message 对象）
        self.msg_id = msg_data.get("id", "")
        self.msg_type = msg_data.get("type", "")
        self.create_time = event_data.get("send_time", 0)
        
        # 聊天信息（从 chat 对象）
        self.chat_id = chat_data.get("id", "")
        # chat.type: p2p(私聊), group(群聊)
        self.chat_type = chat_data.get("type", "")
        
        # 发送者信息（从 sender 对象）
        self.from_user_id = sender_data.get("id", "")
        self.from_user_name = sender_data.get("name", "")
        
        # 消息内容（从 message.content）
        self.content = self._parse_content(msg_data.get("content", {}))
        
        # @信息（从顶层 event_data 或 message 中）
        mentions = event_data.get("mentions", []) or msg_data.get("mentions", [])
        self.at_list: List[Dict] = mentions if isinstance(mentions, list) else []
        self.is_at = len(self.at_list) > 0
        
        # 判断消息类型
        self.ctype = self._get_context_type()
        # chat.type: p2p(私聊), group(群聊)
        self.is_group = self.chat_type == "group"
        
        logger.debug(f"[WPSMessage] Parsed: id={self.msg_id}, type={self.msg_type}")
        logger.debug(f"[WPSMessage] chat_id={self.chat_id}, chat_type={self.chat_type}, is_group={self.is_group}")
        logger.debug(f"[WPSMessage] from_user_id={self.from_user_id}, from_user_name={self.from_user_name}")
        logger.debug(f"[WPSMessage] content={self.content[:50] if self.content else 'EMPTY'}...")
        logger.debug(f"[WPSMessage] is_at={self.is_at}, at_list={self.at_list}")
    
    def _parse_content(self, content_obj: Any) -> str:
        """
        解析消息内容
        
        根据文档，消息 content 结构为：
        {
            "text": {"content": "xxx"},
            "image": {...},
            "file": {...},
            "rich_text": {...}
        }
        """
        if not isinstance(content_obj, dict):
            return str(content_obj) if content_obj else ""
        
        logger.debug(f"[WPSMessage] Parsing content: {content_obj}")
        
        msg_type = self.msg_type
        
        if msg_type == "text":
            # 文本消息: content.text.content
            text_obj = content_obj.get("text", {})
            if isinstance(text_obj, dict):
                content = text_obj.get("content", "")
                logger.debug(f"[WPSMessage] Text content: {content[:100] if content else 'EMPTY'}")
                return content
            else:
                return str(text_obj) if text_obj else ""
        
        elif msg_type == "rich_text":
            # 富文本消息: content.rich_text.elements
            rich_text_obj = content_obj.get("rich_text", {})
            if isinstance(rich_text_obj, dict):
                elements = rich_text_obj.get("elements", [])
                return self._parse_rich_text_elements(elements)
            return "[富文本]"
        
        elif msg_type == "image":
            return "[图片]"
        
        elif msg_type == "file":
            file_obj = content_obj.get("file", {})
            if isinstance(file_obj, dict):
                local_obj = file_obj.get("local", {})
                if isinstance(local_obj, dict):
                    return f"[文件] {local_obj.get('name', '')}"
                cloud_obj = file_obj.get("cloud", {})
                if isinstance(cloud_obj, dict):
                    return f"[云文档] {cloud_obj.get('id', '')}"
            return "[文件]"
        
        elif msg_type == "audio":
            return "[语音]"
        
        elif msg_type == "video":
            return "[视频]"
        
        else:
            # 未知类型，返回整个 content 的字符串表示
            return str(content_obj) if content_obj else ""
    
    def _parse_rich_text_elements(self, elements: List[Dict]) -> str:
        """解析富文本元素"""
        if not elements:
            return ""
        
        result = []
        for elem in elements:
            elem_type = elem.get("type", "")
            
            if elem_type == "text":
                # 纯文本
                text_content = elem.get("text_content", {})
                if isinstance(text_content, dict):
                    result.append(text_content.get("content", ""))
            
            elif elem_type == "style_text_content":
                # 样式文本
                style_content = elem.get("style_text_content", {})
                if isinstance(style_content, dict):
                    result.append(style_content.get("text", ""))
            
            elif elem_type == "mention":
                # @某人
                mention_content = elem.get("mention_content", {})
                if isinstance(mention_content, dict):
                    text = mention_content.get("text", "")
                    result.append(text)
            
            elif elem_type == "nl":
                # 换行
                result.append("\n")
            
            elif elem_type == "image":
                result.append("[图片]")
        
        return "".join(result)
    
    def _get_context_type(self) -> ContextType:
        """获取上下文类型"""
        msg_type = self.msg_type
        
        if msg_type == "text":
            return ContextType.TEXT
        elif msg_type == "rich_text":
            return ContextType.TEXT
        elif msg_type == "image":
            return ContextType.IMAGE
        elif msg_type == "file":
            return ContextType.FILE
        elif msg_type == "audio":
            return ContextType.VOICE
        else:
            return ContextType.TEXT
    
    def get_at_users(self) -> List[str]:
        """获取被@的用户列表"""
        return [at.get("identity", {}).get("id", "") for at in self.at_list if isinstance(at, dict)]
    
    def is_at_user(self, user_id: str) -> bool:
        """是否@了指定用户"""
        return user_id in self.get_at_users()
    
    def __str__(self):
        return (f"WPSMessage(id={self.msg_id}, type={self.msg_type}, "
                f"chat={self.chat_id}({self.chat_type}), from={self.from_user_name}, "
                f"content={self.content[:30] if self.content else 'EMPTY'}...)")
