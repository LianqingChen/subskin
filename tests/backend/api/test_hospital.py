"""医评（/api/hospitals）API 层测试。

覆盖三层：
  1. 目录与基础发布流程（登录、可见性、软删、管理端下架）；
  2. 一期能力（凭证图、有用投票、排序、标签聚合）；
  3. **v3 统一评价体系与风控**（6 维体验档位、疗效维度黑名单、医生称谓脱敏、
     PIPL 单独同意、风险分档、聚合冷处理、举报幂等与阈值、申诉时限、风控看板、
     凭证图不再公开）。
"""

import pytest


@pytest.fixture(autouse=True)
def _reset_write_limiter():
    """写接口限速（10 次/分钟/用户）是进程内共享的，测试间必须重置。"""
    from web.backend.app.middleware.rate_limit import write_limiter

    write_limiter._buckets.clear()
    yield
    write_limiter._buckets.clear()


def test_list_and_detail_are_public(client):
    listed = client.get("/api/hospitals")
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 7
    assert all("医" in h["name"] or "医院" in h["name"] for h in body["items"])

    detail = client.get("/api/hospitals/pumch")
    assert detail.status_code == 200
    assert detail.json()["name"] == "北京协和医院"
    assert client.get("/api/hospitals/does-not-exist").status_code == 404


def test_create_review_requires_login(client):
    listed = client.get("/api/hospitals").json()
    hospital_id = listed["items"][0]["id"]
    response = client.post(
        f"/api/hospitals/{hospital_id}/reviews",
        json={"target": "hospital", "content": "挂号到面诊等了一小时，医生把方案讲得比较清楚。"},
    )
    assert response.status_code in (401, 403)


def test_create_review_requires_separate_health_consent(client, auth_headers):
    """PIPL 第 28/29 条：就医体验属敏感个人信息，必须显式单独同意（禁止默认勾选）。"""
    hospital_id = client.get("/api/hospitals").json()["items"][0]["id"]
    response = client.post(
        f"/api/hospitals/{hospital_id}/reviews",
        headers=auth_headers,
        json={"target": "hospital", "content": "挂号到面诊等了一小时，医生把方案讲得比较清楚。"},
    )
    assert response.status_code == 400
    assert "同意" in response.json()["detail"]


def test_create_review_publishes_and_redacts_pii(client, auth_headers):
    hospital_id = client.get("/api/hospitals").json()["items"][0]["id"]
    response = client.post(
        f"/api/hospitals/{hospital_id}/reviews",
        headers=auth_headers,
        json={
            "target": "doctor",
            "doctor_name": "张医生",
            "doctor_title": "主任医师",
            "doctor_department": "皮肤科",
            "content": "张医生把光疗周期和复查时间都写下来了，有疑问可以打 13800001111 找科室。",
            "experience_scores": {"医患沟通": "satisfied", "费用与告知": "neutral"},
            "tags": ["解释耐心"],
            "health_consent": True,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["pii_redacted"] is True
    assert "13800001111" not in body["review"]["content"]
    assert "138****1111" in body["review"]["content"]
    # v3：医生称谓脱敏落库，不保存可识别真名
    assert body["review"]["doctor_name"] == "张医生（皮肤科）"
    assert body["review"]["experience_scores"] == {"医患沟通": "satisfied", "费用与告知": "neutral"}
    assert body["risk_level"] == "safe"

    # 公开列表可见（免登录即可读到），但公开层不返回旧版星级评分
    listed = client.get(f"/api/hospitals/{hospital_id}/reviews").json()
    assert listed["total"] == 1
    assert listed["items"][0]["doctor_title"] == "主任医师"
    assert listed["items"][0]["ratings"] == {}
    assert listed["items"][0]["experience_scores"]["医患沟通"] == "satisfied"


def test_short_review_returns_friendly_400(client, auth_headers):
    hospital_id = client.get("/api/hospitals").json()["items"][0]["id"]
    response = client.post(
        f"/api/hospitals/{hospital_id}/reviews",
        headers=auth_headers,
        json={"target": "hospital", "content": "太短", "health_consent": True},
    )
    assert response.status_code == 400
    assert "20" in response.json()["detail"]


def test_doctor_and_treatment_reviews_require_their_fields(client, auth_headers):
    hospital_id = client.get("/api/hospitals").json()["items"][0]["id"]
    for target, keyword in (("doctor", "医生"), ("treatment", "方案")):
        response = client.post(
            f"/api/hospitals/{hospital_id}/reviews",
            headers=auth_headers,
            json={
                "target": target,
                "content": "这家医院候诊时间不算长，医生解释得比较耐心。",
                "health_consent": True,
            },
        )
        assert response.status_code == 400
        assert keyword in response.json()["detail"]


def test_community_hospital_can_be_created_and_reviewed(client, auth_headers):
    created = client.post(
        "/api/hospitals",
        headers=auth_headers,
        json={
            "name": "某某市人民医院", "province": "浙江", "city": "杭州",
            "district": "上城区", "address": "某路 1 号", "department": "皮肤科",
        },
    )
    assert created.status_code == 201, created.text
    hospital = created.json()
    assert hospital["origin"] == "community"

    # 病友补充条目立即可被搜到（前端会标注「病友补充·待核实」）
    found = client.get("/api/hospitals", params={"q": "某某市人民医院"}).json()
    assert found["total"] == 1
    assert found["items"][0]["id"] == hospital["id"]

    reviewed = client.post(
        f"/api/hospitals/{hospital['id']}/reviews",
        headers=auth_headers,
        json={
            "target": "experience",
            "content": "第一次去挂的普通皮肤科门诊，医生建议先做光疗观察。",
            "health_consent": True,
        },
    )
    assert reviewed.status_code == 201


def test_delete_review_is_soft_and_owner_scoped(client, auth_headers, admin_headers):
    hospital_id = client.get("/api/hospitals").json()["items"][0]["id"]
    created = client.post(
        f"/api/hospitals/{hospital_id}/reviews",
        headers=auth_headers,
        json={
            "target": "hospital",
            "content": "挂号流程清楚，医生也说明了复诊时间，整体体验还行。",
            "health_consent": True,
        },
    ).json()
    review_id = created["review"]["id"]

    # 非本人（管理员也不是作者）删除 → 404，不泄露他人评价是否存在
    assert client.delete(f"/api/hospitals/reviews/{review_id}", headers=admin_headers).status_code == 404

    assert client.delete(f"/api/hospitals/reviews/{review_id}", headers=auth_headers).status_code == 204
    assert client.get(f"/api/hospitals/{hospital_id}/reviews").json()["total"] == 0


def test_admin_can_hide_community_hospital(client, admin_headers):
    created = client.post(
        "/api/hospitals",
        headers=admin_headers,
        json={"name": "测试医院", "province": "浙江", "city": "杭州"},
    ).json()

    hidden = client.post(f"/api/hospitals/admin/{created['id']}/visibility", params={"hidden": True}, headers=admin_headers)
    assert hidden.status_code == 200 and hidden.json()["status"] == "hidden"
    assert client.get(f"/api/hospitals/{created['slug']}").status_code == 404

    restored = client.post(f"/api/hospitals/admin/{created['id']}/visibility", params={"hidden": False}, headers=admin_headers)
    assert restored.status_code == 200 and restored.json()["status"] == "visible"


# ── 一期：凭证图上传 / 有用投票 / 排序 / 标签聚合 ──

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"0" * 128


def _serve(url: str) -> str:
    """把 /uploads/... 映射成前端实际请求的 /api/files/serve/... 路径。"""
    return "/api/files/serve/" + url[len("/uploads/"):]


def _publish(client, headers, hospital_id, **overrides):
    body = {
        "target": "hospital",
        "content": "挂号到面诊等了一小时，医生把方案和复查时间都写清楚了。",
        "health_consent": True,
    }
    body.update(overrides)
    response = client.post(f"/api/hospitals/{hospital_id}/reviews", headers=headers, json=body)
    assert response.status_code == 201, response.text
    return response.json()["review"]


def test_credential_image_is_private_to_author(client, auth_headers):
    """v3：凭证图不再公开 —— 公开层只给徽标，原图仅作者可读。"""
    hospital_id = client.get("/api/hospitals").json()["items"][0]["id"]
    uploaded = client.post(
        "/api/hospitals/reviews/images",
        headers=auth_headers,
        files={"image": ("receipt.png", PNG_BYTES, "image/png")},
    )
    assert uploaded.status_code == 201, uploaded.text
    url = uploaded.json()["url"]
    assert url.startswith("/uploads/hospital/")

    review = _publish(client, auth_headers, hospital_id,
                      images=[{"url": url, "label": "费用单"}], images_confirmed=True)
    # 作者视角：拿得到原图与徽标
    assert review["images"] == [{"url": url, "label": "费用单"}]
    assert review["credential_labels"] == ["费用单"]
    assert review["detail_score"] >= 1
    # 作者本人可读
    assert client.get(_serve(url), headers=auth_headers).status_code == 200

    # 公开列表（匿名）：只有徽标，没有 URL
    public = client.get(f"/api/hospitals/{hospital_id}/reviews").json()["items"][0]
    assert public["images"] == []
    assert public["credential_labels"] == ["费用单"]
    assert client.get(_serve(url)).status_code in (401, 403)


def test_upload_rejects_non_image_and_bad_label(client, auth_headers):
    bad = client.post(
        "/api/hospitals/reviews/images",
        headers=auth_headers,
        files={"image": ("receipt.png", b"<html>nope</html>", "image/png")},
    )
    assert bad.status_code == 400

    hospital_id = client.get("/api/hospitals").json()["items"][0]["id"]
    response = client.post(
        f"/api/hospitals/{hospital_id}/reviews",
        headers=auth_headers,
        json={"target": "hospital", "content": "这家医院挂号流程还算清楚，医生也说明了复诊安排。",
              "images": [{"url": "/uploads/hospital/1_a.png", "label": "病情照片"}],
              "images_confirmed": True, "health_consent": True},
    )
    assert response.status_code == 400

    # 未勾选确认 → 拒绝
    response = client.post(
        f"/api/hospitals/{hospital_id}/reviews",
        headers=auth_headers,
        json={"target": "hospital", "content": "这家医院挂号流程还算清楚，医生也说明了复诊安排。",
              "images": [{"url": "/uploads/hospital/1_a.png", "label": "费用单"}],
              "health_consent": True},
    )
    assert response.status_code == 400
    assert "确认" in response.json()["detail"]


def test_helpful_vote_endpoint_and_sort(client, auth_headers, admin_headers):
    hospital_id = client.get("/api/hospitals").json()["items"][0]["id"]
    first = _publish(client, auth_headers, hospital_id,
                     content="第一次挂专家门诊，医生把方案和复查时间都写清楚了，费用也提前说明。")
    second = _publish(client, admin_headers, hospital_id,
                      content="第二次复诊候诊比较久，不过沟通还算耐心，整体流程能接受。")

    voted = client.post(f"/api/hospitals/reviews/{first['id']}/helpful", headers=admin_headers)
    assert voted.status_code == 200
    assert voted.json() == {"review_id": first["id"], "helpful_count": 1, "is_helpful": True}

    listed = client.get(f"/api/hospitals/{hospital_id}/reviews", params={"sort": "helpful"}, headers=admin_headers).json()
    assert [item["id"] for item in listed["items"]] == [first["id"], second["id"]]
    assert listed["items"][0]["helpful_count"] == 1 and listed["items"][0]["is_helpful"] is True

    # 自己的评价不能投票
    assert client.post(f"/api/hospitals/reviews/{first['id']}/helpful", headers=auth_headers).status_code == 400
    # 取消投票
    again = client.post(f"/api/hospitals/reviews/{first['id']}/helpful", headers=admin_headers).json()
    assert again["helpful_count"] == 0 and again["is_helpful"] is False

    # 未登录不能投票
    assert client.post(f"/api/hospitals/reviews/{first['id']}/helpful").status_code in (401, 403)


def test_tag_cloud_and_invalid_sort_param(client, auth_headers):
    hospital_id = client.get("/api/hospitals").json()["items"][0]["id"]
    _publish(client, auth_headers, hospital_id, tags=["解释耐心", "费用清楚"],
             experience_scores={"医患沟通": "satisfied"})
    _publish(client, auth_headers, hospital_id, tags=["解释耐心", "候诊较久"])

    listed = client.get(f"/api/hospitals/{hospital_id}/reviews").json()
    tags = {item["tag"]: item["count"] for item in listed["summary"]["top_tags"]}
    assert tags["解释耐心"] == 2

    # 维度提及分布：含「没体验过」档；未评价的维度计数为 0
    dist = {item["dimension"]: item for item in listed["summary"]["dimension_distribution"]}
    assert len(dist) == 6
    assert dist["医患沟通"]["satisfied"] == 1
    assert dist["环境与隐私"]["total"] == 0

    assert client.get(f"/api/hospitals/{hospital_id}/reviews", params={"sort": "bogus"}).status_code == 400


# ── v3：统一评价体系与合规 ──


def test_banned_efficacy_dimension_is_rejected(client, auth_headers):
    """疗效/医术类维度一律不采集（广告法 16 条 / 医疗广告管理办法 7 条）。"""
    hospital_id = client.get("/api/hospitals").json()["items"][0]["id"]
    for payload in (
        {"experience_scores": {"疗效": "satisfied"}},
        {"tags": ["治愈率高"]},
        {"ratings": {"疗效": 5}},
    ):
        body = {
            "target": "hospital",
            "content": "这家医院挂号流程还算清楚，医生也说明了复诊安排。",
            "health_consent": True,
        }
        body.update(payload)
        response = client.post(f"/api/hospitals/{hospital_id}/reviews", headers=auth_headers, json=body)
        assert response.status_code == 400, response.text
        # 非法维度即便提交也不会被写入
    listed = client.get(f"/api/hospitals/{hospital_id}/reviews").json()
    assert listed["total"] == 0


def test_unknown_experience_dimension_and_level_are_dropped(client, auth_headers):
    hospital_id = client.get("/api/hospitals").json()["items"][0]["id"]
    review = _publish(client, auth_headers, hospital_id, experience_scores={
        "医患沟通": "satisfied", "不存在的维度": "satisfied", "费用与告知": "bogus",
    })
    assert review["experience_scores"] == {"医患沟通": "satisfied"}


def test_efficacy_claim_is_hard_blocked_with_rewrite_hint(client, auth_headers):
    """疗效夸大用语从「事后标记」升级为「发布前拦截 + 改写建议」。"""
    hospital_id = client.get("/api/hospitals").json()["items"][0]["id"]
    for content in (
        "这家医院把我根治了，白斑彻底治愈，强烈推荐这家！",
        "医生保证治好，永不复发。这家医院挂号还算方便，复诊也好约。",
    ):
        response = client.post(
            f"/api/hospitals/{hospital_id}/reviews",
            headers=auth_headers,
            json={"target": "hospital", "content": content, "health_consent": True},
        )
        assert response.status_code == 400, response.text
        assert "修改" in response.json()["detail"]
    assert client.get(f"/api/hospitals/{hospital_id}/reviews").json()["total"] == 0


def test_insult_is_blocked_and_opinion_is_allowed(client, auth_headers):
    """侮辱性言辞硬拦截；对过程的批评应放行（不压制真实体验表达）。"""
    hospital_id = client.get("/api/hospitals").json()["items"][0]["id"]

    blocked = client.post(
        f"/api/hospitals/{hospital_id}/reviews",
        headers=auth_headers,
        json={
            "target": "hospital",
            "content": "这个医生就是个骗子，无良医院，挂号等了两个小时也不给解释。",
            "health_consent": True,
        },
    )
    assert blocked.status_code == 400

    allowed = client.post(
        f"/api/hospitals/{hospital_id}/reviews",
        headers=auth_headers,
        json={
            "target": "hospital",
            "content": "候诊等了两个小时，费用里有一项自费项目事先没有说明，希望改进。",
            "health_consent": True,
        },
    )
    assert allowed.status_code == 201, allowed.text


def test_defamation_requires_cooling_confirmation(client, auth_headers):
    """结论性指控（如断言医疗事故）需要「发布前冷静确认」才可发布。"""
    hospital_id = client.get("/api/hospitals").json()["items"][0]["id"]
    body = {
        "target": "hospital",
        "content": "我觉得这家医院就是误诊，把病情耽误了，后续复查也没有安排好。",
        "health_consent": True,
    }
    first = client.post(f"/api/hospitals/{hospital_id}/reviews", headers=auth_headers, json=body)
    assert first.status_code == 400
    assert "确认" in first.json()["detail"]

    body["risk_ack"] = True
    second = client.post(f"/api/hospitals/{hospital_id}/reviews", headers=auth_headers, json=body)
    assert second.status_code == 201, second.text
    payload = second.json()
    assert payload["risk_level"] in ("watch", "restricted", "high")
    assert payload["risk_categories"]
    assert payload["author_hints"]


def test_doctor_name_is_sanitized_in_storage_and_output(client, auth_headers, db_session):
    from web.backend.database.models import HospitalReview

    hospital_id = client.get("/api/hospitals").json()["items"][0]["id"]
    review = _publish(client, auth_headers, hospital_id,
                      target="doctor", doctor_name="张三丰主任医师", doctor_department="皮肤科",
                      content="张主任把光疗周期和复查时间都写清楚了，问题也都回应了。")
    assert review["doctor_name"] == "张主任（皮肤科）"

    row = db_session.query(HospitalReview).filter(HospitalReview.id == review["id"]).one()
    assert row.doctor_name == "张主任（皮肤科）"
    assert "张三丰" not in (row.doctor_name or "")


def test_watch_level_review_is_aggregated_after_cooldown(client, auth_headers, db_session):
    """聚合冷处理：只延迟进入聚合，不延迟发布。"""
    from web.backend.database.models import HospitalReview

    hospital_id = client.get("/api/hospitals").json()["items"][0]["id"]
    review = _publish(client, auth_headers, hospital_id,
                      tags=["候诊较久"],
                      content="医生就是误诊，候诊也很久，费用没有提前说明，后续复查安排也不清楚。",
                      risk_ack=True)
    row = db_session.query(HospitalReview).filter(HospitalReview.id == review["id"]).one()
    assert row.aggregate_after is not None

    # 发布后立即可见（不延迟发布）
    listed = client.get(f"/api/hospitals/{hospital_id}/reviews").json()
    assert listed["total"] == 1
    # 但冷处理期内不进标签聚合
    assert listed["summary"]["top_tags"] == []

    # 冷处理结束后进入聚合
    row.aggregate_after = None
    db_session.commit()
    listed2 = client.get(f"/api/hospitals/{hospital_id}/reviews").json()
    assert {t["tag"] for t in listed2["summary"]["top_tags"]} == {"候诊较久"}


# ── v3：举报 ──


def test_report_review_is_idempotent_and_requires_login(client, auth_headers, admin_headers):
    hospital_id = client.get("/api/hospitals").json()["items"][0]["id"]
    review = _publish(client, auth_headers, hospital_id)

    assert client.post(f"/api/hospitals/reviews/{review['id']}/report",
                       json={"reason_code": "abuse"}).status_code in (401, 403)

    first = client.post(f"/api/hospitals/reviews/{review['id']}/report",
                        json={"reason_code": "abuse", "detail": "含人身攻击"},
                        headers=admin_headers)
    assert first.status_code == 201, first.text
    assert first.json()["report_count"] == 1

    # 同一人重复举报 → 400（幂等）
    again = client.post(f"/api/hospitals/reviews/{review['id']}/report",
                        json={"reason_code": "fake"}, headers=admin_headers)
    assert again.status_code == 400

    # 不能举报自己的评价
    own = client.post(f"/api/hospitals/reviews/{review['id']}/report",
                      json={"reason_code": "fake"}, headers=auth_headers)
    assert own.status_code == 400

    # 非法原因码
    assert client.post(f"/api/hospitals/reviews/{review['id']}/report",
                       json={"reason_code": "bogus"}, headers=admin_headers).status_code == 400


def test_reports_over_threshold_restrict_review(client, auth_headers, admin_headers, db_session):
    """举报达阈值 → 自动 restricted：仍公开可见，但不进聚合、排序垫底。"""
    from web.backend.database.models import HospitalReview, User
    from web.backend.services.auth import create_access_token

    hospital_id = client.get("/api/hospitals").json()["items"][0]["id"]
    review = _publish(client, auth_headers, hospital_id, tags=["解释耐心"])

    # 造 3 个举报人
    for index in range(3):
        user = User(username=f"reporter{index}", email=f"reporter{index}@example.com",
                    hashed_password="x", user_status="normal", token_version=0)
        db_session.add(user)
        db_session.commit()
        headers = {"Authorization": f"Bearer {create_access_token({'sub': user.username})}"}
        response = client.post(f"/api/hospitals/reviews/{review['id']}/report",
                               json={"reason_code": "fake"}, headers=headers)
        assert response.status_code == 201, response.text

    row = db_session.query(HospitalReview).filter(HospitalReview.id == review["id"]).one()
    assert row.moderation_status == "restricted"

    listed = client.get(f"/api/hospitals/{hospital_id}/reviews").json()
    assert listed["total"] == 1            # 仍然公开可见
    assert listed["summary"]["top_tags"] == []   # 不进聚合
    assert listed["items"][0]["restricted_reason"] is None  # 受限原因仅作者可见


# ── v3：申诉 ──


def test_appeal_is_public_and_gets_working_day_deadline(client, auth_headers):
    hospital_id = client.get("/api/hospitals").json()["items"][0]["id"]
    review = _publish(client, auth_headers, hospital_id)

    # 无需登录即可提交（机构申诉不应被登录门槛挡住）
    response = client.post("/api/hospitals/reviews/appeals", json={
        "review_id": review["id"], "claimant_type": "hospital",
        "claimant_name": "某某医院医患办", "contact": "010-00000000",
        "reason": "该评价描述的时间与事实不符，我们已调取当日挂号记录，申请复核。",
    })
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "pending"
    assert body["due_at"] is not None
    assert body["overdue"] is False

    # 校验：理由过短 / 缺联系方式
    bad = client.post("/api/hospitals/reviews/appeals", json={
        "review_id": review["id"], "claimant_type": "hospital",
        "claimant_name": "某医院", "contact": "010-00000000", "reason": "不服",
    })
    assert bad.status_code == 400
    missing_contact = client.post("/api/hospitals/reviews/appeals", json={
        "review_id": review["id"], "claimant_type": "doctor",
        "claimant_name": "张医生", "contact": "",
        "reason": "该评价所述情况与当日诊疗记录不符，申请复核并更正。",
    })
    assert missing_contact.status_code == 400


def test_admin_can_resolve_appeal_and_hide_review(client, auth_headers, admin_headers, db_session):
    from web.backend.database.models import HospitalReview

    hospital_id = client.get("/api/hospitals").json()["items"][0]["id"]
    review = _publish(client, auth_headers, hospital_id)
    appeal = client.post("/api/hospitals/reviews/appeals", json={
        "review_id": review["id"], "claimant_type": "hospital",
        "claimant_name": "某某医院", "contact": "010-00000000",
        "reason": "该评价所述就诊时间与我院记录不符，申请复核并更正。",
    }).json()

    assert client.get("/api/hospitals/admin/risk").status_code in (401, 403)

    resolved = client.post(
        f"/api/hospitals/admin/appeals/{appeal['id']}/resolve",
        params={"accepted": True, "action": "hide", "resolution": "经核实与记录不符"},
        headers=admin_headers,
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["status"] == "accepted"
    assert resolved.json()["resolved_action"] == "hide"

    row = db_session.query(HospitalReview).filter(HospitalReview.id == review["id"]).one()
    assert row.moderation_status == "blocked"
    # 下架后公开列表不再出现
    assert client.get(f"/api/hospitals/{hospital_id}/reviews").json()["total"] == 0


def test_admin_risk_board_reports_pending_items(client, auth_headers, admin_headers):
    hospital_id = client.get("/api/hospitals").json()["items"][0]["id"]
    review = _publish(client, auth_headers, hospital_id)
    client.post(f"/api/hospitals/reviews/{review['id']}/report",
                json={"reason_code": "abuse"}, headers=admin_headers)

    board = client.get("/api/hospitals/admin/risk", headers=admin_headers)
    assert board.status_code == 200, board.text
    body = board.json()
    assert body["pending_reports"] >= 1
    assert body["total"] >= 1
    assert any(item["review_id"] == review["id"] for item in body["items"])
    assert any(item["report_count"] >= 1 for item in body["items"])
