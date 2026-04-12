#!/usr/bin/env python3
"""
测试RAG问答功能
"""

import sys
import os

sys.path.insert(0, "..")
sys.path.insert(0, "../..")

from dotenv import load_dotenv

# 加载.env文件
load_dotenv("../../.env")

from web.backend.database.database import get_db
from web.backend.database.models import Document
from web.backend.services.rag import answer_question

db = next(get_db())
try:
    docs = db.query(Document).all()
    print(f"知识库文档数量: {len(docs)}")
    for doc in docs:
        print(f"  - {doc.title}")
    print()

    # 测试问答
    questions = ["白癜风是什么？", "白癜风有哪些治疗方法？", "白癜风会传染吗？"]

    for question in questions:
        print(f"\n=== 问题: {question} ===")
        try:
            response = answer_question(
                db=db, question=question, conversation_id=None, user_id=None
            )
            print(f"回答:\n{response.answer}\n")
            print(f"来源: {len(response.sources)} 个文档")
            for i, source in enumerate(response.sources, 1):
                print(f"  {i}. {source.title}")
        except Exception as e:
            print(f"❌ 问答失败: {str(e)}")
            import traceback

            traceback.print_exc()

finally:
    db.close()
