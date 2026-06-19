FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y git && \
    git clone https://github.com/Soulter/AstrBot.git . && \
    pip install -r requirements.txt --no-cache-dir

COPY astrbot_config.json /app/

EXPOSE 6185

CMD ["python", "main.py"]
