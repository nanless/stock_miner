import asyncio
import json
import time
from datetime import datetime, timedelta
from playwright.async_api import async_playwright
import aiohttp

# 飞书机器人Webhook地址
webhook_url = "https://open.feishu.cn/open-apis/bot/v2/hook/b5fa30f9-e0d1-42d5-88ba-a943030992c6"

# 定义要爬取的X (Twitter)博主用户名
target_usernames = ["myfxtrader", "tzwqbest", "GlobalMoneyAI", "AsiaFinance", "OldK_Gillis", "qinbafrank", "xlh1238899", "guyisheng1", "telebi7", "caijingshujuku", "hhuang", "zeyu_kap", "bboczeng", "zebrahelps", "angel71911", "yanbojack", "turingou", "Awsomefo", "ANDREW_FDWT", "ngw888", "HitAshareLimit", "BFBSHCD", "realwuzhe", "cnfinancewatch", "zhaocaishijie", "hungjng69679118", "dacefupan", "__Inty__", "andy_sharks", "DogutOscar", "x001fx", "cnAspeculation", "Hoyooyoo", "hongsv11", "ShanghaoJin", "yiguxia", "yamato812536", "tychozzz", "caolei1", "Vson0903", "benjman89"]
target_urls = {username: f"https://x.com/{username}" for username in target_usernames}

# X 登录信息
X_USERNAME = "francis7999@outlook.com"
X_USERID = "YanzuXiu"
X_PASSWORD = "T:b3chA3pjfyvQT"

# 已发送推文ID存储文件
sent_tweets_file = "twitter_push/sent_tweets.json"

# 登录状态变量
last_login_time = None

# 初始化已发送推文ID集合
def load_sent_tweet_ids():
    try:
        with open(sent_tweets_file, "r") as f:
            return set(json.load(f))
    except FileNotFoundError:
        return set()

def save_sent_tweet_ids(ids):
    with open(sent_tweets_file, "w") as f:
        json.dump(list(ids), f)

sent_tweet_ids = load_sent_tweet_ids()

async def send_to_feishu(tweet_text, tweet_url, username):
    message = {
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": f"{username} 的最新推文",
                    "content": [
                        [
                            {"tag": "text", "text": tweet_text},
                            {"tag": "a", "text": "查看原文", "href": tweet_url}
                        ]
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

    # 输入用户名和密码
    await page.fill("input[name='text']", X_USERNAME)
    await page.click("button:has-text('Next')")
    await asyncio.sleep(2)
    await page.fill("input[name='text']", X_USERID)
    await page.click("button:has-text('Next')")
    await asyncio.sleep(2)
    await page.fill("input[name='password']", X_PASSWORD)
    await page.click("button:has-text('Log in')")

    # 确保登录成功
    await asyncio.sleep(10)
    last_login_time = datetime.now()
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"{current_time} 登录成功！")

async def get_tweets(page, username, url):
    await page.goto(url)
    await page.wait_for_selector("article", timeout=10000)

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
                tweet_id = username + href.split("/")[-1]
                if tweet_id not in sent_tweet_ids:
                    tweets.append((tweet_text, tweet_url, tweet_id))
    return tweets

async def main():
    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        page = await browser.new_page()

        await login_if_needed(page)
        for username, url in target_urls.items():
            new_tweets = await get_tweets(page, username, url)
            for tweet_text, tweet_url, tweet_id in new_tweets:
                await send_to_feishu(tweet_text, tweet_url, username)
                sent_tweet_ids.add(tweet_id)
                save_sent_tweet_ids(sent_tweet_ids)

if __name__ == "__main__":
    asyncio.run(main())