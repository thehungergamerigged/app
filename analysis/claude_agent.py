import json
import logging
import re
from typing import Any
import anthropic
import config

logger = logging.getLogger(__name__)
_client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)

_PROMPT_WITH_TRANSCRIPT = """\
You are a misinformation detection expert specializing in content related to Israel, Judaism, Zionism, antisemitism, and anti-Zionism.

IMPORTANT: First determine if this video is related to any of these topics:
Israel, Jews, Judaism, Zionism, antisemitism, anti-Zionism, Israeli-Palestinian conflict, Jewish communities, Hamas, Hezbollah, IDF, Gaza, West Bank, Jewish history, Holocaust.

If the video is NOT related to these topics, return ONLY this JSON:
{{"verdict": "SKIP", "confidence": 0, "reasoning": "Not relevant to Israel/Judaism/Zionism topics.", "flags": []}}

If it IS relevant, analyze whether it contains misinformation or disinformation. Use the full transcript to identify specific claims, quotes, and language patterns.

Video Title: {title}
Channel: {channel}
URL: {url}
Published: {published_at}

Full Transcript:
{transcript}

Respond ONLY with valid JSON — no markdown fences, no extra text:
{{
  "verdict": "REAL|FAKE|UNCERTAIN|SKIP",
  "confidence": <integer 0-100>,
  "reasoning": "<one concise paragraph citing specific transcript content>",
  "flags": ["<flag1>", "<flag2>"]
}}

Valid flags: clickbait, emotional_language, unverified_claims, conspiracy_indicators,
satire, misleading_title, credible_source, state_media, antisemitism, anti_zionism,
pro_israel, pro_palestinian, out_of_context
"""

_PROMPT_TITLE_ONLY = """\
You are a misinformation detection expert specializing in content related to Israel, Judaism, Zionism, antisemitism, and anti-Zionism.

IMPORTANT: First determine if this video is related to any of these topics:
Israel, Jews, Judaism, Zionism, antisemitism, anti-Zionism, Israeli-Palestinian conflict, Jewish communities, Hamas, Hezbollah, IDF, Gaza, West Bank, Jewish history, Holocaust.

If the video is NOT related to these topics, return ONLY this JSON:
{{"verdict": "SKIP", "confidence": 0, "reasoning": "Not relevant to Israel/Judaism/Zionism topics.", "flags": []}}

If it IS relevant, analyze whether it contains misinformation or disinformation.

Video Title: {title}
Channel: {channel}
URL: {url}
Published: {published_at}

Respond ONLY with valid JSON — no markdown fences, no extra text:
{{
  "verdict": "REAL|FAKE|UNCERTAIN|SKIP",
  "confidence": <integer 0-100>,
  "reasoning": "<one concise paragraph>",
  "flags": ["<flag1>", "<flag2>"]
}}

Valid flags: clickbait, emotional_language, unverified_claims, conspiracy_indicators,
satire, misleading_title, credible_source, state_media, antisemitism, anti_zionism,
pro_israel, pro_palestinian, out_of_context
"""

_FALLBACK: dict[str, Any] = {
    "verdict": "UNCERTAIN",
    "confidence": 0,
    "reasoning": "Claude analysis unavailable.",
    "flags": [],
}

async def analyze(video: dict[str, Any]) -> dict[str, Any]:
    try:
        transcript = video.get("transcript")
        if transcript:
            prompt = _PROMPT_WITH_TRANSCRIPT.format(
                title=video.get("title", ""),
                channel=video.get("channel", ""),
                url=video.get("url", ""),
                published_at=video.get("published_at", ""),
                transcript=transcript,
            )
        else:
            prompt = _PROMPT_TITLE_ONLY.format(
                title=video.get("title", ""),
                channel=video.get("channel", ""),
                url=video.get("url", ""),
                published_at=video.get("published_at", ""),
            )
        message = await _client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        text = message.content[0].text.strip()
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            text = match.group(0)
        result = json.loads(text)
        verdict = result.get("verdict", "UNCERTAIN").upper()
        if verdict not in ("REAL", "FAKE", "UNCERTAIN", "SKIP"):
            verdict = "UNCERTAIN"
        return {
            "verdict": verdict,
            "confidence": max(0, min(100, int(result.get("confidence", 50)))),
            "reasoning": str(result.get("reasoning", "")),
            "flags": list(result.get("flags", [])),
        }
    except Exception as exc:
        logger.error(f"Claude analysis failed: {exc}")
        return {**_FALLBACK, "reasoning": f"Claude error: {exc}"}