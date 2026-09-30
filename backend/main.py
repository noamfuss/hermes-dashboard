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
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

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


# OpenCode Zen's published per-million-token rates for paid models present in
# this database. Unknown models/routes stay unknown rather than getting a guess.
_OPENCODE_ZEN_RATES = {
    "gpt-6-luna": (Decimal("0.10"), Decimal("0.50"), Decimal("0.01"), Decimal("0.125")),
    "gpt-5.6-luna": (Decimal("0.20"), Decimal("1.20"), Decimal("0.02"), Decimal("0.25")),
}
_ONE_MILLION = Decimal("1000000")


def _estimate_opencode_zen_cost(row: dict[str, Any]) -> float | None:
    """Estimate an unknown OpenCode Zen session using its published token rates.

    Session totals do not retain per-request context sizes, so estimates use
    the standard (<=272K) rate tier.
    """
    if str(row.get("billing_provider") or "").lower() not in {"opencode", "opencode-zen"}:
        return None
    base_url = urlparse(str(row.get("billing_base_url") or ""))
    if base_url.hostname != "opencode.ai" or not base_url.path.startswith("/zen/"):
        return None
    cost_status = str(row.get("cost_status") or "unknown").lower()
    if cost_status not in {"unknown", "estimated"}:
        return None
    if (row.get("estimated_cost_usd") or 0) != 0 or (row.get("actual_cost_usd") or 0) != 0:
        return None

    model = str(row.get("model") or "").lower().rsplit("/", 1)[-1]
    rates = _OPENCODE_ZEN_RATES.get(model)
    if rates is None:
        return None
    token_fields = ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens")
    tokens = [max(0, int(row.get(field) or 0)) for field in token_fields]
    if not any(tokens):
        return None
    amount = sum(Decimal(count) * rate / _ONE_MILLION for count, rate in zip(tokens, rates))
    return float(amount)


def _opencode_estimate_totals(
    conn: sqlite3.Connection,
    where: str,
    params: list[Any],
    *,
    by_day: bool = False,
) -> dict[tuple[str, str], float] | float:
    """Compute fallback estimates for eligible rows without changing state.db."""
    scope = f"{where} AND" if where else "WHERE"
    day_column = ", date(datetime(started_at, 'unixepoch')) AS day" if by_day else ""
    rows = conn.execute(
        f"""
        SELECT model, billing_provider, billing_base_url, cost_status,
               estimated_cost_usd, actual_cost_usd,
               input_tokens, output_tokens, cache_read_tokens, cache_write_tokens
               {day_column}
        FROM sessions
        {scope} COALESCE(estimated_cost_usd, 0) = 0
          AND COALESCE(actual_cost_usd, 0) = 0
          AND (cost_status IS NULL OR cost_status = 'unknown')
        """,
        params,
    ).fetchall()
    if not by_day:
        return sum(_estimate_opencode_zen_cost(dict(row)) or 0.0 for row in rows)

    totals: dict[tuple[str, str], float] = {}
    for row in rows:
        data = dict(row)
        amount = _estimate_opencode_zen_cost(data)
        if amount is not None:
            key = (data["day"], data["model"] or "unknown")
            totals[key] = totals.get(key, 0.0) + amount
    return totals


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
            COALESCE(SUM(COALESCE(message_count, 0)), 0) AS total_messages,
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

    result = [dict(r) for r in rows]
    # Fill only unknown OpenCode Zen costs from published rates; all other
    # provider-reported and estimated costs remain unchanged.
    fallback_costs = _opencode_estimate_totals(conn, where, params, by_day=True)
    assert isinstance(fallback_costs, dict)
    for r in result:
        r["estimated_cost_usd"] += fallback_costs.get((r["day"], r["model"]), 0.0)
        inp = r.get("input_tokens", 0) or 0
        cache = r.get("cache_read_tokens", 0) or 0
        cache_write = r.get("cache_write_tokens", 0) or 0
        denom = inp + cache + cache_write
        r["cache_hit_ratio"] = round(cache / denom, 4) if denom > 0 else 0.0
    return result


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
            COALESCE(SUM(COALESCE(message_count, 0)), 0) AS total_messages,
            COALESCE(SUM(estimated_cost_usd), 0) AS total_estimated_cost,
            COALESCE(SUM(actual_cost_usd), 0) AS total_actual_cost,
            COUNT(DISTINCT model) AS model_count
        FROM sessions
        {where}
        """,
        params,
    ).fetchone()

    result = dict(row) if row else {}
    fallback_cost = _opencode_estimate_totals(conn, where, params)
    assert isinstance(fallback_cost, float)
    result["total_estimated_cost"] += fallback_cost
    # Input is uncached prompt tokens; cache writes are prompt misses and belong
    # in the denominator alongside uncached and cache-read tokens.
    inp = result.get("total_input_tokens", 0) or 0
    cache = result.get("total_cache_read_tokens", 0) or 0
    cache_write = result.get("total_cache_write_tokens", 0) or 0
    denom = inp + cache + cache_write
    result["cache_hit_ratio"] = round(cache / denom, 4) if denom > 0 else 0.0
    return result


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
            id, model, title, started_at, ended_at, billing_provider, billing_base_url,
            input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
            estimated_cost_usd, actual_cost_usd, cost_status, cost_source,
            message_count, tool_call_count, source
        FROM sessions
        {where}
        ORDER BY started_at DESC
        LIMIT ? OFFSET ?
        """,
        params + [limit, offset],
    ).fetchall()

    sessions = [dict(r) for r in rows]
    for session in sessions:
        estimate = _estimate_opencode_zen_cost(session)
        if estimate is not None:
            session["estimated_cost_usd"] = estimate
            session["cost_status"] = "estimated"
            session["cost_source"] = "opencode_zen_published_rates"

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "sessions": sessions,
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


# ── Static frontend (registered after all /api routes) ────────────────────
STATIC_DIR = Path(os.environ.get("STATIC_DIR", "/app/static"))


@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    """Serve the built SPA.

    FastAPI matches explicit /api routes first, so this catch-all only fires
    for non-API paths: existing files are served directly, everything else
    falls back to index.html (SPA behavior).
    """
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not found")
    candidate = STATIC_DIR / full_path
    if candidate.is_file():
        return FileResponse(candidate)
    return FileResponse(STATIC_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8100, reload=False)
