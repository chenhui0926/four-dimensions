from __future__ import annotations

from datetime import date


def report_candidates(today: date) -> list[str]:
    """Latest report periods that should already be fully published.

    Order is newest first. The caller tries each date until the batch
    endpoint returns rows. Before the annual-report deadline (April 30),
    last year's third quarter is preferred so the universe is complete.
    """
    year = today.year
    out: list[str] = []
    if today.month >= 11:
        out.append(f"{year}0930")
    if today.month >= 9:
        out.append(f"{year}0630")
    if today.month >= 5:
        out.append(f"{year}0331")
        out.append(f"{year - 1}1231")
    else:
        out.append(f"{year - 1}0930")
        out.append(f"{year - 1}1231")
    previous_q3 = f"{year - 1}0930"
    if previous_q3 not in out:
        out.append(previous_q3)
    return out
