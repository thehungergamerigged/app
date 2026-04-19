import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ChannelTrustStore:
    """Tracks per-channel verdict history and computes a 0-100 trust score."""

    def __init__(self, path: str = "channel_trust.json") -> None:
        self._path = Path(path)
        self._data: dict[str, dict[str, int]] = self._load()

    def _load(self) -> dict[str, dict[str, int]]:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _save(self) -> None:
        self._path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    def record_verdict(self, channel: str, verdict: str) -> None:
        if verdict not in ("REAL", "FAKE", "UNCERTAIN") or not channel:
            return
        if channel not in self._data:
            self._data[channel] = {"real": 0, "fake": 0, "uncertain": 0}
        self._data[channel][verdict.lower()] = self._data[channel].get(verdict.lower(), 0) + 1
        self._save()

    def get_trust(self, channel: str) -> dict[str, Any]:
        entry = self._data.get(channel, {})
        real = entry.get("real", 0)
        fake = entry.get("fake", 0)
        uncertain = entry.get("uncertain", 0)
        total = real + fake + uncertain
        decided = real + fake
        score = round(real / decided * 100) if decided > 0 else 50
        return {
            "score": score,
            "real": real,
            "fake": fake,
            "uncertain": uncertain,
            "total": total,
            "reliable": total >= 5,
        }

    def get_all(self) -> dict[str, dict[str, Any]]:
        return {ch: self.get_trust(ch) for ch in self._data}
