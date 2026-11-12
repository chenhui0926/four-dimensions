from __future__ import annotations

from dataclasses import dataclass, field


DISCLAIMER = (
    "市场有风险。这是基本面筛查结果，不是买卖建议。"
    "数据来自公开接口，可能延迟或缺失；缺失的硬性条件视为不通过。"
)

RULE_VERSION = "v1"


@dataclass
class Snapshot:
    code: str
    name: str
    industry: str
    roe: float | None = None
    gross_margin: float | None = None
    net_margin: float | None = None
    roa: float | None = None
    debt_ratio: float | None = None
    ocf: float | None = None
    net_income: float | None = None
    revenue_yoy: float | None = None
    profit_yoy: float | None = None
    roic: float | None = None
    asset_turnover: float | None = None
    current_ratio: float | None = None
    quick_ratio: float | None = None
    equity_multiplier: float | None = None
    pe: float | None = None
    pb: float | None = None
    dividend_yield: float | None = None
    market_cap: float | None = None
    price: float | None = None
    parent_ni: float | None = None
    deducted_ni: float | None = None
    annual_roe: list[float] = field(default_factory=list)
    annual_gm: list[float] = field(default_factory=list)
    history_ok: bool = False
    report_period: str = ""


@dataclass
class Check:
    name: str
    status: str  # pass, fail, pending
    detail: str

    @property
    def ok(self) -> bool:
        return self.status == "pass"


@dataclass
class Review:
    snapshot: Snapshot
    gates: list[Check]
    traps: list[Check]
    peer_roe: str
    peer_gm: str
    pre_eligible: bool
    eligible: bool
