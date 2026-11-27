"""T210 管道验收（红→绿归档）：全链路、降级出报、推送开关、幂等重跑、存储失败阻断。"""

from __future__ import annotations

import sqlite3

import pytest

from daily_report_v2.fetch import CollectorError
from daily_report_v2.pipeline import StorageError, run_pipeline
from daily_report_v2.store import load_team_report, open_db

from .conftest import DAY


def broken_fetcher(day, settings):
    raise CollectorError("模拟网络故障")


def test_mock_end_to_end(settings):
    result = run_pipeline(DAY, settings, push=False)
    assert result.mocked is True
    assert result.collected == {"mock": 56}  # 50 条 + 6 条考勤（变更单 F12）
    assert result.missing_sources == ()
    assert result.entry_count == 9  # 3 成员 × (dev + collab + discuss)
    assert result.elapsed_seconds >= 0


def test_source_failure_degrades(settings):
    result = run_pipeline(DAY, settings, push=False, fetchers={"mock": broken_fetcher})
    assert result.missing_sources == ("mock",)
    assert result.entry_count == 0


def test_push_off(settings):
    assert run_pipeline(DAY, settings, push=False).push_results == ()


def test_push_on_mocked_channels(settings):
    result = run_pipeline(DAY, settings)
    assert {p.channel for p in result.push_results} == {"email", "feishu"}
    assert all(p.mocked for p in result.push_results)


def test_storage_failure_blocks(settings, monkeypatch):
    import daily_report_v2.pipeline as mod

    def boom(*a, **kw):
        raise sqlite3.Error("磁盘错误")

    monkeypatch.setattr(mod, "save_reports", boom)
    with pytest.raises(StorageError):
        run_pipeline(DAY, settings, push=False)


def test_rerun_idempotent(settings):
    run_pipeline(DAY, settings, push=False)
    conn = open_db(settings.db_path)
    first = conn.execute("SELECT COUNT(*) FROM raw_events").fetchone()[0]
    conn.close()
    run_pipeline(DAY, settings, push=False)
    conn = open_db(settings.db_path)
    assert conn.execute("SELECT COUNT(*) FROM raw_events").fetchone()[0] == first
    assert load_team_report(conn, DAY) is not None
    conn.close()


def test_cli_mock_run(settings, monkeypatch, capsys):
    import daily_report_v2.cli as cli_mod

    monkeypatch.setattr(cli_mod, "load_settings", lambda mock=False: settings)
    code = cli_mod.main(["--date", DAY.isoformat(), "--mock", "--no-push"])
    out = capsys.readouterr().out
    assert code == 0
    assert "Mock（内置模拟数据）" in out
    assert "生成条目：9 条" in out


def test_attendance_present_in_report(settings):
    run_pipeline(DAY, settings, push=False)
    conn = open_db(settings.db_path)
    md = load_team_report(conn, DAY)
    assert md is not None
    assert "考勤｜" in md  # 变更涟漪 F12：每名成员日报头部有考勤行
    conn.close()
