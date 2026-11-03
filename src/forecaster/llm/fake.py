from __future__ import annotations

import hashlib


class FakeLLM:
    """Deterministic, no-skill stand-in for offline tests and the demo. Never
    calls the network. Produces a probability pseudo-randomly derived from
    the prompt text and a call counter, so repeated samples vary (letting
    aggregation do something) while staying reproducible run to run."""

    model_name = "fake-v1"

    def __init__(self) -> None:
        self._counter = 0

    def complete(self, system: str, user: str, temperature: float, max_tokens: int) -> str:
        self._counter += 1
        digest = hashlib.sha256(f"{user}|{self._counter}".encode()).hexdigest()
        bucket = int(digest[:8], 16) % 9800
        prob = (bucket + 100) / 10000  # 0.01 .. 0.99
        return (
            "This is a deterministic placeholder rationale with no real forecasting "
            f"skill.\nFINAL PROBABILITY: {prob:.2f}"
        )
