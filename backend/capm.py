"""Cost of equity capital inputs via CAPM: k_e = r_f + beta * MRP.

- r_f: average 10-year Treasury yield (FRED series GS10) over the 12 months
  ending at the fiscal-year end.
- beta: slope of 60 monthly stock returns against the S&P 500 ending at the
  fiscal-year end (minimum 24 months).
"""

import io
from datetime import date

import httpx
import pandas as pd
import yfinance as yf

GS10_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=GS10"
MARKET_INDEX = "^GSPC"
DEFAULT_MARKET_RISK_PREMIUM = 0.055


def _treasury_series() -> pd.Series | None:
    try:
        resp = httpx.get(GS10_URL, timeout=30, follow_redirects=True)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text))
        df.columns = ["date", "value"]
        df["date"] = pd.to_datetime(df["date"])
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        return df.dropna().set_index("date")["value"] / 100
    except Exception:
        return None


def _monthly_returns(symbol: str) -> pd.Series | None:
    try:
        hist = yf.Ticker(symbol).history(period="max", interval="1mo", auto_adjust=True)
    except Exception:
        return None
    if hist is None or hist.empty:
        return None
    close = hist["Close"]
    close.index = close.index.tz_localize(None).to_period("M")
    close = close[~close.index.duplicated(keep="last")]
    return close.pct_change().dropna()


def inputs_for(symbol: str, year_ends: dict[str, str]) -> dict[str, dict]:
    """Return {fiscal_year: {"risk_free_rate", "beta"}} for each fiscal year end."""
    treasury = _treasury_series()
    stock = _monthly_returns(symbol)
    market = _monthly_returns(MARKET_INDEX)
    paired = None
    if stock is not None and market is not None:
        paired = pd.concat([stock, market], axis=1, join="inner", keys=["s", "m"])

    out = {}
    for fy, end_iso in year_ends.items():
        end = pd.Period(date.fromisoformat(end_iso), "M")
        rf = beta = None

        if treasury is not None:
            window = treasury[
                (treasury.index.to_period("M") > end - 12)
                & (treasury.index.to_period("M") <= end)
            ]
            if len(window):
                rf = round(float(window.mean()), 5)

        if paired is not None:
            window = paired[(paired.index > end - 60) & (paired.index <= end)]
            if len(window) >= 24 and window["m"].var() > 0:
                beta = round(float(window["s"].cov(window["m"]) / window["m"].var()), 3)

        out[fy] = {"risk_free_rate": rf, "beta": beta}
    return out
