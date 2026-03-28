from __future__ import annotations

import logging

import pytest

from src.exceptions import APIError, CacheError, CrawlerError, RateLimitError
from src.utils.logger import get_logger


def test_logger_writes_expected_levels(tmp_path, capsys) -> None:
    log_file = tmp_path / "subskin.log"
    logger = get_logger("subskin.test.levels", log_file=log_file, level=logging.DEBUG)

    logger.debug("debug message")
    logger.info("info message")
    logger.warning("warning message")
    logger.error("error message")

    captured = capsys.readouterr().err

    assert "DEBUG" in captured
    assert "INFO" in captured
    assert "WARNING" in captured
    assert "ERROR" in captured
    assert "subskin.test.levels" in captured
    assert "debug message" in captured
    assert "info message" in captured
    assert "warning message" in captured
    assert "error message" in captured

    assert log_file.exists()
    file_contents = log_file.read_text(encoding="utf-8")
    assert "info message" in file_contents


def test_logger_respects_warning_level(capsys) -> None:
    logger = get_logger("subskin.test.warning", level=logging.WARNING)

    logger.debug("hidden debug")
    logger.info("hidden info")
    logger.warning("visible warning")

    captured = capsys.readouterr().err

    assert "hidden debug" not in captured
    assert "hidden info" not in captured
    assert "visible warning" in captured


@pytest.mark.parametrize(
    ("exception_type", "message"),
    [
        (CrawlerError, "crawler failed"),
        (APIError, "api failed"),
        (RateLimitError, "rate limit exceeded"),
        (CacheError, "cache failed"),
    ],
)
def test_custom_exceptions_can_be_raised_and_caught(
    exception_type: type[Exception], message: str
) -> None:
    with pytest.raises(exception_type) as exc_info:
        raise exception_type(message)

    assert message in str(exc_info.value)


def test_custom_exception_cause_is_preserved() -> None:
    cause = ValueError("root cause")

    error = CrawlerError("wrapper", cause=cause)

    assert error.message == "wrapper"
    assert error.cause is cause
    assert error.__cause__ is cause
