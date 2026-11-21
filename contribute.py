from __future__ import annotations

import argparse
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

CATEGORIES = ("text", "image_tiles", "slider", "checkbox", "other")


def choose(prompt: str, optional: bool = False) -> str | None:
    options = ", ".join(CATEGORIES)
    while True:
        value = input(f"{prompt} ({options})" + (" or Enter to skip: " if optional else ": "))
        value = value.strip().lower()
        if optional and not value:
            return None
        if value in CATEGORIES:
            return value
        print("Choose one of the listed categories.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Send optional category feedback")
    parser.add_argument("--server", required=True, help="Community server URL, e.g. https://example.com")
    parser.add_argument("--version", default="0.1.0", help="Client version")
    args = parser.parse_args()

    actual = choose("What kind of challenge did you see")
    predicted = choose("What category did the detector show", optional=True)

    payload = json.dumps({
        "category": actual,
        "predicted_category": predicted,
        "app_version": args.version[:30],
    }).encode("utf-8")

    url = args.server.rstrip("/") + "/api/feedback"
    request = Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=15) as response:
            print(response.read().decode("utf-8"))
        return 0
    except HTTPError as exc:
        print(f"Server rejected the feedback: HTTP {exc.code}", file=sys.stderr)
    except (URLError, TimeoutError) as exc:
        print(f"Could not reach the server: {exc}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
