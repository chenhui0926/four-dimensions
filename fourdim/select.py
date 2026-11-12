from __future__ import annotations

from fourdim.models import Snapshot


def recent_codes(picks: list[dict], limit: int = 10) -> set[str]:
    blocked: set[str] = set()
    for item in picks[-limit:]:
        for code in item.get("codes", []):
            blocked.add(str(code).zfill(6))
    return blocked


def pick_three(rows: list[Snapshot], blocked: set[str]) -> list[Snapshot]:
    """Cheapest positive PE first, one industry each, then relax constraints."""
    ordered = sorted(rows, key=lambda row: (row.pe if row.pe and row.pe > 0 else 1e9, -(row.roe or 0)))
    chosen: list[Snapshot] = []

    def take(*, allow_blocked: bool, allow_same_industry: bool) -> None:
        industries = {item.industry for item in chosen}
        seen = {item.code for item in chosen}
        for row in ordered:
            if len(chosen) == 3:
                return
            if row.code in seen:
                continue
            if not allow_blocked and row.code in blocked:
                continue
            if not allow_same_industry and row.industry in industries:
                continue
            chosen.append(row)
            industries.add(row.industry)
            seen.add(row.code)

    take(allow_blocked=False, allow_same_industry=False)
    take(allow_blocked=True, allow_same_industry=False)
    take(allow_blocked=True, allow_same_industry=True)
    return chosen
