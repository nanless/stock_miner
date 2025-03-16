import asyncio
import aiohttp
import feedparser
import time
from datetime import datetime
import json

# Bloomberg RSSHub地址
rsshub_urls = {
    "彭博": "http://192.168.71.60:1200/bloomberg",
    "彭博商业": "http://192.168.71.60:1200/bloomberg/bbiz",
    "彭博政治": "http://192.168.71.60:1200/bloomberg/bpol",
    "彭博市场": "http://192.168.71.60:1200/bloomberg/markets",
    "彭博科技": "http://192.168.71.60:1200/bloomberg/technology",
    "路透美国": "http://192.168.71.60:1200/reuters/world/us",
    "路透中国": "http://192.168.71.60:1200/reuters/world/china",
    "路透商业": "http://192.168.71.60:1200/reuters/business",
    "路透亚太": "http://192.168.71.60:1200/reuters/world/asia-pacific",
}

# 飞书webhook地址
webhook_url = "https://open.feishu.cn/open-apis/bot/v2/hook/4151bf5e-8b82-4e9a-84f8-6dca5e299c5c"

# 用于存储已发送的文章ID
sent_ids_file = "bloomberg_reuters_push/sent_ids.json"

# Ollama API地址
ollama_api_url = "http://localhost:11434/api/chat"

# 加载已发送的文章ID
def load_sent_ids():
    try:
        with open(sent_ids_file, "r") as f:
            return set(json.load(f))
    except FileNotFoundError:
        return set()

# 保存已发送的文章ID
def save_sent_ids(ids):
    with open(sent_ids_file, "w") as f:
        json.dump(list(ids), f)

sent_ids = load_sent_ids()

async def translate_with_ollama(session, text):
    """使用Ollama API翻译文本"""
    payload = {
        "model": "qwen2.5:14b",
        "messages": [
            {"role": "system", "content": "You are Qwen, a great reader and translator!"},
            {"role": "user", "content": f"Translate this into Chinese, return only the translated text: {text}"}
        ],
        "stream": False
    }
    
    try:
        async with session.post(ollama_api_url, json=payload) as response:
            if response.status == 200:
                result = await response.json()
                return result["message"]["content"].strip()
            else:
                print(f"{datetime.now()}: Ollama API请求失败: 状态码={response.status}, URL={ollama_api_url}")
                return f"[翻译失败] {text}"
    except Exception as e:
        print(f"{datetime.now()}: Ollama API请求错误: {str(e)}, URL={ollama_api_url}")
        return f"[翻译失败] {text}"

async def send_to_feishu(session, title, link, timestamp, source):
    translated_title = await translate_with_ollama(session, title)
    message = {
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": f"{source}资讯 {timestamp}",
                    "content": [
                        [
                            {"tag": "text", "text": f"{title}\n"},
                            {"tag": "text", "text": f"译文: {translated_title}\n"},
                            {"tag": "a", "text": "阅读原文", "href": link}
                        ]
                    ]
                }
            }
        }
    }
    
    try:
        async with session.post(webhook_url, json=message) as response:
            if response.status == 200:
                print(f"{datetime.now()}: 成功发送: {title}")
            else:
                print(f"{datetime.now()}: 发送失败: {title}, 状态码: {response.status}")
    except Exception as e:
        print(f"{datetime.now()}: 发送时发生错误: {e}")

async def check_updates(session, source, url):
    global sent_ids
    try:
        async with session.get(url) as response:
            content = await response.text()
            feed = feedparser.parse(content)
            
            for entry in feed.entries:
                entry_id = entry.link
                # print("----------------------------------------------------------------------------------------------------")
                # for key, value in entry.items():
                #     print(f"{key}: {value}")
                if entry_id not in sent_ids:
                    await send_to_feishu(session, entry.title, entry.link, time.strftime("%Y-%m-%d %H:%M:%S", entry.published_parsed), source)
                    sent_ids.add(entry_id)
                    await asyncio.sleep(1)  # 休眠1秒，防止频繁发送
                    
    except Exception as e:
        print(f"{datetime.now()}: 检查更新时发生错误: {e}")

async def main():
    while True:
        async with aiohttp.ClientSession() as session:
            for source, url in rsshub_urls.items():
                print(f"{datetime.now()}: 开始检查{source}资讯...")
                await check_updates(session, source, url)
            # tasks = [check_updates(session, source, url) for (source, url) in rsshub_urls.items()]
            # await asyncio.gather(*tasks)
        
        save_sent_ids(sent_ids)
        
        print(f"{datetime.now()}: 休眠1小时...")
        await asyncio.sleep(3600)  # 每1小时检查一次更新

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("程序被用户中断")
    except Exception as e:
        print(f"发生未预期的错误: {e}")
    finally:
        save_sent_ids(sent_ids)
