"""
测试阿里云百炼 DashScope API 连接
验证 embedding 和 chat 两个接口是否正常工作
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)

import openai


def test_embedding():
    print("=" * 50)
    print("测试 Embedding API (阿里云百炼 DashScope)")
    print("=" * 50)

    api_key = os.getenv("DASHSCOPE_API_KEY", "")
    base_url = os.getenv(
        "DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    model = os.getenv("DASHSCOPE_EMBEDDING_MODEL", "text-embedding-v4")
    dimensions = int(os.getenv("DASHSCOPE_EMBEDDING_DIMENSIONS", "1024"))

    if not api_key:
        print("❌ DASHSCOPE_API_KEY 未设置")
        return False

    print(f"  API Key: {api_key[:8]}...{api_key[-4:]}")
    print(f"  Base URL: {base_url}")
    print(f"  Model: {model}")
    print(f"  Dimensions: {dimensions}")

    client = openai.OpenAI(api_key=api_key, base_url=base_url)

    try:
        response = client.embeddings.create(
            model=model,
            input="白癜风是一种常见的后天性色素脱失性皮肤黏膜疾病",
            dimensions=dimensions,
        )
        embedding = response.data[0].embedding
        print(f"\n  ✅ Embedding 成功!")
        print(f"  向量维度: {len(embedding)}")
        print(f"  前5个值: {embedding[:5]}")
        print(f"  模型: {response.model}")
        return True
    except Exception as e:
        print(f"\n  ❌ Embedding 失败: {type(e).__name__}: {e}")
        return False


def test_chat():
    print("\n" + "=" * 50)
    print("测试 Chat API (阿里云百炼 DashScope)")
    print("=" * 50)

    api_key = os.getenv("DASHSCOPE_API_KEY", "")
    base_url = os.getenv(
        "DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    model = os.getenv("DASHSCOPE_CHAT_MODEL", "qwen-plus")

    if not api_key:
        print("❌ DASHSCOPE_API_KEY 未设置")
        return False

    print(f"  API Key: {api_key[:8]}...{api_key[-4:]}")
    print(f"  Base URL: {base_url}")
    print(f"  Model: {model}")

    client = openai.OpenAI(api_key=api_key, base_url=base_url)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是一个白癜风知识助手，请简洁回答。"},
                {"role": "user", "content": "什么是白癜风？用一句话回答。"},
            ],
            temperature=0.3,
        )
        answer = response.choices[0].message.content.strip()
        print(f"\n  ✅ Chat 成功!")
        print(f"  模型: {response.model}")
        print(f"  回答: {answer[:200]}")
        return True
    except Exception as e:
        print(f"\n  ❌ Chat 失败: {type(e).__name__}: {e}")
        return False


if __name__ == "__main__":
    embedding_ok = test_embedding()
    chat_ok = test_chat()

    print("\n" + "=" * 50)
    print("测试结果")
    print("=" * 50)
    print(f"  Embedding: {'✅ 通过' if embedding_ok else '❌ 失败'}")
    print(f"  Chat:      {'✅ 通过' if chat_ok else '❌ 失败'}")

    if embedding_ok and chat_ok:
        print("\n🎉 阿里云百炼 DashScope API 配置正确，可以正常使用！")
    else:
        print("\n⚠️  部分测试失败，请检查 API Key 和配置。")
