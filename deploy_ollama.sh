#!/bin/bash

# 检查 Ollama 是否已经在运行
if pgrep -x "ollama" > /dev/null; then
    echo "Ollama 已经在运行中"
else
    echo "启动 Ollama 服务..."
    # 在后台启动 Ollama 服务
    nohup ollama serve > ollama.log 2>&1 &
    
    # 等待服务启动
    sleep 5
    
    # 拉取所需的模型
    echo "正在拉取 qwen2.5:14b 模型..."
    ollama pull qwen2.5:14b
    
    echo "Ollama 服务已启动，日志保存在 ollama.log"
fi

# 显示服务状态
echo "Ollama 服务状态："
ps aux | grep ollama | grep -v grep