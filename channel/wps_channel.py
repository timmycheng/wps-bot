# encoding:utf-8
"""
WPS 协作平台消息通道
处理来自WPS开放平台的订阅消息推送

文档：https://365.kdocs.cn/3rd/open/documents/app-integration-dev/wps365/server/event-subscription/security-verification
"""

import json
import time
from typing import Dict, Optional

from bot.llm_bot import get_bot
from bridge.context import Context, ContextType
from channel.wps_message import WPSMessage
from common.logger import logger
from config import get_config
from lib.wps_api import get_api_client
from lib.wps_crypto import verify_event_signature, decrypt_event_data


class WPSChannel:
    """
    WPS消息通道
    处理消息的接收和发送
    """
    
    # WPS事件类型
    EVENT_URL_VERIFICATION = "url_verification"
    EVENT_MESSAGE_CREATE = "kso.app_chat.message.create"
    
    def __init__(self):
        self.config = get_config()
        self.bot = get_bot()
        
        # 已处理消息ID缓存（幂等控制）
        self.processed_msgs: Dict[str, float] = {}
        self.msg_cache_expire = 300  # 5分钟过期
        
        # 机器人用户ID
        self.bot_user_id = self.config.get("wps_app_id", "")
        
        logger.info("[WPSChannel] Initialized")
    
    def verify_and_decrypt(self, event_data: Dict) -> Optional[Dict]:
        """
        验证事件签名并解密数据
        
        根据 WPS 文档，事件消息格式：
        {
            "topic": "xxx",
            "operation": "xxx",
            "time": 1234567890,
            "nonce": "xxx",
            "signature": "xxx",
            "encrypted_data": "xxx"
        }
        
        :param event_data: 事件数据
        :return: 解密后的事件数据，验证失败返回 None
        """
        try:
            # 提取必要字段
            topic = event_data.get("topic", "")
            operation = event_data.get("operation", "")
            event_time = event_data.get("time", 0)
            nonce = event_data.get("nonce", "")
            signature = event_data.get("signature", "")
            encrypted_data = event_data.get("encrypted_data", "")
            
            if not all([topic, event_time, nonce, signature, encrypted_data]):
                logger.warning("[WPSChannel] Missing required event fields")
                logger.warning(f"[WPSChannel] topic={topic}, time={event_time}, nonce={'*' if nonce else ''}, signature={'*' if signature else ''}, encrypted_data={'*' if encrypted_data else ''}")
                return None
            
            # 验证时间戳（5分钟有效期）
            now = int(time.time())
            time_diff = abs(now - event_time)
            if time_diff > 5 * 60:
                logger.warning(f"[WPSChannel] Event timestamp expired: event_time={event_time}, now={now}, diff={time_diff}s")
                return None
            
            # 获取配置
            app_id = self.config.get("wps_app_id", "")
            app_secret = self.config.get("wps_app_secret", "")
            
            if not app_id or not app_secret:
                logger.error("[WPSChannel] App ID or Secret not configured")
                return None
            
            logger.info(f"[WPSChannel] Verifying event: topic={topic}, app_id={app_id}")
            
            # 验证签名
            if not verify_event_signature(
                app_id=app_id,
                app_secret=app_secret,
                topic=topic,
                nonce=nonce,
                time=event_time,
                encrypted_data=encrypted_data,
                signature=signature
            ):
                logger.warning("[WPSChannel] Signature verification failed")
                return None
            
            logger.info("[WPSChannel] Signature verified, decrypting data...")
            
            # 解密数据
            try:
                decrypted_data = decrypt_event_data(encrypted_data, app_secret, nonce)
                logger.info(f"[WPSChannel] Decryption successful")
                return decrypted_data
            except Exception as e:
                logger.error(f"[WPSChannel] Decryption failed: {e}")
                logger.error(f"[WPSChannel] Please check if WPS_APP_SECRET is correct")
                return None
            
        except Exception as e:
            logger.error(f"[WPSChannel] Verification/Decryption error: {e}")
            return None
    
    def handle_event(self, event_data: Dict) -> Optional[Dict]:
        """
        处理WPS事件
        
        事件格式:
        {
            "topic": "kso.app_chat.message",
            "operation": "create",
            ...
        }
        
        :param event_data: 事件数据（加密格式）
        :return: 响应数据
        """
        try:
            # 先验证签名并解密
            decrypted_data = self.verify_and_decrypt(event_data)
            if decrypted_data is None:
                logger.warning("[WPSChannel] Failed to verify/decrypt event")
                return None
            
            # 从 topic 和 operation 判断事件类型
            topic = event_data.get("topic", "")
            operation = event_data.get("operation", "")
            
            logger.info(f"[WPSChannel] Received event: topic={topic}, operation={operation}")
            
            # 消息创建事件
            # 实际格式: topic="kso.app_chat.message", operation="create"
            if (topic == "kso.app_chat.message" and operation == "create") or \
               topic == "kso.app_chat.message.create":
                return self._handle_message_event(decrypted_data)
            
            # 其他事件
            logger.debug(f"[WPSChannel] Unhandled event: topic={topic}, operation={operation}")
            return None
            
        except Exception as e:
            logger.error(f"[WPSChannel] Error handling event: {e}")
            return None
    
    def _handle_message_event(self, decrypted_data: Dict) -> Optional[Dict]:
        """
        处理机器人接收消息事件
        
        解密后的数据结构:
        {
            "chat": {"id": "xxx", "type": "p2p/group"},
            "message": {"id": "xxx", "type": "text", "content": {...}},
            "sender": {"id": "xxx", "type": "user"},
            ...
        }
        
        :param decrypted_data: 解密后的事件数据
        :return: 响应数据
        """
        try:
            logger.debug(f"[WPSChannel] Decrypted data: {decrypted_data}")
            
            # 解析消息 - 传递完整的数据，因为 chat 和 sender 在顶层
            # WPSMessage 会自己处理 message 嵌套
            msg = WPSMessage(decrypted_data)
            logger.info(f"[WPSChannel] Received message: {msg}")
            
            # 幂等检查
            if self._is_duplicate(msg.msg_id):
                logger.debug(f"[WPSChannel] Duplicate message ignored: {msg.msg_id}")
                return None
            
            # 清理过期缓存
            self._clean_msg_cache()
            
            # 构建上下文
            context = self._compose_context(msg)
            if not context:
                return None
            
            # 调用Bot处理
            reply_text = self._process_message(context)
            
            # 发送回复
            if reply_text:
                self.send_reply(msg, reply_text)
            
            return None
            
        except Exception as e:
            logger.error(f"[WPSChannel] Error handling message event: {e}")
            return None
    
    def _compose_context(self, msg: WPSMessage) -> Optional[Context]:
        """
        构建消息上下文
        
        :param msg: WPS消息
        :return: 上下文对象
        """
        content = msg.content
        
        # 群聊处理
        if msg.is_group:
            # 检查是否在白名单
            if not self._check_group_whitelist(msg.chat_id):
                logger.debug(f"[WPSChannel] Group {msg.chat_id} not in whitelist")
                return None
            
            # 检查是否需要@触发
            if not self.config.get("group_at_off", False):
                if not msg.is_at:
                    logger.debug("[WPSChannel] Group message without @, ignored")
                    return None
                
                # 移除@机器人的内容
                content = self._remove_at_content(content, msg)
        
        else:
            # 单聊：检查前缀
            prefix_list = self.config.get("single_chat_prefix", [""])
            match_prefix = self._check_prefix(content, prefix_list)
            
            if match_prefix is None:
                logger.debug("[WPSChannel] Single chat prefix not match")
                return None
            
            # 移除前缀
            if match_prefix:
                content = content.replace(match_prefix, "", 1).strip()
        
        # 构建上下文
        context = Context(
            type=msg.ctype,
            content=content,
            kwargs={
                "msg": msg,
                "isgroup": msg.is_group,
                "session_id": msg.from_user_id if not msg.is_group else msg.chat_id,
                "receiver": msg.chat_id if msg.is_group else msg.from_user_id,
            }
        )
        
        return context
    
    def _process_message(self, context: Context) -> str:
        """
        处理消息并生成回复
        
        :param context: 消息上下文
        :return: 回复内容
        """
        try:
            session_id = context["session_id"]
            content = context.content
            
            # 调用LLM Bot
            reply_text = self.bot.chat(content, session_id)
            
            # 添加回复前缀（单聊）
            if not context["isgroup"]:
                prefix = self.config.get("single_chat_reply_prefix", "")
                if prefix:
                    reply_text = prefix + reply_text
            
            return reply_text
            
        except Exception as e:
            logger.error(f"[WPSChannel] Process message error: {e}")
            return "抱歉，我暂时无法处理您的请求，请稍后再试"
    
    def send_reply(self, msg: WPSMessage, reply_text: str) -> bool:
        """
        发送回复消息
        
        自动检测内容是否包含 Markdown 格式，如果是则使用 rich_text 类型发送
        
        :param msg: 原消息
        :param reply_text: 回复内容
        :return: 发送结果
        """
        try:
            api_client = get_api_client()
            
            # 确定接收者
            if msg.is_group:
                receiver_id = msg.chat_id
                receiver_type = "chat"
            else:
                receiver_id = msg.from_user_id
                receiver_type = "user"
            
            logger.debug(f"[WPSChannel] Sending reply: is_group={msg.is_group}, "
                        f"receiver_id={receiver_id}, receiver_type={receiver_type}")
            
            # 检查 receiver_id 是否为空
            if not receiver_id:
                logger.error(f"[WPSChannel] Receiver ID is empty! "
                           f"chat_id={msg.chat_id}, from_user_id={msg.from_user_id}")
                return False
            
            logger.info(f"[WPSChannel] Preparing to send reply to {receiver_type}:{receiver_id}")
            logger.info(f"[WPSChannel] Original message: chat_type={msg.chat_type}, "
                       f"sender={msg.from_user_name}({msg.from_user_id})")
            
            # 检测是否包含 Markdown 格式
            msg_type = self._detect_message_type(reply_text)
            logger.debug(f"[WPSChannel] Detected message type: {msg_type}")
            
            result = api_client.send_message(
                receiver_id=receiver_id,
                receiver_type=receiver_type,
                msg_type=msg_type,
                content=reply_text
            )
            
            if result:
                logger.info(f"[WPSChannel] Reply sent successfully to {receiver_type}:{receiver_id}")
            else:
                logger.error(f"[WPSChannel] Failed to send reply to {receiver_type}:{receiver_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"[WPSChannel] Send reply error: {e}")
            return False
    
    def _detect_message_type(self, content: str) -> str:
        """
        检测消息类型
        
        如果内容包含 Markdown 格式标记，返回 rich_text，否则返回 text
        
        :param content: 消息内容
        :return: "text" 或 "rich_text"
        """
        if not content:
            return "text"
        
        # Markdown 特征正则表达式
        markdown_patterns = [
            r'```[\s\S]*?```',           # 代码块
            r'`[^`]+`',                   # 行内代码
            r'\*\*[^*]+\*\*',            # 粗体 **text**
            r'\*[^*]+\*',                 # 斜体 *text*
            r'__[^_]+__',                 # 粗体 __text__
            r'_[^_]+_',                   # 斜体 _text_
            r'#{1,6}\s',                 # 标题 # ## ###
            r'\[([^\]]+)\]\(([^)]+)\)',  # 链接 [text](url)
            r'!\[([^\]]*)\]\(([^)]+)\)', # 图片 ![alt](url)
            r'^\s*[-*+]\s',              # 列表项 - * +
            r'^\s*\d+\.\s',              # 有序列表 1. 2. 3.
            r'^\s*>\s',                  # 引用 >
            r'---|\*\*\*',               # 分隔线 --- ***
            r'\|[^\|]+\|',               # 表格 |
        ]
        
        import re
        for pattern in markdown_patterns:
            if re.search(pattern, content, re.MULTILINE):
                logger.debug(f"[WPSChannel] Markdown pattern matched: {pattern}")
                return "rich_text"
        
        return "text"
    
    def _is_duplicate(self, msg_id: str) -> bool:
        """检查消息是否重复"""
        if msg_id in self.processed_msgs:
            return True
        self.processed_msgs[msg_id] = time.time()
        return False
    
    def _clean_msg_cache(self):
        """清理过期消息缓存"""
        now = time.time()
        expired = [
            msg_id for msg_id, timestamp in self.processed_msgs.items()
            if now - timestamp > self.msg_cache_expire
        ]
        for msg_id in expired:
            del self.processed_msgs[msg_id]
    
    def _check_group_whitelist(self, group_id: str) -> bool:
        """检查组是否在白名单"""
        whitelist = self.config.get("group_name_white_list", [])
        if "ALL_GROUP" in whitelist:
            return True
        return group_id in whitelist
    
    def _check_prefix(self, content: str, prefix_list: list) -> Optional[str]:
        """检查内容前缀"""
        if not prefix_list:
            return ""
        for prefix in prefix_list:
            if prefix and content.startswith(prefix):
                return prefix
            elif not prefix:
                return ""
        return None
    
    def _remove_at_content(self, content: str, msg: WPSMessage) -> str:
        """
        移除@内容
        
        处理多种@格式：
        1. @用户名 后跟空格或特殊空白字符
        2. <at id="xxx">@用户名</at> XML格式
        3. <at id="xxx">用户名</at> 不带@符号的XML格式
        """
        import re
        
        # 先移除 XML 格式的 at 标签
        # 匹配 <at id="...">...</at> 或 <at id='...'>...</at>
        content = re.sub(r'<at\s+id=["\'][^"\']*["\']>[^<]*</at>', '', content)
        
        # 再移除 @用户名 格式
        for at_info in msg.at_list:
            at_name = at_info.get("name", "")
            if at_name:
                # 匹配 @用户名 后跟空格或特殊空白字符（包括全角空格\u3000）
                pattern = f"@{re.escape(at_name)}(\\u2005|\\u0020|\\s|\\u3000)*"
                content = re.sub(pattern, "", content)
        
        # 清理多余的空格
        content = re.sub(r'\s+', ' ', content).strip()
        
        return content


# 全局Channel实例
_channel: Optional[WPSChannel] = None


def get_channel() -> WPSChannel:
    """获取全局Channel实例"""
    global _channel
    if _channel is None:
        _channel = WPSChannel()
    return _channel
