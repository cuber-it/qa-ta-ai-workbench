"""test_retry.py — RetryExhausted, RateLimitHit, Backoff."""
import pytest

from uc_llm_provider.core.retry import RateLimitHit, RetryExhausted, with_retry


@pytest.mark.asyncio
async def test_retry_success_first_attempt():
    calls = []
    async def _fn():
        calls.append(1)
        return "ok"
    result = await with_retry(_fn, {}, [])
    assert result == "ok"
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_retry_success_after_failure():
    calls = []
    async def _fn():
        calls.append(1)
        if len(calls) < 3:
            import httpx
            raise httpx.HTTPStatusError(
                "server error",
                request=httpx.Request("POST", "http://x"),
                response=httpx.Response(500),
            )
        return "ok"
    result = await with_retry(_fn, {"retry": {"max_attempts": 3, "base_delay_s": 0.01}}, [])
    assert result == "ok"
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_retry_exhausted():
    async def _fn():
        import httpx
        raise httpx.HTTPStatusError(
            "error",
            request=httpx.Request("POST", "http://x"),
            response=httpx.Response(500),
        )
    with pytest.raises(RetryExhausted):
        await with_retry(_fn, {"retry": {"max_attempts": 2, "base_delay_s": 0.01}}, [])


@pytest.mark.asyncio
async def test_rate_limit_raises():
    async def _fn():
        import httpx
        raise httpx.HTTPStatusError(
            "rate limit",
            request=httpx.Request("POST", "http://x"),
            response=httpx.Response(429),
        )
    with pytest.raises((RateLimitHit, RetryExhausted)):
        await with_retry(_fn, {"retry": {"max_attempts": 1, "base_delay_s": 0.01}}, [])
