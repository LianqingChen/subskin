"""医评风控规则引擎（review_risk）单元测试。

覆盖：统一评分体系常量与疗效维度黑名单、文本风险扫描与分档、医生称谓脱敏、
维度档位清洗与分布聚合、聚合冷处理策略。
"""

from __future__ import annotations

import pytest

from web.backend.services.review_risk import (
    BANNED_DIMENSIONS,
    EXPERIENCE_DIMENSIONS,
    EXPERIENCE_LEVELS,
    aggregate_delay_seconds,
    clean_experience_scores,
    dimension_distribution,
    level_for_score,
    moderation_status_for_level,
    sanitize_doctor_name,
    score_review,
)


# ── 统一评价体系 ──────────────────────────────────────────────────────────


def test_experience_dimensions_contain_no_efficacy_dimension():
    assert len(EXPERIENCE_DIMENSIONS) == 6
    for banned in BANNED_DIMENSIONS:
        for dim in EXPERIENCE_DIMENSIONS:
            assert banned not in dim, f"体验维度不应包含疗效类词「{banned}」"


def test_experience_levels_include_not_applicable_bucket():
    assert set(EXPERIENCE_LEVELS) == {"satisfied", "neutral", "unsatisfied", "na"}


def test_clean_experience_scores_rejects_banned_and_unknown():
    assert clean_experience_scores({"医患沟通": "satisfied"}) == {"医患沟通": "satisfied"}
    # 黑名单维度与非法档位一律剔除
    assert clean_experience_scores({"疗效": "satisfied"}) == {}
    assert clean_experience_scores({"医患沟通": "bogus"}) == {}
    assert clean_experience_scores({"不存在的维度": "satisfied"}) == {}
    assert clean_experience_scores(None) == {}
    assert clean_experience_scores("nope") == {}


def test_dimension_distribution_counts_all_four_levels():
    rows = [
        {"医患沟通": "satisfied", "费用与告知": "unsatisfied"},
        {"医患沟通": "neutral"},
        {"医患沟通": "na"},
        {"疗効": "satisfied"},  # 非法维度不计入
        None,
    ]
    dist = {item["dimension"]: item for item in dimension_distribution(rows)}
    assert len(dist) == 6
    talk = dist["医患沟通"]
    assert (talk["satisfied"], talk["neutral"], talk["na"], talk["total"]) == (1, 1, 1, 3)
    assert dist["环境与隐私"]["total"] == 0


# ── 文本风险扫描 ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("text", [
    "这家医院把我根治了，白斑彻底治愈。",
    "医生保证治好，永不复发，强烈推荐这家！",
    "都去这家，别去别家，包治百病。",
])
def test_promotion_terms_are_hard_blocked(text):
    result = score_review(text)
    assert result.blocked is True
    assert "疗效夸大" in result.categories
    assert result.hints, "硬拦截必须给出改写建议"


@pytest.mark.parametrize("text", [
    "这个医生就是个骗子，无良医院。",
    "黑心医院，谋财害命。",
    "庸医，没医德。",
])
def test_insults_are_hard_blocked(text):
    result = score_review(text)
    assert result.blocked is True
    assert "侮辱性言辞" in result.categories


def test_debunked_opinion_on_service_is_allowed():
    """对流程/费用的批评必须放行 —— 风控是帮用户写好，不是封口。"""
    result = score_review(
        "候诊等了两个小时，费用里有一项自费项目事先没有说明，复诊也要重新排队挂号。"
    )
    assert result.level == "safe"
    assert result.blocked is False
    assert result.score < 30


def test_contact_info_does_not_gate_publishing():
    """联系方式会被自动脱敏，不应因此把正常评价推进冷静确认。"""
    result = score_review("有问题可以打 13800001111 找科室，挂号流程挺清楚的。")
    assert result.level == "safe"
    assert result.blocked is False


def test_soliciting_private_contact_is_blocked():
    result = score_review("想交流的加我微信，私聊发你费用清单。")
    assert result.blocked is True
    assert "引流广告" in result.categories


def test_defamation_type_claims_trigger_cooling_not_block():
    result = score_review("我觉得这家医院就是误诊，把病情耽误了。")
    assert result.blocked is False
    assert result.level in ("watch", "restricted", "high")
    assert "断言性指控" in result.categories


def test_organized_action_is_flagged():
    result = score_review("大家一起建个维权群，曝光这家医院。")
    assert result.blocked is False
    assert "组织化维权" in result.categories
    assert result.level != "safe"


def test_other_patient_record_number_is_flagged():
    result = score_review("我的病历号 12345678，医生说复诊要带。")
    assert result.level != "safe"
    assert "他人病历信息" in result.categories


def test_hearsay_alone_stays_safe():
    result = score_review("听说这家医院皮肤科不错，我自己没去过。")
    assert result.level == "safe"


def test_doctor_name_plus_insult_is_named_accusation():
    result = score_review("这个医生就是个骗子，挂号乱收费。", doctor_name="张医生")
    assert "指名指控" in result.categories
    assert result.blocked is True


def test_banned_tag_is_blocked():
    result = score_review("整体还行，挂号比较方便。", tags=["治愈率高"])
    assert result.blocked is True
    assert "疗效夸大" in result.categories


def test_empty_text_is_safe():
    result = score_review("")
    assert result.score == 0 and result.level == "safe"


# ── 评分 → 处置映射 ───────────────────────────────────────────────────────


@pytest.mark.parametrize("score,level", [(0, "safe"), (29, "safe"), (30, "watch"),
                                         (59, "watch"), (60, "restricted"),
                                         (79, "restricted"), (80, "high"), (100, "high")])
def test_level_mapping(score, level):
    assert level_for_score(score) == level


def test_moderation_status_mapping():
    assert moderation_status_for_level("safe") == "approved"
    assert moderation_status_for_level("watch") == "flagged"
    assert moderation_status_for_level("restricted") == "restricted"
    assert moderation_status_for_level("high") == "blocked"


def test_aggregate_delay_only_applies_to_watch():
    """safe 立即可聚合（否则正常用户每次都要等 30 分钟）；
    restricted/high 本来就不进聚合，无需延迟；只有 watch 需要复核窗口。"""
    assert aggregate_delay_seconds("safe") == 0
    assert aggregate_delay_seconds("watch") == 1800
    assert aggregate_delay_seconds("restricted") == 0
    assert aggregate_delay_seconds("high") == 0


# ── 医生称谓脱敏 ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("raw,expected", [
    ("张三", "张医生"),
    ("张三医生", "张医生"),
    ("张医生", "张医生"),
    ("李四大夫", "李医生"),
    ("王五主任医师", "王主任"),
    ("赵六教授", "赵教授"),
    ("", None),
    (None, None),
])
def test_sanitize_doctor_name(raw, expected):
    assert sanitize_doctor_name(raw) == expected


def test_sanitize_doctor_name_keeps_department_but_not_full_name():
    result = sanitize_doctor_name("张三丰主任医师", "皮肤科")
    assert result == "张主任（皮肤科）"
    assert "三丰" not in result


def test_sanitize_doctor_name_falls_back_to_placeholder():
    assert sanitize_doctor_name("!!!") == "某医生"
