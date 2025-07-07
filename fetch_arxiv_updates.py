import time
import requests
import feedparser
import os

# 请将此处的 URL 替换为您实际的飞书机器人 Webhook 地址
FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/8e718ac2-e3dd-4125-b11b-f981961c5135"

# 用于存储已处理文章的文件路径
PROCESSED_FILE = "arxiv_push/processed_ids.txt"

# Ollama API配置
OLLAMA_API_URL = "http://localhost:11434/api/chat"  # Ollama API地址
OLLAMA_MODEL = "qwen2.5:14b"  # Ollama中的模型名称

# 代理配置
PROXIES = {
    'http': 'http://127.0.0.1:7899',
    'https': 'http://127.0.0.1:7899'
} if os.getenv('USE_PROXY', 'false').lower() == 'true' else None

# 请求超时设置（秒）
REQUEST_TIMEOUT = 30

def load_processed_ids():
    """从文件中加载已处理的文章 ID 集合"""
    try:
        with open(PROCESSED_FILE, "r") as f:
            processed = {line.strip() for line in f if line.strip()}
    except FileNotFoundError:
        processed = set()
    return processed

def save_processed_ids(processed_ids):
    """将处理过的文章 ID 保存到文件中"""
    with open(PROCESSED_FILE, "w") as f:
        for pid in processed_ids:
            f.write(pid + "\n")

def send_to_feishu(message):
    """
    将消息发送到飞书机器人
    飞书机器人的消息格式为 JSON，下面采用 text 类型消息。
    """
    headers = {"Content-Type": "application/json"}
    data = {
        "msg_type": "text",
        "content": {
            "text": message
        }
    }
    try:
        response = requests.post(FEISHU_WEBHOOK, json=data, headers=headers)
        if response.status_code != 200:
            print("飞书通知失败，状态码：", response.status_code)
    except Exception as e:
        print("发送飞书消息异常：", e)

def translate_to_chinese(text):
    """
    使用 Ollama API 调用 Qwen2.5 模型将英文文本翻译为中文
    """
    messages = [
        {"role": "system", "content": "You are Qwen, a great reader and translator!"},
        {"role": "user", "content": "Translate the following text into Chinese, return only the translated text: " + text}
    ]
    
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False
    }
    
    try:
        response = requests.post(OLLAMA_API_URL, json=payload)
        if response.status_code == 200:
            result = response.json()
            translated_text = result.get("message", {}).get("content", "").strip()
            return translated_text
        else:
            error_text = response.text
            print(f"Ollama API调用失败: {response.status_code}, {error_text}")
            return "翻译失败"
    except Exception as e:
        print(f"翻译异常: {e}")
        return "翻译失败"

def get_pdf_url(article_id):
    """
    根据文章的 arXiv 网址构造 PDF 链接
    例如将 "http://arxiv.org/abs/2302.12345v1" 转换为 "http://arxiv.org/pdf/2302.12345v1.pdf"
    """
    if "/abs/" in article_id:
        return article_id.replace("/abs/", "/pdf/") + ".pdf"
    else:
        return article_id

def check_arxiv_updates():
    """
    检查 arXiv 上 cs.SD 与 eess.AS 两个领域的最新 100 篇文章
    如果文章未处理过，则推送消息
    """
    # 构造查询条件，查询 cs.SD 与 eess.AS 两个领域的最新 50 篇文章
    query = "cat:cs.SD+OR+cat:eess.AS"
    url = f"http://export.arxiv.org/api/query?search_query={query}&start=0&max_results=100&sortBy=submittedDate&sortOrder=descending"
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT, proxies=PROXIES)
    except Exception as e:
        print("获取 arXiv 数据异常：", e)
        return

    feed = feedparser.parse(response.text)
    processed_ids = load_processed_ids()
    new_processed = set(processed_ids)
    new_articles = []

    # 遍历返回的所有条目，如果文章 ID 未被处理，则视为新投稿
    for entry in feed.entries:
        article_id = entry.id  # 文章的唯一标识，通常为其网址，如 http://arxiv.org/abs/XXXX.XXXX
        if article_id not in processed_ids:
            new_articles.append(entry)
            new_processed.add(article_id)

    # 对于每个新文章，通过飞书机器人发送通知
    for article in new_articles:
        article_id = article.id
        title = article.title.strip() if hasattr(article, "title") else "无标题"
        abstract = article.summary.strip() if hasattr(article, "summary") else "无摘要"
        authors = ", ".join([author.name for author in article.authors]) if hasattr(article, "authors") else "未知作者"
        pdf_url = get_pdf_url(article_id)
        # 翻译摘要为中文
        title_cn = translate_to_chinese(title)
        abstract_cn = translate_to_chinese(abstract)
        authors_cn = translate_to_chinese(authors)
        # 获取文档的更新时间
        updated_time = article.updated if hasattr(article, "updated") else "未知时间"

        message = (
            f"文档更新时间：{updated_time}\n"
            f"标题：{title}\n"
            f"标题(中文)：{title_cn}\n"
            f"作者：{authors}\n"
            f"作者(中文)：{authors_cn}\n"
            f"PDF链接：{pdf_url}\n\n"
            f"摘要：\n{abstract}\n\n"
            f"摘要(中文)：\n{abstract_cn}"
        )
        print("发送消息：", message)
        send_to_feishu(message)

    # 更新保存处理过的文章 ID
    save_processed_ids(new_processed)

def main():
    """
    主循环，每隔一小时检查一次 arXiv 更新
    """
    while True:
        print("开始检查 arXiv 更新……")
        check_arxiv_updates()
        print("检查完成，休眠6小时。")
        time.sleep(3600 * 6)  # 每隔6小时执行一次

if __name__ == "__main__":
    main()
