import logging
from datetime import datetime, timezone
from typing import Any

from pyairtable import Api

import config

logger = logging.getLogger(__name__)

_TABLE_NAME = "Videos"


class AirtableClient:
    def __init__(self) -> None:
        self._api = Api(config.AIRTABLE_API_KEY)
        self._table = self._api.table(config.AIRTABLE_BASE_ID, _TABLE_NAME)

    def upsert_video(
        self,
        video: dict[str, Any],
        synthesis: dict[str, Any],
        gemini: dict[str, Any],
        claude: dict[str, Any],
        gpt: dict[str, Any],
    ) -> None:
        fields: dict[str, Any] = {
            "VideoID": video["video_id"],
            "Title": video.get("title", ""),
            "Channel": video.get("channel", ""),
            "URL": video.get("url", ""),
            "PublishedAt": video.get("published_at", ""),
            "FinalVerdict": synthesis["final_verdict"],
            "Confidence": synthesis["confidence"],
            "Consensus": synthesis["consensus"],
            "GeminiVerdict": gemini.get("verdict", "UNCERTAIN"),
            "ClaudeVerdict": claude.get("verdict", "UNCERTAIN"),
            "GPTVerdict": gpt.get("verdict", "UNCERTAIN"),
            "Reasoning": synthesis.get("reasoning", "")[:10000],
            "Flags": ", ".join(synthesis.get("flags", [])),
            "ProcessedAt": datetime.now(timezone.utc).isoformat(),
        }
        try:
            self._table.batch_upsert(
                [{"fields": fields}],
                key_fields=["VideoID"],
            )
            logger.info(f"Airtable upserted: {video['video_id']}")
        except Exception as exc:
            logger.error(f"Airtable upsert failed for {video['video_id']}: {exc}")
            raise

    def get_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        try:
            records = self._table.all(
                sort=["-ProcessedAt"],
                max_records=limit,
            )
            return [r["fields"] for r in records]
        except Exception as exc:
            logger.error(f"Airtable get_recent failed: {exc}")
            return []

    def get_stats(self) -> dict[str, Any]:
        try:
            records = self._table.all(fields=["FinalVerdict"])
            counts: dict[str, Any] = {"REAL": 0, "FAKE": 0, "UNCERTAIN": 0, "total": 0}
            for r in records:
                verdict = r["fields"].get("FinalVerdict", "UNCERTAIN")
                counts[verdict] = counts.get(verdict, 0) + 1
                counts["total"] += 1
            return counts
        except Exception as exc:
            logger.error(f"Airtable get_stats failed: {exc}")
            return {"REAL": 0, "FAKE": 0, "UNCERTAIN": 0, "total": 0}
