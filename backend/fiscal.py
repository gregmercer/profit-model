"""Helpers shared by the data sources."""

from datetime import date


def fiscal_year_for(end: date) -> int:
    """Map a fiscal-year end date to a fiscal year label.

    The label is the calendar year in which the fiscal year ends (Wal-Mart's
    year ended Jan 31, 2000 is fiscal 2000). Companies on a 52/53-week
    calendar sometimes end a few days into January; those belong to the
    prior year.
    """
    if end.month == 1 and end.day <= 7:
        return end.year - 1
    return end.year
