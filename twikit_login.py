from twikit import Client
import asyncio

client = Client('en-US', proxy="http://127.0.0.1:7890")


async def main():
    await client.login(
        # auth_info_1='yoyo21693388475',
        # auth_info_2='iamyourfather20250215@proton.me',
        # password='iamyour88',
        # auth_info_1='fakufakufa15829',
        # auth_info_2='francis7999@qq.com',
        # password='jjxydxrh123!',
        auth_info_1='YanzuXiu',
        auth_info_2='francis7999@outlook.com',
        password='T:b3chA3pjfyvQT',
        # cookies_file='twikit_cookies.json'
    )

    client.save_cookies('twikit_cookies.json')

    tweets = await client.search_tweet('python', 'Latest')

    for tweet in tweets:
        print(
            tweet.user.name,
            tweet.text,
            tweet.created_at
        )

asyncio.run(main())

