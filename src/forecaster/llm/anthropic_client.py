from __future__ import annotations

import anthropic


class AnthropicLLM:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = anthropic.Anthropic(api_key=api_key)
        self.model_name = model

    def complete(self, system: str, user: str, temperature: float, max_tokens: int) -> str:
        # The installed Messages API (anthropic>=2.0) has no temperature/top_p/
        # top_k sampling controls — they were replaced by `speed` (standard/fast)
        # and `output_config.effort`, neither of which is a randomness knob.
        # `temperature` is accepted here only to keep this provider's interface
        # identical to FakeLLM/BedrockLLM (see llm/base.py); it is intentionally
        # unused for this provider. See docs/adr/0006-anthropic-sdk-sampling.md.
        del temperature
        response = self._client.messages.create(
            model=self.model_name,
            system=system,
            messages=[{"role": "user", "content": user}],
            max_tokens=max_tokens,
        )
        return "".join(block.text for block in response.content if block.type == "text")
