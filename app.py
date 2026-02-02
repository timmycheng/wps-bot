# encoding:utf-8
"""
WPS Bot 主应用入口
Flask Web应用，接收WPS开放平台的事件订阅推送
"""

import json
import logging
import signal
import sys

from gradio import JSON

from flask import Flask, request, jsonify

from channel.wps_channel import get_channel
from common.logger import logger, setup_logger
from config import get_config, load_config

# 创建Flask应用
app = Flask(__name__)


@app.route("/", methods=["GET"])
def index():
    """健康检查接口"""
    return jsonify({"status": "ok", "service": "WPS Bot", "version": "1.0.0"})


@app.route("/event/callback", methods=["POST"])
def event_callback():
    """
    WPS 开放平台事件订阅回调接口

    WPS开放平台会将订阅的事件推送到此URL
    包括：
    - URL验证事件 (url_verification)
    - 消息接收事件 (kso.app_chat.message.create)
    - 其他业务事件
    """
    try:
        # 获取请求体
        body = request.get_data(as_text=True)
        headers = dict(request.headers)

        logger.debug(f"[EventCallback] Received request: {body[:500]}")

        # 解析事件数据
        try:
            event_data = json.loads(body)
            if len(event_data) == 1 and "challenge" in event_data:
                # URL验证事件
                logger.info("[EventCallback] URL verification event received")
                return jsonify(event_data)

        except json.JSONDecodeError as e:
            logger.error(f"[EventCallback] Invalid JSON: {e}")
            return jsonify({"code": 400, "msg": "Invalid JSON"}), 400

        # 验证请求（WPS-3签名验证）
        channel = get_channel()
        if not channel.verify_callback(headers, body):
            logger.warning("[EventCallback] Request verification failed")
            return jsonify({"code": 401, "msg": "Unauthorized"}), 401

        # 处理事件
        response_data = channel.handle_event(event_data)

        # 如果需要返回数据（如URL验证），则返回
        if response_data is not None:
            return jsonify(response_data)

        # 返回成功响应
        return jsonify({"code": 0, "msg": "success"})

    except Exception as e:
        logger.exception(f"[EventCallback] Error: {e}")
        return jsonify({"code": 500, "msg": "Internal Server Error"}), 500


@app.route("/webhook", methods=["POST"])
def webhook():
    """
    兼容旧版Webhook接口（如需要）
    某些场景下可能仍需要使用webhook方式
    """
    # 直接转发到事件回调处理
    return event_callback()


@app.route("/health", methods=["GET"])
def health():
    """健康检查"""
    return jsonify({"status": "healthy"})


def signal_handler(sig, frame):
    """信号处理函数"""
    logger.info("[App] Received signal, shutting down...")
    sys.exit(0)


def main():
    """主函数"""
    # 加载配置
    config = load_config()

    # 设置日志级别
    log_level = logging.DEBUG if config.get("debug") else logging.INFO
    setup_logger(level=log_level)

    logger.info("=" * 50)
    logger.info("WPS Bot Starting...")
    logger.info("=" * 50)

    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 获取配置
    host = config.get("host", "0.0.0.0")
    port = config.get("port", 8080)
    debug = config.get("debug", False)

    logger.info(f"[App] Event callback URL: http://{host}:{port}/event/callback")
    logger.info(f"[App] Health check: http://{host}:{port}/health")
    logger.info(f"[App] Debug mode: {debug}")

    # 启动服务
    # 生产环境使用gunicorn，开发环境使用Flask内置服务器
    if len(sys.argv) > 1 and sys.argv[1] == "--dev":
        app.run(host=host, port=port, debug=debug)
    else:
        # 使用Flask内置服务器（可通过gunicorn启动）
        from werkzeug.serving import run_simple

        run_simple(host, port, app, use_reloader=debug, use_debugger=debug)


if __name__ == "__main__":
    main()
