#!/bin/bash

while true
do  
    current_time=$(date +"%Y-%m-%d %H:%M:%S")
    echo "[$current_time] Starting stocknews_read_and_push.py..."
    # 使用nohup让python脚本在后台运行，并将标准输出和标准错误输出重定向到nohup.out文件
    nohup python stocknews_read_and_push.py > logs/stocknews_read_and_push.log 2>&1 &
    # 获取刚在后台启动的python脚本的进程ID（PID）
    python_pid=$!
    # 睡眠1个小时（3600秒）
    sleep 3600
    # 1小时后，尝试杀死之前启动的python脚本的进程，确保它结束运行
    kill $python_pid 2>/dev/null
    # 等待一段时间（比如10秒），确保进程已经被彻底终止，可根据实际情况调整时间
    sleep 10
done