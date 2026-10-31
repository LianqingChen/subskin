"""LLM / CV resilience primitives: client timeouts, concurrency caps, bounded background pool.

Framework-free: ``app/main.py`` maps ``SlotUnavailable`` → 503 and ``QuotaExceeded`` → 429.
"""
import asyncio
import logging
import os
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import asynccontextmanager, contextmanager
from typing import Any, AsyncIterator, Callable, Iterator, Optional

import openai

logger = logging.getLogger(__name__)

LLM_TIMEOUT_CHAT = float(os.getenv("LLM_TIMEOUT_CHAT", "60"))
LLM_TIMEOUT_LONG = float(os.getenv("LLM_TIMEOUT_LONG", "120"))
LLM_MAX_RETRIES = 1

LLM_BUSY_MESSAGE = "AI 服务繁忙，请稍后再试"
CV_BUSY_MESSAGE = "当前排队人数较多，请稍后再试"


class SlotUnavailable(Exception):
    """A bounded resource (CV / LLM slot) could not be acquired in time."""

    def __init__(self, message: str = CV_BUSY_MESSAGE):
        super().__init__(message)
        self.message = message


class QuotaExceeded(Exception):
    """User or guest exceeded a daily usage quota."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except ValueError:
        return default


CV_MAX_CONCURRENCY = _env_int("CV_MAX_CONCURRENCY", 2)
LLM_MAX_CONCURRENCY = _env_int("LLM_MAX_CONCURRENCY", 16)
CV_SLOT_WAIT_SECONDS = float(os.getenv("CV_SLOT_WAIT_SECONDS", "20"))
LLM_SLOT_WAIT_SECONDS = float(os.getenv("LLM_SLOT_WAIT_SECONDS", "20"))

_cv_semaphore = threading.BoundedSemaphore(CV_MAX_CONCURRENCY)
_llm_semaphore = threading.BoundedSemaphore(LLM_MAX_CONCURRENCY)


# ── LLM: cap enforced inside the client so every call site is covered ──


class _Permit:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._held = True

    def release(self) -> None:
        with self._lock:
            if self._held:
                self._held = False
                _llm_semaphore.release()


def _acquire_llm_permit() -> _Permit:
    if not _llm_semaphore.acquire(timeout=LLM_SLOT_WAIT_SECONDS):
        logger.warning("llm slot unavailable after %.0fs", LLM_SLOT_WAIT_SECONDS)
        raise SlotUnavailable(LLM_BUSY_MESSAGE)
    return _Permit()


class _PermitStream:
    """Proxy for a streaming response that holds the LLM permit until exhausted or closed.

    Not tied to a thread: SSE generators may be resumed on different worker threads.
    """

    def __init__(self, stream: Any, permit: _Permit) -> None:
        self._stream = stream
        self._permit = permit

    def __iter__(self) -> Iterator[Any]:
        try:
            for chunk in self._stream:
                yield chunk
        finally:
            self._permit.release()

    def close(self) -> None:
        try:
            close = getattr(self._stream, "close", None)
            if close is not None:
                close()
        finally:
            self._permit.release()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._stream, name)

    def __del__(self) -> None:
        self._permit.release()


def _guard_completions(client: openai.OpenAI) -> openai.OpenAI:
    completions = client.chat.completions
    original = completions.create

    def guarded_create(*args: Any, **kwargs: Any) -> Any:
        permit = _acquire_llm_permit()
        try:
            result = original(*args, **kwargs)
        except BaseException:
            permit.release()
            raise
        if kwargs.get("stream"):
            return _PermitStream(result, permit)
        permit.release()
        return result

    completions.create = guarded_create
    return client


def make_openai_client(config: dict, timeout: float = LLM_TIMEOUT_CHAT) -> openai.OpenAI:
    client = openai.OpenAI(
        api_key=config["api_key"],
        base_url=config["base_url"],
        timeout=timeout,
        max_retries=LLM_MAX_RETRIES,
    )
    return _guard_completions(client)


# ── CV: explicit slots at API / background-job entry points (never nest) ──

_held = threading.local()


@contextmanager
def cv_slot(wait: Optional[float] = None) -> Iterator[None]:
    """Blocking CV slot for sync code paths (background jobs, sync generators)."""
    if getattr(_held, "cv", 0):
        _held.cv += 1
        try:
            yield
        finally:
            _held.cv -= 1
        return
    timeout = CV_SLOT_WAIT_SECONDS if wait is None else wait
    if not _cv_semaphore.acquire(timeout=timeout):
        logger.warning("cv slot unavailable after %.0fs", timeout)
        raise SlotUnavailable(CV_BUSY_MESSAGE)
    _held.cv = 1
    try:
        yield
    finally:
        _held.cv = 0
        _cv_semaphore.release()


@asynccontextmanager
async def async_cv_slot(wait: Optional[float] = None) -> AsyncIterator[None]:
    """Event-loop friendly CV slot for async endpoints (acquired off-loop)."""
    timeout = CV_SLOT_WAIT_SECONDS if wait is None else wait
    loop = asyncio.get_running_loop()
    future = loop.run_in_executor(None, _cv_semaphore.acquire, True, timeout)
    try:
        acquired = await asyncio.shield(future)
    except asyncio.CancelledError:
        # Client went away while queued: release the permit if the worker still gets it.
        future.add_done_callback(
            lambda f: _cv_semaphore.release() if not f.cancelled() and f.result() else None
        )
        raise
    if not acquired:
        logger.warning("cv slot unavailable after %.0fs", timeout)
        raise SlotUnavailable(CV_BUSY_MESSAGE)
    try:
        yield
    finally:
        _cv_semaphore.release()


# ── Bounded pool for fire-and-forget AI jobs (replaces ad-hoc threads) ──

_BACKGROUND_WORKERS = _env_int("BACKGROUND_AI_WORKERS", 4)
_background_pool = ThreadPoolExecutor(max_workers=_BACKGROUND_WORKERS, thread_name_prefix="ai-bg")


def _log_failure(future: Future) -> None:
    exc = future.exception()
    if exc is not None:
        logger.error("background AI job failed", exc_info=(type(exc), exc, exc.__traceback__))


def submit_background(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Future:
    future = _background_pool.submit(fn, *args, **kwargs)
    future.add_done_callback(_log_failure)
    return future
