from __future__ import annotations

import json
import time

import httpx

USER_AGENT = "llm-forecast-pipeline/0.1 (+https://github.com/; read-only research use)"


def get_json(
    url: str,
    params: dict | None = None,
    headers: dict | None = None,
    retries: int = 3,
    backoff_base: float = 1.0,
    timeout: float = 15.0,
) -> dict | list:
    """The single HTTP seam every source client goes through. Tests mock this
    function so nothing in the test suite ever reaches the real network."""
    all_headers = {"User-Agent": USER_AGENT, **(headers or {})}
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            response = httpx.get(url, params=params, headers=all_headers, timeout=timeout)
            if response.status_code == 429:
                retry_after = float(
                    response.headers.get("Retry-After", backoff_base * (2**attempt))
                )
                time.sleep(retry_after)
                continue
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            last_exc = exc
            if attempt < retries - 1:
                time.sleep(backoff_base * (2**attempt))
        except httpx.RequestError as exc:
            last_exc = exc
            if attempt < retries - 1:
                time.sleep(backoff_base * (2**attempt))
        except json.JSONDecodeError as exc:
            # Some APIs (GDELT's rate-limit notice, for one) return 200 with a
            # plain-text body instead of an HTTP error status — still a
            # failed request, just one the status check above can't catch.
            last_exc = exc
            if attempt < retries - 1:
                time.sleep(backoff_base * (2**attempt))
    raise RuntimeError(f"GET {url} failed after {retries} attempts") from last_exc
