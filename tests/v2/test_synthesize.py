"""T208/T214 编排验收（红→绿归档）：分类聚合、协同归属行、考勤行（变更单）、无记录成员。"""

from __future__ import annotations

from datetime import UTC, datetime

from daily_report_v2.domain import RawEvent
from daily_report_v2.rules import apply_rules
from daily_report_v2.synthesize import (
    account_to_name,
    build_entries,
    make_team_report,
    render_team_report,
)

from .conftest import DAY, MEMBERS


def ev(
    source, author="wr-20041110", collaborators=(), payload=None, title="t", ref="r1", hour=10
) -> RawEvent:
    return RawEvent(
        source=source,
        event_type="x",
        ref=ref,
        author=author,
        occurred_at=datetime(2026, 12, 1, hour - 8, 0, tzinfo=UTC),  # 本地 10:00
        title=title,
        collaborators=tuple(collaborators),
        payload=payload or {},
    )


def entries_for(entries, name, category):
    return [e for e in entries if e.member_name == name and e.category == category]


def test_account_mapping_three_ways():
    assert account_to_name("wr-20041110", MEMBERS) == "王然"  # GitHub 用户名
    assert account_to_name("ou_1285ac40fd873adf31e91d930be504b3", MEMBERS) == "咸哲"  # 飞书 open_id
    assert account_to_name("王峻羽", MEMBERS) == "王峻羽"  # 姓名直配
    assert account_to_name("stranger", MEMBERS) is None


def test_plain_commit_to_dev():
    entries = build_entries([ev("github")], [], MEMBERS, DAY)
    assert len(entries_for(entries, "王然", "dev")) == 1


def test_message_to_discuss():
    entries = build_entries(
        [ev("feishu_message", author="ou_1285ac40fd873adf31e91d930be504b3")], [], MEMBERS, DAY
    )
    assert len(entries_for(entries, "咸哲", "discuss")) == 1


def test_r3_message_gets_discuss_and_collab():
    e = ev(
        "feishu_message",
        author="ou_9fb641793dcb3547d8d1c4e655b7e589",
        title="@咸哲 T-201 帮看下",
        collaborators=("ou_1285ac40fd873adf31e91d930be504b3",),
        payload={"task_id": "T-201"},
    )
    attrs = apply_rules([e])
    entries = build_entries([e], attrs, MEMBERS, DAY)
    assert len(entries_for(entries, "王然", "discuss")) == 1
    assert len(entries_for(entries, "王然", "collab")) == 1
    assert len(entries_for(entries, "咸哲", "collab")) == 1
    assert "你发起" in entries_for(entries, "王然", "collab")[0].items[0]
    assert "你参与" in entries_for(entries, "咸哲", "collab")[0].items[0]


def test_attendance_line_at_dev_top():
    e1 = ev(
        "feishu_attendance",
        author="ou_9fb641793dcb3547d8d1c4e655b7e589",
        ref="a1",
        hour=9,
        payload={"period": "am_in"},
        title="考勤打卡（上午上班）",
    )
    e2 = ev(
        "feishu_attendance",
        author="ou_9fb641793dcb3547d8d1c4e655b7e589",
        ref="a2",
        hour=18,
        payload={"period": "pm_out"},
        title="考勤打卡（下午下班）",
    )
    e3 = ev("github", ref="c1", hour=11, title="普通提交")
    entries = build_entries([e1, e2, e3], [], MEMBERS, DAY)
    dev = entries_for(entries, "王然", "dev")[0]
    assert dev.items[0].startswith("考勤｜09:00 上午上班、18:00 下午下班")
    assert any("普通提交" in i for i in dev.items)  # 考勤行在普通条目之前


def test_member_without_events_listed():
    entries = build_entries([ev("github")], [], MEMBERS, DAY)
    team = make_team_report(entries, MEMBERS, [], DAY, mocked=False)
    assert set(team.members_without_events) == {"咸哲", "王峻羽", "尹博弘"}


def test_render_contains_attendance_source_line():
    entries = build_entries([ev("github")], [], MEMBERS, DAY)
    team = make_team_report(entries, MEMBERS, ["feishu_attendance"], DAY, mocked=True)
    md = render_team_report(team)
    assert "数据来源：GitHub 提交 / 飞书任务 / 飞书消息 / 飞书考勤" in md
    assert "缺失数据源：feishu_attendance" in md
    assert "Mock 模式" in md
