import asyncio
import requests
from crawl4ai import AsyncWebCrawler, CacheMode
from transformers import AutoModelForCausalLM, AutoTokenizer
from bs4 import BeautifulSoup
import os
import random
import time

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

async def fetch_and_process_news_feed(crawler, history_news, url):
    try:
        result = await crawler.arun(url=url, cache_mode=CacheMode.BYPASS)
        html_content = result.html
        soup = BeautifulSoup(html_content, 'html.parser')
        news_rows = soup.find_all('div', class_='d-flex py-2 news-row feed-border-gradient rounded my-2')
        
        for row in news_rows[::-1]:
            logo = row.find('img', class_='live-feed-logo')['src']
            symbol = row.find('a', class_='symbol-link notranslate').text
            title = row.find('a', class_='text-gray-dark feed-link').text.strip()
            news_key = f"{symbol}_{title}"
            link = "https://www.stocktitan.net" + row.find('a', class_='text-gray-dark feed-link')['href']
            exchange = row.find('span', class_='feed-ticker').text.split(':')[1].strip()
            time_elem = row.find('time', class_='news-row-datetime')
            date = time_elem.find('span', class_='date').text
            time_info = time_elem.find('span', class_='time').text
            impact = len(row.find('div', class_='impact-bar').find_all('span', class_='dot full'))
            sentiment = len(row.find('div', class_='sentiment-bar').find_all('span', class_='dot full'))

            valuable = (impact >= 4 and sentiment >= 4) or (impact >= 2 and sentiment >= 5) or (impact >= 5 and sentiment >= 2)

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
                # text = f"Translate this news into Chinese: {title}"
                # model_inputs = tokenizer([text], return_tensors="pt").to(model.device)

                generated_ids = model.generate(**model_inputs, max_new_tokens=1024)
                response = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
                translated_title = response.strip()

                current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                # news_info = f"当前时间：{current_time}\n公司代码：{symbol}\n新闻事件：{time_info}\n新闻标题：{translated_title}\n新闻链接：{link}\n影响力：{impact}\n情感倾向：{sentiment}"
                # markdowntext = f"|![{symbol}]({logo}) | {symbol} | {translated_title} | [点击查看]({link}) | {exchange} | {date} {time_info} | {impact} | {sentiment} |\n"
                # 更新新闻信息的显示格式
                news_info = f"当前时间：{current_time}\n公司代码：{symbol}\n新闻事件：{time_info}\n新闻标题（英文）：{title}\n新闻标题（中文）：{translated_title}\n新闻链接：{link}\n影响力：{impact}\n情感倾向：{sentiment}"

                # 更新markdown的展示格式
                markdowntext = f"|![{symbol}]({logo}) | {symbol} | {title} (EN) | {translated_title} (CN) | [点击查看]({link}) | {exchange} | {time_info} | {impact} | {sentiment} |\n"


                with open(markdowntext_file, "a", encoding="utf-8") as f:
                    f.write(markdowntext)
                with open(history_file, "a", encoding="utf-8") as f:
                    f.write(news_key + "\n")
                send_message_to_lark(news_info)
                print(f"推送新闻：{news_key}")

                history_news.add(news_key)
    except Exception as e:
        print(f"爬取或处理新闻时发生异常: {e}")

async def fetch_and_process_news_today(crawler, history_news, url):
    try:
        result = await crawler.arun(url=url, cache_mode=CacheMode.BYPASS)
        html_content = result.html
        soup = BeautifulSoup(html_content, 'html.parser')
        news_rows = soup.find_all('div', class_='d-flex py-2 news-row feed-border-gradient rounded my-2')
        # print(f"今日有{len(news_rows)}条新闻")
        for row in news_rows[::-1]:
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
            exchange_elem = row.find('span', class_='feed-ticker').text.split(':')[1].strip()

            # 提取新闻标题和链接
            title_elem = row.find('a', class_='text-gray-dark feed-link')
            if title_elem is not None:
                title = title_elem.text.strip()
                link = "https://www.stocktitan.net" + title_elem['href']
            else:
                title = "未知"
                link = "未知"

            news_key = f"{symbol}_{title}"

            # 提取时间
            time_elem = row.find('span', class_='news-row-date')
            if time_elem is not None:
                time_info = time_elem.text
            else:
                time_info = "未知"

            # 提取影响力和情感倾向
            impact_elems = row.find('div', class_='impact-bar').find_all('span', class_='dot full')
            impact = len(impact_elems)
            sentiment_elems = row.find('div', class_='sentiment-bar').find_all('span', class_='dot full')
            sentiment = len(sentiment_elems)

            # print(f"processing news today: {news_key} - {title} - {link} - {time_info} - {impact} - {sentiment}")

            valuable = (impact >= 4 and sentiment >= 4) or (impact >= 2 and sentiment >= 5) or (impact >= 5 and sentiment >= 2)

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
                # text = f"Translate this news into Chinese: {title}"
                # model_inputs = tokenizer([text], return_tensors="pt").to(model.device)

                generated_ids = model.generate(**model_inputs, max_new_tokens=1024)
                response = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
                translated_title = response.strip()

                current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                # news_info = f"当前时间：{current_time}\n公司代码：{symbol}\n新闻事件：{time_info}\n新闻标题：{translated_title}\n新闻链接：{link}\n影响力：{impact}\n情感倾向：{sentiment}"
                # markdowntext = f"|![{symbol}]({logo}) | {symbol} | {translated_title} | [点击查看]({link}) | {exchange_elem} | {time_info} | {impact} | {sentiment} |\n"
                # 更新新闻信息的显示格式
                news_info = f"当前时间：{current_time}\n公司代码：{symbol}\n新闻事件：{time_info}\n新闻标题（英文）：{title}\n新闻标题（中文）：{translated_title}\n新闻链接：{link}\n影响力：{impact}\n情感倾向：{sentiment}"

                # 更新markdown的展示格式
                markdowntext = f"|![{symbol}]({logo}) | {symbol} | {title} (EN) | {translated_title} (CN) | [点击查看]({link}) | {exchange_elem} | {time_info} | {impact} | {sentiment} |\n"
                
                with open(markdowntext_file, "a", encoding="utf-8") as f:
                    f.write(markdowntext)
                with open(history_file, "a", encoding="utf-8") as f:
                    f.write(news_key + "\n")
                send_message_to_lark(news_info)
                print(f"推送新闻：{news_key}")

                history_news.add(news_key)
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

            news_key = f"{symbol}_{title}"
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

            # print(f"processing news trending: {news_key} - {title} - {link} - {time_info} - {impact} - {sentiment}")
            if news_key not in history_news:
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
                # text = f"Translate this news into Chinese: {title}"
                # model_inputs = tokenizer([text], return_tensors="pt").to(model.device)


                generated_ids = model.generate(**model_inputs, max_new_tokens=1024)
                response = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
                translated_title = response.strip()

                current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                # news_info = f"当前时间：{current_time}\n公司代码：{symbol}\n新闻事件：{time_info}\n新闻标题：{translated_title}\n新闻链接：{link}\n影响力：{impact}\n情感倾向：{sentiment}"
                # markdowntext = f"|![{symbol}]({logo}) | {symbol} | {translated_title} | [点击查看]({link}) | {exchange} | {time_info} | {impact} | {sentiment} |\n"
                # 更新新闻信息的显示格式
                news_info = f"当前时间：{current_time}\n公司代码：{symbol}\n新闻事件：{time_info}\n新闻标题（英文）：{title}\n新闻标题（中文）：{translated_title}\n新闻链接：{link}\n影响力：{impact}\n情感倾向：{sentiment}"

                # 更新markdown的展示格式
                markdowntext = f"|![{symbol}]({logo}) | {symbol} | {title} (EN) | {translated_title} (CN) | [点击查看]({link}) | {exchange} | {time_info} | {impact} | {sentiment} |\n"


                with open(markdowntext_file, "a", encoding="utf-8") as f:
                    f.write(markdowntext)
                with open(history_file, "a", encoding="utf-8") as f:
                    f.write(news_key + "\n")
                send_message_to_lark(news_info)
                print(f"推送新闻：{news_key}")

                history_news.add(news_key)
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