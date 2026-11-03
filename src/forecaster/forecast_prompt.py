from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path

PROMPT_VERSION = "forecast_v1"
_TEMPLATE_PATH = Path(__file__).parent / "prompts" / f"{PROMPT_VERSION}.md"

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_DELIMITER_TAGS = re.compile(r"</?headlines>", re.IGNORECASE)


def _load_template() -> str:
    return _TEMPLATE_PATH.read_text()


def prompt_sha256() -> str:
    return hashlib.sha256(_load_template().encode("utf-8")).hexdigest()


def sanitize_headline(text: str) -> str:
    """Untrusted input: strip control characters and anything that could
    close/open the <headlines> delimiter early, before it ever reaches the
    model as part of the prompt."""
    text = _CONTROL_CHARS.sub("", text)
    text = _DELIMITER_TAGS.sub("", text)
    return text.strip()


def build_headlines_block(headlines: list[str]) -> str:
    if not headlines:
        return "(no recent headlines found)"
    return "\n".join(f"- {sanitize_headline(h)}" for h in headlines)


def build_prompt(
    question_title: str, close_time: datetime | None, asof: datetime, headlines: list[str]
) -> str:
    template = _load_template()
    return template.format(
        question_title=sanitize_headline(question_title),
        close_time=close_time.isoformat() if close_time else "unknown",
        asof_date=asof.date().isoformat(),
        headlines_block=build_headlines_block(headlines),
    )


_FINAL_PROB_RE = re.compile(r"FINAL PROBABILITY:\s*([01](?:\.\d+)?)", re.IGNORECASE)


def parse_probability(completion: str) -> float | None:
    match = _FINAL_PROB_RE.search(completion)
    if not match:
        return None
    value = float(match.group(1))
    if 0.0 <= value <= 1.0:
        return value
    return None
