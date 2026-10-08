#!/usr/bin/env python3
"""创建 E2E 测试账号及其测试数据（幂等，可重复执行）。

用途：
    为登录态全站 E2E 测试准备一个专用账号，包含：
    - User + UserCredential（手机号 + 密码两种登录方式）
    - PatientProfile（白癜风档案：面部+手部、非节段型、稳定期）
    - 3 条 DiaryEntry（不同日期，含 mood / ai_summary）
    - 1 条 VASIAssessment（最小合法记录，失败则跳过）
    - 1 篇普通社区 Post（"E2E测试帖-请勿互动"）
    并用后端 JWT 签发逻辑生成 7 天有效的 access token，
    打印浏览器 localStorage 注入步骤。

安全约束：
    - 只新增/更新本测试账号自己的数据，不触碰其他任何记录；
    - 不修改业务代码，不重启后端。

运行：
    cd /root/subskin && .venv/bin/python scripts/create_e2e_test_user.py
"""

import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# 必须在导入 web.backend.* 之前加载环境变量（auth.py 在导入时读取 SECRET_KEY）
from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO_ROOT / "web" / "backend" / ".env", override=False)

from sqlalchemy.orm import Session  # noqa: E402

from web.backend.database.database import SessionLocal  # noqa: E402
from web.backend.database.models import (  # noqa: E402
    CommunityCategory,
    DiaryEntry,
    PatientProfile,
    Post,
    User,
)
from web.backend.models.vasi import VASIAssessment  # noqa: E402
from web.backend.services.auth import (  # noqa: E402
    create_access_token,
    create_refresh_token,
    get_password_hash,
)
from web.backend.services.credential import bind_credential, find_credential  # noqa: E402
from web.backend.utils.uid import generate_uid  # noqa: E402

# ── 测试账号固定参数 ──────────────────────────────────────────────
TEST_PHONE = "13800000099"  # 明显虚假的保留号段
TEST_USERNAME = "E2E测试账号"
TEST_PASSWORD = "E2E@Test2026!"  # pragma: allowlist secret
TOKEN_EXPIRE_DAYS = 7
POST_TITLE = "E2E测试帖-请勿互动"
POST_CONTENT = "这是自动化E2E测试专用帖子，仅用于验证页面展示，请勿点赞/评论/收藏。"
PROFILE_NAME = "E2E档案"

DIARY_SEEDS = [
    {
        "days_ago": 9,
        "raw_text": "今天面部白斑看起来比较稳定，继续按医嘱涂抹他克莫司，晚上照了308光。",
        "mood": "hopeful",
        "sleep_quality": "good",
        "skin_condition": "stable",
        "stress_level": 2,
        "ai_summary": "病情处于稳定期，面部白斑无扩散迹象；坚持他克莫司外用与308光疗，情绪积极。",
    },    {
        "days_ago": 5,
        "raw_text": "手背的白斑边缘有点发红，可能是昨天照光剂量略高，其他都还好。",
        "mood": "neutral",
        "sleep_quality": "fair",
        "skin_condition": "stable",
        "stress_level": 3,
        "ai_summary": "手部白斑照光后轻度发红，提示光疗反应，建议下次咨询医生是否微调剂量；整体仍稳定。",
    },
    {
        "days_ago": 1,
        "raw_text": "复查医生说面部有色素岛出现，恢复得不错，心情很好，继续坚持治疗。",
        "mood": "good",
        "sleep_quality": "good",
        "skin_condition": "improving",
        "stress_level": 1,
        "ai_summary": "复诊反馈良好，面部出现色素岛，提示治疗有效；情绪良好，依从性高。",
    },
]


# ── 批量数据用户参数 ─────────────────────────────────────────────
DATA_USER_COUNT = 10
DATA_USER_PHONE_BASE = 13800000100  # 13800000100 ~ 13800000109
DATA_USER_DIARY_COUNT = 10
BACKFILL_DAYS = 90  # 主账号回填近3个月连续日记

MOOD_CYCLE = ["good", "neutral", "hopeful", "bad", "anxious"]
SLEEP_CYCLE = ["good", "fair", "poor"]
SKIN_CYCLE = ["stable", "improving", "stable", "new_spots", "stable"]
VASI_SITES = ["面部", "手部", "躯干"]

RAW_TEXT_TEMPLATES = [
    "今天状态不错，白斑没有明显变化，按时用药，晚上散步放松了一下。",
    "昨晚睡得不太好，早上起来有点累，白斑部位没什么变化，继续观察。",
    "复诊回来，医生说恢复方向是对的，心里踏实了不少，继续坚持光疗。",
    "最近工作压力有点大，担心影响病情，好在皮肤看起来还算稳定。",
    "照完光后皮肤微微发红，属于正常反应，医生说下次可以维持当前剂量。",
    "今天心情很好，和朋友聊了很多，感觉坚持治疗的动力更足了。",
    "饮食上注意了很多，补充了黑豆和坚果，白斑边缘似乎有轻微色素沉着。",
    "天气转凉，皮肤有点干燥，涂了保湿霜，白斑区域没有新变化。",
    "今天有点焦虑，看到白斑还是老样子，不过医生说过恢复需要时间。",
    "记录一下：用药后局部有轻微色素岛出现，是个好信号，继续加油。",
]
SUMMARY_TEMPLATES = [
    "病情稳定，用药依从性良好，情绪平稳，建议保持当前治疗方案。",
    "睡眠质量欠佳，建议规律作息；皮损无明显变化，继续观察。",
    "复诊反馈积极，治疗方向正确，患者信心提升，光疗按计划进行。",
    "压力水平偏高，需关注心理调节；皮损目前稳定。",
    "光疗后出现预期内的轻度红斑反应，剂量适宜，无需调整。",
    "情绪良好，社会支持充分，治疗依从性高。",
    "饮食管理良好，疑似出现早期色素恢复迹象，继续随访。",
    "季节性皮肤干燥，已加强保湿；白斑无进展。",
    "出现轻度焦虑情绪，皮损稳定，建议配合放松训练。",
    "观察到色素岛形成，提示治疗有效，预后积极。",
]


def _upsert_user(db: Session) -> User:
    """查找或创建测试用户（含 phone/password 凭证）。"""
    user = db.query(User).filter(User.phone == TEST_PHONE).first()
    created = False
    if user is None:
        user = User(
            uid=generate_uid(TEST_PHONE, db, is_test=True),
            username=TEST_USERNAME,
            phone=TEST_PHONE,
            is_active=True,
            is_admin=False,
            is_test=True,
            patient_relation="本人",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        created = True

    # 更新而非重复创建
    user.username = TEST_USERNAME
    user.is_active = True
    user.is_test = True
    db.commit()
    db.refresh(user)

    password_hash = get_password_hash(TEST_PASSWORD)

    # phone 凭证（手机验证码/密码登录均依赖此凭证）
    phone_cred = find_credential(db, user.id, "phone")
    if phone_cred is None:
        bind_credential(db, user.id, "phone", TEST_PHONE, verified=True)

    # password 凭证（与 api/user.py 的 _upsert_password_credential 逻辑一致）
    user.hashed_password = password_hash
    db.add(user)
    payload = json.dumps({"hashed_password": password_hash}, ensure_ascii=False)
    password_cred = find_credential(db, user.id, "password")
    if password_cred is not None:
        password_cred.credential_data = payload
        password_cred.verified = True
        password_cred.updated_at = datetime.now(timezone.utc)
        db.add(password_cred)
    else:
        bind_credential(
            db, user.id, "password", "password",
            verified=True, credential_data=payload,
        )
    db.commit()

    print(f"{'创建' if created else '已存在，已更新'}用户: id={user.id} uid={user.uid} "
          f"username={user.username!r} phone={TEST_PHONE}")
    return user


def _upsert_profile(db: Session, user: User) -> PatientProfile:
    profile = (
        db.query(PatientProfile)
        .filter(PatientProfile.user_id == user.id)
        .filter(PatientProfile.name == PROFILE_NAME)
        .first()
    )
    if profile is None:
        profile = PatientProfile(user_id=user.id, name=PROFILE_NAME)
        db.add(profile)

    profile.relationship = "本人"
    profile.gender = "女"
    profile.diagnosis_date = date(2023, 6, 1)
    profile.vitiligo_type = "非节段型"
    profile.notes = "受累部位：面部+手部；病情分期：稳定期（E2E测试档案）"
    profile.is_self = True
    db.commit()
    db.refresh(profile)

    # 设为该用户各模块的默认档案，模拟真实用户行为
    user.default_tracker_profile_id = profile.id
    user.default_report_profile_id = profile.id
    user.default_diary_profile_id = profile.id
    db.commit()

    print(f"患者档案就绪: id={profile.id} 分型={profile.vitiligo_type} "
          f"部位=面部+手部 分期=稳定期")
    return profile


def _upsert_diary(
    db: Session,
    user: User,
    profile_id: int,
    entry_date: date,
    raw_text: str,
    mood: str,
    ai_summary: str,
    sleep_quality: str = "good",
    skin_condition: str = "stable",
    stress_level: int = 2,
) -> bool:
    """创建或更新指定日期的日记。返回是否为新建。"""
    entry = (
        db.query(DiaryEntry)
        .filter(DiaryEntry.user_id == user.id)
        .filter(DiaryEntry.entry_date == entry_date)
        .first()
    )
    created = entry is None
    if created:
        entry = DiaryEntry(user_id=user.id, entry_date=entry_date)
        db.add(entry)
    entry.profile_id = profile_id
    entry.raw_text = raw_text
    entry.input_type = "text"
    entry.mood = mood
    entry.sleep_quality = sleep_quality
    entry.skin_condition = skin_condition
    entry.stress_level = stress_level
    entry.ai_summary = ai_summary
    return created


def _upsert_diaries(db: Session, user: User, profile: PatientProfile) -> int:
    count = 0
    for seed in DIARY_SEEDS:
        entry_date = date.today() - timedelta(days=seed["days_ago"])
        if _upsert_diary(
            db,
            user,
            profile.id,
            entry_date,
            seed["raw_text"],
            seed["mood"],
            seed["ai_summary"],
            sleep_quality=seed["sleep_quality"],
            skin_condition=seed["skin_condition"],
            stress_level=seed["stress_level"],
        ):
            count += 1
    db.commit()
    print(f"病情日记就绪: {count} 条新建（不同日期，均含 mood/ai_summary）")
    return count


def _backfill_main_diaries(db: Session, user: User, profile: PatientProfile) -> int:
    """为主账号回填近 BACKFILL_DAYS 天的连续日记（已有日期优先保留）。"""
    created = 0
    for days_ago in range(BACKFILL_DAYS, -1, -1):
        entry_date = date.today() - timedelta(days=days_ago)
        idx = days_ago % len(RAW_TEXT_TEMPLATES)
        if _upsert_diary(
            db,
            user,
            profile.id,
            entry_date,
            RAW_TEXT_TEMPLATES[idx],
            MOOD_CYCLE[days_ago % len(MOOD_CYCLE)],
            SUMMARY_TEMPLATES[idx],
            sleep_quality=SLEEP_CYCLE[days_ago % len(SLEEP_CYCLE)],
            skin_condition=SKIN_CYCLE[days_ago % len(SKIN_CYCLE)],
            stress_level=(days_ago % 3) + 1,
        ):
            created += 1
        if days_ago % 30 == 0:
            db.commit()  # 分批提交，避免长事务
    db.commit()
    total = db.query(DiaryEntry).filter(DiaryEntry.user_id == user.id).count()
    print(f"主账号日记回填完成: 新建 {created} 条，当前共 {total} 条（覆盖近{BACKFILL_DAYS}天）")
    return total


def _upsert_vasi_for(db: Session, user: User, body_site: str, score: float, area: float) -> bool:
    try:
        existing = (
            db.query(VASIAssessment)
            .filter(VASIAssessment.user_id == user.id)
            .filter(VASIAssessment.body_site == body_site)
            .first()
        )
        if existing is not None:
            print(f"  VASI评估已存在: id={existing.id}（{body_site}），跳过")
            return True
        assessment = VASIAssessment(
            user_id=user.id,
            image_url="/uploads/e2e/e2e-vasi-placeholder.jpg",  # 占位图，仅用于记录展示
            vasi_score=score,
            body_site=body_site,
            area_percentage=area,
            classification="非节段型",
            stage="稳定",
            status="active",
        )
        db.add(assessment)
        db.commit()
        db.refresh(assessment)
        print(f"  VASI评估就绪: id={assessment.id} score={score} 部位={body_site}")
        return True
    except Exception as e:
        db.rollback()
        print(f"  [跳过] VASI评估创建失败（不影响其他数据）: {e}")
        return False


def _upsert_vasi(db: Session, user: User) -> bool:
    return _upsert_vasi_for(db, user, "面部", 2.5, 1.2)


def _upsert_data_users(db: Session) -> int:
    """创建/更新 DATA_USER_COUNT 个数据用户，每人10条日记 + 1条VASI。"""
    created_users = 0
    for i in range(1, DATA_USER_COUNT + 1):
        phone = str(DATA_USER_PHONE_BASE + i - 1)
        username = f"E2E数据用户{i}"
        user = db.query(User).filter(User.phone == phone).first()
        if user is None:
            user = User(
                uid=generate_uid(phone, db, is_test=True),
                username=username,
                phone=phone,
                is_active=True,
                is_admin=False,
                is_test=True,
                patient_relation="本人",
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            bind_credential(db, user.id, "phone", phone, verified=True)
            created_users += 1
        user.username = username
        user.is_active = True
        user.is_test = True
        db.commit()
        db.refresh(user)

        # 档案（日记关联用）
        profile = (
            db.query(PatientProfile)
            .filter(PatientProfile.user_id == user.id)
            .filter(PatientProfile.name == PROFILE_NAME)
            .first()
        )
        if profile is None:
            profile = PatientProfile(
                user_id=user.id,
                name=PROFILE_NAME,
                relationship="本人",
                vitiligo_type="非节段型",
                notes=f"受累部位：{VASI_SITES[(i - 1) % 3]}；分期：稳定期（E2E数据用户{i}）",
                is_self=True,
            )
            db.add(profile)
            db.commit()
            db.refresh(profile)

        # 10条日记：近30天均匀分布（每3天一条）
        for j in range(DATA_USER_DIARY_COUNT):
            days_ago = j * 3 + (i % 3)
            entry_date = date.today() - timedelta(days=days_ago)
            idx = (i + j) % len(RAW_TEXT_TEMPLATES)
            _upsert_diary(
                db,
                user,
                profile.id,
                entry_date,
                RAW_TEXT_TEMPLATES[idx],
                MOOD_CYCLE[(i + j) % len(MOOD_CYCLE)],
                SUMMARY_TEMPLATES[idx],
                sleep_quality=SLEEP_CYCLE[(i + j) % len(SLEEP_CYCLE)],
                skin_condition=SKIN_CYCLE[(i + j) % len(SKIN_CYCLE)],
                stress_level=((i + j) % 4) + 1,
            )
        db.commit()

        # 1条VASI（部位轮换，分数递增制造差异）
        _upsert_vasi_for(
            db,
            user,
            VASI_SITES[(i - 1) % len(VASI_SITES)],
            round(1.0 + i * 0.7, 1),
            round(0.5 + i * 0.3, 1),
        )
        print(f"数据用户就绪: id={user.id} {username} phone={phone} "
              f"(日记{DATA_USER_DIARY_COUNT}条 + VASI 1条)")
    print(f"批量数据用户完成: 新建 {created_users} 个，共 {DATA_USER_COUNT} 个")
    return created_users


def _upsert_post(db: Session, user: User) -> Post:
    category = db.query(CommunityCategory).order_by(CommunityCategory.id.asc()).first()
    if category is None:
        raise RuntimeError("community_categories 为空，无法创建帖子")

    post = (
        db.query(Post)
        .filter(Post.user_id == user.id)
        .filter(Post.title == POST_TITLE)
        .first()
    )
    if post is None:
        post = Post(user_id=user.id, title=POST_TITLE)
        db.add(post)
    post.content = POST_CONTENT
    post.content_preview = POST_CONTENT[:100]
    post.post_type = "text"
    post.category_id = category.id
    post.is_private = False
    post.is_anonymous = False
    post.moderation_status = "normal"
    db.commit()
    db.refresh(post)
    print(f"社区帖子就绪: id={post.id} 标题={post.title!r} 分类={category.name}")
    return post


def _issue_tokens(db: Session, user: User) -> tuple[str, str]:
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=timedelta(days=TOKEN_EXPIRE_DAYS)
    )
    refresh_token = create_refresh_token(data={"sub": user.username}, db=db)
    return access_token, refresh_token


def main() -> None:
    db = SessionLocal()
    try:
        user = _upsert_user(db)
        profile = _upsert_profile(db, user)
        _upsert_diaries(db, user, profile)
        _backfill_main_diaries(db, user, profile)
        _upsert_vasi(db, user)
        _upsert_post(db, user)
        _upsert_data_users(db)
        access_token, refresh_token = _issue_tokens(db, user)

        expire_at = datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRE_DAYS)
        print()
        print("=" * 72)
        print("E2E 测试账号信息")
        print("=" * 72)
        print(f"用户名/昵称 : {TEST_USERNAME}")
        print(f"手机号      : {TEST_PHONE}（保留号段，未真实发送验证码）")
        print(f"密码        : {TEST_PASSWORD}（可用 /api/user/login-by-phone-password 登录）")
        print(f"access token 有效期至: {expire_at.isoformat()}（{TOKEN_EXPIRE_DAYS}天）")
        print()
        print(f"access_token : {access_token}")
        print(f"refresh_token: {refresh_token}")
        print()
        print("=" * 72)
        print("浏览器注入登录态步骤")
        print("=" * 72)
        print("1. 打开 https://www.subskin.cn")
        print("2. 打开浏览器 DevTools Console，粘贴执行以下 JS：")
        print()
        print("---- 复制以下内容 ----")
        print(f"localStorage.setItem('subskin_token', '{access_token}');")
        print(f"localStorage.setItem('subskin_refresh_token', '{refresh_token}');")
        print("location.reload();")
        print("---- 复制结束 ----")
        print()
        print("说明：前端 stores/auth.ts 通过 localStorage key 'subskin_token' 读取")
        print("登录态；用户信息（subskin_user）会在刷新后由 /api/user/me 自动拉取，")
        print("无需手动写入。")
    finally:
        db.close()


if __name__ == "__main__":
    main()
