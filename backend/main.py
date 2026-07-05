"""
Token usage dashboard backend.

Reads Hermes state.db (read-only) and exposes REST endpoints
for daily token/cost aggregation by model.
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

# ── Config ────────────────────────────────────────────────────────────────
HERMES_HOME = Path(os.environ.get("HERMES_HOME", "/opt/data"))
STATE_DB = HERMES_HOME / "state.db"

# ── Database ──────────────────────────────────────────────────────────────


def get_db() -> sqlite3.Connection:
    """Open a read-only connection to the state database."""
    if not STATE_DB.exists():
        raise RuntimeError(f"state.db not found at {STATE_DB}")
    conn = sqlite3.connect(f"file:{STATE_DB}?mode=ro", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


# ── Query helpers ─────────────────────────────────────────────────────────


def daily_totals(
    conn: sqlite3.Connection,
    days: int | None = 30,
    start_date: str | None = None,
    end_date: str | None = None,
    model_filter: str | None = None,
) -> list[dict[str, Any]]:
    """Aggregate token/cost by day and model."""
    clauses: list[str] = []
    params: list[Any] = []

    if days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        clauses.append("datetime(started_at, 'unixepoch') >= ?")
        params.append(cutoff.isoformat())

    if start_date:
        clauses.append("datetime(started_at, 'unixepoch') >= ?")
        params.append(f"{start_date}T00:00:00")

    if end_date:
        clauses.append("datetime(started_at, 'unixepoch') <= ?")
        params.append(f"{end_date}T23:59:59")

    if model_filter:
        clauses.append("model = ?")
        params.append(model_filter)

    where = "WHERE " + " AND ".join(clauses) if clauses else ""

    rows = conn.execute(
        f"""
        SELECT
            date(datetime(started_at, 'unixepoch')) as day,
            COALESCE(model, 'unknown') as model,
            COALESCE(SUM(COALESCE(input_tokens, 0)), 0) AS input_tokens,
            COALESCE(SUM(COALESCE(output_tokens, 0)), 0) AS output_tokens,
            COALESCE(SUM(COALESCE(cache_read_tokens, 0)), 0) AS cache_read_tokens,
            COALESCE(SUM(COALESCE(cache_write_tokens, 0)), 0) AS cache_write_tokens,
            COALESCE(SUM(COALESCE(input_tokens, 0) + COALESCE(output_tokens, 0) + COALESCE(cache_read_tokens, 0) + COALESCE(cache_write_tokens, 0)), 0) AS total_tokens,
            COALESCE(SUM(estimated_cost_usd), 0) AS estimated_cost_usd,
            COALESCE(SUM(actual_cost_usd), 0) AS actual_cost_usd,
            COUNT(*) AS session_count
        FROM sessions
        {where}
        GROUP BY day, model
        ORDER BY day ASC, model ASC
        """,
        params,
    ).fetchall()

    return [dict(r) for r in rows]


def summary_stats(
    conn: sqlite3.Connection,
    days: int | None = 30,
    start_date: str | None = None,
    end_date: str | None = None,
    model_filter: str | None = None,
) -> dict[str, Any]:
    """Overall summary statistics."""
    clauses: list[str] = []
    params: list[Any] = []

    if days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        clauses.append("datetime(started_at, 'unixepoch') >= ?")
        params.append(cutoff.isoformat())

    if start_date:
        clauses.append("datetime(started_at, 'unixepoch') >= ?")
        params.append(f"{start_date}T00:00:00")

    if end_date:
        clauses.append("datetime(started_at, 'unixepoch') <= ?")
        params.append(f"{end_date}T23:59:59")

    if model_filter:
        clauses.append("model = ?")
        params.append(model_filter)

    where = "WHERE " + " AND ".join(clauses) if clauses else ""

    row = conn.execute(
        f"""
        SELECT
            COUNT(*) AS total_sessions,
            COALESCE(SUM(input_tokens), 0) AS total_input_tokens,
            COALESCE(SUM(output_tokens), 0) AS total_output_tokens,
            COALESCE(SUM(cache_read_tokens), 0) AS total_cache_read_tokens,
            COALESCE(SUM(cache_write_tokens), 0) AS total_cache_write_tokens,
            COALESCE(SUM(input_tokens + output_tokens + cache_read_tokens + cache_write_tokens), 0) AS total_tokens,
            COALESCE(SUM(estimated_cost_usd), 0) AS total_estimated_cost,
            COALESCE(SUM(actual_cost_usd), 0) AS total_actual_cost,
            COUNT(DISTINCT model) AS model_count
        FROM sessions
        {where}
        """,
        params,
    ).fetchone()

    return dict(row) if row else {}


def models_list(conn: sqlite3.Connection) -> list[str]:
    """Return all distinct model names."""
    rows = conn.execute(
        "SELECT DISTINCT COALESCE(model, 'unknown') as model FROM sessions ORDER BY model"
    ).fetchall()
    return [r["model"] for r in rows]


def sessions_list(
    conn: sqlite3.Connection,
    days: int | None = 30,
    start_date: str | None = None,
    end_date: str | None = None,
    model_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Paginated list of recent sessions."""
    clauses: list[str] = []
    params: list[Any] = []

    if days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        clauses.append("datetime(started_at, 'unixepoch') >= ?")
        params.append(cutoff.isoformat())

    if start_date:
        clauses.append("datetime(started_at, 'unixepoch') >= ?")
        params.append(f"{start_date}T00:00:00")

    if end_date:
        clauses.append("datetime(started_at, 'unixepoch') <= ?")
        params.append(f"{end_date}T23:59:59")

    if model_filter:
        clauses.append("model = ?")
        params.append(model_filter)

    where = "WHERE " + " AND ".join(clauses) if clauses else ""

    # Total count
    count_row = conn.execute(f"SELECT COUNT(*) AS cnt FROM sessions {where}", params).fetchone()
    total = count_row["cnt"] if count_row else 0

    # Paginated results
    rows = conn.execute(
        f"""
        SELECT
            id, model, title, started_at, ended_at,
            input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
            estimated_cost_usd, actual_cost_usd, cost_status, cost_source,
            billing_provider, message_count, tool_call_count, source
        FROM sessions
        {where}
        ORDER BY started_at DESC
        LIMIT ? OFFSET ?
        """,
        params + [limit, offset],
    ).fetchall()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "sessions": [dict(r) for r in rows],
    }


# ── FastAPI App ───────────────────────────────────────────────────────────

db_conn: sqlite3.Connection | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_conn
    db_conn = get_db()
    yield
    if db_conn:
        db_conn.close()


app = FastAPI(
    title="Hermes Token Dashboard",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/stats/summary")
def api_summary(
    days: int | None = Query(30, ge=0, description="Number of days to look back. 0 = all time."),
    start_date: str | None = Query(None, description="Start date YYYY-MM-DD (overrides days)"),
    end_date: str | None = Query(None, description="End date YYYY-MM-DD (overrides days end)"),
    model: str | None = Query(None, description="Filter by model name"),
):
    n_days = None if days == 0 else days
    return summary_stats(db_conn, days=n_days, start_date=start_date, end_date=end_date, model_filter=model)


@app.get("/api/stats/daily")
def api_daily(
    days: int | None = Query(30, ge=0, description="Number of days to look back. 0 = all time."),
    start_date: str | None = Query(None, description="Start date YYYY-MM-DD"),
    end_date: str | None = Query(None, description="End date YYYY-MM-DD"),
    model: str | None = Query(None, description="Filter by model name"),
):
    n_days = None if days == 0 else days
    data = daily_totals(db_conn, days=n_days, start_date=start_date, end_date=end_date, model_filter=model)
    return data


@app.get("/api/stats/models")
def api_models():
    return models_list(db_conn)


@app.get("/api/stats/sessions")
def api_sessions(
    days: int | None = Query(30, ge=0, description="Number of days to look back. 0 = all time."),
    start_date: str | None = Query(None, description="Start date YYYY-MM-DD"),
    end_date: str | None = Query(None, description="End date YYYY-MM-DD"),
    model: str | None = Query(None, description="Filter by model"),
    limit: int = Query(50, ge=1, le=500, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
):
    n_days = None if days == 0 else days
    return sessions_list(
        db_conn, days=n_days, start_date=start_date, end_date=end_date,
        model_filter=model, limit=limit, offset=offset,
    )


@app.get("/api/health")
def health():
    return {"status": "ok", "state_db": str(STATE_DB)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8100, reload=True)
