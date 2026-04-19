import json
import logging
from typing import Any

from openai import AsyncOpenAI

import config

logger = logging.getLogger(__name__)

_client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)

_PROMPT = """\
You are a misinformation detection expert. Analyze this YouTube video and determine \
whether it likely contains misinformation, disinformation, or fabricated content.

Video Title: {title}
Channel: {channel}
URL: {url}
Published: {published_at}

Assess based on the title, channel reputation, and any detectable linguistic patterns.

Respond ONLY with valid JSON — no markdown fences, no extra text:
{{
  "verdict": "REAL|FAKE|UNCERTAIN",
  "confidence": <integer 0-100>,
  "reasoning": "<one concise paragraph>",
  "flags": ["<flag1>", "<flag2>"]
}}

Valid flags: clickbait, emotional_language, unverified_claims, conspiracy_indicators,
satire, misleading_title, credible_source, state_media, anonymous_source, out_of_context
"""

_FALLBACK: dict[str, Any] = {
    "verdict": "UNCERTAIN",
    "confidence": 0,
    "reasoning": "GPT analysis unavailable.",
    "flags": [],
}


async def analyze(video: dict[str, Any]) -> dict[str, Any]:
    try:
        prompt = _PROMPT.format(
            title=video.get("title", ""),
            channel=video.get("channel", ""),
            url=video.get("url", ""),
            published_at=video.get("published_at", ""),
        )
        response = await _client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            response_format={"type": "json_object"},
        )
        text = response.choices[0].message.content.strip()
        result = json.loads(text)
        verdict = result.get("verdict", "UNCERTAIN").upper()
        if verdict not in ("REAL", "FAKE", "UNCERTAIN"):
            verdict = "UNCERTAIN"
        return {
            "verdict": verdict,
            "confidence": max(0, min(100, int(result.get("confidence", 50)))),
            "reasoning": str(result.get("reasoning", "")),
            "flags": list(result.get("flags", [])),
        }
    except Exception as exc:
        logger.error(f"GPT analysis failed: {exc}")
        return {**_FALLBACK, "reasoning": f"GPT error: {exc}"}
