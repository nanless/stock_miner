import asyncio
import json
from datetime import datetime, timedelta
from playwright.async_api import async_playwright
import aiohttp
from transformers import AutoModelForCausalLM, AutoTokenizer
import random

# --- 配置 ---
webhook_url = "https://open.feishu.cn/open-apis/bot/v2/hook/b5fa30f9-e0d1-42d5-88ba-a943030992c6"
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
target_urls = {username: f"https://x.com/{username}" for username in target_usernames}
X_USERNAME = "iamyourfather20241220@outlook.com"
X_USERID = "pika95083640764"
X_PASSWORD = "iamyour88"
sent_tweets_file = "twitter_push/sent_tweets.json"
model_name = "Qwen/Qwen2.5-7B-Instruct-AWQ"
cache_dir = '/home/kemove/.cache/huggingface/hub'
# --- 配置结束 ---

# 全局变量
last_login_time = None
sent_tweet_ids = set()
url_index = 0
# 加载qwen模型及分词器
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    # torch_dtype=torch.float16,
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


async def login_if_needed(page):
    global last_login_time
    if last_login_time and datetime.now() - last_login_time < timedelta(minutes=5):
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"{current_time} 上次登录未超过5分钟，无需重新登录。")
        return

    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"{current_time} 执行登录操作...")
    await page.goto("https://x.com/login")

    await page.fill("input[name='text']", X_USERNAME)
    await page.click("button:has-text('Next')")
    await asyncio.sleep(5)
    await page.fill("input[name='text']", X_USERID)
    await page.click("button:has-text('Next')")
    await asyncio.sleep(5)
    await page.fill("input[name='password']", X_PASSWORD)
    await page.click("button:has-text('Log in')")

    await asyncio.sleep(10)  # 等待页面加载
    last_login_time = datetime.now()
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"{current_time} 登录成功！")


async def get_tweets(page, username, url):
    await page.goto(url)
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"{current_time} 正在获取 {username} 的推文")
    await page.wait_for_selector("article", timeout=15000)  # 等待推文加载，超时时间设为15秒

    tweets = []
    articles = await page.query_selector_all("article")
    for article in articles:
        tweet_text_element = await article.query_selector("div[data-testid='tweetText']")
        if tweet_text_element:
            tweet_text = await tweet_text_element.inner_text()
            tweet_link = await article.query_selector(f'a[href^="/{username}/status/"]')
            if tweet_link:
                href = await tweet_link.get_attribute("href")
                tweet_url = "https://x.com" + href
                tweet_id = username + href.split("/")[-1]  # 使用用户名+推文ID作为唯一标识符
                if tweet_id not in sent_tweet_ids:
                    tweets.append((tweet_text, tweet_url, tweet_id))
    return tweets


async def main():
    global url_index
    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        page = await browser.new_page()

        while True:
            await login_if_needed(page)

            start_index = url_index
            end_index = min(url_index + 40, len(target_urls))
            urls_to_process = list(target_urls.items())[start_index:end_index]

            for username, url in urls_to_process:
                try:
                    new_tweets = await get_tweets(page, username, url)
                    for tweet_text, tweet_url, tweet_id in new_tweets:
                        await send_to_feishu(tweet_text, tweet_url, username)
                        sent_tweet_ids.add(tweet_id)
                        save_sent_tweet_ids(sent_tweet_ids)
                except Exception as e:
                    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    print(f"{current_time} 发生错误: {e}")

            url_index = end_index  # 直接更新为 end_index
            if url_index == len(target_urls):
                url_index = 0  # 如果读取到末尾，则重置为 0

            sleep_time = random.randint(5400, 10800)
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"{current_time} Sleeping for {sleep_time} seconds...")
            await asyncio.sleep(sleep_time)


if __name__ == "__main__":
    sent_tweet_ids = load_sent_tweet_ids()
    asyncio.run(main())
