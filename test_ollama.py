import requests
import json

def test_ollama_connection():
    """测试 Ollama 服务连接"""
    url = "http://localhost:11434/api/chat"
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Translate this to Chinese: Hello, how are you?"}
    ]
    
    payload = {
        "model": "qwen2.5:14b",
        "messages": messages,
        "stream": False
    }
    
    try:
        print("正在测试 Ollama 服务连接...")
        response = requests.post(url, json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            translated_text = result.get("message", {}).get("content", "").strip()
            print("连接成功！")
            print("翻译结果:", translated_text)
            return True
        else:
            print(f"连接失败，状态码：{response.status_code}")
            print("错误信息:", response.text)
            return False
            
    except Exception as e:
        print("连接异常：", str(e))
        return False

if __name__ == "__main__":
    test_ollama_connection() 