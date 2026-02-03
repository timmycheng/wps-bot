# WPS Bot Dockerfile - 多阶段构建优化版
# 使用uv进行依赖管理，最终镜像体积大幅缩小

# =============================================================================
# 阶段1：依赖安装（使用uv官方镜像）
# =============================================================================
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder

WORKDIR /app

# 启用编译模式加速启动
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# 安装构建依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖定义文件
COPY pyproject.toml uv.lock ./

# 创建虚拟环境并安装依赖（不安装项目本身）
RUN uv venv /app/.venv && \
    uv sync --frozen --no-install-project

# =============================================================================
# 阶段2：最终运行镜像（精简版）
# =============================================================================
FROM python:3.11-slim-bookworm

WORKDIR /app

# 安装运行时必要的系统依赖（仅健康检查所需）
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 从builder阶段复制虚拟环境
COPY --from=builder /app/.venv /app/.venv

# 设置环境变量，使用虚拟环境中的Python
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 复制应用代码
COPY app.py config.py ./
COPY bot/ ./bot/
COPY bridge/ ./bridge/
COPY channel/ ./channel/
COPY common/ ./common/
COPY lib/ ./lib/

# 创建日志目录
RUN mkdir -p /app/logs

# 暴露端口
EXPOSE 8080

# 健康检查（使用curl更轻量）
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -fs http://localhost:8080/health || exit 1

# 启动命令（直接使用虚拟环境中的Python）
CMD ["python", "app.py"]
