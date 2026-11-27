"""主编排管道（v2：函数组合，design.md 4.5 / 附录 A.1）。

采集（注册表）→ 归属（规则管道）→ 编排（纯函数）→ 存储 → 推送。
任一数据源失败记入 missing_sources 降级出报；存储/编排失败抛异常（CLI 退出码 1）。
"""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Callable
from datetime import date

from .deliver import PUSHER_REGISTRY
from .domain import PipelineResult, PushResult, RawEvent
from .fetch import REGISTRY, CollectorError
from .rules import apply_rules
from .store import open_db, save_events, save_reports
from .synthesize import build_entries, make_team_report, render_team_report

#: 真实模式采集源（变更单 F12 后含考勤）；mock 模式单用 "mock" 一键供给全部事件
REAL_SOURCES = ("github", "feishu_task", "feishu_message", "feishu_attendance")


class StorageError(Exception):
    """存储层失败。"""


def run_pipeline(
    day: date,
    settings,
    push: bool = True,
    db_path: str | None = None,
    fetchers: dict[str, Callable] | None = None,
    deliverers: dict[str, Callable] | None = None,
) -> PipelineResult:
    """一键执行采集→生成→存储→推送；返回 PipelineResult 汇总。"""
    started = time.monotonic()
    mock_mode = settings.mock or not (settings.is_github_ready and settings.is_feishu_ready)
    sources = ("mock",) if mock_mode else REAL_SOURCES
    fetchers = fetchers if fetchers is not None else REGISTRY

    events: list[RawEvent] = []
    collected: dict[str, int] = {}
    missing: list[str] = []
    for source in sources:
        try:
            got = fetchers[source](day, settings)
        except CollectorError as exc:
            missing.append(source)
            print(f"[采集] {source} 降级：{exc}")
            continue
        collected[source] = len(got)
        events.extend(got)

    attributions = apply_rules(events)
    entries = build_entries(events, attributions, list(settings.members), day)
    team = make_team_report(entries, list(settings.members), missing, day, mock_mode)
    rendered = render_team_report(team)

    conn = open_db(db_path or settings.db_path)
    try:
        save_events(conn, events)
        save_reports(conn, entries, team, rendered)
    except sqlite3.Error as exc:
        raise StorageError(f"SQLite 写入失败：{type(exc).__name__}: {exc}") from exc
    finally:
        conn.close()

    push_results: tuple[PushResult, ...] = ()
    if push:
        deliverers = deliverers if deliverers is not None else PUSHER_REGISTRY
        push_results = tuple(
            deliverers[channel](team, settings, rendered) for channel in ("email", "feishu")
        )

    return PipelineResult(
        day=day,
        collected=collected,
        missing_sources=tuple(missing),
        entry_count=len(entries),
        push_results=push_results,
        mocked=mock_mode,
        elapsed_seconds=round(time.monotonic() - started, 3),
    )
