# Docker 镜像自动构建

## 快速开始

### Windows (PowerShell)

```powershell
# 递增 patch 版本号 (默认)
.\build.ps1

# 递增 minor 版本号
.\build.ps1 minor

# 递增 major 版本号
.\build.ps1 major

# 指定版本号
.\build.ps1 1.2.3
```

### Linux/Mac (Bash)

```bash
# 递增 patch 版本号 (默认)
./build.sh

# 递增 minor 版本号
./build.sh minor

# 递增 major 版本号
./build.sh major

# 指定版本号
./build.sh 1.2.3
```

## 功能特性

1. **自动版本号管理**
   - 版本号保存在 `.version` 文件中
   - 支持 semantic versioning (major.minor.patch)
   - 自动递增版本号

2. **自动构建**
   - 构建指定版本的镜像
   - 同时标记为 `latest`
   - 使用指定的 Dockerfile

3. **自动保存**
   - 导出为 tar 包：`wps-bot-x.x.x.tar`
   - 可选 gzip 压缩
   - 显示文件大小

4. **构建产物**
   - 镜像：`wps-bot:x.x.x` 和 `wps-bot:latest`
   - 文件：`wps-bot-x.x.x.tar` (可选 `.gz`)

## 使用示例

```powershell
# 第一次构建
PS> .\build.ps1
版本信息:
  当前版本: 0.0.0
  新版本:   0.0.1
...
构建完成!
  镜像: wps-bot:0.0.1
  文件: wps-bot-0.0.1.tar (大小: 245.32 MB)

# 第二次构建 (patch 递增)
PS> .\build.ps1
...
  新版本: 0.0.2

# 功能更新 (minor 递增)
PS> .\build.ps1 minor
...
  新版本: 0.1.0

# 重大更新 (major 递增)
PS> .\build.ps1 major
...
  新版本: 1.0.0
```

## 部署使用

```bash
# 加载镜像
docker load -i wps-bot-1.0.0.tar

# 运行容器
docker run -d --name wps-bot \
  -p 8080:8080 \
  -e WPS_APP_ID=xxx \
  -e WPS_APP_SECRET=xxx \
  -e LLM_API_KEY=xxx \
  wps-bot:1.0.0
```
