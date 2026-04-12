#!/usr/bin/env python
"""创建新表（RAG功能）"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from web.backend.database.database import engine, Base

Base.metadata.create_all(bind=engine)
print("✅ 所有表创建/更新完成")
print(f"已添加表: documents, conversations, messages")
