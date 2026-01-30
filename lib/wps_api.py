# encoding:utf-8
"""
WPS 开放平台 API 客户端
用于发送消息等操作

文档：https://365.kdocs.cn/3rd/open/documents/app-integration-dev/wps365/server/im/message/single-create-msg
API地址：https://openapi.wps.cn/v7/messages/create
签名方法：KSO-1
"""

import time
from typing import Dict, List, Optional

import requests

from common.logger import logger
from config import get_config
from lib.wps_crypto import get_kso1_auth_headers


class WPSAPIClient:
    """
    WPS API 客户端
    支持 KSO-1 签名认证
    """
    
    def __init__(self):
        self.config = get_config()
        self.base_url = self.config.get("wps_base_url", "https://openapi.wps.cn")
        self.app_id = self.config.get("wps_app_id", "")
        self.app_secret = self.config.get("wps_app_secret", "")
        
        # Access Token 缓存
        self._access_token: Optional[str] = None
        self._token_expire_time: float = 0
        
        logger.info("[WPSAPIClient] Initialized")
    
    def _get_access_token(self) -> Optional[str]:
        """
        获取 Access Token
        支持缓存，避免频繁请求
        
        :return: Access Token
        """
        # 检查缓存的token是否有效
        if self._access_token and time.time() < self._token_expire_time:
            return self._access_token
        
        try:
            # 使用KSO-1签名获取token
            # 文档：https://365.kdocs.cn/3rd/open/documents/app-integration-dev/wps365/server/api-description/signature-description-wps-3
            
            url = f"{self.base_url}/oauth2/token"
            
            payload = {
                "grant_type": "client_credentials",
                "client_id": self.app_id,
                "client_secret": self.app_secret
            }
            
            response = requests.post(url, json=payload, timeout=30)
            result = response.json()
            
            if result.get("access_token"):
                self._access_token = result.get("access_token")
                # token有效期通常为2小时，提前5分钟刷新
                expires_in = result.get("expires_in", 7200)
                self._token_expire_time = time.time() + expires_in - 300
                
                logger.info("[WPSAPIClient] Access token refreshed")
                return self._access_token
            else:
                logger.error(f"[WPSAPIClient] Get token failed: {result}")
                return None
                
        except Exception as e:
            logger.error(f"[WPSAPIClient] Get token error: {e}")
            return None
    
    def send_message(
        self,
        receiver_id: str,
        receiver_type: str = "user",
        msg_type: str = "text",
        content: str = "",
        mentions: List[Dict] = None,
        **kwargs
    ) -> bool:
        """
        发送消息
        
        文档：https://365.kdocs.cn/3rd/open/documents/app-integration-dev/wps365/server/im/message/single-create-msg
        
        :param receiver_id: 接收者ID（用户ID或群聊ID）
        :param receiver_type: 接收者类型 (user/chat)
        :param msg_type: 消息类型 (text/rich_text/image/file/audio/video/card)
        :param content: 消息内容
        :param mentions: @列表
        :param kwargs: 额外参数
        :return: 发送结果
        """
        try:
            # API端点
            uri = "/v7/messages/create"
            url = f"{self.base_url}{uri}"
            
            # 构建请求体
            payload = {
                "type": msg_type,
                "receiver": {
                    "receiver_id": receiver_id,
                    "type": receiver_type
                }
            }
            
            # 设置消息内容
            if msg_type == "text":
                payload["content"] = {
                    "text": content
                }
            elif msg_type == "rich_text":
                payload["content"] = {
                    "text": content
                }
            else:
                payload["content"] = {"text": content}
            
            # 添加@列表
            if mentions:
                payload["mentions"] = mentions
            
            body = json.dumps(payload, ensure_ascii=False)
            
            # 获取KSO-1签名头
            kso_headers = get_kso1_auth_headers(
                self.app_id,
                self.app_secret,
                "POST",
                uri,
                body=body
            )
            
            # 获取Access Token
            access_token = self._get_access_token()
            if not access_token:
                logger.error("[WPSAPIClient] No access token available")
                return False
            
            # 构建请求头
            headers = {
                **kso_headers,
                "Authorization": f"Bearer {access_token}"
            }
            
            # 发送请求
            response = requests.post(
                url,
                headers=headers,
                data=body.encode('utf-8'),
                timeout=30
            )
            
            result = response.json()
            
            if result.get("code") == 0:
                logger.info(f"[WPSAPIClient] Message sent successfully, msg_id={result.get('data', {}).get('message_id')}")
                return True
            else:
                logger.error(f"[WPSAPIClient] Send message failed: {result}")
                return False
                
        except Exception as e:
            logger.error(f"[WPSAPIClient] Send message error: {e}")
            return False
    
    def send_text_message(
        self,
        receiver_id: str,
        content: str,
        receiver_type: str = "user",
        **kwargs
    ) -> bool:
        """
        发送文本消息
        
        :param receiver_id: 接收者ID
        :param content: 消息内容
        :param receiver_type: 接收者类型 (user/chat)
        :param kwargs: 额外参数
        :return: 发送结果
        """
        return self.send_message(
            receiver_id=receiver_id,
            receiver_type=receiver_type,
            msg_type="text",
            content=content,
            **kwargs
        )
    
    def reply_message(
        self,
        chat_id: str,
        msg_id: str,
        content: str,
        msg_type: str = "text",
        **kwargs
    ) -> bool:
        """
        回复消息（在群聊中引用原消息）
        
        :param chat_id: 聊天ID
        :param msg_id: 原消息ID
        :param content: 回复内容
        :param msg_type: 消息类型
        :param kwargs: 额外参数
        :return: 发送结果
        """
        # 目前WPS API不直接支持回复引用，直接发送消息
        return self.send_message(
            receiver_id=chat_id,
            receiver_type="chat",
            msg_type=msg_type,
            content=content,
            **kwargs
        )
    
    def upload_image(self, image_data: bytes, filename: str = "image.png") -> Optional[str]:
        """
        上传图片
        
        :param image_data: 图片二进制数据
        :param filename: 文件名
        :return: 图片URL
        """
        try:
            uri = "/v7/media/upload"
            url = f"{self.base_url}{uri}"
            
            # 获取KSO-1签名头
            kso_headers = get_kso1_auth_headers(
                self.app_id,
                self.app_secret,
                "POST",
                uri
            )
            
            # 获取Access Token
            access_token = self._get_access_token()
            if not access_token:
                logger.error("[WPSAPIClient] No access token available")
                return None
            
            # 构建请求头（multipart/form-data不需要Content-Type）
            headers = {
                "X-Kso-Date": kso_headers["X-Kso-Date"],
                "X-Kso-Authorization": kso_headers["X-Kso-Authorization"],
                "Authorization": f"Bearer {access_token}"
            }
            
            files = {
                "file": (filename, image_data, "image/png")
            }
            
            response = requests.post(
                url,
                headers=headers,
                files=files,
                timeout=60
            )
            
            result = response.json()
            
            if result.get("code") == 0:
                image_url = result.get("data", {}).get("url")
                logger.info(f"[WPSAPIClient] Image uploaded: {image_url}")
                return image_url
            else:
                logger.error(f"[WPSAPIClient] Upload image failed: {result}")
                return None
                
        except Exception as e:
            logger.error(f"[WPSAPIClient] Upload image error: {e}")
            return None


# 导入json（在文件末尾导入避免循环引用）
import json

# 全局API客户端实例
_api_client: Optional[WPSAPIClient] = None


def get_api_client() -> WPSAPIClient:
    """获取全局API客户端实例"""
    global _api_client
    if _api_client is None:
        _api_client = WPSAPIClient()
    return _api_client
