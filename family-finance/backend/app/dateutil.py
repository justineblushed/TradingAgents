def month_bounds(month: str) -> tuple[str, str]:
    """'2026-08' -> ('2026-08-01', '2026-09-01'), half-open date range."""
    year, mon = (int(part) for part in month.split("-"))
    start = f"{year:04d}-{mon:02d}-01"
    end = f"{year + 1:04d}-01-01" if mon == 12 else f"{year:04d}-{mon + 1:02d}-01"
    return start, end
