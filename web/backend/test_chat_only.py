#!/usr/bin/env python3
"""
仅测试Chat API（不依赖embedding）
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
chat_endpoint = os.getenv("VOLCENGINE_CHAT_ENDPOINT")

print("=== 测试火山引擎Chat API ===")
print(f"BASE_URL: {base_url}")
print(f"Chat端点: {chat_endpoint}")
print()

# 构造知识库上下文
context = """文档: 白癜风是什么
内容: 白癜风是一种常见的皮肤色素障碍性疾病，特征是皮肤和毛发出现白色斑片。这是因为黑色素细胞被破坏或功能障碍导致的。白癜风在全球发病率约为0.5-2%，可以影响任何年龄、性别和种族的人群。尽管主要影响外观，但白癜风本身不会传染，也不会危及生命。

文档: 白癜风的治疗方法
内容: 白癜风的治疗方法包括：1) 外用药物：如激素类药膏、钙调神经蛋白激酶抑制剂等。2) 光疗：窄谱UVB光疗是常用的方法，每周2-3次。3) 系统治疗：对于泛发性患者，可能使用口服激素或免疫抑制剂。4) 手术治疗：对于稳定期局限性白癜风，可考虑皮肤移植。治疗方案应由专业医生根据患者具体情况制定。
"""

system_prompt = """你是 SubSkin 白癜风知识库的 AI 助手。你需要基于提供的参考资料，回答用户关于白癜风的问题。
回答要:
1. 准确，只基于参考资料回答
2. 通俗易懂，适合普通患者阅读，避免过于专业的术语
3. 如果资料里没有答案，直说"这个问题在当前知识库中没有找到相关信息，建议咨询专业医生"
4. 不胡说八道，不编造信息
5. 最后提醒用户，本回答仅供参考，具体诊疗请遵医嘱

记住：你是帮助患者了解知识，给他们有用信息，缓解信息不对称。用户很多是刚确诊，心理压力大，回答要多给鼓励。
"""

test_questions = [
    "白癜风是什么？",
    "白癜风有哪些治疗方法？",
    "白癜风会传染吗？"
]

for question in test_questions:
    print(f"\n{'='*60}")
    print(f"问题: {question}")
    print(f"{'='*60}")
    
    try:
        client = openai.OpenAI(api_key=api_key, base_url=base_url)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"参考资料:\n\n{context}\n\n我的问题: {question}"}
        ]
        
        response = client.chat.completions.create(
            model=chat_endpoint,
            messages=messages,
            temperature=0.3
        )
        
        answer = response.choices[0].message.content.strip()
        print(f"\n回答:\n{answer}\n")
        print("✅ Chat API调用成功！")
        
    except Exception as e:
        print(f"\n❌ Chat API调用失败: {str(e)}")
        import traceback
        traceback.print_exc()

print("\n=== 测试完成 ===")
