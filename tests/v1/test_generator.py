"""T6 生成层验收：分类规则、协同归属 R1/R2/R3、边界场景。"""

from __future__ import annotations

from datetime import UTC, date, datetime

from daily_report_v1.generators import build_team_report, generate_member_reports
from daily_report_v1.models import UNMAPPED_NAME, Member, RawEvent

DAY = date(2026, 11, 24)
MEMBERS = [
    Member("王然", "wr-20041110", "ou_wr-20041110", "a@x.com"),
    Member("咸哲", "xz0622", "ou_xz0622", "b@x.com"),
    Member("王峻羽", "wjy-jjj", "ou_wjy-jjj", "c@x.com"),
]


def ev(**kw) -> RawEvent:
    base = dict(
        source="github",
        event_type="commit",
        ref="r1",
        author="wr-20041110",
        occurred_at=datetime(2026, 11, 24, 2, 0, tzinfo=UTC),
        title="提交 A",
    )
    base.update(kw)
    return RawEvent(**base)


def entries_of(entries, name, category):
    return [e for e in entries if e.member_name == name and e.category == category]


def test_plain_commit_goes_to_dev():
    entries = generate_member_reports([ev()], MEMBERS, DAY)
    assert len(entries_of(entries, "王然", "dev")) == 1
    assert "提交 A" in entries_of(entries, "王然", "dev")[0].items[0]


def test_plain_message_goes_to_discuss():
    e = ev(
        source="feishu_message", event_type="message", author="ou_xz0622", title="大家看下文档"
    )
    entries = generate_member_reports([e], MEMBERS, DAY)
    assert len(entries_of(entries, "咸哲", "discuss")) == 1


def test_r1_coauthored_commit_attributed_to_both():
    e = ev(ref="c1", collaborators=["xz0622"])
    entries = generate_member_reports([e], MEMBERS, DAY)
    assert len(entries_of(entries, "王然", "collab")) == 1
    assert len(entries_of(entries, "咸哲", "collab")) == 1
    assert "你发起" in entries_of(entries, "王然", "collab")[0].items[0]
    assert "你参与" in entries_of(entries, "咸哲", "collab")[0].items[0]


def test_r2_task_with_collaborators():
    e = ev(
        source="feishu_task",
        event_type="task",
        author="ou_wr-20041110",
        collaborators=["ou_wjy-jjj"],
    )
    entries = generate_member_reports([e], MEMBERS, DAY)
    assert {n for en in entries if en.category == "collab" for n in [en.member_name]} >= {
        "王然",
        "王峻羽",
    }


def test_r3_mention_with_task_id():
    e = ev(
        source="feishu_message",
        event_type="message",
        ref="m1",
        author="ou_wr-20041110",
        title="@咸哲 T-101 帮看下接口",
        collaborators=["ou_xz0622"],
        payload={"task_id": "T-101", "mentions": ["ou_xz0622"]},
    )
    entries = generate_member_reports([e], MEMBERS, DAY)
    # 发言者同时有 discuss 与 collab（R3）
    assert len(entries_of(entries, "王然", "discuss")) == 1
    assert len(entries_of(entries, "王然", "collab")) == 1
    assert len(entries_of(entries, "咸哲", "collab")) == 1


def test_mention_without_task_id_is_not_collab():
    e = ev(
        source="feishu_message",
        event_type="message",
        ref="m2",
        author="ou_wr-20041110",
        title="@咸哲 在吗",
        collaborators=["ou_xz0622"],
        payload={"mentions": ["ou_xz0622"], "task_id": None},
    )
    entries = generate_member_reports([e], MEMBERS, DAY)
    assert not entries_of(entries, "咸哲", "collab")


def test_dedup_same_source_ref():
    entries = generate_member_reports([ev(), ev()], MEMBERS, DAY)
    assert len(entries_of(entries, "王然", "dev")[0].items) == 1


def test_member_without_events_listed():
    team = build_team_report(generate_member_reports([ev()], MEMBERS, DAY), MEMBERS, [], DAY)
    assert "咸哲" in team.members_without_events
    assert "王峻羽" in team.members_without_events


def test_unknown_account_goes_to_unmapped():
    e = ev(author="stranger", collaborators=[])
    entries = generate_member_reports([e], MEMBERS, DAY)
    assert entries_of(entries, UNMAPPED_NAME, "dev")


def test_team_report_ordering_and_markdown():
    entries = generate_member_reports(
        [
            ev(),
            ev(
                source="feishu_message",
                event_type="message",
                author="ou_wr-20041110",
                ref="m9",
                title="讨论",
            ),
        ],
        MEMBERS,
        DAY,
    )
    team = build_team_report(entries, MEMBERS, ["feishu_task"], DAY)
    md = team.to_markdown()
    assert md.startswith(f"# 团队日报 · {DAY.isoformat()}")
    assert "缺失数据源：feishu_task" in md
    assert md.index("## 王然") < md.index("## 咸哲")  # 成员按配置顺序
    assert md.index("### 开发") < md.index("### 讨论")  # 分类按 dev→collab→discuss
    assert "- 今日无记录" in md
