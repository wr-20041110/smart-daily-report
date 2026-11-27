"""SQLite 存储（design.md 模块职责：共享-存储，ADR-002）。

三张表：raw_events / daily_reports / team_reports（design.md 3.2，ER 图见 specs/uml/er.puml）。
全部 SQL 参数化；(source, ref) 唯一约束保证事件去重与重跑幂等（design.md 非功能约束）。
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from pathlib import Path

from .models import DailyReportEntry, RawEvent, TeamReport

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


def init_db(path: str | Path) -> sqlite3.Connection:
    """建表（幂等，tasks.md T2 验收标准）。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(_SCHEMA)
    conn.commit()
    return conn


def save_raw_events(conn: sqlite3.Connection, events: list[RawEvent]) -> None:
    """批量写入原始事件；(source, ref) 重复者忽略（幂等）。"""
    now = datetime.now().astimezone().isoformat()
    rows = [
        (
            e.source,
            e.event_type,
            e.ref,
            e.author,
            e.occurred_at.isoformat(),
            e.title,
            e.url,
            json.dumps(e.collaborators, ensure_ascii=False),
            json.dumps(e.payload, ensure_ascii=False),
            now,
        )
        for e in events
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO raw_events"
        " (source, event_type, ref, author, occurred_at, title, url,"
        "  collaborators, payload, collected_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()


def save_reports(
    conn: sqlite3.Connection,
    entries: list[DailyReportEntry],
    team: TeamReport,
) -> None:
    """写入个人日报条目与团队日报；同 (日期, 成员, 分类) 覆盖更新（幂等重跑）。"""
    now = datetime.now().astimezone().isoformat()
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
                json.dumps(e.raw_refs, ensure_ascii=False),
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
            team.to_markdown(),
            json.dumps(team.missing_sources, ensure_ascii=False),
            (team.generated_at or datetime.now().astimezone()).isoformat(),
        ),
    )
    conn.commit()


def load_team_report(conn: sqlite3.Connection, day: date) -> str | None:
    """按日期查询历史团队日报（proposal.md G5）。"""
    row = conn.execute(
        "SELECT content FROM team_reports WHERE report_date = ?", (day.isoformat(),)
    ).fetchone()
    return row[0] if row else None
