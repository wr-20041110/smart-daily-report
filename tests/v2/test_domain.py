"""T202 领域模型验收（红→绿归档）：frozen 不可变、函数式序列化往返。"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from daily_report_v2.domain import RawEvent, event_from_dict, event_to_dict


def make_event(**kw) -> RawEvent:
    base = dict(
        source="github",
        event_type="commit",
        ref="r1",
        author="wr-20041110",
        occurred_at=datetime(2026, 12, 1, 2, 0, tzinfo=UTC),
        title="测试提交",
    )
    base.update(kw)
    return RawEvent(**base)


def test_frozen_immutable():
    ev = make_event()
    with pytest.raises(Exception):  # frozen 数据类禁止赋值
        ev.title = "篡改"  # type: ignore[misc]


def test_collaborators_are_tuple():
    ev = make_event(collaborators=("XianZhe727",))
    assert isinstance(ev.collaborators, tuple)


def test_event_roundtrip_via_functions():
    ev = make_event(collaborators=("XianZhe727", "wjy-jjj"), payload={"files": 3})
    back = event_from_dict(event_to_dict(ev))
    assert back == ev


def test_naive_datetime_normalized_to_utc():
    ev = event_from_dict({"occurred_at": "2026-12-01T02:00:00", **base_dict()})
    assert ev.occurred_at.tzinfo == UTC


def base_dict():
    return {
        "source": "github",
        "event_type": "commit",
        "ref": "r1",
        "author": "wr-20041110",
        "title": "t",
        "url": "",
        "collaborators": [],
        "payload": {},
    }
