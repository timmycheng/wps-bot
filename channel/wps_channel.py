# encoding:utf-8
"""
WPS 协作平台消息通道
处理来自WPS开放平台的订阅消息推送

事件名：kso.app_chat.message.create（机器人接收消息）
文档：https://365.kdocs.cn/3rd/open/documents/app-integration-dev/wps365/server/event-subscription/subscription-flow
"""

import json
import re
import time
from typing import Dict, Optional

from bot.llm_bot import get_bot
from bridge.context import Context, ContextType
from channel.wps_message import WPSMessage
from common.logger import logger
from config import get_config
from lib.wps_api import get_api_client
from lib.wps_crypto import verify_wps3_signature


class WPSChannel:
    """
    WPS消息通道
    处理消息的接收和发送
    
    接入流程：
    1. 在WPS开放平台创建企业内部应用
    2. 订阅事件：kso.app_chat.message.create（机器人接收消息）
    3. 配置事件回调地址（本服务的URL）
    4. WPS平台将消息推送到回调地址
    """
    
    # WPS事件类型
    EVENT_URL_VERIFICATION = "url_verification"  # URL验证事件
    EVENT_MESSAGE_CREATE = "kso.app_chat.message.create"  # 机器人接收消息事件
    
    def __init__(self):
        self.config = get_config()
        self.bot = get_bot()
        
        # 已处理消息ID缓存（幂等控制）
        self.processed_msgs: Dict[str, float] = {}
        self.msg_cache_expire = 300  # 5分钟过期
        
        # 机器人用户ID
        self.bot_user_id = self.config.get("wps_app_id", "")
        
        logger.info("[WPSChannel] Initialized")
    
    def verify_callback(self, headers: Dict, body: str) -> bool:
        """
        验证WPS事件回调请求（WPS-3签名）
        
        文档：https://365.kdocs.cn/3rd/open/documents/app-integration-dev/wps365/server/event-subscription/security-verification
        
        签名算法: sha256(AppSecret + Timestamp + Nonce + Body)
        
        :param headers: HTTP请求头
        :param body: 请求体
        :return: 验证结果
        """
        try:
            # 获取签名相关头
            signature = headers.get("X-Kso-Signature", "")
            timestamp = headers.get("X-Kso-Timestamp", "")
            nonce = headers.get("X-Kso-Nonce", "")
            app_id = headers.get("X-Kso-AppId", "")
            
            if not all([signature, timestamp, nonce, app_id]):
                logger.warning("[WPSChannel] Missing required headers")
                return False
            
            # 验证AppID
            if app_id != self.config.get("wps_app_id"):
                logger.warning(f"[WPSChannel] AppID mismatch: {app_id}")
                return False
            
            # 验证时间戳（5分钟有效期）
            try:
                ts = int(timestamp)
                now = int(time.time() * 1000)  # 毫秒
                if abs(now - ts) > 5 * 60 * 1000:
                    logger.warning("[WPSChannel] Request timestamp expired")
                    return False
            except ValueError:
                logger.warning("[WPSChannel] Invalid timestamp format")
                return False
            
            # 验证WPS-3签名
            app_secret = self.config.get("wps_app_secret", "")
            if not verify_wps3_signature(app_secret, timestamp, nonce, signature, body):
                logger.warning("[WPSChannel] WPS-3 signature verification failed")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"[WPSChannel] Verification error: {e}")
            return False
    
    def handle_event(self, event_data: Dict) -> Optional[Dict]:
        """
        处理WPS事件
        
        :param event_data: 事件数据
        :return: 响应数据
        """
        try:
            event_type = event_data.get("event", "")
            
            logger.info(f"[WPSChannel] Received event: {event_type}")
            
            # URL验证事件（配置回调地址时触发）
            if event_type == self.EVENT_URL_VERIFICATION:
                return self._handle_url_verification(event_data)
            
            # 机器人接收消息事件
            if event_type == self.EVENT_MESSAGE_CREATE:
                return self._handle_message_event(event_data)
            
            # 其他事件
            logger.debug(f"[WPSChannel] Unhandled event type: {event_type}")
            return None
            
        except Exception as e:
            logger.error(f"[WPSChannel] Error handling event: {e}")
            return None
    
    def _handle_url_verification(self, event_data: Dict) -> Dict:
        """
        处理URL验证事件
        
        文档：https://365.kdocs.cn/3rd/open/documents/app-integration-dev/wps365/server/event-subscription/subscription-flow
        
        :param event_data: 事件数据
        :return: 响应数据
        """
        challenge = event_data.get("challenge", "")
        logger.info("[WPSChannel] Handling URL verification")
        
        return {
            "challenge": challenge
        }
    
    def _handle_message_event(self, event_data: Dict) -> Optional[Dict]:
        """
        处理机器人接收消息事件 (kso.app_chat.message.create)
        
        :param event_data: 事件数据
        :return: 响应数据
        """
        try:
            # 解析消息
            msg = WPSMessage(event_data)
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
            
            return None  # 消息事件不需要同步返回
            
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
        
        文档：https://365.kdocs.cn/3rd/open/documents/app-integration-dev/wps365/server/im/message/single-create-msg
        
        :param msg: 原消息
        :param reply_text: 回复内容
        :return: 发送结果
        """
        try:
            api_client = get_api_client()
            
            # 确定接收者类型
            if msg.is_group:
                # 群聊回复
                result = api_client.send_message(
                    receiver_id=msg.chat_id,
                    receiver_type="chat",
                    msg_type="text",
                    content=reply_text
                )
            else:
                # 单聊回复
                result = api_client.send_message(
                    receiver_id=msg.from_user_id,
                    receiver_type="user",
                    msg_type="text",
                    content=reply_text
                )
            
            if result:
                logger.info(f"[WPSChannel] Reply sent successfully")
            else:
                logger.error(f"[WPSChannel] Failed to send reply")
            
            return result
            
        except Exception as e:
            logger.error(f"[WPSChannel] Send reply error: {e}")
            return False
    
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
        """移除@内容"""
        for at_info in msg.at_list:
            at_name = at_info.get("name", "")
            if at_name:
                pattern = f"@{re.escape(at_name)}(\\u2005|\\u0020|\\s)"
                content = re.sub(pattern, "", content)
        return content.strip()


# 全局Channel实例
_channel: Optional[WPSChannel] = None


def get_channel() -> WPSChannel:
    """获取全局Channel实例"""
    global _channel
    if _channel is None:
        _channel = WPSChannel()
    return _channel
