"""Annual 10-K figures from the SEC EDGAR XBRL "company facts" API.

EDGAR has structured XBRL data for fiscal years from roughly 2009 onward.
The SEC asks every client to send a descriptive User-Agent with contact
details; set SEC_USER_AGENT to override the default.
"""

import os
from datetime import date

import httpx

from fiscal import fiscal_year_for

USER_AGENT = os.environ.get("SEC_USER_AGENT", "profit-model-app contact@example.com")
HEADERS = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"}

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"

ANNUAL_FORMS = {"10-K", "10-K/A", "10-KT", "10-KT/A"}

# Companies switch tags over time, so each metric lists candidates in
# priority order and the first tag with a value for a year wins.
DURATION_TAGS = {
    "net_sales": [
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
        "SalesRevenueGoodsNet",
        "SalesRevenueServicesNet",
    ],
    "net_income": [
        "NetIncomeLoss",
        "ProfitLoss",
        "NetIncomeLossAvailableToCommonStockholdersBasic",
    ],
}
INSTANT_TAGS = {
    "total_assets": ["Assets"],
    "shareholders_equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
}

_cik_cache: dict[str, tuple[int, str]] = {}


def lookup_cik(symbol: str, client: httpx.Client) -> tuple[int, str] | None:
    if not _cik_cache:
        resp = client.get(TICKERS_URL, headers=HEADERS)
        resp.raise_for_status()
        for row in resp.json().values():
            _cik_cache[row["ticker"].upper()] = (int(row["cik_str"]), row["title"])
    return _cik_cache.get(symbol.upper())


def _usd_facts(facts: dict, tag: str) -> list[dict]:
    return [
        f
        for f in facts.get("us-gaap", {}).get(tag, {}).get("units", {}).get("USD", [])
        if f.get("form") in ANNUAL_FORMS
    ]


def _latest_by(facts: list[dict], key) -> dict:
    """Keep the most recently filed value per key, so restatements win."""
    best: dict = {}
    for f in facts:
        k = key(f)
        if k is not None and (k not in best or f["filed"] > best[k]["filed"]):
            best[k] = f
    return best


def _annual_durations(facts: dict, tag: str) -> dict[date, float]:
    def key(f):
        if "start" not in f:
            return None
        start, end = date.fromisoformat(f["start"]), date.fromisoformat(f["end"])
        return end if 340 <= (end - start).days <= 380 else None

    return {end: f["val"] for end, f in _latest_by(_usd_facts(facts, tag), key).items()}


def _instants(facts: dict, tag: str) -> dict[date, float]:
    best = _latest_by(_usd_facts(facts, tag), lambda f: date.fromisoformat(f["end"]))
    return {end: f["val"] for end, f in best.items()}


def fetch(symbol: str) -> dict | None:
    """Return {"cik", "name", "years": {fy: {...}}} or None if not an EDGAR filer."""
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        hit = lookup_cik(symbol, client)
        if hit is None:
            return None
        cik, name = hit
        resp = client.get(FACTS_URL.format(cik=cik), headers=HEADERS)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        facts = resp.json().get("facts", {})

    # Fiscal-year end dates come from the income statement durations.
    durations = {
        metric: [_annual_durations(facts, t) for t in tags]
        for metric, tags in DURATION_TAGS.items()
    }
    instants = {
        metric: [_instants(facts, t) for t in tags]
        for metric, tags in INSTANT_TAGS.items()
    }

    year_ends: dict[int, date] = {}
    for per_tag in durations.values():
        for values in per_tag:
            for end in values:
                fy = fiscal_year_for(end)
                year_ends[fy] = max(year_ends.get(fy, end), end)

    years = {}
    for fy, end in sorted(year_ends.items()):
        row = {"fiscal_year_end": end.isoformat(), "source": "SEC EDGAR"}
        for metric, per_tag in {**durations, **instants}.items():
            row[metric] = next((v[end] for v in per_tag if end in v), None)
        years[str(fy)] = row

    # Foreign filers (20-F, IFRS) are listed but have no us-gaap facts.
    if not years:
        return None
    return {"cik": cik, "name": name, "years": years}
