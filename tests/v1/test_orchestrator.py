"""T9 主编排验收：全链路串联、降级出报、推送开关、幂等重跑、存储失败阻断。"""

from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from daily_report_v1.collectors import BaseCollector
from daily_report_v1.errors import CollectorError, StorageError
from daily_report_v1.models import RawEvent
from daily_report_v1.orchestrator import run_pipeline
from daily_report_v1.storage import init_db, load_team_report

from .conftest import DAY


class FailingCollector(BaseCollector):
    name = "broken"

    def collect(self, day: date) -> list[RawEvent]:
        raise CollectorError("模拟网络故障")


def test_mock_end_to_end(settings):
    result = run_pipeline(DAY, settings, push=False)
    assert result.mocked is True
    assert result.collected == {"github": 20, "feishu_task": 15, "feishu_message": 15}
    assert result.missing_sources == []
    assert result.entry_count == 9  # 3 成员 × (dev + collab + discuss)，每成员每分类 1 条
    assert result.elapsed_seconds >= 0


def test_source_failure_degrades(settings):
    result = run_pipeline(DAY, settings, collectors=[FailingCollector()], push=False)
    assert "broken" in result.missing_sources
    assert result.entry_count == 0  # 无事件 → 无条目，但流程完成（降级出报）


def test_push_off(settings):
    result = run_pipeline(DAY, settings, push=False)
    assert result.push_results == []


def test_push_on_mocked_channels(settings):
    result = run_pipeline(DAY, settings)
    assert {p.channel for p in result.push_results} == {"email", "feishu"}
    assert all(p.mocked for p in result.push_results)  # 无凭证 → mock 留痕


def test_storage_failure_blocks(settings, monkeypatch):
    import daily_report_v1.orchestrator as mod

    def boom(*a, **kw):
        raise sqlite3.Error("磁盘错误")

    monkeypatch.setattr(mod, "save_reports", boom)
    with pytest.raises(StorageError):
        run_pipeline(DAY, settings, push=False)


def test_rerun_idempotent(settings):
    run_pipeline(DAY, settings, push=False)
    conn = init_db(settings.db_path)
    first = conn.execute("SELECT COUNT(*) FROM raw_events").fetchone()[0]
    conn.close()
    run_pipeline(DAY, settings, push=False)  # 同日期重跑
    conn = init_db(settings.db_path)
    assert conn.execute("SELECT COUNT(*) FROM raw_events").fetchone()[0] == first  # 事件不重复入库
    assert load_team_report(conn, DAY) is not None
    conn.close()


def test_cli_mock_run(settings, monkeypatch, capsys):
    import daily_report_v1.cli as cli_mod

    monkeypatch.setattr(cli_mod, "load_settings", lambda mock=False: settings)
    code = cli_mod.main(["--date", DAY.isoformat(), "--mock", "--no-push"])
    out = capsys.readouterr().out
    assert code == 0
    assert "Mock（内置模拟数据）" in out
    assert "生成条目：9 条" in out
