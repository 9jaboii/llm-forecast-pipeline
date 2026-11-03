from __future__ import annotations

import boto3


class BedrockLLM:
    def __init__(self, model_id: str, region: str) -> None:
        self._client = boto3.client("bedrock-runtime", region_name=region)
        self.model_name = model_id

    def complete(self, system: str, user: str, temperature: float, max_tokens: int) -> str:
        response = self._client.converse(
            modelId=self.model_name,
            system=[{"text": system}],
            messages=[{"role": "user", "content": [{"text": user}]}],
            inferenceConfig={"temperature": temperature, "maxTokens": max_tokens},
        )
        blocks = response["output"]["message"]["content"]
        return "".join(block["text"] for block in blocks if "text" in block)
