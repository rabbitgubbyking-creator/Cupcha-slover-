from __future__ import annotations

import os
import sqlite3
import time
from collections import defaultdict
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

APP_NAME = "CAPTCHA Community Feedback"
DB_PATH = Path(os.getenv("CAPTCHA_FEEDBACK_DB", "data/feedback.sqlite3"))
CATEGORIES = ("text", "image_tiles", "slider", "checkbox", "other")

app = FastAPI(
    title=APP_NAME,
    description=(
        "Collects optional, anonymous category feedback. It does not accept "
        "challenge images, answers, tokens, or account details."
    ),
    version="0.1.0",
)

_rate_lock = Lock()
_rate: dict[str, list[float]] = defaultdict(list)
RATE_WINDOW_SECONDS = 3600
RATE_LIMIT = 30


class Feedback(BaseModel):
    category: Literal["text", "image_tiles", "slider", "checkbox", "other"]
    predicted_category: Literal["text", "image_tiles", "slider", "checkbox", "other"] | None = None
    app_version: str = Field(default="unknown", max_length=30)


def db_connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            predicted_category TEXT,
            app_version TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    connection.commit()
    return connection


@app.on_event("startup")
def initialize_database() -> None:
    with closing(db_connect()):
        pass


def check_rate_limit(request: Request) -> None:
    # IP is used transiently for rate limiting and is never written to the database.
    client_host = request.client.host if request.client else "unknown"
    now = time.monotonic()
    with _rate_lock:
        recent = [stamp for stamp in _rate[client_host] if now - stamp < RATE_WINDOW_SECONDS]
        if len(recent) >= RATE_LIMIT:
            raise HTTPException(status_code=429, detail="Rate limit reached. Try again later.")
        recent.append(now)
        _rate[client_host] = recent


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": APP_NAME,
        "status": "running",
        "privacy": "No CAPTCHA images, answers, tokens, or account details are collected.",
    }


@app.get("/api/categories")
def categories() -> dict[str, list[str]]:
    return {"categories": list(CATEGORIES)}


@app.post("/api/feedback", status_code=201)
def submit_feedback(payload: Feedback, request: Request) -> dict[str, str]:
    check_rate_limit(request)
    timestamp = datetime.now(timezone.utc).isoformat()
    with closing(db_connect()) as connection:
        connection.execute(
            """
            INSERT INTO feedback (category, predicted_category, app_version, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (payload.category, payload.predicted_category, payload.app_version, timestamp),
        )
        connection.commit()
    return {"status": "accepted", "message": "Thanks. Your category feedback was recorded."}


@app.get("/api/stats")
def get_stats() -> dict:
    with closing(db_connect()) as connection:
        total = connection.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
        rows = connection.execute(
            "SELECT category, COUNT(*) AS votes FROM feedback GROUP BY category"
        ).fetchall()
        matrix_rows = connection.execute(
            """
            SELECT predicted_category, category, COUNT(*) AS votes
            FROM feedback
            WHERE predicted_category IS NOT NULL
            GROUP BY predicted_category, category
            """
        ).fetchall()

    counts = {category: 0 for category in CATEGORIES}
    for row in rows:
        counts[row["category"]] = row["votes"]

    confusion = {category: {actual: 0 for actual in CATEGORIES} for category in CATEGORIES}
    for row in matrix_rows:
        confusion[row["predicted_category"]][row["category"]] = row["votes"]

    compared = sum(sum(values.values()) for values in confusion.values())
    matches = sum(confusion[c][c] for c in CATEGORIES)
    return {
        "total_feedback": total,
        "category_counts": counts,
        "prediction_comparisons": compared,
        "matching_predictions": matches,
        "observed_match_rate": round(matches / compared, 4) if compared else None,
        "confusion_matrix": confusion,
        "note": "This is community feedback analytics, not an automatic CAPTCHA solver.",
    }
