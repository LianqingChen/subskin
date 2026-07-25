"""
向量存储抽象层

为 RAG 系统提供统一的向量存储接口，支持多种后端：
- SQLite (当前默认): 使用 Text 列存储 JSON 格式的 embedding
- PostgreSQL + pgvector (推荐升级): 使用原生向量类型和索引
- Qdrant (可选): 独立的向量数据库服务

配置方式 (环境变量):
    VECTOR_STORE_BACKEND=sqlite|pgvector|qdrant
    VECTOR_STORE_DIMENSION=1536  # embedding 维度
    QDRANT_URL=http://localhost:6333  # Qdrant 服务地址
    QDRANT_COLLECTION=subskin_documents
"""

import json
import logging
import os
from abc import ABC, abstractmethod
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)


class VectorStore(ABC):
    """向量存储抽象基类"""

    @abstractmethod
    def store_embedding(self, doc_id: int, embedding: List[float]) -> bool:
        """存储文档的 embedding"""
        pass

    @abstractmethod
    def search_similar(
        self, query_embedding: List[float], top_k: int = 5
    ) -> List[Tuple[int, float]]:
        """搜索最相似的文档，返回 (doc_id, similarity) 列表"""
        pass

    @abstractmethod
    def delete_embedding(self, doc_id: int) -> bool:
        """删除文档的 embedding"""
        pass

    @abstractmethod
    def count_embeddings(self) -> int:
        """统计已存储的 embedding 数量"""
        pass


class SQLiteVectorStore(VectorStore):
    """SQLite 向量存储 (当前实现)
    
    使用 Text 列存储 JSON 格式的 embedding，在内存中计算余弦相似度。
    适合小规模数据 (< 10000 文档)。
    """

    def __init__(self, db_session):
        self.db = db_session

    def store_embedding(self, doc_id: int, embedding: List[float]) -> bool:
        from web.backend.database.models import Document

        doc = self.db.query(Document).filter(Document.id == doc_id).first()
        if doc:
            doc.embedding = json.dumps(embedding)
            self.db.commit()
            return True
        return False

    def search_similar(
        self, query_embedding: List[float], top_k: int = 5
    ) -> List[Tuple[int, float]]:
        from web.backend.database.models import Document
        from web.backend.services.rag import cosine_similarity

        docs = self.db.query(Document).filter(Document.embedding != None).all()
        results = []
        for doc in docs:
            try:
                doc_embedding = json.loads(doc.embedding)
                if isinstance(doc_embedding, list):
                    similarity = cosine_similarity(query_embedding, doc_embedding)
                    if similarity > 0:
                        results.append((doc.id, similarity))
            except (json.JSONDecodeError, TypeError):
                continue

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def delete_embedding(self, doc_id: int) -> bool:
        from web.backend.database.models import Document

        doc = self.db.query(Document).filter(Document.id == doc_id).first()
        if doc:
            doc.embedding = None
            self.db.commit()
            return True
        return False

    def count_embeddings(self) -> int:
        from web.backend.database.models import Document

        return (
            self.db.query(Document)
            .filter(Document.embedding != None)
            .count()
        )


class PgVectorStore(VectorStore):
    """PostgreSQL + pgvector 向量存储 (推荐升级)
    
    使用 pgvector 扩展的原生向量类型和 HNSW/IVFFlat 索引。
    适合中大规模数据 (10000 - 1000000 文档)。
    
    需要先安装 pgvector 扩展:
        CREATE EXTENSION vector;
    
    然后修改 documents 表:
        ALTER TABLE documents ADD COLUMN embedding_vector vector(1536);
        CREATE INDEX ON documents USING hnsw (embedding_vector vector_cosine_ops);
    """

    def __init__(self, db_session, dimension: int = 1536):
        self.db = db_session
        self.dimension = dimension

    def store_embedding(self, doc_id: int, embedding: List[float]) -> bool:
        # TODO: 实现 pgvector 存储
        # 需要:
        # 1. 添加 embedding_vector 列 (vector 类型)
        # 2. 使用 SQLAlchemy 的 pgvector 扩展
        logger.warning("PgVectorStore.store_embedding 尚未实现，回退到 SQLite")
        return SQLiteVectorStore(self.db).store_embedding(doc_id, embedding)

    def search_similar(
        self, query_embedding: List[float], top_k: int = 5
    ) -> List[Tuple[int, float]]:
        # TODO: 实现 pgvector 搜索
        # SQL: SELECT id, 1 - (embedding_vector <=> $1) AS similarity
        #      FROM documents
        #      ORDER BY embedding_vector <=> $1
        #      LIMIT $2;
        logger.warning("PgVectorStore.search_similar 尚未实现，回退到 SQLite")
        return SQLiteVectorStore(self.db).search_similar(query_embedding, top_k)

    def delete_embedding(self, doc_id: int) -> bool:
        logger.warning("PgVectorStore.delete_embedding 尚未实现，回退到 SQLite")
        return SQLiteVectorStore(self.db).delete_embedding(doc_id)

    def count_embeddings(self) -> int:
        return SQLiteVectorStore(self.db).count_embeddings()


class QdrantVectorStore(VectorStore):
    """Qdrant 向量存储 (可选)
    
    使用独立的 Qdrant 向量数据库服务。
    适合大规模数据和高并发场景。
    
    需要:
        pip install qdrant-client
        运行 Qdrant 服务: docker run -p 6333:6333 qdrant/qdrant
    """

    def __init__(
        self,
        url: str = "http://localhost:6333",
        collection: str = "subskin_documents",
        dimension: int = 1536,
    ):
        self.url = url
        self.collection = collection
        self.dimension = dimension
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from qdrant_client import QdrantClient
                self._client = QdrantClient(url=self.url)
                self._ensure_collection()
            except ImportError:
                raise RuntimeError("需要安装 qdrant-client: pip install qdrant-client")
        return self._client

    def _ensure_collection(self):
        from qdrant_client.models import Distance, VectorParams

        client = self._client
        collections = client.get_collections().collections
        if not any(c.name == self.collection for c in collections):
            client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(
                    size=self.dimension,
                    distance=Distance.COSINE,
                ),
            )
            logger.info("Created Qdrant collection: %s", self.collection)

    def store_embedding(self, doc_id: int, embedding: List[float]) -> bool:
        from qdrant_client.models import PointStruct

        client = self._get_client()
        client.upsert(
            collection_name=self.collection,
            points=[
                PointStruct(
                    id=doc_id,
                    vector=embedding,
                    payload={"doc_id": doc_id},
                )
            ],
        )
        return True

    def search_similar(
        self, query_embedding: List[float], top_k: int = 5
    ) -> List[Tuple[int, float]]:
        client = self._get_client()
        results = client.search(
            collection_name=self.collection,
            query_vector=query_embedding,
            limit=top_k,
        )
        return [(hit.id, hit.score) for hit in results]

    def delete_embedding(self, doc_id: int) -> bool:
        client = self._get_client()
        client.delete(
            collection_name=self.collection,
            points_selector=[doc_id],
        )
        return True

    def count_embeddings(self) -> int:
        client = self._get_client()
        info = client.get_collection(self.collection)
        return info.points_count


def get_vector_store(db_session=None) -> VectorStore:
    """获取向量存储实例
    
    根据环境变量 VECTOR_STORE_BACKEND 选择后端:
    - sqlite (默认): SQLiteVectorStore
    - pgvector: PgVectorStore
    - qdrant: QdrantVectorStore
    """
    backend = os.getenv("VECTOR_STORE_BACKEND", "sqlite").lower()
    dimension = int(os.getenv("VECTOR_STORE_DIMENSION", "1536"))

    if backend == "pgvector":
        logger.info("Using pgvector backend")
        return PgVectorStore(db_session, dimension)
    elif backend == "qdrant":
        url = os.getenv("QDRANT_URL", "http://localhost:6333")
        collection = os.getenv("QDRANT_COLLECTION", "subskin_documents")
        logger.info("Using Qdrant backend: %s/%s", url, collection)
        return QdrantVectorStore(url, collection, dimension)
    else:
        return SQLiteVectorStore(db_session)
