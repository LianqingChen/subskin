"""医评（/hospitals）服务层回归测试。

覆盖：官方目录种子幂等、目录筛选、病友补充医院、评价发布校验、
PII 自动脱敏、疗效夸大用语标记、公开可见性（屏蔽/软删）、统计聚合。
"""

import pytest

from web.backend.database.models import Hospital
from web.backend.exceptions import (
    HospitalNotFoundError,
    HospitalReviewNotFoundError,
    HospitalReviewRejectedError,
)
from web.backend.models.hospital import HospitalCreate, HospitalReviewCreate
from web.backend.services.hospital import (
    EXAGGERATED_WORDS,
    create_hospital,
    create_review,
    delete_review,
    hide_review,
    list_hospitals,
    list_reviews,
    list_user_reviews,
    save_review_image,
    seed_official_hospitals,
    toggle_helpful,
)


def _review_payload(**kwargs) -> HospitalReviewCreate:
    # v3：就医体验属敏感个人信息，需显式单独同意（PIPL 第 28/29 条，禁止默认勾选）
    base = {
        "target": "hospital",
        "content": "挂号到面诊大约等了一小时，医生把方案和费用讲得比较清楚。",
        "health_consent": True,
    }
    base.update(kwargs)
    return HospitalReviewCreate(**base)


def _seeded_hospital_id(db_session) -> int:
    seed_official_hospitals(db_session)
    return db_session.query(Hospital).filter(Hospital.slug == "pumch").one().id


def test_seed_official_hospitals_is_idempotent(db_session):
    created = seed_official_hospitals(db_session)
    assert created == 7
    # 二次调用不再写入，也不会覆盖既有条目
    assert seed_official_hospitals(db_session) == 0
    assert db_session.query(Hospital).count() == 7


def test_list_hospitals_filters_by_region_and_keyword(db_session):
    seed_official_hospitals(db_session)

    all_hospitals = list_hospitals(db_session)
    assert len(all_hospitals) == 7
    assert all(h.status == "visible" for h in all_hospitals)

    shanghai = list_hospitals(db_session, province="上海")
    assert {h.name for h in shanghai} == {
        "复旦大学附属华山医院", "上海中医药大学附属岳阳中西医结合医院",
    }
    assert [h.name for h in list_hospitals(db_session, city="南京")] == ["中国医学科学院皮肤病医院"]
    assert [h.name for h in list_hospitals(db_session, q="光疗")] == ["四川大学华西医院"]


def test_create_community_hospital_gets_unique_slug_and_badge(db_session, test_user):
    seed_official_hospitals(db_session)
    payload = HospitalCreate(
        name="某某市皮肤病医院", province="浙江", city="杭州", district="上城区",
        address="某路 1 号 3 号楼", department="皮肤科", kind="皮肤病专科",
    )

    first = create_hospital(db_session, test_user.id, payload)
    second = create_hospital(db_session, test_user.id, payload)

    assert first.origin == "community" and first.status == "visible"
    assert first.slug != second.slug  # 同名补充不冲突
    assert first.address == "某路 1 号 3 号楼"
    assert first.lat is None and first.lng is None  # 非城市字典内城市不编造坐标
    assert first.stats is not None and first.stats.review_count == 0


def test_create_review_requires_min_length_and_target_fields(db_session, test_user):
    hospital_id = _seeded_hospital_id(db_session)

    with pytest.raises(HospitalReviewRejectedError):
        create_review(db_session, test_user.id, str(hospital_id), _review_payload(content="太短了"))

    with pytest.raises(HospitalReviewRejectedError):
        create_review(db_session, test_user.id, str(hospital_id), _review_payload(target="doctor"))

    with pytest.raises(HospitalReviewRejectedError):
        create_review(db_session, test_user.id, str(hospital_id), _review_payload(target="treatment"))

    with pytest.raises(HospitalReviewRejectedError):
        create_review(db_session, test_user.id, str(hospital_id), _review_payload(visit_month="2099-01"))

    with pytest.raises(HospitalNotFoundError):
        create_review(db_session, test_user.id, "not-a-hospital", _review_payload())


def test_doctor_review_keeps_only_title_and_department(db_session, test_user):
    hospital_id = _seeded_hospital_id(db_session)
    payload = _review_payload(
        target="doctor", doctor_name="张医生", doctor_title="主任医师",
        doctor_department="皮肤科", content="张医生解释得很细，把光疗的周期和复查时间都写了下来。",
    )
    review, _, _, _, _ = create_review(db_session, test_user.id, str(hospital_id), payload)
    # v3：落库即为脱敏称谓「张医生（皮肤科）」，绝不保存可识别真名
    assert review.doctor_name == "张医生（皮肤科）"
    assert review.doctor_title == "主任医师"
    assert review.target == "doctor"


def test_review_pii_is_auto_redacted_unless_confirmed(db_session, test_user):
    hospital_id = _seeded_hospital_id(db_session)

    redacted, pii_redacted, pii_types, _, _ = create_review(
        db_session, test_user.id, str(hospital_id),
        _review_payload(content="复诊安排写在病历上了，我的联系电话是 13800001111，可以核对。"),
    )
    assert pii_redacted is True and "phone" in pii_types
    assert "13800001111" not in redacted.content
    assert "138****1111" in redacted.content

    kept, pii_redacted2, _, _, _ = create_review(
        db_session, test_user.id, str(hospital_id),
        _review_payload(
            content="复诊提醒我自己记了 13800002222，这条内容我想保留原文。",
            confirm_pii=True,
        ),
    )
    assert pii_redacted2 is False
    assert "13800002222" in kept.content


def test_exaggerated_claims_are_blocked_before_publish(db_session, test_user):
    """v3：疗效夸大用语从「事后标记」升级为「发布前硬拦截 + 改写建议」。

    依据《广告法》第 16 条、《医疗广告管理办法》第 7 条 —— 平台不得宣传治愈率、
    有效率，也不得让患者评价成为变相疗效证明。
    """
    hospital_id = _seeded_hospital_id(db_session)
    with pytest.raises(HospitalReviewRejectedError) as excinfo:
        create_review(
            db_session, test_user.id, str(hospital_id),
            _review_payload(content="在这家医院用了三个月，白斑已经根治了，医生说保证治好不会再复发。"),
        )
    assert "修改" in str(excinfo.value)
    # 未被写入库
    total, items, _ = list_reviews(db_session, hospital_id)
    assert total == 0

    # 中性过程描述可以正常发布
    review, _, _, _, risk = create_review(
        db_session, test_user.id, str(hospital_id),
        _review_payload(content="在这家医院用了三个月，我治疗后白斑有变化，医生说继续观察复查。"),
    )
    assert review.moderation_status in ("approved", "flagged")
    assert risk["level"] in ("safe", "watch")
    total, items, _ = list_reviews(db_session, hospital_id)
    assert total == 1 and items[0].id == review.id


def test_stats_aggregate_ratings_and_target_counts(db_session, test_user, test_admin_user):
    hospital_id = _seeded_hospital_id(db_session)
    _ = create_review(db_session, test_user.id, str(hospital_id), _review_payload(
        ratings={"医护沟通": 5, "费用透明": 4}, tags=["解释耐心"],
    ))
    _ = create_review(db_session, test_admin_user.id, str(hospital_id), _review_payload(
        target="treatment", treatment_name="308 准分子光", ratings={"方案解释": 3},
        content="308 准分子光做了两个月，医生每次都会调整剂量，费用按次结算。",
    ))

    total, items, summary = list_reviews(db_session, hospital_id)
    assert total == 2
    assert summary.review_count == 2
    assert summary.rating_count == 3
    assert summary.rating_avg == 4.0
    assert summary.treatment_review_count == 1
    assert summary.doctor_review_count == 0
    assert summary.targets == {"hospital": 1, "treatment": 1}

    doctor_only_total, doctor_items, _ = list_reviews(db_session, hospital_id, target="doctor")
    assert doctor_only_total == 0 and doctor_items == []

    mine = list_user_reviews(db_session, test_user.id)
    assert len(mine) == 1 and mine[0].is_mine is True
    assert items[0].author is not None


def test_blocked_review_disappears_from_public_list(db_session, test_user):
    hospital_id = _seeded_hospital_id(db_session)
    review, _, _, _, _ = create_review(db_session, test_user.id, str(hospital_id), _review_payload())

    hide_review(db_session, review.id, True)
    total, items, summary = list_reviews(db_session, hospital_id)
    assert total == 0 and items == [] and summary.review_count == 0

    hide_review(db_session, review.id, False)
    assert list_reviews(db_session, hospital_id)[0] == 1


def test_delete_review_is_owner_only_and_soft(db_session, test_user, test_admin_user):
    hospital_id = _seeded_hospital_id(db_session)
    review, _, _, _, _ = create_review(db_session, test_user.id, str(hospital_id), _review_payload())

    with pytest.raises(HospitalReviewNotFoundError):
        delete_review(db_session, test_admin_user.id, review.id)

    delete_review(db_session, test_user.id, review.id)
    assert list_reviews(db_session, hospital_id)[0] == 0
    assert list_user_reviews(db_session, test_user.id) == []

    # 软删除保留行（审计可追溯），不会物理删除
    assert db_session.query(Hospital).count() == 7


# ── 一期新增：凭证图 / 有用投票 / 标签聚合 / 完整度 ──


def _image_payload(url: str = "/uploads/hospital/1_abc.jpg", label: str = "费用单"):
    from web.backend.models.hospital import HospitalReviewImage
    return HospitalReviewImage(url=url, label=label)


def test_review_images_require_label_whitelist_and_confirmation(db_session, test_user):
    hospital_id = _seeded_hospital_id(db_session)
    base = _review_payload(content="这次挂了普通皮肤科门诊，把费用单拍了留个记录，方便后面病友参考。")

    # 未勾选确认 → 拒绝
    with pytest.raises(HospitalReviewRejectedError):
        create_review(db_session, test_user.id, str(hospital_id),
                      base.model_copy(update={"images": [_image_payload()], "images_confirmed": False}))

    # 标签不在白名单 → 拒绝（防止把病情照片当凭证上传）
    with pytest.raises(HospitalReviewRejectedError):
        create_review(db_session, test_user.id, str(hospital_id),
                      base.model_copy(update={"images": [_image_payload(label="病情照片")], "images_confirmed": True}))

    # 非本模块上传路径 → 拒绝
    with pytest.raises(HospitalReviewRejectedError):
        create_review(db_session, test_user.id, str(hospital_id),
                      base.model_copy(update={"images": [_image_payload(url="/uploads/community/x.jpg")],
                                              "images_confirmed": True}))

    # 正常路径
    review, _, _, _, _ = create_review(
        db_session, test_user.id, str(hospital_id),
        base.model_copy(update={"images": [_image_payload()], "images_confirmed": True}),
    )
    assert len(review.images) == 1
    assert review.images[0].label == "费用单"
    assert review.images[0].url.startswith("/uploads/hospital/")


def test_review_images_limited_to_three(db_session, test_user):
    hospital_id = _seeded_hospital_id(db_session)
    payload = _review_payload(content="把挂号单和费用单都拍下来了，供后面病友参考，医院流程还算清楚。")
    payload = payload.model_copy(update={
        "images": [_image_payload(url=f"/uploads/hospital/1_{i}.jpg") for i in range(5)],
        "images_confirmed": True,
    })
    review, _, _, _, _ = create_review(db_session, test_user.id, str(hospital_id), payload)
    assert len(review.images) == 3  # 超过 3 张只保留前 3 张


def test_save_review_image_validates_magic_bytes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 64
    url = save_review_image(7, "receipt.png", png)
    assert url.startswith("/uploads/hospital/7_") and url.endswith(".png")

    with pytest.raises(HospitalReviewRejectedError):
        save_review_image(7, "receipt.jpg", b"<html>not an image</html>")


def test_helpful_toggle_is_idempotent_and_blocks_self_vote(db_session, test_user, test_admin_user):
    hospital_id = _seeded_hospital_id(db_session)
    review, _, _, _, _ = create_review(db_session, test_user.id, str(hospital_id), _review_payload())

    count, is_helpful = toggle_helpful(db_session, test_admin_user.id, review.id)
    assert (count, is_helpful) == (1, True)
    count, is_helpful = toggle_helpful(db_session, test_admin_user.id, review.id)
    assert (count, is_helpful) == (0, False)

    # 同一人重复点不会产生重复票：计数始终在 0 / 1 之间切换
    for expected in (1, 0, 1, 0, 1):
        assert toggle_helpful(db_session, test_admin_user.id, review.id)[0] == expected

    with pytest.raises(HospitalReviewRejectedError):
        toggle_helpful(db_session, test_user.id, review.id)  # 自己的评价


def test_sort_helpful_and_viewer_state(db_session, test_user, test_admin_user):
    hospital_id = _seeded_hospital_id(db_session)
    older, _, _, _, _ = create_review(db_session, test_admin_user.id, str(hospital_id), _review_payload(
        content="第一次去这家医院挂的是专家门诊，医生把方案和复查时间都写清楚了。"))
    newer, _, _, _, _ = create_review(db_session, test_user.id, str(hospital_id), _review_payload(
        content="第二次复诊排期等了比较久，不过医生解释得还算耐心，费用也在预期内。"))

    # 默认最新在前
    _, items, _ = list_reviews(db_session, hospital_id)
    assert [i.id for i in items] == [newer.id, older.id]

    toggle_helpful(db_session, test_user.id, older.id)  # 给"较早"的那条投票
    _, items, _ = list_reviews(db_session, hospital_id, sort="helpful", viewer_id=test_user.id)
    assert items[0].id == older.id
    assert items[0].helpful_count == 1 and items[0].is_helpful is True
    assert items[1].helpful_count == 0 and items[1].is_helpful is False

    with pytest.raises(HospitalReviewRejectedError):
        list_reviews(db_session, hospital_id, sort="whatever")


def test_stats_aggregate_top_tags_and_detail_score(db_session, test_user, test_admin_user):
    hospital_id = _seeded_hospital_id(db_session)
    create_review(db_session, test_user.id, str(hospital_id), _review_payload(
        tags=["解释耐心", "费用清楚"], ratings={"医护沟通": 5}, cost="500–1500元",
        content="挂号和面诊流程都算清楚，医生把方案讲明白了，费用也提前说明了。",
    ))
    create_review(db_session, test_admin_user.id, str(hospital_id), _review_payload(
        tags=["解释耐心", "候诊较久"],
        content="同样提到解释耐心，不过我这次候诊等了一个多小时，建议早点去排队。",
    ))

    _, items, summary = list_reviews(db_session, hospital_id)
    tags = {item.tag: item.count for item in summary.top_tags}
    assert tags["解释耐心"] == 2
    assert tags["费用清楚"] == 1 and tags["候诊较久"] == 1

    by_id = {item.id: item for item in items}
    scored = [item for item in items if item.detail_score >= 2]
    assert len(scored) == 1  # 只有第一条填了评分+费用
    assert by_id[scored[0].id].images == []
