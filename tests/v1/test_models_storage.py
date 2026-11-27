"""T2 共享基础层验收：models / storage（含幂等与往返一致）。"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from daily_report_v1.config import Settings
from daily_report_v1.errors import ConfigError
from daily_report_v1.models import DailyReportEntry, Member, RawEvent, TeamReport
from daily_report_v1.storage import init_db, load_team_report, save_raw_events, save_reports

DAY = date(2026, 11, 24)


def make_event(ref="a1", **kw) -> RawEvent:
    base = dict(
        source="github",
        event_type="commit",
        ref=ref,
        author="wr-20041110",
        occurred_at=datetime(2026, 11, 24, 1, 0, tzinfo=UTC),
        title="测试提交",
    )
    base.update(kw)
    return RawEvent(**base)


def test_member_name_unique_validation():
    dup = [Member("王然", "a", "b", "c@x.com"), Member("王然", "d", "e", "f@x.com")]
    with pytest.raises(ConfigError, match="唯一"):
        Settings(members=dup).validate()


def test_raw_event_roundtrip():
    ev = make_event(collaborators=["XianZhe727"], payload={"files": 3})
    back = RawEvent.from_dict(ev.to_dict())
    assert back == ev


def test_init_db_idempotent(tmp_path):
    path = tmp_path / "r.db"
    init_db(path)
    init_db(path)  # 连跑两次不报错


def test_save_load_roundtrip(tmp_path):
    conn = init_db(tmp_path / "r.db")
    ev = make_event()
    save_raw_events(conn, [ev])
    team = TeamReport(date=DAY, members_without_events=["咸哲"])
    save_reports(
        conn,
        [
            DailyReportEntry(
                date=DAY, member_name="王然", category="dev", items=["- 09:00 测试提交"]
            )
        ],
        team,
    )
    content = load_team_report(conn, DAY)
    assert content is not None and "团队日报" in content
    assert load_team_report(conn, date(2026, 11, 25)) is None


def test_duplicate_event_ignored(tmp_path):
    conn = init_db(tmp_path / "r.db")
    save_raw_events(conn, [make_event(ref="dup"), make_event(ref="dup")])
    n = conn.execute("SELECT COUNT(*) FROM raw_events").fetchone()[0]
    assert n == 1  # (source, ref) 唯一约束 + INSERT OR IGNORE


def test_rerun_overwrites_team_report(tmp_path):
    conn = init_db(tmp_path / "r.db")
    team1 = TeamReport(date=DAY)
    team1.generated_at = datetime(2026, 11, 24, 9, 0, tzinfo=UTC)
    save_reports(conn, [], team1)
    team2 = TeamReport(date=DAY)
    team2.generated_at = datetime(2026, 11, 24, 10, 0, tzinfo=UTC)
    save_reports(conn, [], team2)
    n = conn.execute(
        "SELECT COUNT(*) FROM team_reports WHERE report_date = ?", (DAY.isoformat(),)
    ).fetchone()[0]
    assert n == 1  # 同日期覆盖更新（幂等重跑）


def test_dotenv_loading(tmp_path, monkeypatch):
    """凭证可经 .env 文件注入环境变量（已存在的环境变量优先，不覆盖）。"""
    import daily_report_v1.config as cfg

    env_file = tmp_path / ".env"
    env_file.write_text("GITHUB_TOKEN=from-dotenv\nSMTP_PORT=587\n# 注释行\n", encoding="utf-8")
    monkeypatch.setenv("GITHUB_TOKEN", "already-set")
    cfg._load_dotenv(env_file)
    import os

    assert os.environ["GITHUB_TOKEN"] == "already-set"  # 已有环境变量优先
    assert os.environ["SMTP_PORT"] == "587"
