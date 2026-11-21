from __future__ import annotations

import os
import sqlite3
import time
from collections import OrderedDict, deque
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Iterator, Literal

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field


Category = Literal["text", "image_tiles", "slider", "checkbox", "other"]
CATEGORIES = ("text", "image_tiles", "slider", "checkbox", "other")
DB_PATH = Path(os.getenv("CAPTCHA_FEEDBACK_DB", "data/feedback.sqlite3"))
RATE_LIMIT = 30
RATE_WINDOW = 60 * 60
MAX_TRACKED_CLIENTS = 2_000


class Feedback(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: Category
    predicted_category: Category | None = None
    app_version: str = Field(
        default="unknown",
        min_length=1,
        max_length=30,
        pattern=r"^[A-Za-z0-9._+-]+$",
    )


class RateLimiter:
    """Small in-memory limit for a single-process deployment."""

    def __init__(self) -> None:
        self._requests: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = Lock()

    def check(self, client: str) -> None:
        now = time.monotonic()
        cutoff = now - RATE_WINDOW

        with self._lock:
            # Drop expired entries so the in-memory list stays bounded.
            for address in list(self._requests):
                hits = self._requests[address]
                while hits and hits[0] <= cutoff:
                    hits.popleft()
                if not hits:
                    del self._requests[address]

            if client not in self._requests and len(self._requests) >= MAX_TRACKED_CLIENTS:
                self._requests.popitem(last=False)

            hits = self._requests.setdefault(client, deque())
            if len(hits) >= RATE_LIMIT:
                raise HTTPException(
                    status_code=429,
                    detail="Too many submissions. Try again later.",
                )

            hits.append(now)
            self._requests.move_to_end(client)


limiter = RateLimiter()


@contextmanager
def database() -> Iterator[sqlite3.Connection]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=10)
    try:
        connection.execute("PRAGMA journal_mode = WAL")
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def create_tables() -> None:
    with database() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY,
                category TEXT NOT NULL,
                predicted_category TEXT,
                app_version TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_tables()
    yield


app = FastAPI(
    title="CAPTCHA Feedback",
    description="Collects anonymous, manually submitted challenge-category feedback.",
    version="0.2.0",
    lifespan=lifespan,
)


@app.get("/")
def home() -> dict[str, str]:
    return {
        "name": "CAPTCHA Feedback",
        "status": "running",
        "purpose": "Collect category feedback and report aggregate statistics.",
        "limits": "This service does not solve or approve CAPTCHA challenges.",
    }


@app.get("/api/categories")
def categories() -> dict[str, list[str]]:
    return {"categories": list(CATEGORIES)}


@app.post("/api/feedback", status_code=201)
def submit_feedback(payload: Feedback, request: Request) -> dict[str, str]:
    client = request.client.host if request.client else "unknown"
    limiter.check(client)

    created_at = datetime.now(timezone.utc).isoformat()
    with database() as connection:
        connection.execute(
            """
            INSERT INTO feedback (category, predicted_category, app_version, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                payload.category,
                payload.predicted_category,
                payload.app_version,
                created_at,
            ),
        )

    return {"status": "saved"}


@app.get("/api/stats")
def stats() -> dict:
    with database() as connection:
        total = connection.execute(
            "SELECT COUNT(*) FROM feedback"
        ).fetchone()[0]
        category_rows = connection.execute(
            "SELECT category, COUNT(*) FROM feedback GROUP BY category"
        ).fetchall()
        comparison_rows = connection.execute(
            """
            SELECT predicted_category, category, COUNT(*)
            FROM feedback
            WHERE predicted_category IS NOT NULL
            GROUP BY predicted_category, category
            """
        ).fetchall()

    category_counts = {category: 0 for category in CATEGORIES}
    for category, count in category_rows:
        category_counts[category] = count

    matrix = {
        predicted: {actual: 0 for actual in CATEGORIES}
        for predicted in CATEGORIES
    }
    for predicted, actual, count in comparison_rows:
        matrix[predicted][actual] = count

    compared = sum(sum(row.values()) for row in matrix.values())
    matches = sum(matrix[category][category] for category in CATEGORIES)

    return {
        "total_feedback": total,
        "category_counts": category_counts,
        "prediction_comparisons": compared,
        "matching_predictions": matches,
        "reported_match_rate": round(matches / compared, 4) if compared else None,
        "confusion_matrix": matrix,
        "note": "Self-reported feedback only; this is not a verified accuracy score.",
    }
