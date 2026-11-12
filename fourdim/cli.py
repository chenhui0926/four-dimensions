from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

from fourdim.service import run_analyze, run_recommend


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fourdim", description="四大维度基本面筛查")
    parser.add_argument("--root", default=".", help="仓库根目录，默认当前目录")
    sub = parser.add_subparsers(dest="cmd", required=True)

    recommend = sub.add_parser("recommend", help="按规则选出当天 3 只观察名单")
    recommend.add_argument("--date", help="YYYY-MM-DD，默认今天")

    analyze = sub.add_parser("analyze", help="解析一只股票")
    analyze.add_argument("query", help="股票代码或名称")

    args = parser.parse_args(argv)
    root = Path(args.root)
    try:
        if args.cmd == "recommend":
            day = date.today() if not args.date else datetime.strptime(args.date, "%Y-%m-%d").date()
            sys.stdout.write(run_recommend(day, root))
        else:
            sys.stdout.write(run_analyze(args.query, root))
    except Exception as exc:
        print(f"失败：{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
