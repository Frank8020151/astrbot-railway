FROM soulter/astrbot:latest
# 复制你自己的配置文件覆盖容器里的
COPY astrbot_config.json /app/astrbot_config.json
EXPOSE 6185
