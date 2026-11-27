"""T203 存储层验收（红→绿归档）：幂等建表、事件去重、日报往返与按日期查询。"""

from __future__ import annotations

from datetime import UTC, date, datetime

from daily_report_v2.domain import DailyReportEntry, RawEvent, TeamReport
from daily_report_v2.store import load_team_report, open_db, save_events, save_reports

DAY = date(2026, 12, 1)


def make_event(ref="e1") -> RawEvent:
    return RawEvent(
        source="github",
        event_type="commit",
        ref=ref,
        author="wr-20041110",
        occurred_at=datetime(2026, 12, 1, 2, 0, tzinfo=UTC),
        title="提交",
    )


def test_open_db_idempotent(tmp_path):
    open_db(tmp_path / "r.db")
    open_db(tmp_path / "r.db")  # 连开两次不报错


def test_duplicate_events_ignored(tmp_path):
    conn = open_db(tmp_path / "r.db")
    save_events(conn, [make_event("dup"), make_event("dup")])
    n = conn.execute("SELECT COUNT(*) FROM raw_events").fetchone()[0]
    assert n == 1


def test_reports_roundtrip(tmp_path):
    conn = open_db(tmp_path / "r.db")
    entry = DailyReportEntry(
        date=DAY,
        member_name="王然",
        category="dev",
        items=("- 09:00 提交",),
        raw_refs=("github:e1",),
    )
    team = TeamReport(date=DAY, generated_at=datetime(2026, 12, 1, 10, 0, tzinfo=UTC))
    rendered = "rendered markdown"
    save_reports(conn, [entry], team, rendered)

    content = load_team_report(conn, DAY)
    assert content == rendered
    assert load_team_report(conn, date(2026, 12, 2)) is None

    row = conn.execute("SELECT member_name, category, raw_refs FROM daily_reports").fetchone()
    assert row == ("王然", "dev", '["github:e1"]')


def test_rerun_overwrites(tmp_path):
    conn = open_db(tmp_path / "r.db")
    team1 = TeamReport(date=DAY)
    save_reports(conn, [], team1, "v1")
    team2 = TeamReport(date=DAY)
    save_reports(conn, [], team2, "v2")
    assert load_team_report(conn, DAY) == "v2"
    n = conn.execute("SELECT COUNT(*) FROM team_reports").fetchone()[0]
    assert n == 1
