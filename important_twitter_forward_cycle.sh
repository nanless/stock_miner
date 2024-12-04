while true
do  
    current_time=$(date +"%Y-%m-%d %H:%M:%S")
    echo "[$current_time] Starting important_twitter_forward.py..."
    python important_twitter_forward.py
    # 生成300到600秒之间的随机数作为睡眠时间
    sleep_time=$((RANDOM % 301 + 300))
    sleep $sleep_time
done