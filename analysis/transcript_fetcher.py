import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def fetch_transcript(video_id: str) -> Optional[str]:
    """Fetch YouTube transcript for a video. Returns plain text or None."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled

        loop = asyncio.get_event_loop()
        transcript_list = await loop.run_in_executor(
            None, lambda: YouTubeTranscriptApi().fetch(video_id, languages=["en", "en-US", "en-GB"])
        )
        text = " ".join(entry.text for entry in transcript_list)
        # Truncate to ~12000 chars to stay within model context limits
        if len(text) > 12000:
            text = text[:12000] + "... [transcript truncated]"
        logger.info(f"Transcript fetched for {video_id}: {len(text)} chars")
        return text
    except Exception as exc:
        logger.info(f"No transcript available for {video_id}: {exc}")
        return None
