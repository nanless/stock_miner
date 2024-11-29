import asyncio
import requests
from crawl4ai import AsyncWebCrawler, CacheMode
from transformers import AutoModelForCausalLM, AutoTokenizer
from bs4 import BeautifulSoup
import os

workdir = "./stock_push"
# 填入你的飞书应用的App ID和App Secret
APP_ID = "cli_a7c22ac1d1b8d013"
APP_SECRET = "efGH19knib2AcbTiYJIgGcHfFWeIWxzz"
CHAT_ID = "oc_180cb0c9845d4e7fabd68b6439d0679a"
model_name = "Qwen/Qwen2.5-7B-Instruct"
history_file = f"{workdir}/history_news.txt"  # 定义存储历史新闻的文件
markdowntext_file = f"{workdir}/news.md"

os.makedirs(workdir, exist_ok=True)  # 创建工作目录

def get_access_token():
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {
        "Content-Type": "application/json"
    }
    data = {
        "app_id": APP_ID,
        "app_secret": APP_SECRET
    }
    response = requests.post(url, headers=headers, json=data)
    print("获取访问令牌的请求状态码:", response.status_code)  # 新增打印状态码
    print("获取访问令牌的请求响应内容:", response.text)  # 新增打印完整响应内容
    result = response.json()
    if "tenant_access_token" in result:
        return result["tenant_access_token"]
    else:
        raise Exception(f"获取访问令牌失败: {result}")

def send_message_to_lark(message, access_token, chat_id):
    url = f"https://open.feishu.cn/open-apis/message/v4/send/?access_token={access_token}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
    }
    print("发送消息的请求头:", headers)  # 新增打印请求头语句
    data = {
        "msg_type": "text",
        "content": {
            "text": message
        },
        "chat_id": chat_id
    }
    print("发送消息的请求数据:", data)  # 新增打印请求数据语句
    response = requests.post(url, headers=headers, json=data)
    print("发送消息的请求状态码:", response.status_code)  # 新增打印状态码
    print("发送消息的请求响应内容:", response.text)  # 新增打印完整响应内容
    return response.json()

# model_name = "Qwen/Qwen2.5-7B-Instruct-AWQ"

model = AutoModelForCausalLM.from_pretrained(
    model_name,
    # torch_dtype=torch.float16,
    # attn_implementation="flash_attention_2",
    torch_dtype="auto",
    device_map="auto",
    cache_dir='/home/kemove/.cache/huggingface/hub'
)
tokenizer = AutoTokenizer.from_pretrained(model_name)

async def main():
    access_token = get_access_token()  # 获取访问令牌
    print(f"访问令牌：{access_token}")
    async with AsyncWebCrawler(verbose=True) as crawler:
        history_news = set()  # 用于存储历史新闻的集合，方便快速查找比对
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                for line in f:
                    history_news.add(line.strip())  # 读取历史文件，将每行新闻记录加入集合
        except FileNotFoundError:
            pass  # 如果文件不存在，说明是首次运行，无需处理

        markdowntext = "| 公司标志 | 公司代码 | 新闻标题 | 新闻链接 | 交易所 | 时间 | 影响 | 情感倾向 |\n"
        markdowntext += "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
        with open(markdowntext_file, "w", encoding="utf-8") as f:
            f.write(markdowntext)

        while True:  # 设置循环来持续定时爬取
            result = await crawler.arun(url="https://www.stocktitan.net/news/live.html", cache_mode=CacheMode.BYPASS)
            # markdowntext = result.markdown
            # markdowntext = BeautifulSoup(markdowntext, 'html.parser').get_text()
            # markdowntext = re.sub(r'[^\w\s]', '', markdowntext)
            html_content = result.html

            # 使用BeautifulSoup解析HTML
            soup = BeautifulSoup(html_content, 'html.parser')

            # 找到所有的新闻行
            news_rows = soup.find_all('div', class_='d-flex py-2 news-row feed-border-gradient rounded my-2')

            # new_news_to_send = []  # 存储本次新出现的需要发送的新闻

            # 遍历新闻行并提取信息
            for row in news_rows[::-1]:
                # 提取公司标志
                logo = row.find('img', class_='live-feed-logo')['src']
                # 提取公司代码
                symbol = row.find('a', class_='symbol-link notranslate').text
                # 提取新闻标题
                title = row.find('a', class_='text-gray-dark feed-link').text
                original_title = title.strip()
                news_key = f"{symbol}_{original_title}"  # 构造一个能唯一标识新闻的键，这里简单用公司代码和标题组合，可根据实际情况调整更合适的方式
                # 提取新闻链接
                link = "https://www.stocktitan.net" + row.find('a', class_='text-gray-dark feed-link')['href']
                # 提取交易所
                exchange = row.find('span', class_='feed-ticker').text.split(':')[1].strip()
                # 提取时间
                time = row.find('time', class_='news-row-datetime')
                date = time.find('span', class_='date').text
                time = time.find('span', class_='time').text
                # 提取影响
                impact = len(row.find('div', class_='impact-bar').find_all('span', class_='dot full'))
                # 提取情感倾向
                sentiment = len(row.find('div', class_='sentiment-bar').find_all('span', class_='dot full'))

                # 判断是否值得推送
                valuable = False
                if impact >= 4 and sentiment >= 4:
                    valuable = True
                elif impact >= 2 and sentiment >= 5:
                    valuable = True
                elif impact >= 5 and sentiment >= 2:
                    valuable = True
                else:
                    valuable = False

                # 翻译并推送
                if valuable and news_key not in history_news:
                    # 翻译新闻标题
                    messages = [
                        {"role": "system", "content": "You are Qwen, you are a great reader and translate!"},
                        # {"role": "user", "content": "I want to read news from stocktitan.net and translate it to Chinese. the news are as follows: " + markdowntext}
                        {"role": "user", "content": "I want you to read news and translate it to Chinese without other information, just translate. the news are as follows: " + title}
                    ]
                    text = tokenizer.apply_chat_template(
                        messages,
                        tokenize=False,
                        add_generation_prompt=True
                    )
                    model_inputs = tokenizer([text], return_tensors="pt").to(model.device)

                    generated_ids = model.generate(
                        **model_inputs,
                        max_new_tokens=1024
                    )
                    generated_ids = [
                        output_ids[len(input_ids):] for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
                    ]

                    response = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
                    title = response
                    news_info = f"公司代码：{symbol}\n新闻事件：{time}\n新闻标题：{title}\n新闻链接：{link}\n影响力：{impact}\n情感倾向：{sentiment}"
                    # new_news_to_send.append(news_info)  # 将新的符合条件的新闻加入待发送列表
                    history_news.add(news_key)  # 将新新闻的标识加入历史记录集合
                    # 构造Markdown格式的表格行
                    markdowntext = f"|![{symbol}]({logo}) | {symbol} | {title} | [点击查看]({link}) | {exchange} | {date} {time} | {impact} | {sentiment} |\n"
                    with open(markdowntext_file, "a", encoding="utf-8") as f:
                        f.write(markdowntext)
                    with open(history_file, "a", encoding="utf-8") as f:
                        f.write(news_key + "\n")
                    send_message_to_lark(news_info, access_token, CHAT_ID)
                    print(f"推送新闻：{news_key}")

            await asyncio.sleep(60)  # 每隔一分钟进行一次爬取操作

if __name__ == "__main__":
    asyncio.run(main())