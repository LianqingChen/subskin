"""Tests for custom exceptions module."""

import pytest
from src.exceptions import (
    CrawlerError,
    APIError,
    RateLimitError,
    CacheError,
)


class TestCrawlerExceptions:
    """Test crawler-specific exceptions."""

    def test_crawler_error_inheritance(self):
        """Test CrawlerError inheritance."""
        exc = CrawlerError("Crawler failed")
        assert isinstance(exc, Exception)
        assert "Crawler failed" in str(exc)
        assert exc.message == "Crawler failed"

    def test_api_error(self):
        """Test APIError."""
        exc = APIError("API request failed")
        assert isinstance(exc, CrawlerError)
        assert "API request failed" in str(exc)

    def test_rate_limit_error(self):
        """Test RateLimitError."""
        exc = RateLimitError("Too many requests")
        assert isinstance(exc, CrawlerError)
        assert "Too many requests" in str(exc)

    def test_cache_error(self):
        """Test CacheError."""
        exc = CacheError("Cache read failed")
        assert isinstance(exc, CrawlerError)
