"""Strategic Profit Model API.

Run with:  uv run uvicorn main:app --reload --port 8000
"""

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

import capm
import edgar
import yahoo

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

SYMBOL_RE = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,9}$")
METRICS = ["net_sales", "net_income", "total_assets", "shareholders_equity"]
# Don't hammer the sources when a requested year simply doesn't exist yet.
MISSING_YEAR_REFETCH_AFTER = timedelta(hours=12)

app = FastAPI(title="Strategic Profit Model")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def data_path(symbol: str) -> Path:
    return DATA_DIR / f"{symbol}.json"


def load(symbol: str) -> dict | None:
    path = data_path(symbol)
    return json.loads(path.read_text()) if path.exists() else None


def collect(symbol: str) -> dict:
    """Fetch from EDGAR, fill gaps from Yahoo Finance, add CAPM inputs, save."""
    sources_errors = []

    sec = yf_data = None
    try:
        sec = edgar.fetch(symbol)
    except Exception as exc:
        sources_errors.append(f"SEC EDGAR: {exc}")
    try:
        yf_data = yahoo.fetch(symbol)
    except Exception as exc:
        sources_errors.append(f"Yahoo Finance: {exc}")

    if not sec and not yf_data:
        detail = "; ".join(sources_errors) or "no data from SEC EDGAR or Yahoo Finance"
        raise HTTPException(404, f"No financial data found for {symbol} ({detail})")

    years: dict[str, dict] = {k: dict(v) for k, v in (sec or {}).get("years", {}).items()}
    for fy, yrow in (yf_data or {}).get("years", {}).items():
        row = years.get(fy)
        if row is None:
            years[fy] = dict(yrow)
            continue
        filled = False
        for m in METRICS:
            if row.get(m) is None and yrow.get(m) is not None:
                row[m] = yrow[m]
                filled = True
        if filled:
            row["source"] = "SEC EDGAR + Yahoo Finance"

    # Only keep years where at least one of the four key elements is known.
    years = {
        fy: row
        for fy, row in sorted(years.items())
        if any(row.get(m) is not None for m in METRICS)
    }

    rates = capm.inputs_for(symbol, {fy: r["fiscal_year_end"] for fy, r in years.items()})
    for fy, row in years.items():
        row.update(rates.get(fy, {}))

    record = {
        "symbol": symbol,
        "name": (sec or {}).get("name") or (yf_data or {}).get("name") or symbol,
        "cik": (sec or {}).get("cik"),
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        # EDGAR values are USD; Yahoo reports in the filer's own currency.
        "currency": "USD" if sec else (yf_data.get("currency") or "USD"),
        "years": years,
    }
    data_path(symbol).write_text(json.dumps(record, indent=2))
    return record


def ratio(num, den):
    if num is None or den in (None, 0):
        return None
    return num / den


def build_year(fy: str, row: dict, mrp: float) -> dict:
    ns, ni = row.get("net_sales"), row.get("net_income")
    ta, se = row.get("total_assets"), row.get("shareholders_equity")
    rf, beta = row.get("risk_free_rate"), row.get("beta")
    beta_estimated = beta is None
    beta_used = 1.0 if beta_estimated else beta
    coe = rf + beta_used * mrp if rf is not None else None
    roe = ratio(ni, se)
    return {
        "year": int(fy),
        "fiscal_year_end": row.get("fiscal_year_end"),
        "source": row.get("source"),
        "net_sales": ns,
        "net_income": ni,
        "total_assets": ta,
        "total_equity": ta,  # liabilities + shareholders' equity, as in the book
        "shareholders_equity": se,
        "profit_margin": ratio(ni, ns),
        "asset_turnover": ratio(ns, ta),
        "return_on_assets": ratio(ni, ta),
        "financial_leverage": ratio(ta, se),
        "return_on_equity": roe,
        "risk_free_rate": rf,
        "beta": beta_used,
        "beta_estimated": beta_estimated,
        "cost_of_equity": coe,
        "equity_spread": roe - coe if roe is not None and coe is not None else None,
    }


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/data/{symbol}")
def stored_data(symbol: str):
    """Return the collected data file, data/<SYMBOL>.json, as saved."""
    symbol = symbol.strip().upper()
    if not SYMBOL_RE.match(symbol):
        raise HTTPException(400, f"Invalid symbol: {symbol}")
    record = load(symbol)
    if record is None:
        raise HTTPException(404, f"No data file for {symbol}")
    return record


@app.get("/api/model")
def model(
    symbol: str = Query(..., min_length=1, max_length=10),
    start: int = Query(..., ge=1900, le=2100),
    end: int = Query(..., ge=1900, le=2100),
    refresh: bool = False,
    mrp: float = Query(capm.DEFAULT_MARKET_RISK_PREMIUM, ge=0, le=0.25),
):
    symbol = symbol.strip().upper()
    if not SYMBOL_RE.match(symbol):
        raise HTTPException(400, f"Invalid symbol: {symbol}")
    if start > end:
        raise HTTPException(400, "Start year must be on or before end year")

    record = load(symbol)
    wanted = {str(start), str(end)}
    if refresh or record is None:
        record = collect(symbol)
    elif not wanted <= record["years"].keys():
        fetched = datetime.fromisoformat(record["fetched_at"])
        if datetime.now(timezone.utc) - fetched > MISSING_YEAR_REFETCH_AFTER:
            record = collect(symbol)

    available = sorted(int(y) for y in record["years"])
    missing = sorted(int(y) for y in wanted - record["years"].keys())
    if missing:
        span = f"{available[0]}-{available[-1]}" if available else "none"
        raise HTTPException(
            422,
            f"No data for {symbol} fiscal year(s) {', '.join(map(str, missing))}. "
            f"Available years: {span}.",
        )

    return {
        "symbol": symbol,
        "name": record["name"],
        "fetched_at": record["fetched_at"],
        "currency": record.get("currency", "USD"),
        "data_file": f"data/{symbol}.json",
        "available_years": available,
        "market_risk_premium": mrp,
        "start": build_year(str(start), record["years"][str(start)], mrp),
        "end": build_year(str(end), record["years"][str(end)], mrp),
    }
