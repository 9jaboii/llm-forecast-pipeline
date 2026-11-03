from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def block_real_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nothing in the test suite may reach the real network. Any attempt
    fails loudly and immediately rather than hanging or flaking."""

    def _blocked(*args, **kwargs):
        raise AssertionError("tests must not make network calls")

    monkeypatch.setattr("httpx.get", _blocked)
    monkeypatch.setattr("httpx.post", _blocked)


@pytest.fixture(autouse=True)
def no_gdelt_throttle(monkeypatch: pytest.MonkeyPatch) -> None:
    """GDELT's real client throttles to one request per 5 seconds (see
    sources/gdelt.py); tests mock get_json directly and never need the
    real delay."""
    monkeypatch.setattr("forecaster.sources.gdelt._respect_rate_limit", lambda: None)
