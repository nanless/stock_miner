import asyncio
import json
import time
import random
from datetime import datetime
from twikit import Client
import aiohttp
from dateutil import parser
from pytz import timezone
import os

# --- 配置 ---
webhook_url = "https://open.feishu.cn/open-apis/bot/v2/hook/b5fa30f9-e0d1-42d5-88ba-a943030992c6"
target_usernames = ["tychozzz", "caolei1", "Vson0903", 
                    "benjman89", "dmjk001", "Rumoreconomy", "liqiang365", "dacejiangu", "frost_jazmyn", 
                    "TJ_Research01", "QihongF44102", "SupFin", "yangskyfly", "Capitalpedia", "hybooospx", 
                    "91grok", "financehybooo", "yangcy199510182", "stocktalkweekly", "MonkEchevarria", "ThetaWarrior", "MacroMargin",
                    "hybooonews", "TradingThomas3", "WSJ", "TheTranscript_", "Tesla_Cybercat", "BilingualReader", "The_RockTrading",
                    "realDonaldTrump", "elonmusk", "SpaceX", "joely7758521", "techeconomyana", "jiu_sunny",
                    "wakk94748769", "WSTAnalystApe", "theinformation", "3000upup", "tradehybooo", "hyboootrade",
                    "yuyy614893671", "JamesLt196801", "DrJStrategy", "z0072024", "YeMuXinTu", "Starlink", "IvyUnclestock", "yuexiaoyu111", 
                    "Jukanlosreve", "lianyanshe", "hiCaptainZ", "PallasCatFin", "AntonLaVay", "shijh96", "mvcinvesting", "D_K_Rajasekar",
                    "David_yc607", "arbujiujiu", "myfxtrader", "tzwqbest", "GlobalMoneyAI", "AsiaFinance", "OldK_Gillis", "qinbafrank", 
                    "xlh1238899", "guyisheng1", "telebi7", "caijingshujuku", "hhuang", "zeyu_kap", "bboczeng", 
                    "zebrahelps", "angel71911", "yanbojack", "turingou", "ANDREW_FDWT", "ngw888",
                    "HitAshareLimit", "BFBSHCD", "realwuzhe", "cnfinancewatch", "zhaocaishijie", "hungjng69679118", 
                    "dacefupan", "__Inty__", "andy_sharks", "DogutOscar", "x001fx", "Hoyooyoo", 
                    "hongsv11", "ShanghaoJin", "yiguxia", "yamato812536"]
sent_tweets_file = "twikit_push/sent_tweets.json"
ollama_api_url = "http://localhost:11434/api/chat"  # Ollama API地址
ollama_model = "qwen2.5:14b"  # Ollama中的模型名称
num_parts = 1  # 可以改为4或其他值，用于指定 target_usernames 分成的份数
# --- 配置结束 ---

# 全局变量
sent_tweet_ids = set()

# 将列表分成指定份数的函数
def split_list(lst, num_parts):
    chunk_size = len(lst) // num_parts
    remainder = len(lst) % num_parts
    parts = []
    start = 0
    for i in range(num_parts):
        end = start + chunk_size + (1 if i < remainder else 0)
        parts.append(lst[start:end])
        start = end
    return parts

def load_sent_tweet_ids():
    try:
        with open(sent_tweets_file, "r") as f:
            return set(json.load(f))
    except FileNotFoundError:
        return set()

def save_sent_tweet_ids(ids):
    with open(sent_tweets_file, "w") as f:
        json.dump(list(ids), f)

async def query_ollama(messages):
    """调用Ollama API进行文本生成"""
    payload = {
        "model": ollama_model,
        "messages": messages,
        "stream": False
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(ollama_api_url, json=payload) as response:
            if response.status == 200:
                result = await response.json()
                return result["message"]["content"]
            else:
                error_text = await response.text()
                raise Exception(f"Ollama API调用失败: {response.status}, {error_text}")

async def send_to_feishu(tweet_text, tweet_url, author, formatted_time):
    # 检查是否为英文或其他非中文语言
    messages = [
        {"role": "system", "content": "You are Qwen, a great reader and translator!"},
        {"role": "user", "content": "Is this message in English or other non-Chinese language? Return only yes or no, discard any other text: " + tweet_text}
    ]
    
    response = await query_ollama(messages)
    response = ''.join(filter(str.isalpha, response))
    
    if response.lower() == "yes":
        # 翻译推文
        messages = [
            {"role": "system", "content": "You are Qwen, a great reader and translator!"},
            {"role": "user", "content": "Translate this tweet into Chinese, return only the translated text: " + tweet_text}
        ]
        
        translated_text = await query_ollama(messages)

        message = {
            "msg_type": "post",
            "content": {
                "post": {
                    "zh_cn": {
                        "title": f"{author} 在 {formatted_time} 的推文",
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
    else:
        message = {
            "msg_type": "post",
            "content": {
                "post": {
                    "zh_cn": {
                        "title": f"{author} 在 {formatted_time} 的推文",
                        "content": [
                            [
                                {"tag": "text", "text": "原文:\n" + tweet_text},
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

async def process_twitter_user_updates(client, username):
    global sent_tweet_ids
    
    try:
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 正在抓取 {username} 的推文更新...")
        
        user = await client.get_user_by_screen_name(username)
        tweets = await client.get_user_tweets(user.id, 'Tweets')

        for tweet in tweets:
            tweet_text = tweet.text
            tweet_url = f"https://twitter.com/{username}/status/{tweet.id}"
            tweet_author = tweet.user.name
            dt = parser.parse(tweet.created_at)
            if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
                dt = dt.replace(tzinfo=timezone('UTC'))

            shanghai_tz = timezone('Asia/Shanghai')
            shanghai_time = dt.astimezone(shanghai_tz)
            tweet_timestamp = shanghai_time.strftime('%Y年%m月%d日 %H:%M:%S')
            tweet_id = username + '_' + str(tweet.id)

            if tweet_id not in sent_tweet_ids:
                await send_to_feishu(tweet_text, tweet_url, tweet_author, tweet_timestamp)
                sent_tweet_ids.add(tweet_id)

        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 完成 {username} 的推文处理...")

    except Exception as e:
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 处理 {username} 时发生错误: {e}，跳过该用户。")

async def main():
    global sent_tweet_ids
    sent_tweet_ids = load_sent_tweet_ids()

    # 将 target_usernames 分成 num_parts 份
    username_parts = split_list(target_usernames, num_parts)
    cycle_count = 0

    while True:
        client = Client('en-US', proxy="http://127.0.0.1:7890")
        await client.login(
            auth_info_1='YanzuXiu',
            auth_info_2='francis7999@outlook.com',
            password='T:b3chA3pjfyvQT',
            cookies_file='twikit_cookies.json'
        )

        if not os.path.exists('twikit_cookies.json'):
            client.save_cookies('twikit_cookies.json')

        # 选择当前循环处理的子列表
        current_part_index = cycle_count % num_parts
        current_part = username_parts[current_part_index]
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 开始处理第 {current_part_index} 部分的用户...")

        # 只处理当前子列表中的用户名
        for username in current_part:
            await process_twitter_user_updates(client, username)
            await asyncio.sleep(random.randint(30, 90))

        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 完成第 {current_part_index} 部分的用户处理...")
        save_sent_tweet_ids(sent_tweet_ids)
        cycle_count += 1

        # 在2400s-3600s之间随机选择睡眠时间
        sleep_time = random.randint(3600 * 3, 3600 * 5)  # 3600秒 = 1小时, 7200秒 = 2小时
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 睡眠 {sleep_time:.2f} 秒...")
        await asyncio.sleep(sleep_time)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 发生错误: {e}")