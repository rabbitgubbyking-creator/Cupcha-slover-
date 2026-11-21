from __future__ import annotations

import argparse
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


CATEGORIES = ("text", "image_tiles", "slider", "checkbox", "other")


def ask_category(prompt: str, optional: bool = False) -> str | None:
    choices = ", ".join(CATEGORIES)

    while True:
        suffix = " (press Enter to skip)" if optional else ""
        answer = input(f"{prompt} [{choices}]{suffix}: ").strip().lower()

        if optional and not answer:
            return None
        if answer in CATEGORIES:
            return answer

        print("That category is not on the list. Try again.")


def validate_server_url(value: str) -> str:
    value = value.rstrip("/")
    parsed = urlsplit(value)
    local_hosts = {"localhost", "127.0.0.1", "::1"}

    if not parsed.hostname:
        raise ValueError("Enter a full server URL, including https://.")
    if parsed.scheme != "https" and not (
        parsed.scheme == "http" and parsed.hostname in local_hosts
    ):
        raise ValueError("Use HTTPS for a hosted server. HTTP is allowed on localhost only.")
    if parsed.username or parsed.password:
        raise ValueError("Do not put login details in the server URL.")

    return value


def send_feedback(server: str, payload: dict[str, str | None]) -> None:
    data = json.dumps(payload).encode("utf-8")
    request = Request(
        f"{server}/api/feedback",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urlopen(request, timeout=15) as response:
        print(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Send a manually reviewed challenge-category report."
    )
    parser.add_argument("--server", required=True, help="Feedback server URL")
    parser.add_argument("--version", default="0.2.0", help="Client version")
    args = parser.parse_args()

    try:
        server = validate_server_url(args.server)
        category = ask_category("Which type of challenge did you see")
        predicted = ask_category(
            "Which type did the detector report", optional=True
        )
        send_feedback(
            server,
            {
                "category": category,
                "predicted_category": predicted,
                "app_version": args.version[:30],
            },
        )
    except (HTTPError, URLError, TimeoutError) as error:
        print(f"Could not send feedback: {error}", file=sys.stderr)
        return 1
    except (ValueError, KeyboardInterrupt) as error:
        if isinstance(error, KeyboardInterrupt):
            print("\nCancelled.", file=sys.stderr)
        else:
            print(error, file=sys.stderr)
        return 1

    print("Feedback saved. Thanks for helping with the category data.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
