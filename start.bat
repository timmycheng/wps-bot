@echo off
chcp 65001 >nul

REM WPS Bot 启动脚本 (Windows)

echo ========================================
echo     WPS Bot 启动脚本
echo ========================================
echo.

REM 检查配置文件
if not exist "config.json" (
    if not exist ".env" (
        echo [警告] 未找到配置文件
        echo 请复制并编辑配置文件：
        echo   copy config.json.template config.json
        echo   或
        echo   copy .env.template .env
        echo.
    )
)

REM 检查Python环境
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python
    pause
    exit /b 1
)

REM 检查依赖
python -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo [信息] 安装依赖...
    pip install -r requirements.txt
)

REM 启动模式选择
if "%1"=="dev" (
    echo [信息] 以开发模式启动...
    set DEBUG=true
    set LOG_LEVEL=DEBUG
    python app.py --dev
) else if "%1"=="docker" (
    echo [信息] 以 Docker 模式启动...
    docker-compose up -d
    echo [信息] 服务已启动，查看日志: docker-compose logs -f
) else if "%1"=="docker-build" (
    echo [信息] 构建 Docker 镜像...
    docker-compose build
    docker-compose up -d
) else if "%1"=="stop" (
    echo [信息] 停止服务...
    docker-compose down 2>nul
    taskkill /F /IM python.exe 2>nul
    echo [信息] 服务已停止
) else (
    echo [信息] 以正常模式启动...
    python app.py
)

pause
