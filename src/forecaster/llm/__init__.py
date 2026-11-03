from __future__ import annotations

from forecaster.config import Settings
from forecaster.llm.base import LLMClient


def build_llm_client(settings: Settings) -> LLMClient:
    provider = settings.LLM_PROVIDER
    if provider == "fake":
        from forecaster.llm.fake import FakeLLM

        return FakeLLM()
    if provider == "anthropic":
        from forecaster.llm.anthropic_client import AnthropicLLM

        if not settings.ANTHROPIC_API_KEY or not settings.ANTHROPIC_MODEL:
            raise RuntimeError(
                "Set FC_ANTHROPIC_API_KEY and FC_ANTHROPIC_MODEL to use FC_LLM_PROVIDER=anthropic"
            )
        return AnthropicLLM(api_key=settings.ANTHROPIC_API_KEY, model=settings.ANTHROPIC_MODEL)
    if provider == "bedrock":
        from forecaster.llm.bedrock_client import BedrockLLM

        if not settings.BEDROCK_MODEL_ID:
            raise RuntimeError("Set FC_BEDROCK_MODEL_ID to use FC_LLM_PROVIDER=bedrock")
        return BedrockLLM(model_id=settings.BEDROCK_MODEL_ID, region=settings.AWS_REGION)
    raise ValueError(f"unknown FC_LLM_PROVIDER: {provider}")
