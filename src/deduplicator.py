import json
import os
from typing import Dict, List, Any

from src.utils import get_logger

logger = get_logger(__name__)

_STATE_PATH = os.path.join("output", "seen_ids.json")


class SeenStore:
    """
    Persists IDs of records already dispatched to the webhook so that
    consecutive runs covering the same date window don't re-send them.

    State is stored in output/seen_ids.json, keyed by pipeline name:
        {
            "comments": ["abc123", "def456"],
            "posts":    ["xyz789"]
        }

    IDs are only written after a confirmed successful webhook call.
    If the webhook fails, records will be retried on the next run.
    """

    def __init__(self, path: str = _STATE_PATH):
        self.path = path
        self._store: Dict[str, set] = self._load()

    def _load(self) -> Dict[str, set]:
        if not os.path.exists(self.path):
            return {}
        try:
            with open(self.path, encoding="utf-8") as f:
                raw = json.load(f)
            return {pipeline: set(ids) for pipeline, ids in raw.items()}
        except Exception as e:
            logger.warning(f"Could not read seen_ids store, starting fresh: {e}")
            return {}

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(
                    {p: list(ids) for p, ids in self._store.items()},
                    f,
                    indent=2,
                )
        except Exception as e:
            logger.error(f"Could not persist seen_ids store: {e}")

    def filter_new(self, pipeline: str, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Returns only records whose 'id' has not been seen for this pipeline."""
        seen = self._store.get(pipeline, set())
        new = [r for r in records if r["id"] not in seen]
        skipped = len(records) - len(new)
        if skipped:
            logger.info(f"Dedup [{pipeline}]: skipped {skipped} already-sent record(s), {len(new)} new.")
        return new

    def mark_sent(self, pipeline: str, records: List[Dict[str, Any]]) -> None:
        """Persists IDs of records that were successfully dispatched."""
        if not records:
            return
        if pipeline not in self._store:
            self._store[pipeline] = set()
        for r in records:
            self._store[pipeline].add(r["id"])
        self._save()
        logger.info(f"Dedup [{pipeline}]: marked {len(records)} record(s) as sent.")
