#!/usr/bin/env python3
"""
测试火山引擎端点连接
"""

import sys
import os
sys.path.insert(0, '..')
sys.path.insert(0, '../..')

from dotenv import load_dotenv
import openai

# 加载.env文件
load_dotenv('../../.env')

api_key = os.getenv("VOLCENGINE_API_KEY")
base_url = os.getenv("VOLCENGINE_BASE_URL")
embedding_endpoint = os.getenv("VOLCENGINE_EMBEDDING_ENDPOINT")
chat_endpoint = os.getenv("VOLCENGINE_CHAT_ENDPOINT")

print("=== 测试火山引擎API连接 ===")
print(f"BASE_URL: {base_url}")
print(f"API Key: {api_key[:20]}..." if api_key else "未设置")
print()

# 测试embedding
print("1. 测试Embedding API...")
try:
    client = openai.OpenAI(api_key=api_key, base_url=base_url)
    response = client.embeddings.create(
        model=embedding_endpoint,
        input="测试文本"
    )
    print(f"   ✅ Embedding成功! 向量维度: {len(response.data[0].embedding)}")
except Exception as e:
    print(f"   ❌ Embedding失败: {str(e)}")

print()

# 测试chat
print("2. 测试Chat API...")
try:
    client = openai.OpenAI(api_key=api_key, base_url=base_url)
    response = client.chat.completions.create(
        model=chat_endpoint,
        messages=[{"role": "user", "content": "你好，请简单介绍一下白癜风"}],
        temperature=0.3
    )
    print(f"   ✅ Chat成功!")
    print(f"   回答: {response.choices[0].message.content[:100]}...")
except Exception as e:
    print(f"   ❌ Chat失败: {str(e)}")

print("\n=== 测试完成 ===")
