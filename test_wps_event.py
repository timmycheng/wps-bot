# encoding:utf-8
"""
WPS 事件消息签名验证和解密测试

使用方法:
1. 从日志中复制实际收到的事件数据
2. 替换下面的 test_event_data 变量
3. 运行: python test_wps_event.py
"""

import json
import os
import sys

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib.wps_crypto import verify_event_signature, decrypt_event_data, hmac_sha256


def test_with_real_data():
    """使用真实数据进行测试"""
    
    # 请替换为实际的配置
    app_id = os.environ.get("WPS_APP_ID", "")
    app_secret = os.environ.get("WPS_APP_SECRET", "")
    
    # 请替换为实际收到的事件数据（从日志中复制）
    test_event_data = {
        "topic": "kso.app_chat.message.create",
        "operation": "create",
        "time": 0,
        "nonce": "",
        "signature": "",
        "encrypted_data": ""
    }
    
    print("=" * 70)
    print("WPS 事件签名验证和解密测试")
    print("=" * 70)
    
    if not app_id or not app_secret:
        print("\n错误: 请设置 WPS_APP_ID 和 WPS_APP_SECRET 环境变量")
        print("  export WPS_APP_ID=your_app_id")
        print("  export WPS_APP_SECRET=your_app_secret")
        return
    
    print(f"\n配置信息:")
    print(f"  App ID: {app_id}")
    print(f"  App Secret (前4字符): {app_secret[:4]}... (长度: {len(app_secret)})")
    
    print(f"\n事件数据:")
    print(f"  Topic: {test_event_data.get('topic')}")
    print(f"  Time: {test_event_data.get('time')}")
    print(f"  Nonce: {test_event_data.get('nonce', '')[:20]}...")
    print(f"  Signature: {test_event_data.get('signature', '')[:20]}...")
    enc_data = test_event_data.get('encrypted_data', '')
    print(f"  Encrypted Data: {enc_data[:50]}... (长度: {len(enc_data)})")
    
    # 步骤1: 验证签名
    print("\n" + "-" * 70)
    print("步骤1: 验证签名")
    print("-" * 70)
    
    topic = test_event_data.get("topic", "")
    nonce = test_event_data.get("nonce", "")
    event_time = test_event_data.get("time", 0)
    signature = test_event_data.get("signature", "")
    encrypted_data = test_event_data.get("encrypted_data", "")
    
    # 构建签名内容
    content = f"{app_id}:{topic}:{nonce}:{event_time}:{encrypted_data}"
    computed_sig = hmac_sha256(content, app_secret)
    
    print(f"\n签名内容:")
    print(f"  {content[:100]}...")
    print(f"\n计算签名: {computed_sig}")
    print(f"接收签名: {signature}")
    print(f"签名匹配: {computed_sig == signature}")
    
    sig_result = verify_event_signature(
        app_id=app_id,
        app_secret=app_secret,
        topic=topic,
        nonce=nonce,
        time=event_time,
        encrypted_data=encrypted_data,
        signature=signature
    )
    
    print(f"\n签名验证结果: {'✓ 通过' if sig_result else '✗ 失败'}")
    
    if not sig_result:
        print("\n提示: 签名失败通常是因为 App Secret 不正确")
        print("      请检查 WPS 开放平台的应用配置")
        return
    
    # 步骤2: 解密数据
    print("\n" + "-" * 70)
    print("步骤2: 解密数据")
    print("-" * 70)
    
    try:
        decrypted = decrypt_event_data(encrypted_data, app_secret, nonce)
        print(f"\n解密成功!")
        print(f"\n解密结果:")
        print(json.dumps(decrypted, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"\n解密失败: {e}")
        print("\n可能的错误原因:")
        print("  1. App Secret 不正确（最常见）")
        print("  2. Nonce/IV 不正确")
        print("  3. Encrypted Data 损坏")
        print("\n建议:")
        print("  - 在 WPS 开放平台重新生成 App Secret")
        print("  - 检查环境变量是否正确设置")
        print("  - 开启 DEBUG 日志查看详细信息")


def quick_test():
    """快速测试（使用示例数据）"""
    print("=" * 70)
    print("快速测试（使用示例数据）")
    print("=" * 70)
    print("\n注意: 这个测试使用示例数据，预期会失败")
    print("      请使用真实事件数据进行测试")
    print("\n要测试真实数据，请修改脚本中的 test_event_data 变量")
    print("或者运行: python test_wps_event.py real")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "real":
        test_with_real_data()
    else:
        quick_test()
        print("\n" + "=" * 70)
        print("使用说明:")
        print("=" * 70)
        print("1. 从程序日志中复制实际收到的事件数据")
        print("2. 修改本脚本中的 test_event_data 变量")
        print("3. 运行: python test_wps_event.py real")
        print("\n或者设置环境变量:")
        print("  export WPS_APP_ID=your_app_id")
        print("  export WPS_APP_SECRET=your_app_secret")
