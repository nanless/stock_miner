import yfinance as yf
import time
import requests
import json
from datetime import datetime

# 飞书机器人 webhook URL
FEISHU_WEBHOOK_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/b3ec2a31-37df-4523-b6f4-0e2d174872ef"

# 要跟踪的股票代码列表
STOCKS = ["TQQQ", "TSLA", "NVDA", "PLTR", "AAPL", "GOOG", "BABA", "RIVN", "RGTI", "AMD", "OXY", "MU", "SNOW", "OKLO"]

# 设置价格变动阈值（百分比）
PRICE_THRESHOLD = 0.5

# 设置成交量变动阈值（百分比）
VOLUME_THRESHOLD = 20

# 获取股票当前数据（修改为支持盘前、盘后、夜盘）
def get_stock_data(symbol):
    stock = yf.Ticker(symbol)
    # 获取过去1天的数据，包含盘前、盘后、夜盘，时间间隔设为1分钟
    data = stock.history(period="1d", interval="1m")
    return {
        'price': data['Close'].iloc[-1],
        'volume': data['Volume'].iloc[-1],
        'prev_volume': data['Volume'].iloc[-1]
    }

# 发送飞书消息
def send_feishu_message(content):
    headers = {
        "Content-Type": "application/json"
    }
    payload = {
        "msg_type": "text",
        "content": {
            "text": content
        }
    }
    response = requests.post(FEISHU_WEBHOOK_URL, headers=headers, data=json.dumps(payload))
    return response.status_code == 200

# 主循环
def main():
    last_data = {symbol: get_stock_data(symbol) for symbol in STOCKS}

    while True:
        for symbol in STOCKS:
            current_data = get_stock_data(symbol)

            print(f"{symbol} 当前价格: ${current_data['price']:.2f}, 成交量: {current_data['volume']:,}")

            price_change = (current_data['price'] - last_data[symbol]['price']) / last_data[symbol]['price'] * 100
            volume_change = (current_data['volume'] - last_data[symbol]['prev_volume']) / last_data[symbol]['prev_volume'] * 100

            message = ""

            if abs(price_change) >= PRICE_THRESHOLD:
                message += f"股票 {symbol} 价格变动超过 {PRICE_THRESHOLD}%!\n"
                message += f"当前价格: ${current_data['price']:.2f}\n"
                message += f"价格变动: {price_change:.2f}%\n"

            if abs(volume_change) >= VOLUME_THRESHOLD:
                message += f"股票 {symbol} 成交量变动超过 {VOLUME_THRESHOLD}%!\n"
                message += f"当前成交量: {current_data['volume']:,}\n"
                message += f"成交量变动: {volume_change:.2f}%\n"

            if message:
                message += f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

                if send_feishu_message(message):
                    print(f"已发送 {symbol} 的提醒")
                else:
                    print(f"发送 {symbol} 的提醒失败")

                last_data[symbol] = current_data

        # 等待1分钟
        time.sleep(60)

if __name__ == "__main__":
    main()