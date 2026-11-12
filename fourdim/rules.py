from __future__ import annotations

import math
from statistics import pstdev

from fourdim.models import Check, Review, Snapshot

FINANCIAL_KEYS = ("银行", "保险", "证券", "多元金融", "信托")
CYCLICAL_KEYS = (
    "普钢",
    "特钢",
    "钢铁",
    "煤炭",
    "焦炭",
    "石油",
    "油服",
    "工业金属",
    "贵金属",
    "小金属",
    "有色",
    "化学原料",
    "化学制品",
    "化工",
    "水泥",
    "玻璃",
    "航运",
    "航空",
    "养殖",
    "种植",
    "农产品",
)
MIN_MARKET_CAP = 5_000_000_000  # 50 亿
MIN_ROE = 15.0
MIN_ANNUAL_ROE = 12.0
MIN_GROSS_MARGIN = 40.0
MAX_DEBT = 60.0
MIN_OCF_TO_NI = 0.8
MAX_PE = 40.0
ONE_OFF_GAP = 0.20


def is_st(name: str) -> bool:
    text = name.upper().replace(" ", "")
    return "ST" in text or "退" in name


def is_financial(industry: str) -> bool:
    return any(key in industry for key in FINANCIAL_KEYS)


def is_cyclical(industry: str) -> bool:
    if any(key in industry for key in ("装备", "设备", "器件")):
        return False
    return any(key in industry for key in CYCLICAL_KEYS)


def percentile(values: list[float], q: float) -> float | None:
    xs = sorted(v for v in values if v is not None and not math.isnan(v))
    if not xs:
        return None
    if len(xs) == 1:
        return xs[0]
    pos = q * (len(xs) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    frac = pos - lo
    return xs[lo] * (1 - frac) + xs[hi] * frac


def rank_label(value: float | None, values: list[float]) -> str:
    xs = [v for v in values if v is not None and not math.isnan(v)]
    if value is None or len(xs) < 8:
        return "未计算"
    below = sum(1 for item in xs if item < value)
    pct = 100.0 * below / len(xs)
    return f"高于行业内 {pct:.0f}% 的公司（样本 {len(xs)}）"


class PeerTable:
    def __init__(self, rows: list[Snapshot]):
        self.roe: dict[str, list[float]] = {}
        self.gm: dict[str, list[float]] = {}
        for row in rows:
            if is_st(row.name) or is_financial(row.industry):
                continue
            if row.roe is not None:
                self.roe.setdefault(row.industry, []).append(row.roe)
            if row.gross_margin is not None:
                self.gm.setdefault(row.industry, []).append(row.gross_margin)

    def gm_threshold(self, industry: str) -> tuple[float, str]:
        if not is_cyclical(industry):
            return MIN_GROSS_MARGIN, "非周期行业，毛利率不低于 40%"
        values = self.gm.get(industry, [])
        if len(values) < 8:
            return 20.0, "周期行业样本不足 8 家，毛利率不低于 20%"
        cut = percentile(values, 0.60)
        assert cut is not None
        return cut, f"周期行业，毛利率不低于行业 60 分位 {cut:.1f}%"


def _check(name: str, passed: bool, detail: str) -> Check:
    return Check(name, "pass" if passed else "fail", detail)


def _pending(name: str, detail: str) -> Check:
    return Check(name, "pending", detail)


def evaluate(row: Snapshot, peers: PeerTable, *, require_history: bool) -> Review:
    gates: list[Check] = []
    gates.append(
        _check("不是 ST / 退市", not is_st(row.name), row.name)
    )
    gates.append(
        _check(
            "不是金融业",
            not is_financial(row.industry),
            row.industry or "行业缺失",
        )
    )
    gates.append(
        _check(
            "净资产收益率 ≥ 15%",
            row.roe is not None and row.roe >= MIN_ROE,
            _fmt(row.roe, "%"),
        )
    )
    gm_cut, gm_reason = peers.gm_threshold(row.industry)
    gates.append(
        _check(
            "毛利率门槛",
            row.gross_margin is not None and row.gross_margin >= gm_cut,
            f"{_fmt(row.gross_margin, '%')}；{gm_reason}",
        )
    )
    gates.append(
        _check(
            "净利润为正",
            row.net_income is not None and row.net_income > 0,
            _fmt(row.net_income, "元"),
        )
    )
    gates.append(
        _check(
            "经营现金流为正",
            row.ocf is not None and row.ocf > 0,
            _fmt(row.ocf, "元"),
        )
    )
    if row.ocf is None or row.net_income is None or row.net_income <= 0:
        ocf_ratio = None
        ocf_ok = False
    else:
        ocf_ratio = row.ocf / row.net_income
        ocf_ok = ocf_ratio >= MIN_OCF_TO_NI
    gates.append(
        _check(
            "经营现金流 / 净利润 ≥ 0.8",
            ocf_ok,
            "缺失" if ocf_ratio is None else f"{ocf_ratio:.2f}",
        )
    )
    gates.append(
        _check(
            "资产负债率 < 60%",
            row.debt_ratio is not None and row.debt_ratio < MAX_DEBT,
            _fmt(row.debt_ratio, "%"),
        )
    )
    if row.market_cap is None:
        gates.append(_pending("总市值 ≥ 50 亿", "行情未取到") if not require_history else _check("总市值 ≥ 50 亿", False, "行情缺失"))
    else:
        gates.append(
            _check(
                "总市值 ≥ 50 亿",
                row.market_cap >= MIN_MARKET_CAP,
                _fmt(row.market_cap / 1e8, "亿"),
            )
        )

    history_ready = row.history_ok and len(row.annual_roe) >= 5
    if not require_history and not history_ready:
        gates.append(_pending("近 5 年年报净资产收益率每年 ≥ 12%", "留到候选复核"))
    elif len(row.annual_roe) < 5:
        gates.append(
            _check(
                "近 5 年年报净资产收益率每年 ≥ 12%",
                False,
                f"只有 {len(row.annual_roe)} 年年报",
            )
        )
    else:
        last = row.annual_roe[:5]
        lowest = min(last)
        note = "、".join(f"{item:.1f}%" for item in last)
        if lowest < 15:
            note += f"；最低 {lowest:.1f}%，低于连续 5 年 15% 的更严标准，按 12% 线放行"
        gates.append(_check("近 5 年年报净资产收益率每年 ≥ 12%", lowest >= MIN_ANNUAL_ROE, note))

    traps: list[Check] = []
    traps.append(_leverage_trap(row, require_history))
    traps.append(_one_off_trap(row, require_history))
    traps.append(_value_trap(row))

    structural = [
        item
        for item in gates
        if item.name
        not in {
            "近 5 年年报净资产收益率每年 ≥ 12%",
            "总市值 ≥ 50 亿",
        }
    ]
    pre_eligible = all(item.status == "pass" for item in structural)
    # 质量和价格分开。市盈率只在每日排序时使用，不写进通过与否。
    eligible = all(item.status == "pass" for item in gates) and all(
        item.status == "pass" for item in traps
    )
    return Review(
        snapshot=row,
        gates=gates,
        traps=traps,
        peer_roe=rank_label(row.roe, peers.roe.get(row.industry, [])),
        peer_gm=rank_label(row.gross_margin, peers.gm.get(row.industry, [])),
        pre_eligible=pre_eligible,
        eligible=eligible,
    )


def _leverage_trap(row: Snapshot, require_history: bool) -> Check:
    name = "高杠杆堆出来的高净资产收益率"
    if row.roa is None or row.net_margin is None or row.equity_multiplier is None:
        if require_history:
            return _check(name, False, "缺少总资产收益率或权益乘数，无法排除")
        return _pending(name, "留到候选复核")
    weak_roa = (
        row.roe is not None
        and row.roe >= MIN_ROE
        and row.debt_ratio is not None
        and row.debt_ratio >= 50
        and row.roa < 6
    )
    weak_margin = (
        row.roe is not None
        and row.roe >= MIN_ROE
        and row.equity_multiplier >= 2.5
        and row.net_margin < 10
    )
    if weak_roa or weak_margin:
        return _check(
            name,
            False,
            f"净资产收益率 {_fmt(row.roe, '%')}，总资产收益率 {_fmt(row.roa, '%')}，"
            f"权益乘数 {_fmt(row.equity_multiplier, '')}，净利率 {_fmt(row.net_margin, '%')}",
        )
    return _check(
        name,
        True,
        f"总资产收益率 {_fmt(row.roa, '%')}，权益乘数 {_fmt(row.equity_multiplier, '')}",
    )


def _one_off_trap(row: Snapshot, require_history: bool) -> Check:
    name = "一次性收益"
    if row.parent_ni is None or row.deducted_ni is None or row.parent_ni == 0:
        if require_history:
            return _check(name, False, "缺少扣非净利润")
        return _pending(name, "留到候选复核")
    gap = abs(row.parent_ni - row.deducted_ni) / abs(row.parent_ni)
    if gap > ONE_OFF_GAP:
        return _check(name, False, f"扣非与归母相差 {gap:.0%}")
    return _check(name, True, f"扣非与归母相差 {gap:.0%}")


def _value_trap(row: Snapshot) -> Check:
    name = "低市盈率或低市净率但基本面在变差"
    cheap = (row.pe is not None and 0 < row.pe < 15) or (
        row.pb is not None and 0 < row.pb < 1
    )
    if row.revenue_yoy is None or row.profit_yoy is None:
        if not cheap:
            return _check(name, True, "估值不处于偏低区间")
        return _check(name, False, "估值偏低，但营收或利润同比缺失，无法排除基本面变差")
    deteriorating = row.revenue_yoy < 0 and row.profit_yoy < 0
    if cheap and deteriorating:
        return _check(
            name,
            False,
            f"市盈率 {_fmt(row.pe, '')}，市净率 {_fmt(row.pb, '')}，"
            f"营收同比 {_fmt(row.revenue_yoy, '%')}，净利润同比 {_fmt(row.profit_yoy, '%')}",
        )
    return _check(
        name,
        True,
        f"营收同比 {_fmt(row.revenue_yoy, '%')}，净利润同比 {_fmt(row.profit_yoy, '%')}",
    )


def margin_stability(values: list[float]) -> str:
    last = [item for item in values[:5] if item is not None]
    if len(last) < 5:
        return "年报不足 5 年"
    return f"近 5 年毛利率标准差 {pstdev(last):.1f} 个百分点"


def _fmt(value: float | None, unit: str) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "缺失"
    if unit == "元":
        return f"{value:,.0f} 元"
    if unit == "亿":
        return f"{value:.1f} 亿"
    if unit == "%":
        return f"{value:.1f}%"
    return f"{value:.2f}"
