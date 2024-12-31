import asyncio
import json
import time
import random
from datetime import datetime, timedelta
import aiohttp
from transformers import AutoModelForCausalLM, AutoTokenizer
import feedparser
from playwright.async_api import async_playwright

# --- 配置 ---
webhook_url = "https://open.feishu.cn/open-apis/bot/v2/hook/f97028b8-d693-4c23-989b-639a68807e2d"
target_usernames = ["myfxtrader", "tzwqbest", "GlobalMoneyAI", "AsiaFinance", "OldK_Gillis", "qinbafrank", 
                    "xlh1238899", "guyisheng1", "telebi7", "caijingshujuku", "hhuang", "zeyu_kap", "bboczeng", 
                    "zebrahelps", "angel71911", "yanbojack", "turingou", "Awsomefo", "ANDREW_FDWT", "ngw888", 
                    "HitAshareLimit", "BFBSHCD", "realwuzhe", "cnfinancewatch", "zhaocaishijie", "hungjng69679118", 
                    "dacefupan", "__Inty__", "andy_sharks", "DogutOscar", "x001fx", "cnAspeculation", "Hoyooyoo", 
                    "hongsv11", "ShanghaoJin", "yiguxia", "yamato812536", "tychozzz", "caolei1", "Vson0903", 
                    "benjman89", "dmjk001", "Rumoreconomy", "liqiang365", "dacejiangu", "frost_jazmyn", 
                    "TJ_Research01", "QihongF44102", "SupFin", "yangskyfly", "Capitalpedia", "hybooospx", 
                    "91grok", "financehybooo", "yangcy199510182", "business", "economics", "BloombergAsia", 
                    "markets", "stocktalkweekly", "MonkEchevarria", "ThetaWarrior", "MacroMargin", "hybooonews",
                    "TradingThomas3", "WSJ", "TheTranscript_", "Tesla_Cybercat", "BilingualReader", "The_RockTrading",
                    "realDonaldTrump", "elonmusk", "SpaceX"]
target_urls = {username: f"https://rsshub.app/twitter/user/{username}" for username in target_usernames}
sent_tweets_file = "twitter_push/sent_tweets.json"
model_name = "Qwen/Qwen2.5-7B-Instruct-AWQ"
cache_dir = '/home/kemove/.cache/huggingface/hub'
max_concurrent_requests = 4  # 设置最大并发数
# --- 配置结束 ---

# 全局变量
sent_tweet_ids = set()

# 加载qwen模型及分词器
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype="auto",
    device_map="auto",
    cache_dir=cache_dir
)
tokenizer = AutoTokenizer.from_pretrained(model_name)

def load_sent_tweet_ids():
    try:
        with open(sent_tweets_file, "r") as f:
            return set(json.load(f))
    except FileNotFoundError:
        return set()

def save_sent_tweet_ids(ids):
    with open(sent_tweets_file, "w") as f:
        json.dump(list(ids), f)

async def send_to_feishu(tweet_text, tweet_url, username):
    messages = [
        {"role": "system", "content": "You are Qwen, a great reader and translator!"},
        {"role": "user", "content": "Translate this tweet into Chinese, return only the translated text: " + tweet_text}
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
                    "title": f"{username} 的最新推文",
                    "content": [
                        [
                            {"tag": "text", "text": "原文:\n" + tweet_text + "\n" + "译文:\n" + translated_text},
                            {"tag": "a", "text": "查看原文", "href": tweet_url}
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
            print(f"{current_time} 已推送推文到飞书，推文内容: {tweet_text}, 推文链接: {tweet_url}, 飞书响应状态码: {response.status}, 响应内容: {await response.text()}")

# 使用 Playwright 获取 RSS Feed
async def fetch_rss_feed(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)  # 启动 Chromium 浏览器
        page = await browser.new_page()
        try:
            await page.goto(url)
            page_source = await page.content()  # 获取页面源代码
            feed = feedparser.parse(page_source)
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return []
        finally:
            await browser.close()
        
        return feed.entries

# 定义信号量以控制并发数
semaphore = asyncio.Semaphore(max_concurrent_requests)

async def process_twitter_rss():
    tasks = []
    for username, url in target_urls.items():
        tasks.append(process_user_rss(username, url))
    
    await asyncio.gather(*tasks)

# 处理每个用户的 RSS
async def process_user_rss(username, url):
    global sent_tweet_ids
    
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 正在抓取 {username} 的RSS更新...")
    
    try:
        # 获取该用户的RSS更新
        entries = await fetch_rss_feed(url)
        
        for entry in entries:
            tweet_text = entry.title
            tweet_url = entry.link
            tweet_id = username + tweet_url.split("/")[-1]  # 使用用户名+推文ID作为唯一标识符

            if tweet_id not in sent_tweet_ids:
                # 使用信号量限制并发
                async with semaphore:
                    await send_to_feishu(tweet_text, tweet_url, username)
                    sent_tweet_ids.add(tweet_id)
                
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 完成 {username} 的RSS处理...")
    except Exception as e:
        print(f"Error processing {username}: {e}")
        return

async def main():
    global sent_tweet_ids
    sent_tweet_ids = load_sent_tweet_ids()

    while True:
        await process_twitter_rss()

        save_sent_tweet_ids(sent_tweet_ids)
        # 每小时运行一次
        sleep_time = 3600  # 1小时
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 睡眠 {sleep_time} 秒...")
        await asyncio.sleep(sleep_time)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 发生错误: {e}")
