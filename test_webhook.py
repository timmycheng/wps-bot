# encoding:utf-8
"""
WPS 事件回调测试脚本
用于本地测试 WPS 开放平台的事件推送接口

文档：https://365.kdocs.cn/3rd/open/documents/app-integration-dev/wps365/server/event-subscription/security-verification
签名：WPS-3 (sha256(AppSecret + Timestamp + Nonce + Body))
"""

import argparse
import hashlib
import json
import time

import requests


def generate_wps3_signature(app_secret: str, timestamp: str, nonce: str, body: str = "") -> str:
    """生成 WPS-3 签名"""
    sign_str = f"{app_secret}{timestamp}{nonce}{body}"
    return hashlib.sha256(sign_str.encode('utf-8')).hexdigest()


def test_url_verification(url: str, app_id: str, app_secret: str):
    """测试 URL 验证事件"""
    
    event_data = {
        "event": "url_verification",
        "challenge": f"test_challenge_{int(time.time())}"
    }
    
    body = json.dumps(event_data, ensure_ascii=False)
    timestamp = str(int(time.time() * 1000))  # 毫秒时间戳
    nonce = f"test_nonce_{int(time.time())}"
    signature = generate_wps3_signature(app_secret, timestamp, nonce, body)
    
    headers = {
        "Content-Type": "application/json",
        "X-Kso-AppId": app_id,
        "X-Kso-Signature": signature,
        "X-Kso-Timestamp": timestamp,
        "X-Kso-Nonce": nonce
    }
    
    print("=" * 60)
    print("测试 URL 验证事件")
    print("=" * 60)
    print(f"URL: {url}")
    print(f"Headers: {json.dumps(headers, indent=2)}")
    print(f"Body: {body}")
    print("-" * 60)
    
    try:
        response = requests.post(url, headers=headers, data=body.encode('utf-8'), timeout=30)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            resp_data = response.json()
            if resp_data.get("challenge") == event_data["challenge"]:
                print("✓ URL 验证测试通过!")
            else:
                print("✗ challenge 不匹配!")
        else:
            print("✗ URL 验证测试失败!")
            
    except Exception as e:
        print(f"✗ 请求失败: {e}")


def test_message_receive(url: str, app_id: str, app_secret: str):
    """测试机器人接收消息事件 (kso.app_chat.message.create)"""
    
    event_data = {
        "event": "kso.app_chat.message.create",
        "msg_id": f"test_{int(time.time())}",
        "msg_type": "text",
        "content": "你好，这是一条测试消息",
        "chat_id": "test_chat_123",
        "chat_type": "single",
        "from_user_id": "user_test",
        "from_user_name": "测试用户",
        "create_time": int(time.time()),
        "at_list": []
    }
    
    body = json.dumps(event_data, ensure_ascii=False)
    timestamp = str(int(time.time() * 1000))
    nonce = f"test_nonce_{int(time.time())}"
    signature = generate_wps3_signature(app_secret, timestamp, nonce, body)
    
    headers = {
        "Content-Type": "application/json",
        "X-Kso-AppId": app_id,
        "X-Kso-Signature": signature,
        "X-Kso-Timestamp": timestamp,
        "X-Kso-Nonce": nonce
    }
    
    print("\n" + "=" * 60)
    print("测试机器人接收消息事件 (kso.app_chat.message.create)")
    print("=" * 60)
    print(f"URL: {url}")
    print(f"Headers: {json.dumps(headers, indent=2)}")
    print(f"Body: {body}")
    print("-" * 60)
    
    try:
        response = requests.post(url, headers=headers, data=body.encode('utf-8'), timeout=30)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("✓ 消息接收测试通过!")
        else:
            print("✗ 消息接收测试失败!")
            
    except Exception as e:
        print(f"✗ 请求失败: {e}")


def test_health(url: str):
    """测试健康检查接口"""
    print("\n" + "=" * 60)
    print("测试健康检查")
    print("=" * 60)
    
    try:
        response = requests.get(f"{url}/health", timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("✓ 健康检查通过!")
        else:
            print("✗ 健康检查失败!")
            
    except Exception as e:
        print(f"✗ 健康检查失败: {e}")


def main():
    parser = argparse.ArgumentParser(description="WPS Bot 事件回调测试工具")
    parser.add_argument("--url", default="http://localhost:8080/event/callback", 
                        help="事件回调URL")
    parser.add_argument("--app-id", default="test_app_id", help="WPS AppID")
    parser.add_argument("--app-secret", default="test_app_secret", help="WPS AppSecret")
    parser.add_argument("--test", choices=["url_verification", "message", "health", "all"], 
                        default="all", help="测试类型")
    
    args = parser.parse_args()
    
    base_url = args.url.rstrip('/').replace('/event/callback', '')
    callback_url = f"{base_url}/event/callback"
    
    print("=" * 60)
    print("WPS Bot 测试工具")
    print("=" * 60)
    print(f"回调地址: {callback_url}")
    print(f"AppID: {args.app_id}")
    print(f"签名算法: WPS-3 (sha256)")
    print()
    
    if args.test in ["health", "all"]:
        test_health(base_url)
    
    if args.test in ["url_verification", "all"]:
        test_url_verification(callback_url, args.app_id, args.app_secret)
    
    if args.test in ["message", "all"]:
        test_message_receive(callback_url, args.app_id, args.app_secret)
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
