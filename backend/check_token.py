"""
Check that a MAX bot token works, before debugging anything else.

The fastest possible smoke test: GET /me returns the bot's identity if the token is
valid. Run this the moment a token arrives — it separates "the token is wrong" from
"our code is wrong", which is worth a lot at 2am.

    export MAX_BOT_TOKEN=...
    python3 backend/check_token.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import httpx  # noqa: E402

from app.config import settings, ssl_context  # noqa: E402


def main() -> int:
    if not settings.has_max_token:
        print("MAX_BOT_TOKEN is not set.")
        print("Put it in .env (see .env.example) or export it.")
        return 1

    url = f"{settings.max_api_base}/me"
    print(f"GET {url}")

    try:
        r = httpx.get(
            url,
            headers={"Authorization": settings.max_bot_token},
            timeout=15.0,
            verify=ssl_context(),
        )
    except httpx.HTTPError as exc:
        print(f"\nRequest failed: {exc}")
        print("Check the network and MAX_API_BASE.")
        return 1

    print(f"HTTP {r.status_code}\n")

    if r.status_code == 401:
        print("Unauthorized — the token is wrong, expired, or revoked.")
        return 1
    if r.status_code == 404:
        print("Not found — MAX_API_BASE may be wrong, or the endpoint moved.")
        print("Re-check dev.max.ru/docs-api; the brief warns that MAX docs change.")
        return 1
    if r.status_code != 200:
        print(r.text[:500])
        return 1

    try:
        me = r.json()
    except ValueError:
        print("Response was not JSON:")
        print(r.text[:500])
        return 1

    print(json.dumps(me, ensure_ascii=False, indent=2))

    if me.get("is_bot"):
        print(f"\nToken works. Bot: @{me.get('username')} ({me.get('name')})")
        print("Next:  python3 backend/runner.py")
        return 0

    print("\nResponded, but is_bot is not true — is this a bot token?")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
