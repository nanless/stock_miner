import yfinance as yf

# 设置要查询的股票代码（这里以苹果公司为例）
stock_symbol = "AAPL"

# 获取股票数据
stock = yf.Ticker(stock_symbol)

info = stock.info  # 获取股票的基本信息
print(info)

# 获取实时数据
real_time_data = stock.history(period="1d")  # 获取当天的股票数据
print("Real-time data:")
print(real_time_data)

# 获取历史数据（过去5天的收盘价）
historical_data = stock.history(period="5d")
print("\nHistorical data (last 5 days):")
print(historical_data)
