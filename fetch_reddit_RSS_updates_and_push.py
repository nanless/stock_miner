import asyncio
import json
import time
import random
from datetime import datetime
import aiohttp
from transformers import AutoModelForCausalLM, AutoTokenizer
import feedparser
import requests

# --- 配置 ---
webhook_url = "https://open.feishu.cn/open-apis/bot/v2/hook/c1e4eee2-d642-49bc-9916-5b3e9fa79502"
reddit_rss_urls = [
    "https://www.reddit.com/r/Shortsqueeze/.rss",
    "https://www.reddit.com/r/pennystocks/.rss",
    "https://www.reddit.com/r/wallstreetbets/.rss",
    "https://www.reddit.com/r/investing/.rss",
    "https://www.reddit.com/r/stocks/.rss",
    "https://www.reddit.com/r/options/.rss"
]
sent_posts_file = "reddit_push/sent_posts.json"
model_name = "Qwen/Qwen2.5-7B-Instruct-AWQ"
cache_dir = '/home/kemove/.cache/huggingface/hub'
# --- 配置结束 ---

# 全局变量
sent_post_ids = set()

# 加载qwen模型及分词器
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype="auto",
    device_map="auto",
    cache_dir=cache_dir
)
tokenizer = AutoTokenizer.from_pretrained(model_name)

def load_sent_post_ids():
    try:
        with open(sent_posts_file, "r") as f:
            return set(json.load(f))
    except FileNotFoundError:
        return set()

def save_sent_post_ids(ids):
    with open(sent_posts_file, "w") as f:
        json.dump(list(ids), f)

async def send_to_feishu(post_title, post_content, post_url, author, timestamp):
    formatted_time = time.strftime("%Y-%m-%d %H:%M:%S", timestamp)
    messages = [
        {"role": "system", "content": "You are Qwen, a great reader and translator!"},
        {"role": "user", "content": "Translate this Reddit post title into Chinese, return only the translated text: Title: " + post_title}
    ]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    model_inputs = tokenizer([text], return_tensors="pt").to(model.device)
    generated_ids = model.generate(**model_inputs, max_new_tokens=512)
    generated_ids = [output_ids[len(input_ids):] for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)]
    response = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
    translated_text = response.strip()

    message = {
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": f"{author} 在 {formatted_time} 的Reddit帖子",
                    "content": [
                        [
                            {"tag": "text", "text": "标题原文: " + post_title + "\n标题译文:" + translated_text + "\n"},
                            {"tag": "a", "text": "查看原文", "href": post_url}
                        ],
                    ]
                }
            }
        }
    }
    headers = {'Content-Type': 'application/json'}
    async with aiohttp.ClientSession() as session:
        async with session.post(webhook_url, json=message, headers=headers) as response:
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"{current_time} 已推送Reddit帖子到飞书，帖子标题: {post_title}, 帖子链接: {post_url}, 飞书响应状态码: {response.status}, 响应内容: {await response.text()}")

def fetch_rss_feed(url):
    feeds = feedparser.parse(url)
    return feeds

async def process_reddit_rss():
    global sent_post_ids
    
    try:
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 正在抓取 Reddit RSS更新...")
        
        for reddit_rss_url in reddit_rss_urls:
            # 获取RSS更新
            entries = fetch_rss_feed(reddit_rss_url).entries
            
            for entry in entries:
                post_title = entry.title
                post_content = entry.summary
                post_url = entry.link
                post_author = entry.author
                post_timestamp = entry.published_parsed
                post_id = entry.id

                if post_id not in sent_post_ids:
                    await send_to_feishu(post_title, post_content, post_url, post_author, post_timestamp)
                    sent_post_ids.add(post_id)
                
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 完成 Reddit RSS处理...")

    except Exception as e:
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 处理Reddit RSS时发生错误: {e}")

async def main():
    global sent_post_ids
    sent_post_ids = load_sent_post_ids()

    while True:
        await process_reddit_rss()
        save_sent_post_ids(sent_post_ids)

        # 在1-2小时之间随机选择睡眠时间
        sleep_time = random.uniform(1800, 3200)  # 3600秒 = 1小时, 7200秒 = 2小时
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 睡眠 {sleep_time:.2f} 秒...")
        await asyncio.sleep(sleep_time)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 发生错误: {e}")
