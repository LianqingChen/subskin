"""Tests for the OpenAI-based translator."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import openai
import pytest

from src.exceptions import APIError
from src.processors.translator import Translator
from src.utils.cache import Cache
from src.utils.rate_limiter import RateLimiter


@pytest.fixture
def cache() -> Cache:
    return Cache()


@pytest.fixture
def fast_limiter() -> RateLimiter:
    return RateLimiter(1000.0)


@pytest.fixture
def mock_openai():
    with patch("src.processors.translator.OpenAI") as cls:
        client = MagicMock()
        cls.return_value = client

        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = "白癜风治疗概述"
        client.chat.completions.create.return_value = response

        yield client


@pytest.fixture
def translator(
    mock_openai: MagicMock, cache: Cache, fast_limiter: RateLimiter
) -> Translator:
    return Translator(
        api_key="test-key",
        cache=cache,
        rate_limiter=fast_limiter,
        max_retries=3,
    )


class TestTranslatorInit:
    def test_missing_api_key_raises(self) -> None:
        with patch("src.processors.translator.os.getenv", return_value=None):
            with pytest.raises(APIError, match="OPENAI_API_KEY"):
                Translator()

    def test_reads_key_from_env(self, mock_openai: MagicMock) -> None:
        with patch("src.processors.translator.os.getenv", return_value="env-key"):
            t = Translator()
            assert t is not None

    def test_explicit_key_overrides_env(self, mock_openai: MagicMock) -> None:
        t = Translator(api_key="explicit-key")
        assert t is not None

    def test_custom_model(self, mock_openai: MagicMock) -> None:
        t = Translator(api_key="key", model="gpt-4")
        assert t._model == "gpt-4"


class TestTranslate:
    def test_returns_translated_text(
        self, translator: Translator, mock_openai: MagicMock
    ) -> None:
        result = translator.translate("Vitiligo treatment overview")
        assert result == "白癜风治疗概述"
        mock_openai.chat.completions.create.assert_called_once()

    def test_strips_input_whitespace(
        self, translator: Translator, mock_openai: MagicMock
    ) -> None:
        translator.translate("  some text  ")
        call_kwargs = mock_openai.chat.completions.create.call_args.kwargs
        user_content = call_kwargs["messages"][1]["content"]
        assert "some text" in user_content
        assert "  some text  " not in user_content

    def test_empty_text_raises(self, translator: Translator) -> None:
        with pytest.raises(ValueError, match="text must not be empty"):
            translator.translate("")

    def test_whitespace_only_raises(self, translator: Translator) -> None:
        with pytest.raises(ValueError, match="text must not be empty"):
            translator.translate("   \n\t  ")

    def test_empty_content_raises(
        self, mock_openai: MagicMock, cache: Cache, fast_limiter: RateLimiter
    ) -> None:
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = None
        mock_openai.chat.completions.create.return_value = resp

        t = Translator(api_key="k", cache=cache, rate_limiter=fast_limiter)
        with pytest.raises(APIError, match="empty content"):
            t.translate("test")

    def test_no_choices_raises(
        self, mock_openai: MagicMock, cache: Cache, fast_limiter: RateLimiter
    ) -> None:
        resp = MagicMock()
        resp.choices = []
        mock_openai.chat.completions.create.return_value = resp

        t = Translator(api_key="k", cache=cache, rate_limiter=fast_limiter)
        with pytest.raises(APIError, match="no choices"):
            t.translate("test")


class TestCaching:
    def test_cache_hit_avoids_api_call(
        self, translator: Translator, mock_openai: MagicMock
    ) -> None:
        translator.translate("hello")
        translator.translate("hello")
        assert mock_openai.chat.completions.create.call_count == 1

    def test_different_text_triggers_api_call(
        self, translator: Translator, mock_openai: MagicMock
    ) -> None:
        translator.translate("text one")
        translator.translate("text two")
        assert mock_openai.chat.completions.create.call_count == 2

    def test_cache_key_is_deterministic(self) -> None:
        assert Translator._cache_key("abc") == Translator._cache_key("abc")

    def test_cache_key_differs_for_different_text(self) -> None:
        assert Translator._cache_key("a") != Translator._cache_key("b")

    def test_cache_key_has_prefix(self) -> None:
        assert Translator._cache_key("x").startswith("translate:")


class TestRateLimiting:
    def test_limiter_acquired_on_cache_miss(
        self, mock_openai: MagicMock, cache: Cache
    ) -> None:
        limiter = MagicMock(spec=RateLimiter)
        t = Translator(api_key="k", cache=cache, rate_limiter=limiter)
        t.translate("text")
        limiter.acquire.assert_called_once()

    def test_limiter_not_acquired_on_cache_hit(
        self, mock_openai: MagicMock, cache: Cache
    ) -> None:
        limiter = MagicMock(spec=RateLimiter)
        t = Translator(api_key="k", cache=cache, rate_limiter=limiter)
        t.translate("text")
        t.translate("text")
        assert limiter.acquire.call_count == 1


class TestRetry:
    def test_retries_on_internal_server_error(
        self, mock_openai: MagicMock, cache: Cache, fast_limiter: RateLimiter
    ) -> None:
        mock_openai.chat.completions.create.side_effect = [
            openai.InternalServerError(
                message="500",
                response=MagicMock(status_code=500),
                body=None,
            ),
            MagicMock(choices=[MagicMock(message=MagicMock(content="成功"))]),
        ]
        t = Translator(
            api_key="k", cache=cache, rate_limiter=fast_limiter, max_retries=3
        )
        with patch("time.sleep"):
            result = t.translate("text")
        assert result == "成功"
        assert mock_openai.chat.completions.create.call_count == 2

    def test_retries_on_rate_limit_error(
        self, mock_openai: MagicMock, cache: Cache, fast_limiter: RateLimiter
    ) -> None:
        mock_openai.chat.completions.create.side_effect = [
            openai.RateLimitError(
                message="429",
                response=MagicMock(status_code=429),
                body=None,
            ),
            MagicMock(choices=[MagicMock(message=MagicMock(content="OK"))]),
        ]
        t = Translator(
            api_key="k", cache=cache, rate_limiter=fast_limiter, max_retries=3
        )
        with patch("time.sleep"):
            assert t.translate("text") == "OK"

    def test_retries_on_timeout(
        self, mock_openai: MagicMock, cache: Cache, fast_limiter: RateLimiter
    ) -> None:
        mock_openai.chat.completions.create.side_effect = [
            openai.APITimeoutError(request=MagicMock()),
            MagicMock(choices=[MagicMock(message=MagicMock(content="重试OK"))]),
        ]
        t = Translator(
            api_key="k", cache=cache, rate_limiter=fast_limiter, max_retries=3
        )
        with patch("time.sleep"):
            assert t.translate("text") == "重试OK"

    def test_retries_on_connection_error(
        self, mock_openai: MagicMock, cache: Cache, fast_limiter: RateLimiter
    ) -> None:
        mock_openai.chat.completions.create.side_effect = [
            openai.APIConnectionError(request=MagicMock()),
            MagicMock(choices=[MagicMock(message=MagicMock(content="连接恢复"))]),
        ]
        t = Translator(
            api_key="k", cache=cache, rate_limiter=fast_limiter, max_retries=3
        )
        with patch("time.sleep"):
            assert t.translate("text") == "连接恢复"

    def test_exhausted_retries_raise_api_error(
        self, mock_openai: MagicMock, cache: Cache, fast_limiter: RateLimiter
    ) -> None:
        mock_openai.chat.completions.create.side_effect = (
            openai.InternalServerError(
                message="down",
                response=MagicMock(status_code=500),
                body=None,
            )
        )
        t = Translator(
            api_key="k", cache=cache, rate_limiter=fast_limiter, max_retries=2
        )
        with patch("time.sleep"):
            with pytest.raises(APIError, match="Translation failed after"):
                t.translate("text")

    def test_non_retryable_error_propagates_immediately(
        self, mock_openai: MagicMock, cache: Cache, fast_limiter: RateLimiter
    ) -> None:
        mock_openai.chat.completions.create.side_effect = openai.BadRequestError(
            message="bad",
            response=MagicMock(status_code=400),
            body=None,
        )
        t = Translator(
            api_key="k", cache=cache, rate_limiter=fast_limiter, max_retries=3
        )
        with pytest.raises(APIError, match="OpenAI error"):
            t.translate("text")
        assert mock_openai.chat.completions.create.call_count == 1
