from __future__ import annotations

from typing import Protocol


class LLMClient(Protocol):
    model_name: str

    def complete(self, system: str, user: str, temperature: float, max_tokens: int) -> str: ...
