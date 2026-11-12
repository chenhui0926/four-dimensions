from datetime import date

from fourdim.history import load_picks, remember
from fourdim.models import DISCLAIMER, Snapshot
from fourdim.periods import report_candidates
from fourdim.render import render_review
from fourdim.rules import PeerTable, evaluate
from fourdim.select import pick_three, recent_codes
from fourdim.sources import merge_statements, norm_code

import pandas as pd


def company(**kwargs) -> Snapshot:
    base = dict(
        code="600519",
        name="贵州茅台",
        industry="白酒",
        roe=32.0,
        gross_margin=91.0,
        net_margin=50.0,
        roa=28.0,
        debt_ratio=18.0,
        ocf=100.0,
        net_income=80.0,
        revenue_yoy=8.0,
        profit_yoy=10.0,
        roic=30.0,
        equity_multiplier=1.2,
        pe=20.0,
        pb=6.0,
        market_cap=1.7e12,
        parent_ni=80.0,
        deducted_ni=79.0,
        annual_roe=[32, 36, 34, 30, 29],
        annual_gm=[91, 92, 92, 91, 91],
        history_ok=True,
        report_period="20260930",
    )
    base.update(kwargs)
    return Snapshot(**base)


def review(row: Snapshot, peers=None, **kwargs):
    return evaluate(row, peers or PeerTable([row]), **kwargs)


def test_quality_name_passes():
    result = review(company(), require_history=True)
    assert result.eligible
    assert result.pre_eligible


def test_missing_quote_keeps_the_quality_verdict():
    text = render_review(review(company(market_cap=None), require_history=True))
    assert "质量条件通过" in text
    assert "行情缺失" in text
    assert DISCLAIMER not in text


def test_low_cash_conversion_fails():
    result = review(company(ocf=40), require_history=False)
    assert not result.pre_eligible


def test_bank_and_st_fail():
    assert not review(company(industry="银行"), require_history=True).pre_eligible
    assert not review(company(name="*ST茅台"), require_history=True).pre_eligible


def test_one_off_profit_vetoes():
    result = review(company(deducted_ni=50), require_history=True)
    assert not result.eligible
    assert any(item.name.startswith("一次性") and item.status == "fail" for item in result.traps)


def test_value_trap_needs_falling_fundamentals():
    trapped = review(company(pe=8, pb=0.8, revenue_yoy=-3, profit_yoy=-4), require_history=True)
    assert any(item.status == "fail" and "低市盈率" in item.name for item in trapped.traps)
    cheap_but_growing = review(company(pe=8, pb=0.8, revenue_yoy=6, profit_yoy=7), require_history=True)
    assert cheap_but_growing.eligible


def test_cyclical_uses_industry_percentile():
    peers = [
        company(code=f"00000{i}", name=f"钢厂{i}", industry="普钢", gross_margin=gm, roe=16)
        for i, gm in enumerate([5, 8, 10, 12, 14, 16, 18, 22, 30])
    ]
    table = PeerTable(peers)
    weak = review(peers[0], table, require_history=True)
    strong = review(peers[-1], table, require_history=True)
    assert not weak.pre_eligible
    assert strong.pre_eligible


def test_pick_three_skips_recent_and_splits_industries():
    rows = [
        company(code="600001", name="甲", industry="白酒", pe=10),
        company(code="600002", name="乙", industry="白酒", pe=11),
        company(code="600003", name="丙", industry="家电", pe=12),
        company(code="600004", name="丁", industry="医药", pe=13),
    ]
    picked = pick_three(rows, blocked={"600001"})
    assert [row.code for row in picked] == ["600002", "600003", "600004"]


def test_recent_codes_cover_last_ten_days():
    picks = [{"date": f"2026-01-{day:02d}", "codes": [f"{day:06d}"]} for day in range(1, 13)]
    blocked = recent_codes(picks, limit=10)
    assert "000001" not in blocked
    assert "000002" not in blocked
    assert "000003" in blocked
    assert "000012" in blocked


def test_remember_replaces_same_day(tmp_path):
    path = tmp_path / "picks.json"
    remember(path, "2026-11-12", ["600519"])
    remember(path, "2026-11-12", ["000858"])
    assert recent_codes(load_picks(path)) == {"000858"}


def test_november_uses_third_quarter():
    assert report_candidates(date(2026, 11, 12))[0] == "20260930"


def test_january_prefers_previous_third_quarter():
    assert report_candidates(date(2026, 1, 15))[0] == "20250930"


def test_merge_statements_keeps_gate_fields():
    income = pd.DataFrame(
        [
            {
                "股票代码": "600519",
                "股票简称": "贵州茅台",
                "所处行业": "白酒",
                "净资产收益率": 24.5,
                "销售毛利率": 89.5,
                "净利润-净利润": 100.0,
                "营业总收入-同比增长": 2.0,
                "净利润-同比增长": 1.0,
            }
        ]
    )
    balance = pd.DataFrame([{"股票代码": "600519", "资产负债率": 16.0}])
    cash = pd.DataFrame([{"股票代码": "600519", "经营性现金流-现金流量净额": 90.0}])
    rows = merge_statements(income, balance, cash, "20260930")
    assert rows[0].code == "600519"
    assert rows[0].ocf == 90
    assert norm_code("600519.SH") == "600519"
