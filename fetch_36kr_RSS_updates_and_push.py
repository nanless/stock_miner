import asyncio
import aiohttp
import feedparser
import time
from datetime import datetime
import json


# RSSHub地址
rsshub_urls = [
    "http://localhost:1200/36kr/newsflashes",
    "http://localhost:1200/36kr/hot-list"
]

# 飞书webhook地址
webhook_url = "https://open.feishu.cn/open-apis/bot/v2/hook/b2fc3cb6-75cd-4927-8f5b-e1e29b539156"

# 用于存储已发送的文章ID
sent_ids_file = "36kr_push/sent_ids.json"

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

async def send_to_feishu(session, title, link, timestamp, source):
    message = {
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": f"36氪资讯 {timestamp} - {source}",
                    "content": [
                        [
                            {"tag": "text", "text": f"{title}\n"},
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

async def check_updates(session, url):
    try:
        async with session.get(url) as response:
            content = await response.text()
            feed = feedparser.parse(content)
            # import pdb; pdb.set_trace()
            
            source = url.split("/")[-1]  # 从URL中提取源名称
            
            for entry in feed.entries:
                entry_id = entry.id if hasattr(entry, 'id') else entry.link
                if entry_id not in sent_ids:
                    await send_to_feishu(session, entry.title, entry.link, time.strftime("%Y-%m-%d %H:%M:%S", entry.published_parsed), source)
                    sent_ids.add(entry_id)
                    ## 休眠1秒，防止频繁发送
                    await asyncio.sleep(1)
                    
    except Exception as e:
        print(f"{datetime.now()}: 检查更新时发生错误: {e}")

async def main():
    while True:
        async with aiohttp.ClientSession() as session:
            tasks = [check_updates(session, url) for url in rsshub_urls]
            await asyncio.gather(*tasks)
        
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
