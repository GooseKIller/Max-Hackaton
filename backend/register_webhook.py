"""Explicit deployment step; never register on application startup.

Stops polling delivery for this bot! Coordinate the switch with the teammate.
Usage: python backend/register_webhook.py https://your-host/webhook --confirm-switch
"""
import argparse
import re
from urllib.parse import urlsplit

from app.config import settings
from app.max_client import MaxClient


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("--confirm-switch", action="store_true")
    args = parser.parse_args()
    url = urlsplit(args.url)
    if url.scheme != "https" or not url.hostname or url.username or url.password or url.port not in (None, 443) or url.query or url.fragment:
        parser.error("Expected public HTTPS webhook URL on port 443")
    if not args.confirm_switch:
        parser.error("Stop the team's polling process, then pass --confirm-switch")
    if not re.fullmatch(r"[A-Za-z0-9_-]{32,256}", settings.max_webhook_secret):
        parser.error("Set a random MAX_WEBHOOK_SECRET of 32–256 characters in .env")
    client = MaxClient(settings.max_bot_token, settings.max_api_base)
    try:
        client.subscribe_webhook(args.url, settings.max_webhook_secret)
        print("Webhook registered. Do not run polling alongside it.")
    finally:
        client.close()


if __name__ == "__main__":
    main()
