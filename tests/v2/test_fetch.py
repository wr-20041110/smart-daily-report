"""T204–T206/T213 采集层验收（红→绿归档）：mock 数据集、GitHub、飞书任务/消息/考勤。"""

from __future__ import annotations

import pytest

from daily_report_v2.fetch import (
    MAX_REQUESTS_PER_RUN,
    CollectorError,
    CredentialsMissingError,
    build_mock_events_v2,
    day_window,
    fetch_feishu_attendance,
    fetch_feishu_message,
    fetch_feishu_task,
    fetch_github,
    fetch_mock,
)

from .conftest import DAY, MEMBERS, FakeClient, Settings


def github_settings(**kw) -> Settings:
    return Settings(members=tuple(MEMBERS), github_repo="team/repo", github_token="tok", **kw)


def feishu_settings(**kw) -> Settings:
    return Settings(
        members=tuple(MEMBERS),
        feishu_app_id="id",
        feishu_app_secret="sec",
        feishu_group_id="oc_group",
        **kw,
    )


def feishu_settings_no_group(**kw) -> Settings:
    return Settings(
        members=tuple(MEMBERS),
        feishu_app_id="id",
        feishu_app_secret="sec",
        feishu_group_id=None,
        **kw,
    )


# ---- Mock 数据集（阶段二全新内容） ----


def test_mock_v2_counts_with_attendance():
    events = build_mock_events_v2(DAY)
    by_source: dict[str, int] = {}
    for e in events:
        by_source[e.source] = by_source.get(e.source, 0) + 1
    assert by_source == {
        "github": 20,
        "feishu_task": 15,
        "feishu_message": 15,
        "feishu_attendance": 6,
    }


def test_fetch_mock_entrypoint():
    events = fetch_mock(DAY, Settings(members=tuple(MEMBERS)))
    assert len(events) == 56


# ---- GitHub ----


def _commit(login="wr-20041110", message="feat: 测试提交", sha="abc", date="2026-12-01T02:00:00Z"):
    return {
        "sha": sha,
        "html_url": f"https://github.com/team/repo/commit/{sha}",
        "author": {"login": login},
        "commit": {"message": message, "committer": {"date": date}},
    }


def test_github_requires_token():
    s = Settings(members=tuple(MEMBERS), github_repo="team/repo")
    with pytest.raises(CredentialsMissingError):
        fetch_github(DAY, s, session=FakeClient([[]]))


def test_github_window_filter_and_auth():
    client = FakeClient([[_commit(), _commit(login="outsider")]])
    events = fetch_github(DAY, github_settings(), session=client)
    start, end = day_window(DAY)
    params = client.calls[0]["params"]
    assert params["since"] == start.isoformat() and params["until"] == end.isoformat()
    assert params["since"].startswith("2026-11-30T16:00:00")  # Asia/Shanghai → UTC
    assert client.calls[0]["headers"]["Authorization"] == "Bearer tok"
    assert len(events) == 1 and events[0].author == "wr-20041110"


def test_github_coauthor_parsing():
    msg = "feat: 规则引擎\n\nCo-authored-by: XianZhe727 <XianZhe727@example.com>"
    client = FakeClient([[_commit(message=msg)]])
    events = fetch_github(DAY, github_settings(), session=client)
    assert events[0].collaborators == ("XianZhe727",)
    assert events[0].payload["co_authored"] is True


def test_github_pagination_and_guard(monkeypatch):
    import daily_report_v2.fetch as fetch_mod

    monkeypatch.setattr(fetch_mod.time, "sleep", lambda s: None)
    page = [_commit(sha=f"s{i}") for i in range(100)]
    client = FakeClient([page] * 30)
    with pytest.raises(CollectorError, match="上限"):
        fetch_github(DAY, github_settings(), session=client)
    assert len(client.calls) <= MAX_REQUESTS_PER_RUN + 1


def test_github_retry_then_success(monkeypatch):
    import daily_report_v2.fetch as fetch_mod

    monkeypatch.setattr(fetch_mod.time, "sleep", lambda s: None)
    client = FakeClient([[_commit()]], fail_times=2)
    events = fetch_github(DAY, github_settings(), session=client)
    assert len(events) == 1


def test_github_retry_exhausted(monkeypatch):
    import daily_report_v2.fetch as fetch_mod

    monkeypatch.setattr(fetch_mod.time, "sleep", lambda s: None)
    with pytest.raises(CollectorError, match="重试 3 次"):
        fetch_github(DAY, github_settings(), session=FakeClient([[]], fail_times=99))


# ---- 飞书 ----


def _task(guid="g1", assignee="ou_wr-20041110", collabs=(), summary="任务A"):
    return {
        "guid": guid,
        "assignee": assignee,
        "collaborator_ids": list(collabs),
        "summary": summary,
    }


def test_feishu_requires_credentials():
    s = Settings(members=tuple(MEMBERS))
    with pytest.raises(CredentialsMissingError):
        fetch_feishu_task(DAY, s, session=FakeClient([[]]))


def test_feishu_task_mapping():
    client = FakeClient([{"code": 0, "data": {"items": [_task(collabs=("ou_XianZhe727",))]}}])
    events = fetch_feishu_task(DAY, feishu_settings(), session=client)
    assert events[0].author == "ou_wr-20041110"
    assert events[0].collaborators == ("ou_XianZhe727",)
    assert events[0].ref == "g1"
    assert client.calls[0]["json"] == {"app_id": "id", "app_secret": "sec"}


def test_feishu_message_parsing():
    item = {
        "message_id": "m1",
        "sender": {"id": "ou_wr-20041110"},
        "create_time": "1764550400000",
        "body": {"content": '{"text": "@咸哲 T-201 骨架帮我评审"}'},
    }
    client = FakeClient([{"code": 0, "data": {"items": [item]}}])
    events = fetch_feishu_message(DAY, feishu_settings(), session=client)
    assert events[0].collaborators == ("咸哲",)
    assert events[0].payload["task_id"] == "T-201"


def test_feishu_message_requires_group():
    s = feishu_settings_no_group()
    with pytest.raises(CredentialsMissingError):
        fetch_feishu_message(DAY, s, session=FakeClient([{"code": 0, "data": {"items": []}}]))


def test_attendance_mapping():
    body = {
        "code": 0,
        "data": {
            "user_stats": [
                {
                    "user_id": "ou_wr-20041110",
                    "records": [{"check_type": "am_in", "check_time": "1764550920000"}],
                },
                {
                    "user_id": "ou_other",
                    "records": [{"check_type": "am_in", "check_time": "1764550920000"}],
                },
            ]
        },
    }
    client = FakeClient([body])
    events = fetch_feishu_attendance(DAY, feishu_settings(), session=client)
    assert len(events) == 1  # 非团队成员考勤被过滤
    assert events[0].source == "feishu_attendance"
    assert events[0].payload["period"] == "am_in"
