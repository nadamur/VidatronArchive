#!/usr/bin/env python3
"""
One-time Spotify OAuth helper for Vidatron.

1. Create an app at https://developer.spotify.com/dashboard
2. Add Redirect URI: http://127.0.0.1:8888/callback (must match exactly)
3. Export in ai/.env:
     SPOTIFY_CLIENT_ID=...
     SPOTIFY_CLIENT_SECRET=...
4. Run (from the ai/ directory):
     python setup_spotify_token.py

Open the printed URL, approve access, paste the full redirect URL (or ?code=...).
Add SPOTIFY_REFRESH_TOKEN=<printed value> to .env.

Optional: python setup_spotify_token.py --list-devices
  (requires SPOTIFY_REFRESH_TOKEN already set; shows ids for SPOTIFY_DEVICE_ID)
"""

from __future__ import annotations

import argparse
import http.server
import os
import sys
import urllib.parse
from pathlib import Path

import httpx

REDIRECT_HOST = "127.0.0.1"
REDIRECT_PORT = 8888
REDIRECT_URI = f"http://{REDIRECT_HOST}:{REDIRECT_PORT}/callback"
SCOPES = (
    "user-read-playback-state user-modify-playback-state "
    "user-read-currently-playing"
)


def _load_dotenv() -> None:
    env = Path(__file__).resolve().parent / ".env"
    if not env.is_file():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())


def _token_from_refresh(client_id: str, client_secret: str, refresh_token: str) -> str:
    r = httpx.post(
        "https://accounts.spotify.com/api/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=30.0,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def list_devices() -> None:
    _load_dotenv()
    cid = os.environ.get("SPOTIFY_CLIENT_ID", "").strip()
    sec = os.environ.get("SPOTIFY_CLIENT_SECRET", "").strip()
    ref = os.environ.get("SPOTIFY_REFRESH_TOKEN", "").strip()
    if not (cid and sec and ref):
        print("Set SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REFRESH_TOKEN in ai/.env", file=sys.stderr)
        sys.exit(1)
    token = _token_from_refresh(cid, sec, ref)
    r = httpx.get(
        "https://api.spotify.com/v1/me/player/devices",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30.0,
    )
    r.raise_for_status()
    devices = r.json().get("devices", [])
    if not devices:
        print("No devices returned. Open Spotify on a phone or desktop and try again.")
        return
    for d in devices:
        active = " (active)" if d.get("is_active") else ""
        print(f"{d.get('name', '?')}{active}")
        print(f"  id: {d.get('id')}")
        print(f"  type: {d.get('type')}  volume: {d.get('volume_percent')}")


def interactive_oauth(client_id: str, client_secret: str) -> None:
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "show_dialog": "true",
    }
    url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(params)
    print(
        "\n"
        "NOTE: After you approve Spotify, it sends your browser to\n"
        "  http://127.0.0.1:8888/callback?code=...\n"
        "That must hit THIS machine (where this script runs).\n"
        "\n"
        "  • If you opened Spotify on your phone → it will fail (wrong localhost).\n"
        "  • Use a browser on this same computer, OR use an SSH tunnel from your PC:\n"
        "      ssh -L 8888:127.0.0.1:8888 YOU@THIS_HOST\n"
        "    (leave it connected), then open the URL below in the PC browser.\n"
        "  • Or run this script on your laptop (same Client ID/Secret in .env), copy\n"
        "    SPOTIFY_REFRESH_TOKEN to the robot's ai/.env.\n"
        "\n"
        "If the callback page errors but the address bar shows ?code=..., paste the full URL:\n"
        "  ./venv313/bin/python setup_spotify_token.py 'http://127.0.0.1:8888/callback?code=...'\n"
    )
    print("Open this URL in a browser (logged into Spotify):\n")
    print(url)
    print("\nWaiting for callback on http://127.0.0.1:8888 ...\n")

    code_holder: dict[str, str] = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path != "/callback":
                self.send_response(404)
                self.end_headers()
                return
            qs = urllib.parse.parse_qs(parsed.query)
            if "error" in qs:
                code_holder["error"] = qs["error"][0]
            if "code" in qs:
                code_holder["code"] = qs["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<html><body>You can close this tab and return to the terminal.</body></html>"
            )

        def log_message(self, *_args):
            pass

    server = http.server.HTTPServer((REDIRECT_HOST, REDIRECT_PORT), Handler)
    server.timeout = 1.0
    for _ in range(300):
        server.handle_request()
        if "code" in code_holder or "error" in code_holder:
            break
    server.server_close()

    if "error" in code_holder:
        print(f"Spotify returned error: {code_holder['error']}", file=sys.stderr)
        sys.exit(1)
    if "code" not in code_holder:
        print("Timed out waiting for authorization.", file=sys.stderr)
        print("Paste mode: run with the redirect URL as first argument, e.g.", file=sys.stderr)
        print('  python setup_spotify_token.py "http://127.0.0.1:8888/callback?code=..."', file=sys.stderr)
        sys.exit(1)

    code = code_holder["code"]
    r = httpx.post(
        "https://accounts.spotify.com/api/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=30.0,
    )
    if r.status_code != 200:
        print(r.text, file=sys.stderr)
        r.raise_for_status()
    data = r.json()
    refresh = data.get("refresh_token")
    if not refresh:
        print("No refresh_token in response. Try revoking app access in Spotify account settings and run again.", file=sys.stderr)
        sys.exit(1)
    print("\nAdd this line to ai/.env:\n")
    print(f"SPOTIFY_REFRESH_TOKEN={refresh}\n")


def exchange_pasted_url(client_id: str, client_secret: str, pasted: str) -> None:
    if "code=" not in pasted:
        print("Expected a URL containing code=", file=sys.stderr)
        sys.exit(1)
    parsed = urllib.parse.urlparse(pasted.strip())
    qs = urllib.parse.parse_qs(parsed.query)
    if "code" not in qs:
        print("Could not parse code from URL", file=sys.stderr)
        sys.exit(1)
    code = qs["code"][0]
    r = httpx.post(
        "https://accounts.spotify.com/api/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=30.0,
    )
    if r.status_code != 200:
        print(r.text, file=sys.stderr)
        r.raise_for_status()
    data = r.json()
    refresh = data.get("refresh_token")
    if not refresh:
        print("No refresh_token in response.", file=sys.stderr)
        sys.exit(1)
    print("\nAdd this line to ai/.env:\n")
    print(f"SPOTIFY_REFRESH_TOKEN={refresh}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Spotify OAuth helper for Vidatron")
    parser.add_argument(
        "pasted_url",
        nargs="?",
        help="Optional full redirect URL if the local server callback failed",
    )
    parser.add_argument("--list-devices", action="store_true", help="List device ids (needs refresh token in .env)")
    args = parser.parse_args()

    if args.list_devices:
        list_devices()
        return

    _load_dotenv()
    client_id = os.environ.get("SPOTIFY_CLIENT_ID", "").strip()
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        print("Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in ai/.env first.", file=sys.stderr)
        sys.exit(1)

    if args.pasted_url:
        exchange_pasted_url(client_id, client_secret, args.pasted_url)
    else:
        interactive_oauth(client_id, client_secret)


if __name__ == "__main__":
    main()
