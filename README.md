# WPS Bot - WPS协作平台智能助手

基于大语言模型的 WPS 协作平台应用机器人，支持对接私有化部署的 WPS 协作平台和私有化 LLM 网关。

## 功能特性

- 🤖 **智能对话**：支持单聊和群聊，具备上下文记忆能力
- 🔒 **私有化部署**：完全支持内网环境，无需互联网接入
- 🔐 **安全验证**：支持 WPS-3 签名验证（事件回调）和 KSO-1 签名（API调用）
- ⚡ **OpenAI标准接口**：兼容各类私有化 LLM 网关
- 🐳 **Docker支持**：提供Docker镜像，方便部署
- 📝 **WPS深度集成**：支持文本、Markdown、图片等多种消息类型

## 架构设计

```
┌─────────────────┐     ┌─────────────┐     ┌─────────────────┐
│   WPS开放平台   │────▶│   WPS Bot   │────▶│  私有化LLM网关  │
│  (事件订阅推送) │◀────│  (中间层)   │◀────│  (OpenAI接口)   │
└─────────────────┘     └─────────────┘     └─────────────────┘
```

## 接入流程

1. **创建企业内部应用**
   - 登录 WPS 开放平台
   - 创建"企业内部应用"
   - 获取 AppID 和 AppSecret
   - 打开机器人应用能力

2. **部署应用**
   - 配置 AppID、AppSecret、LLM网关地址
   - 启动服务

3. **订阅消息事件**
   - 进入应用管理 → 事件订阅
   - 配置事件回调地址 `https://your-server.com/event/callback`（本服务的事件回调URL）
   - 订阅 `kso.app_chat.message.create` 接收消息事件

## 快速开始

### 1. 环境准备

- Python 3.11+ (直接运行)
- Docker 20.10+ (推荐)
- 私有化 WPS 协作平台 或 WPS公有云服务
- 私有化 LLM 网关（OpenAI标准接口）

### 2. Docker 部署（推荐）

```bash
# 1. 配置环境变量
cp .env.template .env
# 编辑 .env 文件，填写 WPS_APP_ID、WPS_APP_SECRET、LLM_API_KEY 等

# 2. 构建并启动
docker-compose up -d

# 3. 查看日志
docker-compose logs -f
```

### 3. 使用 UV 运行（推荐）

本项目使用 [uv](https://docs.astral.sh/uv/) 进行 Python 项目管理。

```bash
# 克隆项目
git clone https://github.com/yourusername/wps-bot.git
cd wps-bot

# 创建虚拟环境并安装依赖
uv sync

# 配置
cp config.json.template config.json
# 编辑 config.json

# 运行
uv run python app.py
```

### 4. 使用 pip 运行

```bash
# 安装依赖
pip install -r requirements.txt

# 配置
cp config.json.template config.json
# 编辑 config.json

# 运行
python app.py
```

## 配置说明

### 核心配置项

| 配置项 | 环境变量 | 说明 | 必填 |
|--------|---------|------|------|
| wps_app_id | WPS_APP_ID | WPS应用ID | 是 |
| wps_app_secret | WPS_APP_SECRET | WPS应用密钥 | 是 |
| llm_api_key | LLM_API_KEY | LLM API密钥 | 是 |
| llm_api_base | LLM_API_BASE | LLM网关地址 | 是 |
| event_callback_url | EVENT_CALLBACK_URL | 事件回调地址 | 否 |

### WPS开放平台配置

1. 登录 [WPS开放平台](https://open.wps.cn/)
2. 创建企业内部应用
3. 获取 **AppID** 和 **AppSecret**
4. 打开机器人能力
5. 进入"事件订阅"，配置回调地址
6. 订阅以下事件：
   - `kso.app_chat.message.create` - 机器人接收消息

参考文档：
- [事件订阅流程](https://365.kdocs.cn/3rd/open/documents/app-integration-dev/wps365/server/event-subscription/subscription-flow)
- [安全校验](https://365.kdocs.cn/3rd/open/documents/app-integration-dev/wps365/server/event-subscription/security-verification)

### 可选配置项

| 配置项 | 默认值 | 说明 |
|--------|-------|------|
| wps_base_url | https://xz.wps.cn | WPS平台地址（私有化可修改） |
| llm_model | gpt-3.5-turbo | 模型名称 |
| port | 8080 | 服务端口 |
| temperature | 0.7 | LLM温度参数 |

## API 接口

### 事件回调接口

```
POST /event/callback
```

接收 WPS 开放平台推送的事件消息。

**请求头：**
- `X-Kso-AppId`: 应用ID
- `X-Kso-Signature`: WPS-3签名
- `X-Kso-Timestamp`: 时间戳（毫秒）
- `X-Kso-Nonce`: 随机字符串

**请求体示例：**
```json
{
  "event": "kso.app_chat.message.create",
  "msg_id": "msg_xxx",
  "msg_type": "text",
  "content": "你好",
  "chat_id": "chat_xxx",
  "chat_type": "single",
  "from_user_id": "user_xxx",
  "from_user_name": "用户名",
  "create_time": 1234567890
}
```

### 健康检查

```
GET /health
```

返回服务健康状态。

## 使用指南

### 单聊使用

用户直接与机器人私聊，发送消息即可触发对话。

### 群聊使用

在群聊中 @机器人 发送消息，机器人会回复并@用户。

### 内置命令

| 命令 | 说明 |
|------|------|
| `#帮助` / `#help` | 显示帮助信息 |
| `#清除记忆` / `#reset` | 清空当前会话记忆 |

## 安全机制

### WPS-3 签名验证（事件回调）

WPS开放平台使用 WPS-3 签名算法验证事件回调请求：

文档：https://365.kdocs.cn/3rd/open/documents/app-integration-dev/wps365/server/event-subscription/security-verification

```
X-Kso-AppId: {APPID}
X-Kso-Signature: {Signature}
X-Kso-Timestamp: {Timestamp}
X-Kso-Nonce: {Nonce}

Signature = sha256(AppSecret + Timestamp + Nonce + Body)
```

本服务会自动验证签名，确保请求来自WPS平台。

### KSO-1 签名（API调用）

调用WPS API时使用 KSO-1 签名：

文档：https://365.kdocs.cn/3rd/open/documents/app-integration-dev/wps365/server/api-description/signature-description-wps-3

```
X-Kso-Authorization: KSO-1:{AppID}:{Signature}
X-Kso-Date: {RFC1123 Date}

Signature = base64(hmac-sha1(AppSecret, StringToSign))
```

### 消息加密（可选）

如开启消息加密，需要配置 `wps_encrypt_key`，服务会自动解密消息。

## 目录结构

```
wps-bot/
├── app.py                 # Flask主应用入口
├── config.py             # 配置管理
├── requirements.txt      # 依赖列表
├── Dockerfile            # Docker镜像构建
├── docker-compose.yml    # Docker Compose配置
├── channel/              # 消息通道模块
│   ├── wps_channel.py   # WPS通道处理
│   └── wps_message.py   # 消息封装
├── bot/                  # LLM Bot模块
│   └── llm_bot.py       # LLM对话处理
├── lib/                  # 工具库
│   ├── wps_api.py       # WPS API客户端
│   └── wps_crypto.py    # WPS-3签名、KSO-1签名和加解密
└── common/               # 公共模块
    ├── logger.py        # 日志工具
    └── session_manager.py # 会话管理
```

## 常见问题

### Q: 如何获取 WPS AppID 和 AppSecret？

A: 
1. 登录 WPS 开放平台
2. 创建"企业内部应用"
3. 在应用详情页查看 AppID 和 AppSecret

### Q: 签名验证失败怎么办？

A: 请检查：
1. WPS_APP_ID 和 WPS_APP_SECRET 配置是否正确
2. 服务器时间是否准确（需要NTP同步）
3. 回调地址是否可以被WPS平台访问

### Q: LLM 调用失败？

A: 请检查：
1. LLM_API_BASE 地址是否正确
2. LLM_API_KEY 是否有效
3. 网络是否连通（内网环境）
4. LLM网关是否支持OpenAI标准接口

### Q: 收不到消息推送？

A: 请检查：
1. WPS开放平台的事件订阅是否已配置
2. 回调地址是否正确
3. 是否订阅了对应的事件类型
4. 服务是否正常运行

## 开发指南

### 添加新功能

1. **扩展消息处理**：修改 `channel/wps_channel.py`
2. **自定义回复逻辑**：修改 `bot/llm_bot.py`
3. **添加新命令**：在 `llm_bot.py` 的 `_handle_command` 方法中添加

## 许可证

MIT License

## 致谢

本项目参考了 [chatgpt-on-wechat](https://github.com/zhayujie/chatgpt-on-wechat) 的架构设计。
