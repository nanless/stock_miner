import asyncio
import time
from datetime import datetime
import feedparser
from selenium import webdriver
import requests

# 这里假设配置部分只保留单个目标用户相关信息示例
target_username = "myfxtrader"
target_url = f"http://localhost:1200/twitter/user/{target_username}"

# 全局变量（这里示例简化，实际可能按原逻辑处理更多）
sent_tweet_ids = set()

def fetch_rss_feed(url):
    # options = webdriver.ChromeOptions()
    # # options.add_argument('--headless')  # 无头模式

    # driver = webdriver.Chrome(options=options)
    # driver.get(url)

    # time.sleep(10)
    # page_source = driver.page_source
    # driver.quit()

    # feed = feedparser.parse(page_source)
    # return feed.entries

    response = requests.get(url)
    return feedparser.parse(response.content)

async def process_twitter_rss_for_user(username, url):
    global sent_tweet_ids
    
    try:
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 正在抓取 {username} 的RSS更新...")
        
        # 获取该用户的RSS更新
        entries = fetch_rss_feed(url)["entries"]

        # import ipdb; ipdb.set_trace()
        
        for entry in entries:
            tweet_text = entry.title
            tweet_url = entry.link
            tweet_id = username + tweet_url.split("/")[-1]  # 使用用户名+推文ID作为唯一标识符

            # 这里简化示例，仅打印相关信息，原逻辑是判断是否已推送等操作
            print(f"推文内容: {tweet_text}, 推文链接: {tweet_url}, 推文唯一标识: {tweet_id}")

        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 完成 {username} 的RSS处理...")

    except Exception as e:
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 处理 {username} 时发生错误: {e}，跳过该用户。")

async def main():
    global sent_tweet_ids
    # 这里简化，假设sent_tweet_ids初始为空集，实际可能按原逻辑加载已有记录等

    await process_twitter_rss_for_user(target_username, target_url)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 发生错误: {e}")