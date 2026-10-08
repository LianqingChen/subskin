"""用户自报事实与微询问日志（图像数据库专项 SS-32/33）。

自报事实是 T1（用户事实），**不是临床标签**：不进入确诊正例，也不替代医生判断。
- ``SelfReportFact`` 追加式：修改答案 = 新增一行，同一键取最新一行。
- ``MicroAskLog`` 记录“展示/作答/跳过”，用于频率上限与冷却，不含答案内容。
仅增量新表。
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text

from web.backend.database.database import Base


class SelfReportFact(Base):
    __tablename__ = "self_report_facts"
    __table_args__ = (
        Index("idx_srf_key", "user_id", "question_id", "body_site"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    profile_id = Column(Integer, nullable=True)  # 病友档案；不加外键
    question_id = Column(String(8), nullable=False)  # Q1..Q7
    question_version = Column(String(16), nullable=False)
    body_site = Column(String(50), nullable=True)  # 按部位提问的题目才有
    answer_json = Column(Text, nullable=False)  # 单选为字符串，多选为列表；"unknown" 为合法值
    source = Column(String(20), nullable=False, default="micro_ask")  # micro_ask / checklist
    answered_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class MicroAskLog(Base):
    __tablename__ = "micro_ask_log"
    __table_args__ = (
        Index("idx_mal_user_time", "user_id", "created_at"),
        Index("idx_mal_session", "user_id", "session_id"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    question_id = Column(String(8), nullable=False)
    body_site = Column(String(50), nullable=True)
    event = Column(String(12), nullable=False)  # shown / answered / skipped / listed
    session_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
