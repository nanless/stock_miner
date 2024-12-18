import asyncio
import requests
from crawl4ai import AsyncWebCrawler, CacheMode
from transformers import AutoModelForCausalLM, AutoTokenizer
from bs4 import BeautifulSoup
import os
import random
import time
import yfinance as yf

workdir = "./stock_push"
model_name = "Qwen/Qwen2.5-7B-Instruct-AWQ"
history_file = f"{workdir}/history_news.txt"
markdowntext_file = f"{workdir}/news.md"

os.makedirs(workdir, exist_ok=True)  # 创建工作目录

def send_message_to_lark(message):
    webhook_url = "https://open.feishu.cn/open-apis/bot/v2/hook/28a08908-d41f-44f5-b27b-58c80ec43cd0"
    headers = {
        "Content-Type": "application/json"
    }
    data = {
        "msg_type": "text",
        "content": {
            "text": message
        }
    }
    response = requests.post(webhook_url, headers=headers, json=data)
    print("发送消息状态码:", response.status_code)
    print("发送消息响应:", response.text)
    return response.json()

model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype="auto",
    device_map="auto",
    cache_dir='/home/kemove/.cache/huggingface/hub'
)
tokenizer = AutoTokenizer.from_pretrained(model_name)

def parse_news_row_trending(row):
    # 提取公司标志（logo），这里根据html中class为news-card-logo下的img标签的src属性获取，需根据实际情况调整
    logo_elem = row.find('div', class_='news-card-logo').find('img')
    if logo_elem is not None:
        logo = logo_elem['src']
    else:
        logo = "未知"
    # 提取公司代码（symbol），根据类名为news-card-symbol的a标签文本获取
    symbol_elem = row.find('a', class_='news-card-symbol symbol-link')
    if symbol_elem is not None:
        symbol = symbol_elem.text
    else:
        symbol = "未知"
    # 提取新闻标题（title），根据类名为news-card-title的a标签文本获取，并去除首尾空白字符
    title_elem = row.find('a', class_='news-card-title')
    if title_elem is not None:
        title = title_elem.text.strip()
    else:
        title = "未知"
    # 构造新闻链接（link），根据类名为news-card-title的a标签的href属性结合网站基础域名构造完整链接
    link_elem = row.find('a', class_='news-card-title')
    if link_elem is not None:
        link = "https://www.stocktitan.net" + link_elem['href']
    else:
        link = "未知"
    # 提取新闻正文中相关信息（这里示例中暂未处理，如需提取更多如影响力、情感倾向等，要按网页结构找对应元素来解析，目前html结构中没明显对应展示，可根据实际业务需求完善）
    # 示例中先简单赋值默认值，你可以后续调整补充获取方式
    exchange = "未知"
    time_info = "未知"
    impact = "未知"
    sentiment = "未知"
    news_key = f"{symbol}_{title}"

    return logo, symbol, exchange, title, link, time_info, impact, sentiment, news_key

def parse_news_row(row):
    # 提取公司标志
    logo_elem = row.find('img', class_='live-feed-logo')
    if logo_elem is not None:
        logo = logo_elem['src']
    else:
        logo = "未知"
    # 提取公司代码和交易所
    symbol_elem = row.find('a', class_='symbol-link notranslate')
    if symbol_elem is not None:
        symbol = symbol_elem.text
    else:
        symbol = "未知"
    exchange = row.find('span', class_='feed-ticker').text.split(':')[1].strip()
    # 提取新闻标题和链接
    title_elem = row.find('a', class_='text-gray-dark feed-link')
    if title_elem is not None:
        title = title_elem.text.strip()
        link = "https://www.stocktitan.net" + title_elem['href']
    else:
        title = "未知"
        link = "未知"
    # 提取时间
    time_elem1 = row.find('time', class_='news-row-datetime')
    time_elem2 = row.find('span', class_='news-row-date')
    if time_elem1 is not None:
        # time_info = time_elem1.find('span', class_='data').text + " " + time_elem1.find('span', class_='time').text
        time_info = time_elem1.text.strip().replace('\n', ' ')
    elif time_elem2 is not None:
        time_info = time_elem2.text.strip()
    else:
        time_info = "未知"
    # 提取影响力和情感倾向
    impact_elems = row.find('div', class_='impact-bar').find_all('span', class_='dot full')
    if impact_elems is not None:
        impact = len(impact_elems)
    else:
        impact = "未知"
    sentiment_elems = row.find('div', class_='sentiment-bar').find_all('span', class_='dot full')
    if sentiment_elems is not None:
        sentiment = len(sentiment_elems)
    else:
        sentiment = "未知"

    news_key = f"{symbol}_{title}"
    
    return logo, symbol, exchange, title, link, time_info, impact, sentiment, news_key


def process_news_info(logo, symbol, exchange, title, link, time_info, impact, sentiment, news_key, history_news):
    if impact == "未知" or sentiment == "未知":
        valuable = True
    # elif impact >= 4 and sentiment >= 4:
    #     valuable = True
    elif impact >= 1 and sentiment >= 5:
        valuable = True
    elif impact >= 5 and sentiment >= 1:
        valuable = True
    else:
        valuable = False
    if valuable and news_key not in history_news:
        messages = [
            {"role": "system", "content": "You are Qwen, you are a great reader and translator!"},
            {"role": "user", "content": "Translate this title into Chinese, return only the translated text, discard all other texts: " + title}
        ]
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        model_inputs = tokenizer([text], return_tensors="pt").to(model.device)
        generated_ids = model.generate(**model_inputs, max_new_tokens=512)
        generated_ids = [output_ids[len(input_ids):] for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)]
        response = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
        translated_title = response.strip()

        # 获取股票数据
        stock = yf.Ticker(symbol)
        # print(f"股票数据：{stock}")
        info = stock.info  # 获取股票的基本信息
        # print(f"股票基本信息：{info}")
        longBusinessSummary = info['longBusinessSummary'] if 'longBusinessSummary' in info else "未知"
        if longBusinessSummary != "未知":
            messages = [
                {"role": "system", "content": "You are Qwen, you are a great reader and translator!"},
                {"role": "user", "content": "Translate this message into Chinese, return only the translated text, discard all other texts: " + longBusinessSummary}
            ]
            text = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True
            )
            model_inputs = tokenizer([text], return_tensors="pt").to(model.device)
            generated_ids = model.generate(**model_inputs, max_new_tokens=512)
            generated_ids = [output_ids[len(input_ids):] for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)]
            response = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
            longBusinessSummary_cn = response.strip()
        else:
            longBusinessSummary_cn = "未知"
        marketCap = info['marketCap'] if'marketCap' in info else "未知"
        if marketCap != "未知":
            marketCap = f"{marketCap/100000000:,.2f}亿"
        forwardPE = info['forwardPE'] if 'forwardPE' in info else "未知"
        forwardEps = info['forwardEps'] if 'forwardEps' in info else "未知"
        dividendYield = info['dividendYield'] if 'dividendYield' in info else "未知"
        regularMarketPrice = info['regularMarketPrice'] if'regularMarketPrice' in info else "未知"
        regularMarketChangePercent = info['regularMarketChangePercent'] if'regularMarketChangePercent' in info else "未知"
        regularMarketChange = info['regularMarketChange'] if'regularMarketChange' in info else "未知"
        regularMarketOpen = info['regularMarketOpen'] if'regularMarketOpen' in info else "未知"
        regularMarketDayHigh = info['regularMarketDayHigh'] if'regularMarketDayHigh' in info else "未知"
        regularMarketDayLow = info['regularMarketDayLow'] if'regularMarketDayLow' in info else "未知"

        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        news_info = f"当前时间：{current_time}\n"
        news_info += f"新闻时间：{time_info}\n"
        # news_info += f"公司标志：{logo}\n"
        news_info += f"公司代码：{symbol}\n"
        news_info += f"交易所：{exchange}\n"
        news_info += f"新闻标题（英文）：{title}\n"
        news_info += f"新闻标题（中文）：{translated_title}\n"
        news_info += f"新闻链接：{link}\n"
        news_info += f"影响力：{impact}\n"
        news_info += f"情感倾向：{sentiment}\n"
        # news_info += f"公司简介：{longBusinessSummary}\n"
        news_info += f"公司简介（中文）：{longBusinessSummary_cn}\n"
        news_info += f"市值：{marketCap}\n"
        news_info += f"PE: {forwardPE}\n"
        news_info += f"EPS: {forwardEps}\n"
        news_info += f"股息率：{dividendYield}\n"
        news_info += f"股价：{regularMarketPrice}\n"
        # news_info += f"涨跌幅：{regularMarketChangePercent}\n"
        # news_info += f"涨跌额：{regularMarketChange}\n"
        # news_info += f"开盘价：{regularMarketOpen}\n"
        # news_info += f"最高价：{regularMarketDayHigh}\n"
        # news_info += f"最低价：{regularMarketDayLow}\n"

        markdowntext = f"|![{symbol}]({logo}) | {symbol} | {title} (EN) | {translated_title} (CN) | [点击查看]({link}) | {exchange} | {time_info} | {impact} | {sentiment} |\n"
        with open(markdowntext_file, "a", encoding="utf-8") as f:
            f.write(markdowntext)
        with open(history_file, "a", encoding="utf-8") as f:
            f.write(news_key + "\n")
        send_message_to_lark(news_info)
        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        print(f"[{current_time}] 推送新闻：{news_key}")

        history_news.add(news_key)

async def fetch_and_process_news_feed(crawler, history_news, url):
    try:
        result = await crawler.arun(url=url, cache_mode=CacheMode.BYPASS)
        html_content = result.html
        soup = BeautifulSoup(html_content, 'html.parser')
        news_rows = soup.find_all('div', class_='d-flex py-2 news-row feed-border-gradient rounded my-2')
        
        for row in news_rows[::-1]:
            logo, symbol, exchange, title, link, time_info, impact, sentiment, news_key = parse_news_row(row)
            process_news_info(logo, symbol, exchange, title, link, time_info, impact, sentiment, news_key, history_news)
    except Exception as e:
        print(f"爬取或处理新闻时发生异常: {e}")

async def fetch_and_process_news_today(crawler, history_news, url):
    try:
        result = await crawler.arun(url=url, cache_mode=CacheMode.BYPASS)
        html_content = result.html
        soup = BeautifulSoup(html_content, 'html.parser')
        news_rows = soup.find_all('div', class_='d-flex py-2 news-row feed-border-gradient rounded my-2')
        for row in news_rows[::-1]:
            logo, symbol, exchange, title, link, time_info, impact, sentiment, news_key = parse_news_row(row)
            process_news_info(logo, symbol, exchange, title, link, time_info, impact, sentiment, news_key, history_news)
    except Exception as e:
        print(f"爬取或处理新闻时发生异常: {e}")

async def fetch_and_process_news_trending(crawler, history_news, url):
    try:
        result = await crawler.arun(url=url, cache_mode=CacheMode.BYPASS)
        html_content = result.html
        soup = BeautifulSoup(html_content, 'html.parser')
        # 从trending.html结构来看，新闻条目似乎都在类名为news-card的div中，这里据此提取新闻行元素，可根据实际情况调整
        news_rows = soup.find_all('div', class_='news-card')

        for row in news_rows:
            logo, symbol, exchange, title, link, time_info, impact, sentiment, news_key = parse_news_row_trending(row)
            process_news_info(logo, symbol, exchange, title, link, time_info, impact, sentiment, news_key, history_news)
    except Exception as e:
        print(f"爬取或处理新闻时发生异常: {e}")

async def main():
    history_news = set()
    try:
        with open(history_file, "r", encoding="utf-8") as f:
            history_news.update(line.strip() for line in f)
    except FileNotFoundError:
        pass

    markdowntext = "| 公司标志 | 公司代码 | 新闻标题 (EN ) | 新闻标题 (CN ) | 新闻链接 | 交易所 | 时间 | 影响 | 情感倾向 |\n"
    markdowntext += "| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
    with open(markdowntext_file, "w", encoding="utf-8") as f:
        f.write(markdowntext)

    url1 = "https://www.stocktitan.net/news/live.html"
    url2 = "https://www.stocktitan.net/news/today"
    url3 = "https://www.stocktitan.net/news/trending.html"  # 新增要监测的网页地址
    while True:
        try:
            async with AsyncWebCrawler(verbose=True) as crawler:
                await fetch_and_process_news_feed(crawler, history_news, url1)
                await fetch_and_process_news_today(crawler, history_news, url2)
                await fetch_and_process_news_trending(crawler, history_news, url3)  # 调用新的处理函数
                sleep_time = random.randint(30, 80)
                print(f"等待 {sleep_time} 秒后继续爬取...")
                await asyncio.sleep(sleep_time)
        except Exception as e:
            print(f"主循环发生异常: {e}")
            print("尝试重新初始化爬取器...")
            await asyncio.sleep(60)  # 等待60秒后重试

if __name__ == "__main__":
    asyncio.run(main())