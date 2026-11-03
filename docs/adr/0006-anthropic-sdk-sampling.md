# 0006 — Sampling control on the direct Anthropic API has changed

## Status
Accepted. The follow-up below has since been tested against a funded
account and resolved — see Resolution.

## Context
This project's core aggregation design (guide §00, §04 notebook 03) is "ask
the model for a probability five times at `FC_TEMPERATURE=0.7`, take the
median" — it depends on `temperature` producing sample-to-sample diversity.

While wiring up `llm/anthropic_client.py` against a real account, the
installed `anthropic` Python SDK (`pip install anthropic` resolves to 2.4.0
as of 2026-11) turned out to have a `messages.create()` signature with no
`temperature`, `top_p`, or `top_k` parameter at all — verified directly
against the SDK's source (`anthropic/resources/messages/messages.py`), not
assumed from older documentation. In its place: `speed`
(`"standard" | "fast"`, a latency/quality tradeoff) and
`output_config.effort` (`"low" | "medium" | "high" | "xhigh" | "max"`, a
reasoning-depth control) — neither is a randomness knob. This shape is
identical back through the 1.x line tested (1.17.0), so it is current
reality, not a version-specific regression to pin around.

## Decision
`AnthropicLLM.complete()` accepts `temperature` (to keep the same interface
as `FakeLLM` and `BedrockLLM` — see `llm/base.py`) but does not pass it to
the API; it's explicitly discarded with a comment explaining why, rather
than silently dropped. `pyproject.toml` pins the dependency floor to
`anthropic>=2.0` to match what actually installs today.

Amazon Bedrock's Converse API (`llm/bedrock_client.py`) is unaffected — it's
a separate, AWS-operated API surface and still accepts `temperature` in
`inferenceConfig`. This divergence between the two providers behind the
same `LLMClient` interface is itself worth knowing about if debugging why
sample spread differs between `FC_LLM_PROVIDER=anthropic` and `=bedrock`.

## Resolution (tested against a real, funded account)
Five live calls against `claude-haiku-4-5-20251001` with the same prompt
and no temperature control produced probabilities of
`0.48, 0.48, 0.42, 0.48, 0.45` — three distinct values, a ~0.06 spread.
Default decoding on the direct API is evidently still non-greedy even
without an exposed sampling knob, so `FC_SAMPLES` + median aggregation
still does something real on this path. No Bedrock-only fallback needed.

A separate, real bug surfaced during the same test: the first attempt (at
`MAX_TOKENS=300`, then the old pipeline default of 500) truncated mid-
reasoning before the model reached its `FINAL PROBABILITY:` line, so
`forecast_prompt.parse_probability` returned `None` for every sample. Fixed
two ways: `pipeline.MAX_TOKENS` raised from 500 to 1024, and
`prompts/forecast_v1.md` now explicitly asks for concise reasoning ("a few
sentences per step... well under 300 words") rather than the long
structured markdown essays the model produced by default. Both changes
matter — the token budget alone would work but cost more per call than
necessary; the concision instruction alone isn't a truncation guarantee.
