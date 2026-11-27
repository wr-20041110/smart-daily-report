"""主编排入口（design.md 4.5 契约）：采集 → 生成 → 存储 → 推送。"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass, field
from datetime import date

from .collectors import (
    BaseCollector,
    FeishuMessageCollector,
    FeishuTaskCollector,
    GitHubCollector,
    MockCollector,
)
from .config import Settings
from .errors import CollectorError, StorageError
from .generators import build_team_report, generate_member_reports
from .models import RawEvent
from .pushers import BasePusher, EmailPusher, FeishuBotPusher, PushResult
from .storage import init_db, save_raw_events, save_reports


@dataclass
class PipelineResult:
    """全流程汇总（design.md 4.5）。"""

    day: date
    collected: dict[str, int] = field(default_factory=dict)
    missing_sources: list[str] = field(default_factory=list)
    entry_count: int = 0
    push_results: list[PushResult] = field(default_factory=list)
    mocked: bool = False
    elapsed_seconds: float = 0.0


def run_pipeline(
    day: date,
    settings: Settings,
    collectors: list[BaseCollector] | None = None,
    pushers: list[BasePusher] | None = None,
    push: bool = True,
    conn: sqlite3.Connection | None = None,
) -> PipelineResult:
    """一键执行采集→生成→存储→推送。

    降级规则（design.md 4.5）：任一数据源失败 → 记入 missing_sources 继续出报；
    生成层/存储层失败 → 抛异常（CLI 退出码 1，不推送）。
    """
    started = time.monotonic()
    mock_mode = settings.mock or not (settings.is_github_ready and settings.is_feishu_ready)
    collectors = collectors if collectors is not None else _choose_collectors(settings, mock_mode)

    result = PipelineResult(day=day, mocked=mock_mode)
    events: list[RawEvent] = []
    for collector in collectors:
        try:
            collected = collector.collect(day)
        except CollectorError as exc:
            result.missing_sources.append(collector.name)
            print(f"[采集] {collector.name} 降级：{exc}")
            continue
        result.collected[collector.name] = len(collected)
        events.extend(collected)

    entries = generate_member_reports(events, settings.members, day)
    team = build_team_report(entries, settings.members, result.missing_sources, day)
    team.mocked = mock_mode
    result.entry_count = len(entries)

    db = conn if conn is not None else init_db(settings.db_path)
    try:
        save_raw_events(db, events)
        save_reports(db, entries, team)
    except sqlite3.Error as exc:
        raise StorageError(f"SQLite 写入失败：{type(exc).__name__}: {exc}") from exc
    finally:
        if conn is None:
            db.close()

    if push:
        pushers = pushers if pushers is not None else _choose_pushers(settings)
        result.push_results = [p.push(team) for p in pushers]

    result.elapsed_seconds = round(time.monotonic() - started, 3)
    return result


def _choose_collectors(settings: Settings, mock_mode: bool) -> list[BaseCollector]:
    if mock_mode:
        return [
            MockCollector("github"),
            MockCollector("feishu_task"),
            MockCollector("feishu_message"),
        ]
    return [
        GitHubCollector(
            settings.github_repo,
            settings.github_token,
            [m.github_username for m in settings.members],
        ),
        FeishuTaskCollector(
            settings.feishu_app_id,
            settings.feishu_app_secret,
            [m.feishu_open_id for m in settings.members],
        ),
        FeishuMessageCollector(
            settings.feishu_app_id, settings.feishu_app_secret, settings.feishu_group_id
        ),
    ]


def _choose_pushers(settings: Settings) -> list[BasePusher]:
    return [
        EmailPusher(
            settings.smtp_host,
            settings.smtp_port,
            settings.smtp_user,
            settings.smtp_password,
            settings.report_sender,
            settings.report_recipients,
        ),
        FeishuBotPusher(
            settings.feishu_bot_webhook,
            settings.feishu_app_id,
            settings.feishu_app_secret,
            settings.feishu_group_id,
        ),
    ]
