# encoding:utf-8
"""
WPS 开放平台加密/解密和签名工具
支持：
- WPS-3 签名（事件回调安全校验）
- KSO-1 签名（API调用）
- 消息加解密
"""

import base64
import hashlib
import hmac
import json
import struct
import urllib.parse
from datetime import datetime
from typing import Dict, Optional

from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad

from common.logger import logger


class WPSCrypto:
    """WPS消息加解密类"""
    
    AES_KEY_SIZE = 32  # AES-256
    AES_IV_SIZE = 16   # AES IV长度
    
    def __init__(self, encoding_aes_key: str = ""):
        """
        初始化
        :param encoding_aes_key: 加密密钥（Base64编码）
        """
        self.encoding_aes_key = encoding_aes_key
        self.aes_key = None
        
        if encoding_aes_key:
            try:
                # 解码Base64密钥
                self.aes_key = base64.b64decode(encoding_aes_key + "=")
                if len(self.aes_key) != self.AES_KEY_SIZE:
                    raise ValueError(f"Invalid AES key size: {len(self.aes_key)}")
            except Exception as e:
                logger.error(f"[WPSCrypto] Failed to decode AES key: {e}")
                raise
    
    def encrypt(self, text: str, app_id: str) -> str:
        """加密消息"""
        if not self.aes_key:
            raise ValueError("AES key not initialized")
        
        try:
            # 构造明文：随机16字节 + 消息长度(4字节) + 消息 + app_id
            random_bytes = get_random_bytes(16)
            msg_bytes = text.encode('utf-8')
            msg_len = struct.pack('!I', len(msg_bytes))
            app_id_bytes = app_id.encode('utf-8')
            
            plaintext = random_bytes + msg_len + msg_bytes + app_id_bytes
            
            # PKCS7填充
            padded = pad(plaintext, AES.block_size)
            
            # AES-256-CBC加密
            iv = get_random_bytes(self.AES_IV_SIZE)
            cipher = AES.new(self.aes_key, AES.MODE_CBC, iv)
            ciphertext = cipher.encrypt(padded)
            
            # 组合IV和密文，Base64编码
            result = base64.b64encode(iv + ciphertext).decode('utf-8')
            return result
            
        except Exception as e:
            logger.error(f"[WPSCrypto] Encryption failed: {e}")
            raise
    
    def decrypt(self, ciphertext: str, app_id: str) -> str:
        """解密消息"""
        if not self.aes_key:
            raise ValueError("AES key not initialized")
        
        try:
            # Base64解码
            encrypted = base64.b64decode(ciphertext)
            
            # 分离IV和密文
            iv = encrypted[:self.AES_IV_SIZE]
            ciphertext = encrypted[self.AES_IV_SIZE:]
            
            # AES-256-CBC解密
            cipher = AES.new(self.aes_key, AES.MODE_CBC, iv)
            padded = cipher.decrypt(ciphertext)
            
            # 去除PKCS7填充
            plaintext = unpad(padded, AES.block_size)
            
            # 解析明文结构
            msg_len = struct.unpack('!I', plaintext[16:20])[0]
            msg = plaintext[20:20+msg_len].decode('utf-8')
            received_app_id = plaintext[20+msg_len:].decode('utf-8')
            
            # 验证app_id
            if received_app_id != app_id:
                raise ValueError(f"AppID mismatch: {received_app_id} != {app_id}")
            
            return msg
            
        except Exception as e:
            logger.error(f"[WPSCrypto] Decryption failed: {e}")
            raise


# ==================== WPS-3 签名（事件回调安全校验）====================

def generate_wps3_signature(app_secret: str, timestamp: str, nonce: str, body: str = "") -> str:
    """
    生成 WPS-3 签名（用于事件回调安全校验）
    
    签名算法: sha256(AppSecret + Timestamp + Nonce + Body)
    
    :param app_secret: 应用密钥
    :param timestamp: 时间戳（毫秒）
    :param nonce: 随机字符串
    :param body: 请求体
    :return: 签名
    """
    try:
        sign_str = f"{app_secret}{timestamp}{nonce}{body}"
        signature = hashlib.sha256(sign_str.encode('utf-8')).hexdigest()
        return signature
    except Exception as e:
        logger.error(f"[WPSCrypto] WPS-3 signature generation failed: {e}")
        raise


def verify_wps3_signature(app_secret: str, timestamp: str, nonce: str, signature: str, body: str = "") -> bool:
    """
    验证 WPS-3 签名
    
    :param app_secret: 应用密钥
    :param timestamp: 时间戳
    :param nonce: 随机字符串
    :param signature: 待验证的签名
    :param body: 请求体
    :return: 验证结果
    """
    try:
        computed = generate_wps3_signature(app_secret, timestamp, nonce, body)
        return hmac.compare_digest(computed.lower(), signature.lower())
    except Exception as e:
        logger.error(f"[WPSCrypto] WPS-3 signature verification failed: {e}")
        return False


# ==================== KSO-1 签名（API调用）====================

def generate_kso1_signature(
    app_id: str,
    app_secret: str,
    method: str,
    uri: str,
    date: str,
    query_params: Dict = None,
    body: str = ""
) -> str:
    """
    生成 KSO-1 签名（用于API调用）
    
    签名算法:
    Authorization = KSO-1:{AppID}:{Signature}
    Signature = base64(hmac-sha1(AppSecret, StringToSign))
    StringToSign = HTTP-Verb + "\n" + 
                   Content-MD5 + "\n" + 
                   Content-Type + "\n" + 
                   Date + "\n" + 
                   {CanonicalizedKSOHeaders} + 
                   {CanonicalizedResource}
    
    :param app_id: 应用ID
    :param app_secret: 应用密钥
    :param method: HTTP方法 (GET/POST等)
    :param uri: 请求URI (如 /v7/messages/create)
    :param date: RFC1123格式的日期
    :param query_params: URL查询参数
    :param body: 请求体
    :return: 签名
    """
    try:
        # 计算Content-MD5（如果有body）
        content_md5 = ""
        content_type = "application/json" if body else ""
        
        if body:
            content_md5 = hashlib.md5(body.encode('utf-8')).hexdigest()
        
        # 构建CanonicalizedResource
        canonicalized_resource = uri
        if query_params:
            sorted_params = sorted(query_params.items())
            query_string = urllib.parse.urlencode(sorted_params)
            canonicalized_resource += "?" + query_string
        
        # 构建StringToSign
        string_to_sign = f"{method.upper()}\n{content_md5}\n{content_type}\n{date}\n{canonicalized_resource}"
        
        # HMAC-SHA1签名
        signature = base64.b64encode(
            hmac.new(
                app_secret.encode('utf-8'),
                string_to_sign.encode('utf-8'),
                hashlib.sha1
            ).digest()
        ).decode('utf-8')
        
        return signature
        
    except Exception as e:
        logger.error(f"[WPSCrypto] KSO-1 signature generation failed: {e}")
        raise


def get_kso1_auth_headers(
    app_id: str,
    app_secret: str,
    method: str,
    uri: str,
    query_params: Dict = None,
    body: str = ""
) -> Dict[str, str]:
    """
    获取 KSO-1 认证的请求头
    
    :return: 请求头字典
    """
    # RFC1123格式的日期
    date = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')
    
    # 生成签名
    signature = generate_kso1_signature(app_id, app_secret, method, uri, date, query_params, body)
    
    return {
        "X-Kso-Date": date,
        "X-Kso-Authorization": f"KSO-1:{app_id}:{signature}",
        "Content-Type": "application/json" if body else ""
    }


# ==================== 工具函数 ====================

def decrypt_message(encrypt_key: str, encrypted_msg: str, app_id: str) -> dict:
    """解密WPS消息"""
    crypto = WPSCrypto(encrypt_key)
    decrypted = crypto.decrypt(encrypted_msg, app_id)
    return json.loads(decrypted)


def encrypt_message(encrypt_key: str, msg_dict: dict, app_id: str) -> str:
    """加密WPS消息"""
    crypto = WPSCrypto(encrypt_key)
    msg_str = json.dumps(msg_dict, ensure_ascii=False)
    return crypto.encrypt(msg_str, app_id)
