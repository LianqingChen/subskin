"""用户UID生成

正式用户格式: SS-{YYYYMMDDHHmm}-{10位序号}
测试用户格式: SSTC-{YYYYMMDDHHmm}-{10位序号}

序号规则：
- 正式用户序号只统计正式用户总数（is_test=False），测试账号不计入
- 测试用户序号统计测试用户总数（is_test=True）
- 时间戳使用中国时区 (Asia/Shanghai, UTC+8)

示例:
- 正式用户第1位: SS-202604170036-0000000001
- 测试用户第3位: SSTC-202604161555-0000000003
"""

from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session

from web.backend.database.models import User

CST = timezone(timedelta(hours=8))

TEST_PREFIX = "SSTC"
PROD_PREFIX = "SS"
SEQUENCE_WIDTH = 10


def generate_uid(identifier: str, db: Session, is_test: bool = False) -> str:
    now_cst = datetime.now(CST)
    timestamp = now_cst.strftime("%Y%m%d%H%M")
    prefix = TEST_PREFIX if is_test else PROD_PREFIX

    if is_test:
        total = db.query(User).filter(User.is_test == True).count()
    else:
        total = db.query(User).filter(User.is_test == False).count()

    sequence = total + 1

    uid = f"{prefix}-{timestamp}-{sequence:0{SEQUENCE_WIDTH}d}"

    for attempt in range(10):
        existing = db.query(User).filter(User.uid == uid).first()
        if not existing:
            return uid
        sequence = total + 1 + attempt + 1
        uid = f"{prefix}-{timestamp}-{sequence:0{SEQUENCE_WIDTH}d}"

    import uuid

    uid = f"{prefix}-{timestamp}-{uuid.uuid4().hex[:10]}"
    return uid
