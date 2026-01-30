#!/bin/bash
# WPS Bot 启动脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}    WPS Bot 启动脚本${NC}"
echo -e "${GREEN}================================${NC}"
echo ""

# 检查配置文件
if [ ! -f "config.json" ] && [ ! -f ".env" ]; then
    echo -e "${YELLOW}警告: 未找到配置文件${NC}"
    echo "请复制并编辑配置文件："
    echo "  cp config.json.template config.json"
    echo "  或"
    echo "  cp .env.template .env"
    echo ""
fi

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误: 未找到 Python3${NC}"
    exit 1
fi

# 检查虚拟环境
if [ -d "venv" ]; then
    echo -e "${GREEN}激活虚拟环境...${NC}"
    source venv/bin/activate
fi

# 检查依赖
if ! python3 -c "import flask" 2>/dev/null; then
    echo -e "${YELLOW}安装依赖...${NC}"
    pip install -r requirements.txt
fi

# 启动模式选择
MODE=${1:-"normal"}

case $MODE in
    dev)
        echo -e "${GREEN}以开发模式启动...${NC}"
        export DEBUG=true
        export LOG_LEVEL=DEBUG
        python3 app.py --dev
        ;;
    docker)
        echo -e "${GREEN}以 Docker 模式启动...${NC}"
        docker-compose up -d
        echo -e "${GREEN}服务已启动，查看日志: docker-compose logs -f${NC}"
        ;;
    docker-build)
        echo -e "${GREEN}构建 Docker 镜像...${NC}"
        docker-compose build
        docker-compose up -d
        ;;
    stop)
        echo -e "${YELLOW}停止服务...${NC}"
        docker-compose down 2>/dev/null || true
        pkill -f "python3 app.py" 2>/dev/null || true
        echo -e "${GREEN}服务已停止${NC}"
        ;;
    *)
        echo -e "${GREEN}以正常模式启动...${NC}"
        python3 app.py
        ;;
esac
