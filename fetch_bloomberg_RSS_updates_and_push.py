import asyncio
import aiohttp
import feedparser
import time
from datetime import datetime
import json
from transformers import AutoModelForCausalLM, AutoTokenizer

# Bloomberg RSSHub地址
rsshub_urls = [
    "http://192.168.71.60:1200/bloomberg",
    "http://192.168.71.60:1200/bloomberg/bbiz",
    "http://192.168.71.60:1200/bloomberg/bpol",
    "http://192.168.71.60:1200/bloomberg/markets",
    "http://192.168.71.60:1200/bloomberg/technology"
]

# 飞书webhook地址
webhook_url = "https://open.feishu.cn/open-apis/bot/v2/hook/4151bf5e-8b82-4e9a-84f8-6dca5e299c5c"

# 用于存储已发送的文章ID
sent_ids_file = "bloomberg_push/sent_ids.json"

model_name = "Qwen/Qwen2.5-7B-Instruct-AWQ"
cache_dir = '/home/kemove/.cache/huggingface/hub'

# 加载qwen模型及分词器
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype="auto",
    device_map="auto",
    cache_dir=cache_dir
)
tokenizer = AutoTokenizer.from_pretrained(model_name)

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
    messages = [
        {"role": "system", "content": "You are Qwen, a great reader and translator!"},
        {"role": "user", "content": "Translate this into Chinese, return only the translated text: " + title}
    ]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    model_inputs = tokenizer([text], return_tensors="pt").to(model.device)
    generated_ids = model.generate(**model_inputs, max_new_tokens=512)
    generated_ids = [output_ids[len(input_ids):] for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)]
    response = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
    translated_title = response.strip()
    message = {
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": f"Bloomberg资讯 {timestamp} - {source}",
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

async def check_updates(session, url):
    try:
        async with session.get(url) as response:
            content = await response.text()
            feed = feedparser.parse(content)
            
            source = url.split("/")[-1]  # 从URL中提取源名称
            
            for entry in feed.entries:
                entry_id = entry.id if hasattr(entry, 'id') else entry.link
                print("----------------------------------------------------------------------------------------------------")
                for key, value in entry.items():
                    print(f"{key}: {value}")
                if entry_id not in sent_ids:
                    await send_to_feishu(session, entry.title, entry.link, time.strftime("%Y-%m-%d %H:%M:%S", entry.published_parsed), source)
                    sent_ids.add(entry_id)
                    await asyncio.sleep(1)  # 休眠1秒，防止频繁发送
                    
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
