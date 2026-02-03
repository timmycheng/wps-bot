# encoding:utf-8
"""
WPS 开放平台加密/解密和签名工具
支持：
- 事件消息签名验证（HMAC-SHA256）
- 事件消息解密（AES-CBC）
- KSO-1 签名（API调用）- 新版签名算法
"""

import base64
import hashlib
import hmac
import json
import urllib.parse
from datetime import datetime
from typing import Dict

from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

from common.logger import logger


def md5_hash(s: str) -> str:
    """计算 MD5 哈希（小写十六进制）"""
    return hashlib.md5(s.encode('utf-8')).hexdigest()


def hmac_sha256(message: str, secret: str) -> str:
    """
    HMAC-SHA256 签名，返回 URL Safe No Padding base64
    
    注意：这是 WPS 事件消息签名使用的算法
    """
    key = secret.encode('utf-8')
    msg = message.encode('utf-8')
    signature = hmac.new(key, msg, hashlib.sha256).digest()
    # URL Safe No Padding base64
    return base64.urlsafe_b64encode(signature).rstrip(b'=').decode('utf-8')


def verify_event_signature(
    app_id: str,
    app_secret: str,
    topic: str,
    nonce: str,
    time: int,
    encrypted_data: str,
    signature: str
) -> bool:
    """
    验证 WPS 事件消息签名
    
    签名算法: HMAC-SHA256(AppSecret, content)
    其中 content = app_id:topic:nonce:time:encrypted_data
    签名结果使用 URL Safe No Padding base64 编码
    
    :param app_id: 应用 ID
    :param app_secret: 应用密钥
    :param topic: 消息主题
    :param nonce: 随机字符串（也是解密用的 IV）
    :param time: 时间戳（秒）
    :param encrypted_data: 加密数据
    :param signature: 待验证的签名
    :return: 验证结果
    """
    try:
        # 构建签名内容
        content = f"{app_id}:{topic}:{nonce}:{time}:{encrypted_data}"
        
        # 计算签名
        computed = hmac_sha256(content, app_secret)
        
        logger.debug(f"[WPSCrypto] Sign content: {content}")
        logger.debug(f"[WPSCrypto] Computed signature: {computed}")
        logger.debug(f"[WPSCrypto] Received signature: {signature}")
        
        # 比较签名（不区分大小写，因为 base64 可能有大小写差异）
        result = hmac.compare_digest(computed, signature)
        if not result:
            logger.warning(f"[WPSCrypto] Signature mismatch! computed={computed}, received={signature}")
        return result
    except Exception as e:
        logger.error(f"[WPSCrypto] Signature verification failed: {e}")
        return False


def decrypt_event_data(encrypted_data: str, app_secret: str, nonce: str) -> dict:
    """
    解密 WPS 事件消息
    
    根据官方文档：
    1. encrypted_data 使用标准的有填充 base64 编码，解密前需要先进行 base64 解码
    2. 数据通过 AES-CBC 进行加密
    3. cipher 为 md5 编码后的 secretKey（32字符 hex 字符串）
    4. nonce 即 iv 向量
    5. 解密后的数据经过 PKCS7 填充，解密后需要删除尾部填充
    
    参考 Go 实现：
    - cipher := Md5(secretKey)  // 返回 32字符 hex 字符串
    - rawData, err := AESCBCPKCS7Decrypt(data, []byte(cipher), []byte(nonce))
    
    Go 的 aes.NewCipher 会根据 key 长度自动选择：
    - 16 字节 = AES-128
    - 24 字节 = AES-192  
    - 32 字节 = AES-256
    
    由于 md5 hex 是 32 字符，转成 []byte 是 32 字节，所以 Go 代码使用的是 AES-256
    
    :param encrypted_data: 加密的数据（base64 编码）
    :param app_secret: 应用密钥
    :param nonce: IV 向量
    :return: 解密后的 JSON 字典
    """
    # 1. Base64 解码加密数据
    try:
        encrypted_bytes = base64.b64decode(encrypted_data)
    except Exception as e:
        logger.error(f"[WPSCrypto] Base64 decode failed: {e}")
        raise
    
    # 2. 计算 cipher: md5(secretKey) -> 32字符 hex 字符串
    cipher_key = md5_hash(app_secret)  # 如 "5d41402abc4b2a76b9719d911017c592"
    
    # 3. 密钥: hex 字符串转成 bytes（32字节 = AES-256）
    key = cipher_key.encode('utf-8')
    
    # 4. IV: nonce 转成 bytes（取前16字节确保长度）
    iv = nonce.encode('utf-8')
    if len(iv) < 16:
        # 如果 nonce 不足16字节，右填充 \0
        iv = iv.ljust(16, b'\0')
    elif len(iv) > 16:
        iv = iv[:16]
    
    logger.info(f"[WPSCrypto] Decrypting event data...")
    logger.debug(f"[WPSCrypto] App secret length: {len(app_secret)}")
    logger.debug(f"[WPSCrypto] Cipher (md5 hex): {cipher_key}")
    logger.debug(f"[WPSCrypto] Key bytes: {len(key)} bytes (hex: {key.hex()})")
    logger.debug(f"[WPSCrypto] IV bytes: {len(iv)} bytes (hex: {iv.hex()})")
    logger.debug(f"[WPSCrypto] Encrypted data length: {len(encrypted_data)} (base64)")
    logger.debug(f"[WPSCrypto] Encrypted bytes: {len(encrypted_bytes)}")
    logger.debug(f"[WPSCrypto] Encrypted bytes (hex): {encrypted_bytes[:32].hex()}...")
    
    # 检查密文长度是否是16的倍数
    if len(encrypted_bytes) % 16 != 0:
        logger.error(f"[WPSCrypto] Invalid ciphertext length: {len(encrypted_bytes)} (not multiple of 16)")
        raise ValueError(f"Ciphertext length must be multiple of 16, got {len(encrypted_bytes)}")
    
    # 5. AES-CBC 解密
    try:
        cipher = AES.new(key, AES.MODE_CBC, iv)
        decrypted_padded = cipher.decrypt(encrypted_bytes)
        logger.debug(f"[WPSCrypto] Decrypted bytes (with padding): {len(decrypted_padded)}")
        logger.debug(f"[WPSCrypto] Last 16 bytes (hex): {decrypted_padded[-16:].hex()}")
        logger.debug(f"[WPSCrypto] Last byte (padding indicator): {decrypted_padded[-1]}")
    except Exception as e:
        logger.error(f"[WPSCrypto] AES decrypt failed: {e}")
        raise
    
    # 6. PKCS7 去填充
    try:
        padding_len = decrypted_padded[-1]
        logger.debug(f"[WPSCrypto] PKCS7 padding length: {padding_len}")
        
        # 验证填充是否合法
        if padding_len < 1 or padding_len > 16:
            logger.error(f"[WPSCrypto] Invalid PKCS7 padding length: {padding_len}")
            raise ValueError(f"Invalid PKCS7 padding length: {padding_len}")
        
        # 验证填充字节是否一致
        padding_bytes = decrypted_padded[-padding_len:]
        if not all(b == padding_len for b in padding_bytes):
            logger.error(f"[WPSCrypto] Invalid PKCS7 padding bytes")
            raise ValueError("Invalid PKCS7 padding bytes")
        
        decrypted = decrypted_padded[:-padding_len]
        logger.debug(f"[WPSCrypto] Decrypted bytes (after unpad): {len(decrypted)}")
    except Exception as e:
        logger.error(f"[WPSCrypto] PKCS7 unpad failed: {e}")
        # 尝试使用库函数
        try:
            decrypted = unpad(decrypted_padded, AES.block_size)
            logger.debug(f"[WPSCrypto] Unpad successful using library function")
        except Exception as e2:
            logger.error(f"[WPSCrypto] Library unpad also failed: {e2}")
            raise
    
    # 7. JSON 解析
    try:
        decrypted_text = decrypted.decode('utf-8')
        logger.debug(f"[WPSCrypto] Decrypted text (first 200 chars): {decrypted_text[:200]}")
        result = json.loads(decrypted_text)
        logger.info(f"[WPSCrypto] Decryption successful")
        return result
    except json.JSONDecodeError as e:
        logger.error(f"[WPSCrypto] JSON parse failed: {e}")
        logger.error(f"[WPSCrypto] Decrypted text: {decrypted[:200]}")
        raise
    except Exception as e:
        logger.error(f"[WPSCrypto] Decoding failed: {e}")
        raise


# ==================== KSO-1 签名（API调用）====================

def generate_kso1_signature(
    app_id: str,
    app_secret: str,
    method: str,
    uri: str,
    content_type: str,
    kso_date: str,
    body: str = ""
) -> str:
    """
    生成 KSO-1 签名（新版签名算法）
    
    根据官方文档：
    signature = HMAC-SHA256(secretKey, content)
    content = "KSO-1" + Method + RequestURI + ContentType + KsoDate + sha256(RequestBody)
    
    其中：
    - "KSO-1": 固定内容，签名版本字符串
    - Method: 请求的方法 (GET/POST等)
    - RequestURI: 请求的 URI，包含 query 参数，例：/v7/messages/create
    - ContentType: 如 application/json
    - KsoDate: RFC1123 格式的日期
    - sha256(RequestBody): 当请求体不为空时，使用 SHA256 哈希算法计算请求体的值（hex 编码）
    
    返回的签名是 hex 编码的字符串（不是 base64）
    
    :param app_id: 应用ID (用于构建 Authorization header，不参与签名)
    :param app_secret: 应用密钥 (用于签名)
    :param method: HTTP方法 (GET/POST等)
    :param uri: 请求URI (包含 query 参数，如 /v7/messages/create)
    :param content_type: Content-Type 头，如 application/json
    :param kso_date: RFC1123格式的日期
    :param body: 请求体（原始字符串）
    :return: 签名（hex 编码）
    """
    try:
        # 计算请求体的 SHA256
        sha256_hex = ""
        if body:
            sha256_hex = hashlib.sha256(body.encode('utf-8')).hexdigest()
        
        # 构建签名内容
        # content = "KSO-1" + Method + RequestURI + ContentType + KsoDate + sha256(RequestBody)
        sign_content = f"KSO-1{method.upper()}{uri}{content_type}{kso_date}{sha256_hex}"
        
        logger.debug(f"[WPSCrypto] KSO-1 sign content: {sign_content}")
        logger.debug(f"[WPSCrypto] KSO-1 sha256(body): {sha256_hex}")
        
        # HMAC-SHA256 签名
        signature = hmac.new(
            app_secret.encode('utf-8'),
            sign_content.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        logger.debug(f"[WPSCrypto] KSO-1 signature: {signature}")
        
        return signature
        
    except Exception as e:
        logger.error(f"[WPSCrypto] KSO-1 signature generation failed: {e}")
        raise


def get_kso1_auth_headers(
    app_id: str,
    app_secret: str,
    method: str,
    uri: str,
    body: str = ""
) -> Dict[str, str]:
    """
    获取 KSO-1 认证的请求头
    
    :param app_id: 应用ID
    :param app_secret: 应用密钥
    :param method: HTTP方法
    :param uri: 请求URI（包含 query 参数）
    :param body: 请求体
    :return: 请求头字典
    """
    # RFC1123 格式的日期
    kso_date = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')
    content_type = "application/json" if body else ""
    
    # 生成签名
    signature = generate_kso1_signature(
        app_id, app_secret, method, uri, content_type, kso_date, body
    )
    
    # Authorization 格式: "KSO-1 accessKey:signature"
    # 注意：KSO-1 后面有一个空格
    return {
        "X-Kso-Date": kso_date,
        "X-Kso-Authorization": f"KSO-1 {app_id}:{signature}",
        "Content-Type": content_type
    }
