FROM python:3.10-slim as base

WORKDIR /app

# Copy ffmpeg binary from a dedicated ffmpeg image to avoid apt downloads (works better in China)
FROM jrottenberg/ffmpeg:4.4-ubuntu2004 as ffmpeg

FROM base

# Copy only the ffmpeg binaries we need from the ffmpeg image
COPY --from=ffmpeg /usr/local/bin/ffmpeg /usr/local/bin/ffmpeg
COPY --from=ffmpeg /usr/local/bin/ffprobe /usr/local/bin/ffprobe

# 安装系统依赖（不包含 ffmpeg）
# Keep this minimal to avoid large builds in restricted networks
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    wget \
    && rm -rf /var/lib/apt/lists/* || (apt-get update && apt-get install -y --no-install-recommends ca-certificates wget --fix-missing -o Acquire::Retries=3 && rm -rf /var/lib/apt/lists/*)

# 安装Python依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 创建音频目录
RUN mkdir -p /app/audio

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 8001

# 启动应用
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]