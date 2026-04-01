"""
RAG 问答服务
基于已收集的白癜风知识库回答用户问题
"""

import os
import json
from typing import List, Tuple
from sqlalchemy.orm import Session
from database.models import Document, Conversation, Message
from models.rag import QuestionResponse, Source

import openai


def get_embedding(text: str) -> List[float]:
    """获取文本嵌入向量"""
    client = openai.OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    )
    response = client.embeddings.create(
        model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        input=text
    )
    return response.data[0].embedding


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """计算余弦相似度"""
    dot_product = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x ** 2 for x in a) ** 0.5
    norm_b = sum(x ** 2 for x in b) ** 0.5
    return dot_product / (norm_a * norm_b) if norm_a > 0 and norm_b > 0 else 0


def search_documents(db: Session, query: str, top_k: int = 5) -> List[Tuple[Document, float]]:
    """基于向量搜索查找相关文档"""
    # 获取查询向量
    query_embedding = get_embedding(query)

    # 获取所有文档
    docs = db.query(Document).filter(Document.content != "").all()

    # 计算相似度并排序
    results = []
    for doc in docs:
        if doc.embedding:
            doc_embedding = json.loads(doc.embedding)
            similarity = cosine_similarity(query_embedding, doc_embedding)
            results.append((doc, similarity))

    # 按相似度排序返回top_k
    results.sort(key=lambda x: x[1], reverse=True)
    return results[:top_k]


def generate_answer(query: str, docs: List[Document], conversation_history: List[dict] = None) -> str:
    """根据检索到的文档生成回答"""
    client = openai.OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    )

    # 构建上下文
    context = "\n\n".join([
        f"文档: {doc.title}\n内容: {doc.content[:1000]}"
        for doc in docs
    ])

    # 系统提示
    system_prompt = """你是 SubSkin 白癜风知识库的 AI 助手。
你需要基于提供的参考资料，回答用户关于白癜风的问题。
回答要:
1. 准确，只基于参考资料回答
2. 通俗易懂，适合普通患者阅读，避免过于专业的术语
3. 如果资料里没有答案，直说"这个问题在当前知识库中没有找到相关信息，建议咨询专业医生"
4. 不胡说八道，不编造信息
5. 最后提醒用户，本回答仅供参考，具体诊疗请遵医嘱

记住：你是帮助患者了解知识，给他们有用信息，缓解信息不对称。
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"参考资料:\n\n{context}\n\n我的问题: {query}"}
    ]

    # 如果有对话历史，加上
    if conversation_history:
        # 插入系统提示之后，当前问题之前
        messages = [messages[0]] + conversation_history + [messages[-1]]

    response = client.chat.completions.create(
        model=os.getenv("LLM_MODEL", "gpt-3.5-turbo"),
        messages=messages,
        temperature=0.3,
    )

    return response.choices[0].message.content.strip()


def answer_question(
    db: Session,
    question: str,
    conversation_id: str = None,
    user_id: int = None
) -> QuestionResponse:
    """完整的RAG问答流程"""
    # 检索相关文档
    results = search_documents(db, question)
    docs = [doc for doc, score in results if score > 0.5]

    if not docs:
        # 如果没有匹配到，用所有文档里找最相关的前3个
        docs = [doc for doc, score in results[:3]]

    # 准备来源
    sources = [
        Source(
            title=doc.title,
            url=doc.source_url if doc.source_url else "",
            snippet=doc.content[:200] + "..." if len(doc.content) > 200 else doc.content
        )
        for doc in docs
    ]

    # 获取对话历史（如果有）
    conversation_history = None
    if conversation_id:
        history = db.query(Message)\
            .filter(Message.conversation_id == conversation_id)\
            .order_by(Message.created_at)\
            .all()
        conversation_history = [
            {"role": msg.role, "content": msg.content} for msg in history
        ]

        # 确保对话存在
        conv = db.query(Conversation)\
            .filter(Conversation.conversation_id == conversation_id)\
            .first()
        if not conv:
            conv = Conversation(
                conversation_id=conversation_id,
                user_id=user_id
            )
            db.add(conv)
            db.commit()

    # 生成回答
    answer = generate_answer(question, docs, conversation_history)

    # 保存对话
    if conversation_id:
        # 保存用户问题
        user_msg = Message(
            conversation_id=conversation_id,
            role="user",
            content=question
        )
        db.add(user_msg)
        # 保存助手回答
        assistant_msg = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=answer
        )
        db.add(assistant_msg)
        db.commit()

    return QuestionResponse(
        answer=answer,
        sources=sources
    )


def add_document(db: Session, title: str, content: str, source: str = None, source_url: str = None, category: str = None) -> Document:
    """添加文档到知识库并计算嵌入"""
    embedding = get_embedding(content[:8000])  # 限制长度
    doc = Document(
        title=title,
        content=content,
        source=source,
        source_url=source_url,
        category=category,
        embedding=json.dumps(embedding)
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc
