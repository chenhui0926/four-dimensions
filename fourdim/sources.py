from __future__ import annotations

import math
import time
from typing import Any

import pandas as pd
import requests

from fourdim.models import Snapshot
from fourdim.periods import report_candidates


def num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def norm_code(value: Any) -> str:
    text = str(value).strip().upper()
    if text.endswith(".SH") or text.endswith(".SZ") or text.endswith(".BJ"):
        text = text.split(".")[0]
    if text.endswith(".0"):
        text = text[:-2]
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits.zfill(6)[-6:]


def em_symbol(code: str) -> str:
    code = norm_code(code)
    if code.startswith(("6", "9")):
        return f"{code}.SH"
    if code.startswith(("4", "8", "92")):
        return f"{code}.BJ"
    return f"{code}.SZ"


def secid(code: str) -> str:
    code = norm_code(code)
    market = "1" if code.startswith(("6", "9")) else "0"
    return f"{market}.{code}"


def load_universe(today) -> tuple[str, list[Snapshot]]:
    import akshare as ak

    last_error: Exception | None = None
    for period in report_candidates(today):
        try:
            print(f"拉取报告期 {period} …", flush=True)
            income = ak.stock_yjbb_em(date=period)
            balance = ak.stock_zcfz_em(date=period)
            cash = ak.stock_xjll_em(date=period)
        except Exception as exc:  # network or upstream shape
            last_error = exc
            print(f"报告期 {period} 失败：{exc}", flush=True)
            continue
        rows = merge_statements(income, balance, cash, period)
        if rows:
            return period, rows
        print(f"报告期 {period} 没有合并出股票", flush=True)
    raise RuntimeError(f"没有拿到可用的全市场财报：{last_error}")


def merge_statements(
    income: pd.DataFrame,
    balance: pd.DataFrame,
    cash: pd.DataFrame,
    period: str,
) -> list[Snapshot]:
    income = income.copy()
    balance = balance.copy()
    cash = cash.copy()
    for frame in (income, balance, cash):
        frame["code"] = frame["股票代码"].map(norm_code)
    balance = balance.drop_duplicates("code")
    cash = cash.drop_duplicates("code")
    merged = income.merge(
        balance[["code", "资产负债率"]],
        on="code",
        how="left",
    ).merge(
        cash[["code", "经营性现金流-现金流量净额"]],
        on="code",
        how="left",
    )
    merged = merged.drop_duplicates("code")
    rows: list[Snapshot] = []
    for record in merged.to_dict("records"):
        rows.append(
            Snapshot(
                code=record["code"],
                name=str(record.get("股票简称") or ""),
                industry=str(record.get("所处行业") or ""),
                roe=num(record.get("净资产收益率")),
                gross_margin=num(record.get("销售毛利率")),
                net_income=num(record.get("净利润-净利润")),
                revenue_yoy=num(record.get("营业总收入-同比增长")),
                profit_yoy=num(record.get("净利润-同比增长")),
                debt_ratio=num(record.get("资产负债率")),
                ocf=num(record.get("经营性现金流-现金流量净额")),
                report_period=period,
            )
        )
    return rows


def fetch_quotes(codes: list[str]) -> dict[str, dict]:
    found: dict[str, dict] = {}
    for start in range(0, len(codes), 40):
        chunk = codes[start : start + 40]
        params = {
            "fltt": "2",
            "invt": "2",
            "fields": "f12,f14,f2,f9,f20,f23,f133",
            "secids": ",".join(secid(code) for code in chunk),
        }
        try:
            payload = _get_json("/api/qt/ulist.np/get", params)
        except Exception as exc:
            print(f"批量行情失败，改为逐只拉取这 {len(chunk)} 只：{exc}", flush=True)
            streak = 0
            for code in chunk:
                try:
                    found[norm_code(code)] = fetch_stock_quote(code)
                    streak = 0
                except Exception as item_exc:
                    streak += 1
                    print(f"跳过 {code} 的行情：{item_exc}", flush=True)
                    if streak >= 3:
                        print("行情连续失败，停止这一批", flush=True)
                        break
                time.sleep(0.15)
            continue
        diff = ((payload or {}).get("data") or {}).get("diff") or []
        for item in diff:
            code = norm_code(item.get("f12"))
            found[code] = {
                "price": num(item.get("f2")),
                "pe": num(item.get("f9")),
                "pb": num(item.get("f23")),
                "market_cap": num(item.get("f20")),
                "dividend_yield": num(item.get("f133")),
            }
        time.sleep(0.2)
    return found


def fetch_stock_quote(code: str) -> dict:
    """One-stock quote. Also carries the Eastmoney industry name."""
    payload = _get_json(
        "/api/qt/stock/get",
        {
            "fltt": "2",
            "invt": "2",
            "fields": "f43,f57,f58,f116,f127,f133,f162,f167",
            "secid": secid(code),
        },
    )
    data = (payload or {}).get("data") or {}
    return {
        "price": num(data.get("f43")),
        "pe": num(data.get("f162")),
        "pb": num(data.get("f167")),
        "market_cap": num(data.get("f116")),
        "dividend_yield": num(data.get("f133")),
        "industry": str(data.get("f127") or ""),
        "name": str(data.get("f58") or ""),
    }


QUOTE_HOSTS = (
    "https://push2delay.eastmoney.com",
    "http://push2.eastmoney.com",
    "https://push2.eastmoney.com",
)


def _get_json(path: str, params: dict) -> dict:
    last_error: Exception | None = None
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Referer": "https://quote.eastmoney.com/",
    }
    for host in QUOTE_HOSTS:
        try:
            response = requests.get(
                host + path,
                params=params,
                timeout=20,
                headers=headers,
            )
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            last_error = exc
            time.sleep(0.4)
    raise RuntimeError(last_error)


def apply_quote(row: Snapshot, quote: dict | None) -> None:
    if not quote:
        return
    row.price = quote.get("price")
    row.pe = quote.get("pe")
    row.pb = quote.get("pb")
    row.market_cap = quote.get("market_cap")
    row.dividend_yield = quote.get("dividend_yield")
    industry = quote.get("industry")
    if industry and not row.industry:
        row.industry = str(industry)
    name = quote.get("name")
    if name and not row.name:
        row.name = str(name)


def fetch_indicator(code: str) -> pd.DataFrame:
    import akshare as ak

    return ak.stock_financial_analysis_indicator_em(
        symbol=em_symbol(code),
        indicator="按报告期",
    )


def apply_history(row: Snapshot, frame: pd.DataFrame) -> None:
    if frame is None or frame.empty:
        row.history_ok = False
        return
    data = frame.copy()
    data["REPORT_DATE"] = pd.to_datetime(data["REPORT_DATE"])
    data = data.sort_values("REPORT_DATE", ascending=False)
    latest = data.iloc[0]
    row.net_margin = num(latest.get("XSJLL"))
    row.roa = num(latest.get("ZZCJLL"))
    row.roic = num(latest.get("ROIC"))
    row.asset_turnover = num(latest.get("TOAZZL"))
    row.current_ratio = num(latest.get("LD"))
    row.quick_ratio = num(latest.get("SD"))
    row.equity_multiplier = num(latest.get("QYCS"))
    row.parent_ni = num(latest.get("PARENTNETPROFIT"))
    row.deducted_ni = num(latest.get("KCFJCXSYJLR"))
    # 批量接口已经给了全市场同一报告期的收益率。个股接口用来补年报序列。
    if row.roe is None:
        row.roe = num(latest.get("ROEJQ"))
    if row.gross_margin is None:
        row.gross_margin = num(latest.get("XSMLL"))
    if row.debt_ratio is None:
        row.debt_ratio = num(latest.get("ZCFZL"))
    annual = data[data["REPORT_TYPE"] == "年报"]
    row.annual_roe = _series(annual, "ROEJQ")
    row.annual_gm = _series(annual, "XSMLL")
    row.history_ok = True


def snapshot_from_indicator(code: str, name: str, frame: pd.DataFrame) -> Snapshot:
    data = frame.copy()
    data["REPORT_DATE"] = pd.to_datetime(data["REPORT_DATE"])
    data = data.sort_values("REPORT_DATE", ascending=False)
    latest = data.iloc[0]
    period = str(latest.get("REPORT_DATE_NAME") or "")[:20]
    row = Snapshot(
        code=norm_code(code),
        name=name or str(latest.get("SECURITY_NAME_ABBR") or ""),
        industry="",
        roe=num(latest.get("ROEJQ")),
        gross_margin=num(latest.get("XSMLL")),
        net_margin=num(latest.get("XSJLL")),
        roa=num(latest.get("ZZCJLL")),
        debt_ratio=num(latest.get("ZCFZL")),
        net_income=num(latest.get("PARENTNETPROFIT")),
        revenue_yoy=num(latest.get("TOTALOPERATEREVETZ")),
        profit_yoy=num(latest.get("PARENTNETPROFITTZ")),
        ocf=None,
        report_period=period,
    )
    # 个股接口没有经营现金流金额。用「经营现金流/净利润」还原本期现金流，供同一条门槛使用。
    ratio = num(latest.get("NCO_NETPROFIT"))
    if ratio is not None and row.net_income is not None:
        row.ocf = ratio * row.net_income
    apply_history(row, frame)
    return row


def resolve_query(query: str) -> tuple[str, str]:
    text = query.strip()
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) >= 6 and not any("\u4e00" <= ch <= "\u9fff" for ch in text):
        return norm_code(digits), ""
    import akshare as ak

    table = ak.stock_info_a_code_name()
    columns = list(table.columns)
    code_col, name_col = columns[0], columns[1]
    names = table[name_col].astype(str)
    exact = table[names == text]
    hits = exact if not exact.empty else table[names.str.contains(text, na=False)]
    if hits.empty:
        raise RuntimeError(f"没有找到股票：{query}")
    if len(hits) > 1 and exact.empty:
        sample = "、".join(
            f"{norm_code(record[code_col])} {record[name_col]}"
            for record in hits.head(8).to_dict("records")
        )
        raise RuntimeError(f"「{query}」匹配到多只股票，请改用代码。例如：{sample}")
    record = hits.iloc[0]
    return norm_code(record[code_col]), str(record[name_col])


def _series(frame: pd.DataFrame, column: str) -> list[float]:
    values: list[float] = []
    for item in frame[column].tolist():
        number = num(item)
        if number is not None:
            values.append(number)
        if len(values) == 10:
            break
    return values
