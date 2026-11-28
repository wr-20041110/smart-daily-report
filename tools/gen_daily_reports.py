"""生成项目周期（2026-11-02 至 2026-11-26）工作日日报历史。

- 阶段一（11.2–11.15）：用 v1-SDD 版生成（无考勤源，对应课程第 1–2 周）
- 阶段二（11.16–11.26）：用 v2-Superpowers 版生成（含考勤变更单 F12，对应第 3–4 周）
- 全部 mock 模式（日报显式标注"Mock 模式"），push=False（不打扰收件箱）

用法：python tools/gen_daily_reports.py
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from daily_report_v1.config import load_settings as load_v1
from daily_report_v1.orchestrator import run_pipeline as run_v1
from daily_report_v2.pipeline import run_pipeline as run_v2
from daily_report_v2.settings import load_settings as load_v2

START = date(2026, 11, 2)
END = date(2026, 11, 26)
SWITCH = date(2026, 11, 16)  # 阶段二起点


def workdays(start: date, end: date):
    d = start
    while d <= end:
        if d.weekday() < 5:
            yield d
        d += timedelta(days=1)


def main() -> int:
    total = 0
    for day in workdays(START, END):
        if day < SWITCH:
            settings = load_v1(mock=True)
            result = run_v1(day, settings, push=False)
            tag = "v1-SDD"
        else:
            settings = load_v2(mock=True)
            result = run_v2(day, settings, push=False)
            tag = "v2-Superpowers"
        print(
            f"{day.isoformat()} [{tag}] 条目 {result.entry_count} 条，耗时 {result.elapsed_seconds}s"
        )
        total += 1
    print(f"共生成 {total} 份团队日报（历史已留存 SQLite：data/reports.db）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
