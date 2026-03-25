"""Persistent Groq/Ollama chat turns (JSONL) for continuity and user context."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ChatHistoryStore:
    """
    Append-only JSONL: one object per line {"role","content","ts"}.
    Editable: trim or delete lines in the file to forget old context.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        max_stored_messages: int = 500,
        max_context_messages: int = 24,
    ):
        self.path = Path(path)
        self.max_stored = max(10, int(max_stored_messages))
        self.max_context = max(2, int(max_context_messages))

    def _ensure_parent(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read_all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        out: list[dict[str, Any]] = []
        try:
            text = self.path.read_text(encoding="utf-8")
        except OSError:
            return []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict) and row.get("role") in ("user", "assistant") and row.get("content"):
                out.append(row)
        return out

    def _write_trim(self, rows: list[dict[str, Any]]) -> None:
        self._ensure_parent()
        if len(rows) > self.max_stored:
            rows = rows[-self.max_stored :]
        with self.path.open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    def messages_for_api(self) -> list[dict[str, str]]:
        """Recent turns as OpenAI-style messages (no system)."""
        rows = self._read_all()
        if len(rows) > self.max_context:
            rows = rows[-self.max_context :]
        return [{"role": r["role"], "content": str(r["content"])} for r in rows]

    def append_exchange(self, user_text: str, assistant_text: str) -> None:
        """Record one user question and assistant reply after a successful reply."""
        u = (user_text or "").strip()
        a = (assistant_text or "").strip()
        if not u or not a:
            return
        rows = self._read_all()
        rows.append({"role": "user", "content": u, "ts": _utc_now()})
        rows.append({"role": "assistant", "content": a, "ts": _utc_now()})
        self._write_trim(rows)
