"""
Spotify Web API: search tracks and start playback on the user's active device.

Requires Spotify Premium for /me/player/play. Uses a refresh token (see setup_spotify_token.py).
"""

from __future__ import annotations

import re
import time
from typing import Tuple

import httpx

TOKEN_URL = "https://accounts.spotify.com/api/token"
API_BASE = "https://api.spotify.com/v1"


class SpotifyError(Exception):
    """Spotify API or configuration error with a user-safe message."""


def _normalize_search_query(q: str) -> str:
    q = q.strip()
    if len(q) < 2:
        return q
    q = re.sub(
        r"(?i)\s*(?:please|thanks|thank you|now|for me)\s*$",
        "",
        q,
    ).strip()
    return q


class SpotifyTool:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        device_id: str = "",
    ):
        self.client_id = client_id.strip()
        self.client_secret = client_secret.strip()
        self.refresh_token = refresh_token.strip()
        self.device_id = (device_id or "").strip()
        self._access_token: str = ""
        self._token_expires_at: float = 0.0

    def _refresh_access_token(self) -> None:
        with httpx.Client(timeout=30.0) as client:
            r = client.post(
                TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
            )
        if r.status_code != 200:
            try:
                detail = r.json()
            except Exception:
                detail = r.text
            raise SpotifyError(
                f"Spotify login failed ({r.status_code}). Check SPOTIFY_CLIENT_ID, "
                f"SPOTIFY_CLIENT_SECRET, and SPOTIFY_REFRESH_TOKEN. {detail}"
            )
        data = r.json()
        self._access_token = data["access_token"]
        self._token_expires_at = time.time() + int(data.get("expires_in", 3600))

    def _headers(self) -> dict:
        if not self._access_token or time.time() >= self._token_expires_at - 60:
            self._refresh_access_token()
        return {"Authorization": f"Bearer {self._access_token}"}

    def _with_token_retry(self, fn):
        try:
            return fn(self._headers())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                self._access_token = ""
                self._refresh_access_token()
                return fn(self._headers())
            raise

    def _list_devices(self, client: httpx.Client, headers: dict) -> list:
        r = client.get(f"{API_BASE}/me/player/devices", headers=headers)
        r.raise_for_status()
        return r.json().get("devices", []) or []

    def _pick_device_id(self, devices: list) -> str | None:
        for d in devices:
            if d.get("is_active") and d.get("id"):
                return d["id"]
        for d in devices:
            if d.get("id") and not d.get("is_restricted"):
                return d["id"]
        return None

    def _transfer_to_device(self, client: httpx.Client, headers: dict, device_id: str) -> None:
        r = client.put(
            f"{API_BASE}/me/player",
            json={"device_ids": [device_id], "play": False},
            headers={**headers, "Content-Type": "application/json"},
        )
        if r.status_code not in (200, 204):
            r.raise_for_status()

    def _search_request(self, client: httpx.Client, headers: dict, q: str, limit: int):
        r = client.get(
            f"{API_BASE}/search",
            params={"q": q, "type": "track", "limit": limit},
            headers=headers,
        )
        r.raise_for_status()
        return r

    def search_track_uri(self, query: str) -> Tuple[str | None, str]:
        """Return (spotify_uri, human_label) for the best track match."""
        q = _normalize_search_query(query)
        if not q:
            return None, ""

        with httpx.Client(timeout=30.0) as client:

            def search(h, text: str, limit: int = 1):
                r = self._search_request(client, h, text, limit)
                return r

            r = self._with_token_retry(lambda h: search(h, q, 1))
            tracks = r.json().get("tracks", {}).get("items", [])
            if not tracks and len(q.split()) > 5:
                shorter = " ".join(q.split()[:5])
                r2 = self._with_token_retry(lambda h: search(h, shorter, 1))
                tracks = r2.json().get("tracks", {}).get("items", [])

            if not tracks:
                return None, ""
            t = tracks[0]
            uri = t.get("uri")
            name = t.get("name", "Unknown")
            artists = ", ".join(a["name"] for a in t.get("artists", []))
            label = f"{name} by {artists}" if artists else name
            return uri, label

    def play_uri(self, uri: str) -> None:
        body = {"uris": [uri]}

        with httpx.Client(timeout=30.0) as client:

            def try_play(h, dev: str | None):
                params = {}
                if dev:
                    params["device_id"] = dev
                r = client.put(
                    f"{API_BASE}/me/player/play",
                    params=params or None,
                    json=body,
                    headers={**h, "Content-Type": "application/json"},
                )
                return r

            def resolve_and_play(h):
                primary = self.device_id or None
                r = try_play(h, primary)
                if r.status_code == 404 and not primary:
                    devices = self._list_devices(client, h)
                    dev = self._pick_device_id(devices)
                    if not dev:
                        raise SpotifyError(
                            "No Spotify devices found. Open Spotify on your phone, tablet, or "
                            "computer, or set SPOTIFY_DEVICE_ID from "
                            "python setup_spotify_token.py --list-devices"
                        )
                    self._transfer_to_device(client, h, dev)
                    time.sleep(0.35)
                    r = try_play(h, dev)
                if r.status_code == 404:
                    raise SpotifyError(
                        "No active Spotify device. Open the Spotify app and try again, or set "
                        "SPOTIFY_DEVICE_ID from python setup_spotify_token.py --list-devices"
                    )
                if r.status_code == 403:
                    try:
                        err = r.json()
                    except Exception:
                        err = {}
                    msg = (err.get("error") or {}).get("message") or r.text
                    raise SpotifyError(
                        "Spotify refused playback. A Premium account is required for the Web API, "
                        f"and the account must own the content. ({msg})"
                    )
                if r.status_code not in (200, 204):
                    r.raise_for_status()
                return r

            self._with_token_retry(resolve_and_play)

    def pause(self) -> None:
        with httpx.Client(timeout=30.0) as client:

            def call(h):
                params = {}
                if self.device_id:
                    params["device_id"] = self.device_id
                r = client.put(
                    f"{API_BASE}/me/player/pause",
                    params=params or None,
                    headers=h,
                )
                if r.status_code == 404 and not self.device_id:
                    devices = self._list_devices(client, h)
                    dev = self._pick_device_id(devices)
                    if dev:
                        self._transfer_to_device(client, h, dev)
                        time.sleep(0.25)
                        r = client.put(
                            f"{API_BASE}/me/player/pause",
                            params={"device_id": dev},
                            headers=h,
                        )
                if r.status_code == 404:
                    raise SpotifyError(
                        "No active Spotify device to pause. Open Spotify on one of your devices first."
                    )
                if r.status_code not in (200, 204):
                    r.raise_for_status()
                return r

            self._with_token_retry(call)

    def play_search(self, query: str) -> str:
        """Search and play; returns a short phrase for TTS."""
        q = _normalize_search_query(query)
        uri, label = self.search_track_uri(q)
        if not uri:
            return f"I could not find a track matching {q!r} on Spotify."
        try:
            self.play_uri(uri)
        except SpotifyError:
            raise
        except Exception as e:
            raise SpotifyError(f"Could not start Spotify playback: {e}") from e
        return f"Playing {label} on Spotify."
