while true
do  
    current_time=$(date +"%Y-%m-%d %H:%M:%S")
    echo "[$current_time] Starting important_twitter_forward.py..."
    python -u important_twitter_forward.py
    # 生成2000到4000秒之间的随机数作为睡眠时间
    sleep_time=$((RANDOM % 2001 + 2000))
    sleep $sleep_time
done