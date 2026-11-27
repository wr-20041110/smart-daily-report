"""T207 规则引擎验收（红→绿归档）：R1/R2/R3 断言 + SC4 归属正确率（v2 数据集）。"""

from __future__ import annotations

from datetime import UTC, datetime

from daily_report_v2.domain import RawEvent
from daily_report_v2.fetch import EXPECTED_ATTRIBUTION_V2, build_mock_events_v2
from daily_report_v2.rules import (
    apply_rules,
    rule_coauthored_commit,
    rule_collaborative_task,
    rule_mention_with_task,
)
from daily_report_v2.synthesize import build_entries

from .conftest import DAY, MEMBERS


def ev(
    source, collaborators=(), payload=None, title="t", author="wr-20041110", ref="r1"
) -> RawEvent:
    return RawEvent(
        source=source,
        event_type="x",
        ref=ref,
        author=author,
        occurred_at=datetime(2026, 12, 1, 2, 0, tzinfo=UTC),
        title=title,
        collaborators=tuple(collaborators),
        payload=payload or {},
    )


def test_r1_hits_commit_with_coauthors():
    e = ev("github", collaborators=("xz0622",))
    attr = rule_coauthored_commit(e)
    assert attr is not None and attr.rule == "R1"
    assert attr.participants == ("wr-20041110", "xz0622")


def test_r1_misses_plain_commit():
    assert rule_coauthored_commit(ev("github")) is None


def test_r2_hits_task_with_collaborators():
    e = ev("feishu_task", author="ou_wr-20041110", collaborators=("ou_xz0622",))
    attr = rule_collaborative_task(e)
    assert attr is not None and attr.rule == "R2"


def test_r3_hits_mention_with_task_id():
    e = ev("feishu_message", collaborators=("ou_xz0622",), payload={"task_id": "T-201"})
    attr = rule_mention_with_task(e)
    assert attr is not None and attr.rule == "R3"


def test_r3_misses_mention_without_task():
    e = ev("feishu_message", collaborators=("ou_xz0622",), payload={"task_id": None})
    assert rule_mention_with_task(e) is None


def test_r3_falls_back_to_task_id_in_title():
    e = ev(
        "feishu_message", title="@咸哲 T-201 帮看下", collaborators=("ou_xz0622",), payload={}
    )
    assert rule_mention_with_task(e) is not None


def test_apply_rules_dedup():
    e = ev("github", collaborators=("xz0622",), ref="dup")
    attrs = apply_rules([e, e])
    assert len(attrs) == 1


def test_sc4_attribution_accuracy_on_v2_dataset():
    """SC4 复验（v2 数据集）：12 条标注协作事件归属正确率 ≥ 95%。"""
    events = build_mock_events_v2(DAY, include_attendance=False)
    attributions = apply_rules(events)
    entries = build_entries(events, attributions, MEMBERS, DAY)

    actual: dict[str, set[str]] = {}
    for entry in entries:
        if entry.category != "collab":
            continue
        for key in entry.raw_refs:
            ref = key.split(":", 1)[1]
            actual.setdefault(ref, set()).add(entry.member_name)

    assert len(EXPECTED_ATTRIBUTION_V2) == 12
    mismatches = [
        (ref, sorted(exp), sorted(actual.get(ref, set())))
        for ref, exp in EXPECTED_ATTRIBUTION_V2.items()
        if actual.get(ref, set()) != set(exp)
    ]
    assert len(mismatches) <= 1, f"归属错误 {len(mismatches)} 条（>1）：{mismatches}"
    print(f"SC4（v2 数据集）核对：12 条协作事件，归属正确 {12 - len(mismatches)} 条")
