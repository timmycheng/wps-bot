# WPS Bot 部署手册

## 一、系统要求

### 1.1 硬件要求

- CPU: 1核+
- 内存: 512MB+
- 磁盘: 1GB+

### 1.2 软件要求

- Docker 20.10+ （推荐）
- 或 Python 3.11+
- 网络: 与 WPS开放平台、LLM网关互通

## 二、WPS开放平台配置

### 2.1 创建企业内部应用

1. **登录 WPS 开放平台**
   - 访问 https://open.wps.cn/
   - 使用企业管理员账号登录

2. **创建应用**
   - 进入"应用管理"
   - 点击"创建应用"
   - 选择"企业内部应用"
   - 填写应用名称、描述等信息

3. **获取凭证**
   - 进入应用详情页
   - 记录 **AppID**
   - 记录 **AppSecret**（仅显示一次，请妥善保存）

### 2.2 配置事件订阅

1. **设置回调地址**
   - 进入应用详情 → 事件订阅
   - 填写回调URL: `https://your-server.com/event/callback`
   - 保存配置

2. **订阅事件类型**
   订阅以下事件：
   | 事件类型 | 说明 |
   |---------|------|
   | `url_verification` | URL验证（配置时自动触发） |
   | `kso.app_chat.message.create` | 机器人接收消息事件 |
   
   参考文档：https://365.kdocs.cn/3rd/open/documents/app-integration-dev/wps365/server/event-subscription/subscription-flow

3. **URL验证**
   - 保存回调地址时，WPS会发送验证请求
   - 服务需要正确响应验证请求
   - 验证通过后，才能正常接收事件

### 2.3 权限配置

确保应用有以下权限：
- 读取会话消息
- 发送会话消息
- 读取用户信息

## 三、服务部署

### 3.1 Docker 部署（推荐）

#### 步骤1: 准备环境文件

```bash
cd wps-bot

# 复制环境变量模板
cp .env.template .env

# 编辑 .env 文件
vim .env
```

填写必要配置：
```env
# WPS配置
WPS_APP_ID=your_app_id_here
WPS_APP_SECRET=your_app_secret_here
WPS_BASE_URL=https://xz.wps.cn

# LLM配置
LLM_API_KEY=your_llm_key
LLM_API_BASE=http://your-llm-gateway:8000/v1
LLM_MODEL=gpt-3.5-turbo
```

#### 步骤2: 构建并启动

```bash
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

#### 步骤3: 配置Nginx反向代理（生产环境）

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 3.2 直接部署

#### 步骤1: 安装依赖

```bash
# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

#### 步骤2: 配置

```bash
cp config.json.template config.json
vim config.json
```

#### 步骤3: 启动

```bash
# 正常模式
python app.py

# 或使用启动脚本
./start.sh
```

## 四、WPS-3 签名验证（事件回调）

WPS开放平台使用 WPS-3 签名算法验证事件回调请求合法性。

文档：https://365.kdocs.cn/3rd/open/documents/app-integration-dev/wps365/server/event-subscription/security-verification

### 签名算法

```
X-Kso-AppId: {APPID}
X-Kso-Signature: {Signature}
X-Kso-Timestamp: {Timestamp}
X-Kso-Nonce: {Nonce}

Signature = sha256(AppSecret + Timestamp + Nonce + Body)
```

### 请求头

| 请求头 | 说明 |
|--------|------|
| X-Kso-AppId | 应用ID |
| X-Kso-Signature | WPS-3签名 |
| X-Kso-Timestamp | 时间戳（毫秒） |
| X-Kso-Nonce | 随机字符串 |

### 验证逻辑

本服务会自动验证：
1. 请求头是否完整
2. AppID 是否匹配
3. 时间戳是否在有效期内（5分钟）
4. WPS-3 签名是否正确

## 五、KSO-1 签名（API调用）

调用WPS API时使用 KSO-1 签名。

文档：https://365.kdocs.cn/3rd/open/documents/app-integration-dev/wps365/server/api-description/signature-description-wps-3

### 签名算法

```
X-Kso-Authorization: KSO-1:{AppID}:{Signature}
X-Kso-Date: {RFC1123 Date}

Signature = base64(hmac-sha1(AppSecret, StringToSign))
StringToSign = HTTP-Verb + "\n" + Content-MD5 + "\n" + Content-Type + "\n" + Date + "\n" + {CanonicalizedResource}
```

### 请求头

| 请求头 | 说明 |
|--------|------|
| X-Kso-Authorization | KSO-1签名 |
| X-Kso-Date | RFC1123格式的日期 |
| Authorization | Bearer {access_token} |

## 五、内网环境特殊配置

### 5.1 纯内网部署

在无法访问互联网的环境中：

1. **离线构建镜像**
   ```bash
   # 在有网的机器构建
   docker-compose build
   docker save wps-bot > wps-bot.tar
   
   # 拷贝到内网机器
   docker load < wps-bot.tar
   ```

2. **使用内网PyPI源**
   ```bash
   pip install -r requirements.txt -i http://your-pypi-mirror/simple --trusted-host your-pypi-mirror
   ```

### 5.2 私有化WPS协作平台

如果使用私有化部署的WPS：

```env
# 修改WPS基础URL
WPS_BASE_URL=http://your-wps-server
```

### 5.3 网络连通性检查

```bash
# 检查WPS平台连通性
curl http://your-wps-server/api/v1/health

# 检查LLM网关连通性
curl http://your-llm-gateway:8000/v1/models
```

## 六、验证测试

### 6.1 URL验证测试

配置回调地址后，WPS会发送验证请求：

```json
{
  "event_type": "url_verification",
  "challenge": "random_challenge_string"
}
```

服务应返回：
```json
{
  "challenge": "random_challenge_string"
}
```

### 6.2 健康检查

```bash
curl http://localhost:8080/health

# 预期返回
{"status":"healthy"}
```

### 6.3 功能测试

1. **单聊测试**
   - 在WPS协作平台搜索机器人
   - 添加为好友
   - 发送消息测试

2. **群聊测试**
   - 创建测试群
   - 添加机器人进群
   - @机器人发送消息

## 七、监控与维护

### 7.1 日志查看

```bash
# Docker方式
docker-compose logs -f

# 直接运行方式
tail -f wps_bot.log
```

### 7.2 常见问题排查

#### 问题1: URL验证失败

症状: 在WPS开放平台配置回调地址时提示验证失败

排查:
1. 确认服务已启动并可访问
2. 检查防火墙设置
3. 查看服务日志，确认收到验证请求
4. 确认 WPS_APP_ID 和 WPS_APP_SECRET 配置正确

#### 问题2: 收不到消息推送

症状: 配置完成后，发送消息机器人无响应

排查:
1. 检查WPS开放平台的事件订阅配置
   - 回调地址是否正确
   - 是否订阅了 `kso.app_chat.message.create` 事件
2. 检查服务日志，确认是否收到推送
3. 检查网络连通性（WPS平台是否能访问回调地址）
4. 确认机器人在会话中（已添加好友或在群中）

#### 问题3: 签名验证失败

症状: 日志显示签名验证失败

排查:
1. 确认 WPS_APP_SECRET 配置正确
2. 检查服务器时间是否准确（需要NTP同步）
3. 查看请求头是否包含 Authorization、X-Wps-Nonce、X-Wps-Timestamp

#### 问题4: LLM调用超时

症状: 机器人响应慢或提示超时

排查:
1. 检查 LLM_API_BASE 地址是否正确
2. 检查网络连通性
3. 调整 request_timeout 配置
4. 检查LLM网关状态

## 八、安全加固

### 8.1 网络安全

1. **防火墙配置**
   ```bash
   # 仅开放必要端口
   iptables -A INPUT -p tcp --dport 443 -j ACCEPT
   iptables -A INPUT -p tcp --dport 8080 -s <wps-ip-range> -j ACCEPT
   iptables -A INPUT -p tcp --dport 8080 -j DROP
   ```

2. **HTTPS配置**
   - 生产环境必须使用HTTPS
   - 配置有效的SSL证书

### 8.2 密钥管理

1. 使用环境变量存储密钥
2. 定期轮换 AppSecret
3. 使用密钥管理服务（如Vault）

## 九、升级维护

### 9.1 版本升级

```bash
# 拉取新版本
git pull

# 重新构建
docker-compose down
docker-compose build
docker-compose up -d
```

### 9.2 数据备份

备份内容：
- 配置文件（config.json 或 .env）
- 日志文件

```bash
tar czvf wps-bot-backup.tar.gz config.json .env logs/
```

## 十、参考文档

- [WPS开放平台](https://open.wps.cn/)
- [OpenAI API文档](https://platform.openai.com/docs/)

## 获取支持

如有问题，请检查：
1. README.md 中的常见问题
2. 应用日志输出
3. WPS开放平台文档
