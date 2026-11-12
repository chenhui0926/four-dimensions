from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

from fourdim.history import load_picks, remember
from fourdim.models import DISCLAIMER, Review, Snapshot
from fourdim.render import render_daily, render_review
from fourdim.rules import MAX_PE, PeerTable, evaluate
from fourdim.select import pick_three, recent_codes
from fourdim.sources import (
    apply_history,
    apply_quote,
    fetch_indicator,
    fetch_quotes,
    fetch_stock_quote,
    load_universe,
    resolve_query,
    snapshot_from_indicator,
)


def run_recommend(today: date | None = None, root: Path | None = None) -> str:
    today = today or date.today()
    root = root or Path(".")
    day = today.isoformat()
    period, rows = load_universe(today)
    peers = PeerTable(rows)
    print(f"合并 {len(rows)} 只，计算硬门槛…", flush=True)
    shortlist: list[Snapshot] = []
    for row in rows:
        review = evaluate(row, peers, require_history=False)
        if review.pre_eligible:
            shortlist.append(row)
    print(f"硬门槛通过 {len(shortlist)} 只，拉取行情…", flush=True)
    quotes = fetch_quotes([row.code for row in shortlist]) if shortlist else {}
    if shortlist and not quotes:
        raise RuntimeError("行情接口没有返回数据，这次不写观察名单")
    priced: list[Snapshot] = []
    for row in shortlist:
        apply_quote(row, quotes.get(row.code))
        if row.pe is not None and 0 < row.pe <= MAX_PE and (row.market_cap or 0) >= 5_000_000_000:
            priced.append(row)
    priced.sort(key=lambda row: row.pe or 1e9)
    print(f"市盈率 0–40 且市值达标 {len(priced)} 只，开始复核年报…", flush=True)

    qualified: list[tuple[Snapshot, Review]] = []
    for row in priced[:40]:
        print(f"复核 {row.code} {row.name}", flush=True)
        try:
            frame = fetch_indicator(row.code)
            apply_history(row, frame)
        except Exception as exc:
            print(f"跳过 {row.code}：{exc}", flush=True)
            continue
        review = evaluate(row, peers, require_history=True)
        if review.eligible:
            qualified.append((row, review))
    chosen_rows = pick_three([row for row, _ in qualified], recent_codes(load_picks(root / "data" / "picks.json")))
    chosen_codes = {row.code for row in chosen_rows}
    chosen = [review for row, review in qualified if row.code in chosen_codes]
    # pick_three 的顺序才是展示顺序
    order = {row.code: index for index, row in enumerate(chosen_rows)}
    chosen.sort(key=lambda review: order[review.snapshot.code])

    text = render_daily(day, period, chosen, len(shortlist), len(qualified))
    out = root / "daily" / f"{day}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    remember(root / "data" / "picks.json", day, [row.code for row in chosen_rows])
    _save_peers(root / "data" / "cache" / "peers.json", rows, period)
    print(f"已写入 {out}", flush=True)
    return text


def run_analyze(query: str, root: Path | None = None) -> str:
    root = root or Path(".")
    code, name = resolve_query(query)
    print(f"解析 {code} {name}".rstrip(), flush=True)
    frame = fetch_indicator(code)
    row = snapshot_from_indicator(code, name, frame)
    try:
        apply_quote(row, fetch_stock_quote(code))
    except Exception as exc:
        print(f"行情缺失：{exc}", flush=True)
    peers = _load_peers(root / "data" / "cache" / "peers.json", row)
    review = evaluate(row, peers, require_history=True)
    if not row.industry:
        review.peer_roe = "未计算（个股接口没有行业，先跑一次 recommend 会写入行业缓存）"
        review.peer_gm = review.peer_roe
    return render_review(review) + "\n" + DISCLAIMER + "\n"


def _save_peers(path: Path, rows: list[Snapshot], period: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "period": period,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "rows": [
            {
                "code": row.code,
                "name": row.name,
                "industry": row.industry,
                "roe": row.roe,
                "gross_margin": row.gross_margin,
            }
            for row in rows
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _load_peers(path: Path, target: Snapshot) -> PeerTable:
    if not path.exists():
        return PeerTable([target])
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for item in payload.get("rows", []):
        row = Snapshot(
            code=item["code"],
            name=item.get("name") or "",
            industry=item.get("industry") or "",
            roe=item.get("roe"),
            gross_margin=item.get("gross_margin"),
        )
        if row.code == target.code:
            target.industry = row.industry or target.industry
            target.name = target.name or row.name
        rows.append(row)
    if target.code not in {row.code for row in rows}:
        rows.append(target)
    return PeerTable(rows)
