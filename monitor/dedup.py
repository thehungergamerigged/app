import json
from pathlib import Path


class DeduplicationStore:
    def __init__(self, filepath: str):
        self.filepath = Path(filepath)
        self._seen: set[str] = set()
        self._load()

    def _load(self) -> None:
        if self.filepath.exists():
            try:
                data = json.loads(self.filepath.read_text(encoding="utf-8"))
                self._seen = set(data.get("seen_ids", []))
            except (json.JSONDecodeError, KeyError):
                self._seen = set()

    def _save(self) -> None:
        self.filepath.write_text(
            json.dumps({"seen_ids": list(self._seen)}, indent=2),
            encoding="utf-8",
        )

    def is_seen(self, video_id: str) -> bool:
        return video_id in self._seen

    def mark_seen(self, video_id: str) -> None:
        self._seen.add(video_id)
        self._save()

    def count(self) -> int:
        return len(self._seen)
