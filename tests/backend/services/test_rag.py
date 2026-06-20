# pyright: reportAny=false, reportPrivateUsage=false, reportUnknownVariableType=false

"""Tests for RAG service helpers."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from web.backend.services.rag import _detect_report_type, _interpret_report


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
        "web.backend.services.rag._get_llm_config", return_value={"provider": "none"}
    ):
        result = _interpret_report("TSH 5.2 uIU/mL", "帮我看看甲状腺报告")

    assert result == {
        "report_type": "thyroid",
        "risk_level": "amber",
        "summary": "AI服务未配置，暂时无法自动解读报告。建议结合原始报告中的异常箭头、参考范围和医生意见综合判断。",
        "key_findings": [],
        "recommendations": ["若报告存在异常箭头或超出参考范围，请咨询医生进一步判断。"],
        "disclaimer": "⚠️ 以上解读由AI生成，仅供参考，不构成医疗诊断。请咨询医生获取专业意见。",
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
        "disclaimer": "⚠️ 以上解读由AI生成，仅供参考，不构成医疗诊断。请咨询医生获取专业意见。",
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
            "web.backend.services.rag._get_llm_config",
            return_value={
                "provider": "dashscope",
                "api_key": "test-key",
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
