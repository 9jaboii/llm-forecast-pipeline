import json

import httpx
import pytest

from forecaster.sources.http import get_json


class _FakeResponse:
    def __init__(self, status_code, payload=None, headers=None, text_body=None):
        self.status_code = status_code
        self._payload = payload
        self._text_body = text_body
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)

    def json(self):
        if self._text_body is not None:
            # Mirrors httpx: json.loads on a non-JSON body raises JSONDecodeError
            return json.loads(self._text_body)
        return self._payload


def test_get_json_returns_payload_on_success(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _FakeResponse(200, {"ok": True}))
    assert get_json("https://example.invalid") == {"ok": True}


def test_get_json_retries_then_succeeds(monkeypatch, caplog):
    calls = {"n": 0}

    def _get(*a, **k):
        calls["n"] += 1
        if calls["n"] < 2:
            return _FakeResponse(500)
        return _FakeResponse(200, {"ok": True})

    monkeypatch.setattr(httpx, "get", _get)
    monkeypatch.setattr("time.sleep", lambda *_: None)
    result = get_json("https://example.invalid", retries=3)
    assert result == {"ok": True}
    assert calls["n"] == 2


def test_get_json_honors_retry_after_on_429(monkeypatch):
    calls = {"n": 0}
    slept = []

    def _get(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            return _FakeResponse(429, headers={"Retry-After": "0.01"})
        return _FakeResponse(200, {"ok": True})

    monkeypatch.setattr(httpx, "get", _get)
    monkeypatch.setattr("time.sleep", lambda s: slept.append(s))
    result = get_json("https://example.invalid", retries=3)
    assert result == {"ok": True}
    assert slept == [0.01]


def test_get_json_raises_after_exhausting_retries(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _FakeResponse(500))
    monkeypatch.setattr("time.sleep", lambda *_: None)
    with pytest.raises(RuntimeError):
        get_json("https://example.invalid", retries=2)


def test_get_json_retries_on_200_with_non_json_body(monkeypatch):
    # Mirrors GDELT's rate-limit response: HTTP 200 with a plain-text body,
    # not a 429 — raise_for_status() won't catch it, only .json() will fail.
    calls = {"n": 0}

    def _get(*a, **k):
        calls["n"] += 1
        if calls["n"] < 2:
            return _FakeResponse(200, text_body="Please limit requests to one every 5 seconds.")
        return _FakeResponse(200, {"ok": True})

    monkeypatch.setattr(httpx, "get", _get)
    monkeypatch.setattr("time.sleep", lambda *_: None)
    result = get_json("https://example.invalid", retries=3)
    assert result == {"ok": True}
    assert calls["n"] == 2


def test_get_json_raises_runtime_error_when_always_non_json(monkeypatch):
    monkeypatch.setattr(
        httpx, "get", lambda *a, **k: _FakeResponse(200, text_body="rate limited, not json")
    )
    monkeypatch.setattr("time.sleep", lambda *_: None)
    with pytest.raises(RuntimeError):
        get_json("https://example.invalid", retries=2)
