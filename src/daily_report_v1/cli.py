"""CLI 入口（design.md 4.5）：python -m daily_report_v1 [--date] [--mock] [--no-push]。"""

from __future__ import annotations

import argparse
import sys
from datetime import date

from . import __version__
from .config import load_settings
from .errors import DailyReportError
from .orchestrator import run_pipeline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="daily-report", description="智能日报生成器 v1（SDD 规范驱动版）"
    )
    parser.add_argument(
        "--date", type=date.fromisoformat, default=date.today(), help="日报日期（默认今天）"
    )
    parser.add_argument("--mock", action="store_true", help="强制使用内置模拟数据源")
    parser.add_argument("--no-push", action="store_true", help="跳过推送（仅采集生成与存储）")
    args = parser.parse_args(argv)

    try:
        settings = load_settings(mock=args.mock)
        result = run_pipeline(args.date, settings, push=not args.no_push)
    except DailyReportError as exc:
        print(f"[错误] {exc}")
        return 1

    print(f"智能日报生成器 v{__version__}")
    print(f"日报日期：{result.day.isoformat()}")
    print(f"运行模式：{'Mock（内置模拟数据）' if result.mocked else '真实数据源'}")
    collected = "，".join(f"{k}={v}" for k, v in result.collected.items()) or "无"
    print(f"采集结果：{collected}")
    if result.missing_sources:
        print(f"缺失数据源：{'、'.join(result.missing_sources)}（已降级出报）")
    print(f"生成条目：{result.entry_count} 条")
    for pr in result.push_results:
        tag = "mock 留痕" if pr.mocked else ("成功" if pr.ok else "失败")
        print(f"推送[{pr.channel}]：{tag}｜{pr.detail}")
    print(f"耗时：{result.elapsed_seconds}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
