"""Tests for the OpenAI-powered medical paper summarizer."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from openai import APIConnectionError, APITimeoutError, RateLimitError

from src.processors.summarizer import _SYSTEM_PROMPT, Summarizer, SummarizerError
from src.utils.cache import Cache
from src.utils.rate_limiter import RateLimiter

_TEST_API_KEY = "sk-test-key-for-unit-tests"

_SAMPLE_ABSTRACT = (
    "This randomized controlled trial evaluated the efficacy of ruxolitinib "
    "cream 1.5% in patients with nonsegmental vitiligo. After 52 weeks, "
    "patients treated with ruxolitinib achieved significantly greater "
    "repigmentation compared to vehicle control (p<0.001). The treatment "
    "was well-tolerated with minimal side effects."
)

_SAMPLE_SUMMARY = (
    "一项随机对照试验评估了芦可替尼乳膏对非节段型白癜风患者的疗效。"
    "经过52周治疗后，使用芦可替尼的患者复色效果显著优于对照组。"
    "该治疗耐受性良好，副作用较少。\n\n"
    "以上内容仅供科普参考，不构成医疗建议。具体治疗方案请咨询专业医生。"
)


def _make_mock_response(content: str = _SAMPLE_SUMMARY) -> MagicMock:
    message = MagicMock()
    message.content = content

    choice = MagicMock()
    choice.message = message

    response = MagicMock()
    response.choices = [choice]
    return response


def _make_empty_response() -> MagicMock:
    response = MagicMock()
    response.choices = []
    return response


def _make_summarizer(
    cache: Cache | None = None,
    rate_limiter: RateLimiter | None = None,
    max_retries: int = 3,
) -> Summarizer:
    return Summarizer(
        api_key=_TEST_API_KEY,
        cache=cache,
        rate_limiter=rate_limiter or RateLimiter(1000),
        max_retries=max_retries,
    )


class TestSummarizerInit:
    def test_raises_without_api_key(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="API key is required"):
                Summarizer()

    def test_uses_env_api_key(self) -> None:
        with patch.dict("os.environ", {"OPENAI_API_KEY": _TEST_API_KEY}):
            s = Summarizer(rate_limiter=RateLimiter(1000))
            assert s._model == "gpt-3.5-turbo"

    def test_explicit_key_overrides_env(self) -> None:
        with patch.dict("os.environ", {"OPENAI_API_KEY": "env-key"}):
            s = Summarizer(api_key="explicit-key", rate_limiter=RateLimiter(1000))
            assert s._client.api_key == "explicit-key"

    def test_custom_model(self) -> None:
        s = Summarizer(
            api_key=_TEST_API_KEY,
            model="gpt-4",
            rate_limiter=RateLimiter(1000),
        )
        assert s._model == "gpt-4"


class TestSummarize:
    @patch("src.processors.summarizer.OpenAI")
    def test_returns_summary(self, mock_openai_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_response()
        mock_openai_cls.return_value = mock_client

        s = _make_summarizer()
        s._client = mock_client

        result = s.summarize(_SAMPLE_ABSTRACT)

        assert result == _SAMPLE_SUMMARY
        mock_client.chat.completions.create.assert_called_once()

    @patch("src.processors.summarizer.OpenAI")
    def test_prompt_contains_abstract(self, mock_openai_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_response()
        mock_openai_cls.return_value = mock_client

        s = _make_summarizer()
        s._client = mock_client
        s.summarize(_SAMPLE_ABSTRACT)

        call_kwargs = mock_client.chat.completions.create.call_args
        messages = call_kwargs.kwargs["messages"]

        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == _SYSTEM_PROMPT
        assert messages[1]["role"] == "user"
        assert _SAMPLE_ABSTRACT in messages[1]["content"]

    def test_empty_abstract_raises(self) -> None:
        s = _make_summarizer()
        with pytest.raises(ValueError, match="empty"):
            s.summarize("")

    def test_whitespace_abstract_raises(self) -> None:
        s = _make_summarizer()
        with pytest.raises(ValueError, match="empty"):
            s.summarize("   \n\t  ")

    @patch("src.processors.summarizer.OpenAI")
    def test_strips_whitespace_from_abstract(
        self, mock_openai_cls: MagicMock
    ) -> None:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_response()
        mock_openai_cls.return_value = mock_client

        s = _make_summarizer()
        s._client = mock_client
        s.summarize(f"  {_SAMPLE_ABSTRACT}  ")

        call_kwargs = mock_client.chat.completions.create.call_args
        user_content = call_kwargs.kwargs["messages"][1]["content"]
        assert _SAMPLE_ABSTRACT in user_content
        assert "  " + _SAMPLE_ABSTRACT not in user_content


class TestCaching:
    @patch("src.processors.summarizer.OpenAI")
    def test_cache_miss_calls_api(self, mock_openai_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_response()
        mock_openai_cls.return_value = mock_client

        cache = Cache()
        s = _make_summarizer(cache=cache)
        s._client = mock_client

        result = s.summarize(_SAMPLE_ABSTRACT)

        assert result == _SAMPLE_SUMMARY
        mock_client.chat.completions.create.assert_called_once()

    @patch("src.processors.summarizer.OpenAI")
    def test_cache_hit_skips_api(self, mock_openai_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_response()
        mock_openai_cls.return_value = mock_client

        cache = Cache()
        s = _make_summarizer(cache=cache)
        s._client = mock_client

        first = s.summarize(_SAMPLE_ABSTRACT)
        second = s.summarize(_SAMPLE_ABSTRACT)

        assert first == second == _SAMPLE_SUMMARY
        mock_client.chat.completions.create.assert_called_once()

    @patch("src.processors.summarizer.OpenAI")
    def test_different_abstracts_cached_separately(
        self, mock_openai_cls: MagicMock
    ) -> None:
        other_summary = "另一篇论文的摘要。"
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [
            _make_mock_response(_SAMPLE_SUMMARY),
            _make_mock_response(other_summary),
        ]
        mock_openai_cls.return_value = mock_client

        cache = Cache()
        s = _make_summarizer(cache=cache)
        s._client = mock_client

        r1 = s.summarize(_SAMPLE_ABSTRACT)
        r2 = s.summarize("A different abstract about phototherapy.")

        assert r1 == _SAMPLE_SUMMARY
        assert r2 == other_summary
        assert mock_client.chat.completions.create.call_count == 2

    @patch("src.processors.summarizer.OpenAI")
    def test_no_cache_still_works(self, mock_openai_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_response()
        mock_openai_cls.return_value = mock_client

        s = _make_summarizer(cache=None)
        s._client = mock_client

        result = s.summarize(_SAMPLE_ABSTRACT)
        assert result == _SAMPLE_SUMMARY


class TestRateLimiting:
    @patch("src.processors.summarizer.OpenAI")
    def test_acquire_called_before_api(self, mock_openai_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_response()
        mock_openai_cls.return_value = mock_client

        limiter = MagicMock(spec=RateLimiter)

        s = _make_summarizer(rate_limiter=limiter)
        s._client = mock_client
        s.summarize(_SAMPLE_ABSTRACT)

        limiter.acquire.assert_called_once()

    @patch("src.processors.summarizer.OpenAI")
    def test_cache_hit_skips_rate_limit(self, mock_openai_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_response()
        mock_openai_cls.return_value = mock_client

        cache = Cache()
        key = Summarizer._cache_key(_SAMPLE_ABSTRACT)
        cache.set(key, _SAMPLE_SUMMARY, ttl=3600)

        limiter = MagicMock(spec=RateLimiter)

        s = _make_summarizer(cache=cache, rate_limiter=limiter)
        s._client = mock_client
        s.summarize(_SAMPLE_ABSTRACT)

        limiter.acquire.assert_not_called()
        mock_client.chat.completions.create.assert_not_called()


class TestRetryLogic:
    @patch("src.processors.summarizer.time.sleep")
    @patch("src.processors.summarizer.OpenAI")
    def test_retries_on_connection_error(
        self, mock_openai_cls: MagicMock, mock_sleep: MagicMock
    ) -> None:
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [
            APIConnectionError(request=MagicMock()),
            _make_mock_response(),
        ]
        mock_openai_cls.return_value = mock_client

        s = _make_summarizer(max_retries=3)
        s._client = mock_client

        result = s.summarize(_SAMPLE_ABSTRACT)

        assert result == _SAMPLE_SUMMARY
        assert mock_client.chat.completions.create.call_count == 2

    @patch("src.processors.summarizer.time.sleep")
    @patch("src.processors.summarizer.OpenAI")
    def test_retries_on_timeout_error(
        self, mock_openai_cls: MagicMock, mock_sleep: MagicMock
    ) -> None:
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [
            APITimeoutError(request=MagicMock()),
            _make_mock_response(),
        ]
        mock_openai_cls.return_value = mock_client

        s = _make_summarizer(max_retries=3)
        s._client = mock_client

        result = s.summarize(_SAMPLE_ABSTRACT)
        assert result == _SAMPLE_SUMMARY

    @patch("src.processors.summarizer.time.sleep")
    @patch("src.processors.summarizer.OpenAI")
    def test_retries_on_rate_limit_error(
        self, mock_openai_cls: MagicMock, mock_sleep: MagicMock
    ) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {}

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [
            RateLimitError(
                message="Rate limit exceeded",
                response=mock_response,
                body=None,
            ),
            _make_mock_response(),
        ]
        mock_openai_cls.return_value = mock_client

        s = _make_summarizer(max_retries=3)
        s._client = mock_client

        result = s.summarize(_SAMPLE_ABSTRACT)
        assert result == _SAMPLE_SUMMARY

    @patch("src.processors.summarizer.time.sleep")
    @patch("src.processors.summarizer.OpenAI")
    def test_raises_after_all_retries_exhausted(
        self, mock_openai_cls: MagicMock, mock_sleep: MagicMock
    ) -> None:
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = APIConnectionError(
            request=MagicMock()
        )
        mock_openai_cls.return_value = mock_client

        s = _make_summarizer(max_retries=3)
        s._client = mock_client

        with pytest.raises(SummarizerError, match="failed after 3 retries"):
            s.summarize(_SAMPLE_ABSTRACT)

        assert mock_client.chat.completions.create.call_count == 3

    @patch("src.processors.summarizer.time.sleep")
    @patch("src.processors.summarizer.OpenAI")
    def test_exponential_backoff_timing(
        self, mock_openai_cls: MagicMock, mock_sleep: MagicMock
    ) -> None:
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [
            APIConnectionError(request=MagicMock()),
            APIConnectionError(request=MagicMock()),
            _make_mock_response(),
        ]
        mock_openai_cls.return_value = mock_client

        mock_limiter = MagicMock(spec=RateLimiter)
        s = _make_summarizer(max_retries=3, rate_limiter=mock_limiter)
        s._client = mock_client
        s.summarize(_SAMPLE_ABSTRACT)

        sleep_calls = [c.args[0] for c in mock_sleep.call_args_list]
        assert sleep_calls == [1.0, 2.0]


class TestEmptyResponse:
    @patch("src.processors.summarizer.OpenAI")
    def test_empty_choices_raises(self, mock_openai_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_empty_response()
        mock_openai_cls.return_value = mock_client

        s = _make_summarizer(max_retries=1)
        s._client = mock_client

        with pytest.raises(SummarizerError, match="empty response"):
            s.summarize(_SAMPLE_ABSTRACT)

    @patch("src.processors.summarizer.OpenAI")
    def test_none_content_raises(self, mock_openai_cls: MagicMock) -> None:
        response = _make_mock_response()
        response.choices[0].message.content = None

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = response
        mock_openai_cls.return_value = mock_client

        s = _make_summarizer(max_retries=1)
        s._client = mock_client

        with pytest.raises(SummarizerError, match="empty response"):
            s.summarize(_SAMPLE_ABSTRACT)


class TestCacheKey:
    def test_deterministic(self) -> None:
        k1 = Summarizer._cache_key("hello")
        k2 = Summarizer._cache_key("hello")
        assert k1 == k2

    def test_different_inputs_different_keys(self) -> None:
        k1 = Summarizer._cache_key("abstract A")
        k2 = Summarizer._cache_key("abstract B")
        assert k1 != k2

    def test_prefix(self) -> None:
        key = Summarizer._cache_key("test")
        assert key.startswith("summary:")
