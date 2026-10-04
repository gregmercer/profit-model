"""Fallback annual figures from Yahoo Finance (about the last 4-5 fiscal years)."""

import math

import yfinance as yf

from fiscal import fiscal_year_for

ROWS = {
    "net_sales": ("financials", ["Total Revenue", "Operating Revenue"]),
    "net_income": ("financials", ["Net Income", "Net Income Common Stockholders"]),
    "total_assets": ("balance_sheet", ["Total Assets"]),
    "shareholders_equity": (
        "balance_sheet",
        ["Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest"],
    ),
}


def _clean(value) -> float | None:
    if value is None:
        return None
    value = float(value)
    return None if math.isnan(value) else value


def fetch(symbol: str) -> dict | None:
    ticker = yf.Ticker(symbol)
    tables = {"financials": ticker.financials, "balance_sheet": ticker.balance_sheet}
    if all(t is None or t.empty for t in tables.values()):
        return None

    years: dict[str, dict] = {}
    for metric, (table_name, labels) in ROWS.items():
        table = tables[table_name]
        if table is None or table.empty:
            continue
        label = next((l for l in labels if l in table.index), None)
        if label is None:
            continue
        for col, value in table.loc[label].items():
            end = col.date()
            row = years.setdefault(
                str(fiscal_year_for(end)),
                {"fiscal_year_end": end.isoformat(), "source": "Yahoo Finance"},
            )
            row[metric] = _clean(value)

    for row in years.values():
        for metric in ROWS:
            row.setdefault(metric, None)

    name, currency = None, None
    try:
        info = ticker.info
        name = info.get("longName") or info.get("shortName")
        currency = info.get("financialCurrency")
    except Exception:
        pass
    return {"name": name, "currency": currency, "years": years}
