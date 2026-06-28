"""OpenBrowserCommand: Opens URLs and searches with input validation."""

from __future__ import annotations

import logging
import re
import webbrowser
from typing import Any
from urllib.parse import quote_plus

from dictator.agent.commands import Command

logger = logging.getLogger(__name__)

ALLOWED_SCHEMES = ("http://", "https://")
URL_PATTERN = re.compile(r"^https?://[^\s]+$")


class OpenBrowserCommand(Command):
    @property
    def name(self) -> str:
        return "open_browser"

    @property
    def description(self) -> str:
        return "Open a web browser, optionally searching for a query or opening a URL"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "app_name": {
                    "type": "string",
                    "description": "Browser or site name (e.g. chrome, youtube)",
                    "default": "default",
                },
                "search_query": {
                    "type": "string",
                    "description": "Text to search for",
                },
                "url": {
                    "type": "string",
                    "description": "Direct URL to open",
                },
            },
            "required": [],
        }

    def validate(self, args: dict[str, Any]) -> str | None:
        url = args.get("url")
        if url:
            if not any(url.startswith(scheme) for scheme in ALLOWED_SCHEMES):
                return f"URL must start with http:// or https:// (got: {url[:30]})"
            if not URL_PATTERN.match(url):
                return "URL contains invalid characters"
        return None

    def execute(self, args: dict[str, Any]) -> str:
        query = args.get("search_query")
        url = args.get("url")
        app = args.get("app_name", "default").lower()

        target_url = url

        if "youtube" in app:
            if query:
                target_url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
            else:
                target_url = "https://www.youtube.com"
        elif "google" in app and not target_url:
            target_url = "https://www.google.com"

        if not target_url:
            if query:
                target_url = f"https://www.google.com/search?q={quote_plus(query)}"
            else:
                target_url = "https://www.google.com"

        try:
            webbrowser.open(target_url)
            return f"Opened: {query if query else target_url}"
        except Exception as e:
            return f"Failed to open browser: {e}"
