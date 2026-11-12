from __future__ import annotations

from fourdim.models import DISCLAIMER, RULE_VERSION, Review
from fourdim.rules import margin_stability

_STATUS = {"pass": "通过", "fail": "不通过", "pending": "待复核"}


def peg(pe: float | None, growth: float | None) -> str:
    if pe is None or growth is None or pe <= 0 or growth <= 0:
        return "不适用"
    return f"{pe / growth:.2f}（市盈率 / 净利润同比，不是三年复合增速）"


def render_review(review: Review, *, picked: bool = False) -> str:
    row = review.snapshot
    lines = [
        f"## {row.code} {row.name}",
        "",
        f"行业：{row.industry or '缺失'}　报告期：{row.report_period or '缺失'}",
        "",
        "### 四个维度",
        "",
        f"- 盈利：毛利率 { _num(row.gross_margin, '%') }，净利率 { _num(row.net_margin, '%') }，"
        f"净资产收益率 { _num(row.roe, '%') }，总资产收益率 { _num(row.roa, '%') }",
        f"- 效率：总资产周转率 { _num(row.asset_turnover, '') }，投入资本回报率 { _num(row.roic, '%') }，"
        f"权益乘数 { _num(row.equity_multiplier, '') }",
        f"- 财务：资产负债率 { _num(row.debt_ratio, '%') }，流动比率 { _num(row.current_ratio, '') }，"
        f"速动比率 { _num(row.quick_ratio, '') }",
        f"- 估值：股价 { _num(row.price, '元') }，市盈率 { _num(row.pe, '') }，市净率 { _num(row.pb, '') }，"
        f"PEG { peg(row.pe, row.profit_yoy) }，股息率 { _num(row.dividend_yield, '%') }，"
        f"总市值 { _num(None if row.market_cap is None else row.market_cap / 1e8, '亿') }",
        "",
        "### 硬门槛",
        "",
    ]
    for item in review.gates:
        lines.append(f"- {_STATUS[item.status]}　{item.name}：{item.detail}")
    lines.extend(["", "### 纵向", ""])
    if row.annual_roe:
        lines.append("- 近端年报净资产收益率：" + "、".join(f"{item:.1f}%" for item in row.annual_roe[:5]))
    else:
        lines.append("- 近端年报净资产收益率：还没有拉到")
    lines.append(f"- 毛利率稳定度：{margin_stability(row.annual_gm)}")
    lines.extend(
        [
            "",
            "### 横向",
            "",
            f"- 净资产收益率{review.peer_roe}",
            f"- 毛利率{review.peer_gm}",
            "",
            "### 陷阱",
            "",
        ]
    )
    for item in review.traps:
        lines.append(f"- {_STATUS[item.status]}　{item.name}：{item.detail}")
    lines.extend(["", "### 结论", ""])
    lines.append(_conclusion(review, picked=picked))
    lines.append("")
    return "\n".join(lines)


def render_daily(
    day: str,
    report_period: str,
    reviews: list[Review],
    pool_size: int,
    candidate_size: int,
) -> str:
    lines = [
        f"# {day} 观察名单",
        "",
        f"规则 {RULE_VERSION}。报告期 {report_period}。"
        "先过硬门槛和三条否决，再在市盈率大于 0 且不超过 40 倍的公司里，"
        "按市盈率从低到高取 3 只。同一行业只留 1 只；近 10 次已经出现过的代码先跳过。",
        "",
        f"全市场进入复核前的候选约 {pool_size} 只，复核后仍合格的有 {candidate_size} 只，今天列出 {len(reviews)} 只。",
        "",
    ]
    if not reviews:
        lines.append("今天没有股票同时通过质量条件和估值排序。")
        lines.append("")
    for index, review in enumerate(reviews, start=1):
        body = render_review(review, picked=True)
        body = body.replace("## ", f"## {index}. ", 1)
        lines.append(body.rstrip())
        lines.append("")
    lines.append(DISCLAIMER)
    lines.append("")
    return "\n".join(lines)


def _conclusion(review: Review, *, picked: bool = False) -> str:
    cap = next(item for item in review.gates if item.name.startswith("总市值"))
    others = [item for item in review.gates if item is not cap]
    quality_ok = all(item.status == "pass" for item in others) and all(
        item.status == "pass" for item in review.traps
    )
    if picked and review.eligible:
        return "已列入今天的观察名单。"
    if review.eligible:
        return "质量条件通过。能否进入当天 3 只，还要看市盈率是否在 0 到 40 倍、行业是否重复，以及近 10 次是否已经推荐过。"
    if quality_ok:
        return f"质量条件通过。{cap.detail}，因此不进入当天 3 只。"
    return "质量条件未通过，不进入当天的推荐排序。"


def _num(value: float | None, unit: str) -> str:
    if value is None:
        return "缺失"
    if unit == "%":
        return f"{value:.1f}%"
    if unit == "亿":
        return f"{value:.1f} 亿"
    if unit == "元":
        return f"{value:.2f} 元"
    return f"{value:.2f}"
