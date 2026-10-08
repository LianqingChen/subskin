# pyright: reportAny=false, reportPrivateUsage=false, reportUnknownVariableType=false

"""Tests for RAG service helpers."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from web.backend.database.models import (
    DiaryEntry,
    MedicationReminder,
    PatientProfile,
    TreatmentEvent,
    User,
)
from web.backend.services.rag import (
    _build_butler_prompt,
    _build_knowledge_prompt,
    _build_llm_messages,
    _detect_report_type,
    _interpret_report,
    _mode_temperature,
    build_user_context,
    resolve_site_navigation,
    SITE_ROUTE_MAP,
)


def test_detect_report_type_recognizes_supported_reports():
    assert _detect_report_type("血红蛋白 110 g/L, WBC 6.2, PLT 210") == "blood_routine"
    assert _detect_report_type("ALT 65 U/L, AST 41 U/L, 胆红素正常") == "liver_function"
    assert (
        _detect_report_type("TSH 5.2, T4 正常, 甲状腺过氧化物酶抗体偏高") == "thyroid"
    )
    assert _detect_report_type("ANA 阳性, IgG 升高, 补体 C3 偏低") == "immunology"
    assert _detect_report_type("尿常规未见明显异常") == "general"


def test_interpret_report_returns_structured_fallback_when_llm_unavailable():
    with patch(
        "web.backend.services.rag.get_llm_config", return_value={"provider": "none"}
    ):
        result = _interpret_report("TSH 5.2 uIU/mL", "帮我看看甲状腺报告")

    assert result == {
        "report_type": "thyroid",
        "risk_level": "amber",
        "summary": "AI服务未配置，暂时无法自动解读报告。建议结合原始报告中的异常箭头、参考范围和医生意见综合判断。",
        "key_findings": [],
        "recommendations": ["若报告存在异常箭头或超出参考范围，请咨询医生进一步判断。"],
        "disclaimer": "以上解读由AI生成，仅供参考，不构成医疗诊断。请咨询医生获取专业意见。",
    }


def test_interpret_report_parses_structured_llm_json():
    response_content = {
        "report_type": "thyroid",
        "risk_level": "amber",
        "summary": "甲状腺相关指标有轻度异常，建议结合症状复查。",
        "key_findings": [
            {
                "name": "TSH",
                "value": "5.2",
                "reference": "0.27-4.2",
                "status": "high",
                "risk": "amber",
                "explanation": "提示甲状腺调节信号偏高，可能需要结合FT4和抗体进一步判断。",
            }
        ],
        "recommendations": ["1-3个月内复查甲状腺功能。"],
        "disclaimer": "以上解读由AI生成，仅供参考，不构成医疗诊断。请咨询医生获取专业意见。",
    }
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=str(response_content).replace("'", '"'))
            )
        ]
    )

    with (
        patch(
            "web.backend.services.rag.get_llm_config",
            return_value={
                "provider": "dashscope",
                "api_key": "test-key",  # pragma: allowlist secret
                "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "chat_model": "qwen-plus",
            },
        ),
        patch("web.backend.services.rag.openai.OpenAI", return_value=mock_client),
    ):
        result = _interpret_report("TSH 5.2 uIU/mL", "帮我看看甲状腺报告")

    assert result["report_type"] == "thyroid"
    assert result["risk_level"] == "amber"
    assert result["summary"] == "甲状腺相关指标有轻度异常，建议结合症状复查。"
    assert result["key_findings"][0]["name"] == "TSH"
    assert result["recommendations"] == ["1-3个月内复查甲状腺功能。"]
    messages = mock_client.chat.completions.create.call_args.kwargs["messages"]
    assert messages[0]["role"] == "system"
    assert "甲状腺" in messages[0]["content"]
    assert "JSON" in messages[0]["content"]


# ── 用户个人上下文（任务 #5：AI问答个性化） ──


def _mock_user_context_db(
    profile=None, entries=None, reminders=None, events=None
):
    """构造 build_user_context 所需的 mock db（只读查询链）。"""

    def make_chain(first_result=None, all_result=None):
        chain = MagicMock()
        chain.filter.return_value = chain
        chain.order_by.return_value = chain
        chain.limit.return_value = chain
        chain.first.return_value = first_result
        chain.all.return_value = all_result if all_result is not None else []
        return chain

    chains = {
        User: make_chain(
            first_result=SimpleNamespace(default_diary_profile_id=None)
        ),
        PatientProfile: make_chain(first_result=profile),
        DiaryEntry: make_chain(all_result=entries or []),
        MedicationReminder: make_chain(all_result=reminders or []),
        TreatmentEvent: make_chain(all_result=events or []),
    }
    db = MagicMock()
    db.query.side_effect = lambda model: chains[model]
    return db


def test_build_user_context_returns_empty_for_guest():
    assert build_user_context(MagicMock(), None) == ""


def test_build_user_context_returns_empty_when_no_data():
    db = _mock_user_context_db()
    assert build_user_context(db, user_id=1) == ""


def test_build_user_context_aggregates_profile_diary_and_medication():
    profile = SimpleNamespace(
        name="小白",
        relationship="本人",
        gender="男",
        diagnosis_date=date(2023, 5, 1),
        vitiligo_type="节段型",
        notes="手臂有白斑",
    )
    entries = [
        SimpleNamespace(
            entry_date=date.today(),
            ai_summary="今天状态稳定，心情不错",
            raw_text="原始文本",
            skin_condition="stable",
        ),
        SimpleNamespace(
            entry_date=date.today(),
            ai_summary=None,
            raw_text="最近睡眠不太好",
            skin_condition=None,
        ),
    ]
    reminders = [
        SimpleNamespace(
            medication_name="他克莫司软膏",
            dosage="0.1%",
            frequency="twice_daily",
        )
    ]
    db = _mock_user_context_db(
        profile=profile, entries=entries, reminders=reminders
    )

    context = build_user_context(db, user_id=1)

    assert context
    assert len(context) <= 500
    assert "【病情档案】" in context
    assert "节段型" in context
    assert "病程" in context
    assert "【近14天日记摘要】" in context
    assert "今天状态稳定" in context
    assert "最近睡眠不太好" in context  # ai_summary 缺失时回退 raw_text
    assert "【正在使用的药物】" in context
    assert "他克莫司软膏" in context
    assert "每日两次" in context
    assert "【近期治疗记录】" not in context  # 无治疗事件则跳过


def test_build_llm_messages_injects_user_context_section():
    messages = _build_llm_messages(
        "我的病型适合光疗吗？", docs=[], user_context="【病情档案】病型：节段型"
    )
    system = messages[0]["content"]
    assert messages[0]["role"] == "system"
    assert "## 该用户的个人情况（仅供参考，用户已授权）" in system
    assert "病型：节段型" in system
    assert "不得替代医生诊断" in system


def test_build_llm_messages_without_context_keeps_guest_prompt_unchanged():
    base = _build_llm_messages("什么是白癜风？", docs=[])
    with_ctx_none = _build_llm_messages("什么是白癜风？", docs=[], user_context=None)
    with_ctx_empty = _build_llm_messages("什么是白癜风？", docs=[], user_context="")
    assert base[0]["content"] == with_ctx_none[0]["content"]
    assert base[0]["content"] == with_ctx_empty[0]["content"]
    assert "## 该用户的个人情况" not in base[0]["content"]


def test_build_llm_messages_counseling_mode_ignores_user_context():
    messages = _build_llm_messages(
        "最近心情很差", docs=[], mode="counseling", user_context="【病情档案】…"
    )
    assert "## 该用户的个人情况" not in messages[0]["content"]


def test_knowledge_prompt_authorizes_personalization_with_safety_constraints():
    prompt = _build_knowledge_prompt()
    # 新增：授权引用本人记录 + 隐私约束
    assert "已获授权" in prompt
    assert "不得向第三方泄露" in prompt
    assert "仍以医学知识库为主要依据" in prompt
    # 旧的全盘禁止表述已移除
    assert "任何涉及个人信息的内容，你都不可以查询、透露或讨论" not in prompt
    # 原有安全约束保持不变
    assert "拒绝诊断" in prompt
    assert "不构成医疗诊断建议" in prompt



# ── 小白管家（butler mode）──


def test_butler_prompt_contains_safety_sections():
    prompt = _build_butler_prompt()
    # 受控执行
    assert "行动卡片" in prompt
    assert "绝不静默保存" in prompt
    # 个人隐私（含本人 PII 不回显）
    assert "个人中心" in prompt
    assert "为保护你的隐私" in prompt
    # 政治回避
    assert "政治" in prompt
    assert "一律不讨论" in prompt
    # 危机干预
    assert "400-161-9995" in prompt


def test_butler_prompt_navigation_table_has_no_stale_routes():
    prompt = _build_butler_prompt()
    # IM 与百科已下线，导航表不得再引用失效路由
    assert "/messages" not in prompt
    assert "/contacts" not in prompt
    assert "/encyclopedia" not in prompt
    # 现有路由与当前导航命名
    assert "/assessment" in prompt
    assert "/community" in prompt
    assert "/profile" in prompt
    assert "分享" in prompt
    assert "手帐" in prompt
    # 已下线模块只能以"如实告知"的说明出现
    assert "小白百科" not in prompt.replace("小白百科：已下线", "")


def test_build_llm_messages_butler_mode_uses_butler_prompt_and_docs():
    doc = SimpleNamespace(title="白癜风指南", content="NB-UVB 是一线光疗方案", source_url="")
    messages = _build_llm_messages("光疗怎么做？", docs=[doc], mode="butler")
    assert messages[0]["role"] == "system"
    assert "小白管家" in messages[0]["content"]
    assert "参考资料" in messages[-1]["content"]
    assert "NB-UVB" in messages[-1]["content"]


def test_build_llm_messages_butler_mode_injects_user_context():
    messages = _build_llm_messages(
        "我的情况适合光疗吗？",
        docs=[],
        mode="butler",
        user_context="【病情档案】病型：节段型",
    )
    system = messages[0]["content"]
    assert "## 该用户的个人情况（仅供参考，用户已授权）" in system
    # 管家模式下额外强调不复述隐私字段
    assert "手机号" in system


def test_mode_temperature_butler_between_knowledge_and_counseling():
    assert _mode_temperature("knowledge") == 0.3
    assert _mode_temperature(None) == 0.3
    assert _mode_temperature("butler") == 0.5
    assert _mode_temperature("counseling") == 0.7


def test_resolve_site_navigation_matches_assessment_and_profile():
    navs = resolve_site_navigation("怎么评估白斑严重程度")
    assert navs
    assert navs[0]["label"] == "手帐"
    assert navs[0]["path"] == "/assessment"

    navs = resolve_site_navigation("我的手机号在哪里改")
    assert navs
    assert any(n["path"] == "/profile" for n in navs)


def test_resolve_site_navigation_caps_at_three_and_dedupes():
    # 同时命中多个模块关键词时最多 3 条
    navs = resolve_site_navigation("怎么测评、怎么看白斑报告、怎么发帖到社区、看百科")
    assert len(navs) <= 3
    labels = [n["label"] for n in navs]
    assert len(labels) == len(set(labels))


def test_resolve_site_navigation_returns_empty_for_unrelated_question():
    assert resolve_site_navigation("今天天气怎么样") == []


# ── 站点模块清单与网站导航保持同步（site-modules.json）──

# 与 web/app/src/router/index.ts 及 BottomNav/AppHeader 对应的合法路径前缀
_KNOWN_ROUTE_PREFIXES = ("/", "/assessment", "/community", "/profile")


def test_site_route_map_only_contains_live_routes_and_current_names():
    labels = {m["label"] for m in SITE_ROUTE_MAP}
    paths = {m["path"].split("?")[0] for m in SITE_ROUTE_MAP}
    # 当前导航命名（与 BottomNav 一致）
    assert {"问答", "手帐", "分享", "个人中心"} <= labels
    # 旧命名不得再作为在线模块出现
    assert not labels & {"小白助手", "小白追踪", "小白社区", "小白百科", "白友圈"}
    # 已下线路由不得出现
    assert "/encyclopedia" not in paths
    assert "/messages" not in paths
    assert "/contacts" not in paths
    # 所有路径必须是真实存在的路由
    for path in paths:
        assert any(path == p or path.startswith(p.rstrip("/") + "/") for p in _KNOWN_ROUTE_PREFIXES), path


def test_resolve_site_navigation_maps_legacy_names_to_current_modules():
    # 用户用旧名提问时仍能导航到正确的当前模块
    navs = resolve_site_navigation("小白追踪在哪里")
    assert navs and navs[0]["path"] == "/assessment"
    navs = resolve_site_navigation("怎么去小白社区发帖")
    assert navs and any(n["path"] == "/community" for n in navs)


def test_butler_prompt_offline_module_note_present():
    prompt = _build_butler_prompt()
    assert "已下线" in prompt
