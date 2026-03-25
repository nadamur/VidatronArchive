"""Persistent user preferences (JSON on disk). Edit the file or learn from short phrases."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


DEFAULT_PROFILE: dict[str, Any] = {
    "name": "",
    "preferred_name": "",
    "music_preferences": "",
    "notes": "",
    "custom": {},
}


def _deep_merge_defaults(data: dict[str, Any]) -> dict[str, Any]:
    out = {**DEFAULT_PROFILE}
    for k, v in data.items():
        if k == "custom" and isinstance(v, dict) and isinstance(out.get("custom"), dict):
            out["custom"] = {**out["custom"], **v}
        elif k in out and k != "custom":
            out[k] = v
        elif k == "custom" and isinstance(v, dict):
            out["custom"] = {**DEFAULT_PROFILE["custom"], **v}
    return out


def _strip_wake_prefix(text: str) -> str:
    s = text.strip()
    s = re.sub(
        r"(?is)^\s*(?:hey|ok|okay)[,.\s]+(?:vidatron|veedatron|jansky)\b[,.\s!]*",
        "",
        s,
    )
    s = re.sub(
        r"(?is)^\s*(?:vidatron|veedatron|jansky)\b[,.\s!]+",
        "",
        s,
    )
    return s.strip()


class UserProfileStore:
    """Load/save `user_profile.json` and format a short block for LLM system prompts."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def _ensure_file(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text(
                json.dumps(DEFAULT_PROFILE, indent=2) + "\n",
                encoding="utf-8",
            )

    def load(self) -> dict[str, Any]:
        self._ensure_file()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return {**DEFAULT_PROFILE}
            return _deep_merge_defaults(raw)
        except (OSError, json.JSONDecodeError):
            return {**DEFAULT_PROFILE}

    def save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        merged = _deep_merge_defaults(data)
        self.path.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")

    def format_for_prompt(self) -> str:
        """Reread from disk each time so manual edits apply without restarting."""
        p = self.load()
        lines: list[str] = []
        pref = (p.get("preferred_name") or "").strip()
        name = (p.get("name") or "").strip()
        has_name = bool(pref or name)
        if pref:
            lines.append(f"Preferred name: {pref}")
        elif name:
            lines.append(f"Name: {name}")
        mus = (p.get("music_preferences") or "").strip()
        if mus:
            lines.append(f"Music preferences: {mus}")
        notes = (p.get("notes") or "").strip()
        if notes:
            lines.append(f"Other notes: {notes}")
        custom = p.get("custom")
        if isinstance(custom, dict):
            for k, v in sorted(custom.items()):
                s = str(v).strip() if v is not None else ""
                if s:
                    lines.append(f"{k}: {s}")
        out = "\n".join(lines).strip()
        if has_name and out:
            out = (
                "Address the user by the name below when it feels natural "
                "(e.g. greetings, thanks, goodbyes). Do not use their name in every sentence.\n\n"
                + out
            )
        return out

    def learn_from_text(self, text: str) -> bool:
        """Apply simple phrase patterns; save if anything changed."""
        if not text or len(text) > 2000:
            return False
        t = _strip_wake_prefix(text)
        if not t:
            return False

        data = self.load()
        changed = False

        m_call = re.match(
            r"(?is)^(?:please\s+)?(?:call me|i'?m called|i am called)\s+"
            r"([A-Za-z][A-Za-z\s'.-]{0,48}?)(?:[.!?]|$)",
            t,
        )
        if m_call:
            pref = m_call.group(1).strip().rstrip(".,!?")
            if 1 <= len(pref) < 60:
                data["preferred_name"] = pref
                changed = True

        m_name = re.match(
            r"(?is)^(?:please\s+)?my name is\s+"
            r"([A-Za-z][A-Za-z\s'.-]{0,48}?)(?:[.!?]|$)",
            t,
        )
        if m_name:
            nm = m_name.group(1).strip().rstrip(".,!?")
            if 1 <= len(nm) < 60:
                data["name"] = nm
                changed = True

        m_mus = re.match(
            r"(?is)^(?:please\s+)?"
            r"(?:my (?:favorite )?music(?:\s+preference)?s?\s+(?:is|are)|"
            r"i (?:love|like|prefer|enjoy)(?:\s+to)?(?:\s+listen(?:ing)?\s+to)?)\s+"
            r"(.+)$",
            t,
        )
        if m_mus:
            mus = m_mus.group(1).strip().rstrip(".,!?")
            if mus and len(mus) < 500:
                data["music_preferences"] = mus
                changed = True

        m_rem = re.match(r"(?is)^remember (?:that )?(.+)$", t)
        if m_rem:
            note = m_rem.group(1).strip()
            if note and len(note) < 1000:
                prev = (data.get("notes") or "").strip()
                data["notes"] = (prev + " | " + note) if prev else note
                changed = True

        if changed:
            self.save(data)
        return changed
