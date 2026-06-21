#!/bin/bash
set -e

echo "🚀 AstrBot + 休眠代理 启动中..."

# ========== 1️⃣ 启动 AstrBot ==========
# 尝试几种方式启动 AstrBot（总有一种能工作）
echo "⏳ 正在启动 AstrBot..."

# 方式1: 直接运行 bot.py（最可靠）
if [ -f "/app/astrbot/bot.py" ]; then
    echo "📂 找到 /app/astrbot/bot.py，方式1启动..."
    cd /app
    python3 -u astrbot/bot.py &
    ASTRBOT_PID=$!
    
# 方式2: 检查 /AstrBot/bot.py
elif [ -f "/AstrBot/bot.py" ]; then
    echo "📂 找到 /AstrBot/bot.py，方式2启动..."
    cd /AstrBot
    python3 -u bot.py &
    ASTRBOT_PID=$!
    
# 方式3: 使用 astrbot 命令（有些版本有）
elif command -v astrbot &> /dev/null; then
    echo "📂 使用 astrbot 命令启动..."
    astrbot &
    ASTRBOT_PID=$!
    
else
    echo "⚠️ 未找到 AstrBot 入口文件，搜索中..."
    # 尝试搜索
    BOT_FILE=$(find / -name "bot.py" -path "*/astrbot*" 2>/dev/null | head -1)
    if [ -n "$BOT_FILE" ]; then
        echo "📂 找到: $BOT_FILE"
        cd "$(dirname "$(dirname "$BOT_FILE")")"
        python3 -u "$BOT_FILE" &
        ASTRBOT_PID=$!
    else
        echo "❌ 无法找到 AstrBot 入口！"
        echo "📁 列出 /app 目录:"
        ls -la /app/
        echo "📁 列出 /AstrBot 目录:"
        ls -la /AstrBot/ 2>/dev/null || echo "（不存在）"
        exit 1
    fi
fi

echo "✅ AstrBot 已启动 (PID: $ASTRBOT_PID)"

# ========== 2️⃣ 等待 AstrBot 就绪 ==========
echo "⏳ 等待 AstrBot 就绪（5秒）..."
sleep 5

# 检查是否还活着
if kill -0 $ASTRBOT_PID 2>/dev/null; then
    echo "🟢 AstrBot 运行中"
else
    echo "⚠️ AstrBot 已退出，检查日志中..."
    wait $ASTRBOT_PID 2>/dev/null || true
fi

# ========== 3️⃣ 启动休眠代理 ==========
echo "⏳ 启动休眠代理..."
cd /app
python3 -u sleep_proxy.py
