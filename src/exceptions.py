from __future__ import annotations


class CrawlerError(Exception):
    """Base exception for crawler-related errors.

    Args:
        message: Human-readable error message.
        cause: Optional underlying exception.
    """

    def __init__(self, message: str, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.cause = cause
        if cause is not None:
            self.__cause__ = cause


class APIError(CrawlerError):
    """Raised when an API request fails."""


class RateLimitError(CrawlerError):
    """Raised when a rate limit is exceeded."""


class CacheError(CrawlerError):
    """Raised when cache operations fail."""
