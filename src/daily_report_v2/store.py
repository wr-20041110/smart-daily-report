"""SQLite 存储（v2：from zero 实现；三表结构与唯一约束继承 design.md 3.2 / ADR-002）。

与 v1 的差异：全部用 `with conn:` 事务块；序列化经由 domain 的模块级函数。
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path

from .domain import DailyReportEntry, RawEvent, TeamReport, event_to_dict

_SCHEMA = """
CREATE TABLE IF NOT EXISTS raw_events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source        TEXT NOT NULL,
    event_type    TEXT NOT NULL,
    ref           TEXT NOT NULL,
    author        TEXT NOT NULL,
    occurred_at   TEXT NOT NULL,
    title         TEXT NOT NULL,
    url           TEXT,
    collaborators TEXT NOT NULL DEFAULT '[]',
    payload       TEXT NOT NULL DEFAULT '{}',
    collected_at  TEXT NOT NULL,
    UNIQUE(source, ref)
);
CREATE TABLE IF NOT EXISTS daily_reports (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    report_date TEXT NOT NULL,
    member_name TEXT NOT NULL,
    category    TEXT NOT NULL,
    content     TEXT NOT NULL,
    raw_refs    TEXT NOT NULL DEFAULT '[]',
    created_at  TEXT NOT NULL,
    UNIQUE(report_date, member_name, category)
);
CREATE TABLE IF NOT EXISTS team_reports (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    report_date     TEXT NOT NULL UNIQUE,
    content         TEXT NOT NULL,
    missing_sources TEXT NOT NULL DEFAULT '[]',
    generated_at    TEXT NOT NULL
);
"""


def open_db(path: str | Path) -> sqlite3.Connection:
    """打开（必要时创建目录）并幂等建表。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    with conn:
        conn.executescript(_SCHEMA)
    return conn


def save_events(conn: sqlite3.Connection, events: list[RawEvent]) -> None:
    """批量写入原始事件；(source, ref) 重复者忽略（幂等）。"""
    now = datetime.now().astimezone().isoformat()
    rows = []
    for ev in events:
        d = event_to_dict(ev)
        rows.append(
            (
                d["source"],
                d["event_type"],
                d["ref"],
                d["author"],
                d["occurred_at"],
                d["title"],
                d["url"],
                json.dumps(d["collaborators"], ensure_ascii=False),
                json.dumps(d["payload"], ensure_ascii=False),
                now,
            )
        )
    with conn:
        conn.executemany(
            "INSERT OR IGNORE INTO raw_events"
            " (source, event_type, ref, author, occurred_at, title, url,"
            "  collaborators, payload, collected_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )


def save_reports(
    conn: sqlite3.Connection,
    entries: list[DailyReportEntry],
    team: TeamReport,
    rendered: str,
) -> None:
    """写入个人条目与团队日报（团队日报全文由调用方渲染后传入，保持单一渲染入口）。"""
    now = datetime.now().astimezone().isoformat()
    with conn:
        conn.executemany(
            "INSERT OR REPLACE INTO daily_reports"
            " (report_date, member_name, category, content, raw_refs, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    e.date.isoformat(),
                    e.member_name,
                    e.category,
                    "\n".join(e.items),
                    json.dumps(list(e.raw_refs), ensure_ascii=False),
                    now,
                )
                for e in entries
            ],
        )
        conn.execute(
            "INSERT OR REPLACE INTO team_reports"
            " (report_date, content, missing_sources, generated_at)"
            " VALUES (?, ?, ?, ?)",
            (
                team.date.isoformat(),
                rendered,
                json.dumps(list(team.missing_sources), ensure_ascii=False),
                (team.generated_at or datetime.now().astimezone()).astimezone(UTC).isoformat(),
            ),
        )


def load_team_report(conn: sqlite3.Connection, day: date) -> str | None:
    """按日期查询历史团队日报。"""
    row = conn.execute(
        "SELECT content FROM team_reports WHERE report_date = ?", (day.isoformat(),)
    ).fetchone()
    return row[0] if row else None
