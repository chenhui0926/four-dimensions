from __future__ import annotations

import json
from pathlib import Path


def load_picks(path: Path) -> list[dict]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return list(data.get("picks", []))


def save_picks(path: Path, picks: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"picks": picks}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def remember(path: Path, day: str, codes: list[str]) -> None:
    picks = [item for item in load_picks(path) if item.get("date") != day]
    if codes:
        picks.append({"date": day, "codes": codes})
    save_picks(path, picks)
