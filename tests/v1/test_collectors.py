"""T3/T4/T5 采集层验收：Mock 数据集、GitHub、飞书（含契约：日期窗口/过滤/重试/请求上限）。"""

from __future__ import annotations

import httpx
import pytest

from daily_report_v1.collectors import (
    FeishuMessageCollector,
    FeishuTaskCollector,
    GitHubCollector,
    MockCollector,
    day_window,
)
from daily_report_v1.collectors.mock_data import MOCK_COUNTS, build_mock_events
from daily_report_v1.errors import CollectorError, CredentialsMissingError

from .conftest import DAY

# ---- Mock 数据集 ----


def test_mock_counts_match_spec():
    events = build_mock_events(DAY)
    by_source: dict[str, int] = {}
    for e in events:
        by_source[e.source] = by_source.get(e.source, 0) + 1
    assert by_source == MOCK_COUNTS == {"github": 20, "feishu_task": 15, "feishu_message": 15}


def test_mock_collector_filters_by_source_and_day():
    for source, count in MOCK_COUNTS.items():
        got = MockCollector(source).collect(DAY)
        assert len(got) == count
        assert all(e.source == source for e in got)
        assert all(e.occurred_at.day in _utc_days(DAY) for e in got)


def test_mock_collector_rejects_unknown_source_and_scene():
    with pytest.raises(CollectorError):
        MockCollector("unknown_source")
    with pytest.raises(CollectorError):
        MockCollector("github", data_key="not-a-scene")


def _utc_days(day):
    """UTC 时间可能落在本地日或前一日/次日（时区边界），允许集合校验。"""
    start, end = day_window(day)
    return {start.day, end.day}


# ---- GitHub 采集器 ----


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "err", request=httpx.Request("GET", "http://x"), response=self
            )

    def json(self):
        return self._payload


class FakeClient:
    """记录调用参数的假 httpx.Client。pages: 依次返回的页。"""

    def __init__(self, pages, fail_times=0):
        self.pages = list(pages)
        self.fail_times = fail_times
        self.calls: list[dict] = []

    def get(self, url, params=None, headers=None):
        self.calls.append(
            {"url": url, "params": dict(params or {}), "headers": dict(headers or {})}
        )
        if self.fail_times > 0:
            self.fail_times -= 1
            raise httpx.ConnectError("模拟网络失败")
        return FakeResponse(self.pages.pop(0))

    def close(self):
        pass


def _commit(
    login="wr-20041110", message="fix: 修复归属去重", sha="abc123", date="2026-11-24T02:00:00Z"
):
    return {
        "sha": sha,
        "html_url": f"https://github.com/team/repo/commit/{sha}",
        "author": {"login": login},
        "commit": {"message": message, "committer": {"date": date}},
    }


def test_github_requires_token():
    collector = GitHubCollector("team/repo", None, ["wr-20041110"], session=FakeClient([[]]))
    with pytest.raises(CredentialsMissingError):
        collector.collect(DAY)


def test_github_date_window_and_filter():
    client = FakeClient([[_commit(), _commit(login="outsider")]])
    collector = GitHubCollector("team/repo", "tok", ["wr-20041110"], session=client)
    events = collector.collect(DAY)

    start, end = day_window(DAY)
    params = client.calls[0]["params"]
    assert params["since"] == start.isoformat()
    assert params["until"] == end.isoformat()
    assert params["since"].startswith("2026-11-23T16:00:00")  # Asia/Shanghai 换 UTC
    assert client.calls[0]["headers"]["Authorization"] == "Bearer tok"
    assert len(events) == 1 and events[0].author == "wr-20041110"  # 非团队成员被过滤


def test_github_coauthor_parsing():
    msg = "fix: 归属去重\n\nCo-authored-by: xianzhe <xianzhe@example.com>"
    client = FakeClient([[_commit(message=msg)]])
    events = GitHubCollector(
        "team/repo", "tok", ["wr-20041110", "xianzhe"], session=client
    ).collect(DAY)
    assert events[0].collaborators == ["xianzhe"]
    assert events[0].payload["co_authored"] is True


def test_github_pagination_and_request_guard():
    full_page = [_commit(sha=f"s{i}") for i in range(100)]
    client = FakeClient([full_page, [_commit(sha="last")]])
    events = GitHubCollector("team/repo", "tok", ["wr-20041110"], session=client).collect(DAY)
    assert len(events) == 101  # 两页合并
    assert len(client.calls) == 2


def test_github_request_limit(monkeypatch):
    from daily_report_v1.collectors import base as base_mod

    monkeypatch.setattr(base_mod.time, "sleep", lambda s: None)
    page = [_commit(sha=f"s{i}") for i in range(100)]
    client = FakeClient([page] * 30)  # 每页都满 → 持续翻页
    with pytest.raises(CollectorError, match="上限"):
        GitHubCollector("team/repo", "tok", ["wr-20041110"], session=client).collect(DAY)
    assert len(client.calls) <= 21


def test_github_retry_then_success(monkeypatch):
    from daily_report_v1.collectors import base as base_mod

    monkeypatch.setattr(base_mod.time, "sleep", lambda s: None)
    client = FakeClient([[_commit()]], fail_times=2)  # 失败 2 次后成功（3 次重试内）
    events = GitHubCollector("team/repo", "tok", ["wr-20041110"], session=client).collect(DAY)
    assert len(events) == 1 and client.fail_times == 0


def test_github_retry_exhausted(monkeypatch):
    from daily_report_v1.collectors import base as base_mod

    monkeypatch.setattr(base_mod.time, "sleep", lambda s: None)
    client = FakeClient([[_commit()]], fail_times=99)
    with pytest.raises(CollectorError, match="重试 3 次"):
        GitHubCollector("team/repo", "tok", ["wr-20041110"], session=client).collect(DAY)


# ---- 飞书采集器 ----


class FakeFeishuClient(FakeClient):
    def post(self, url, json=None):
        self.calls.append({"url": url, "json": json})
        return FakeResponse({"code": 0, "tenant_access_token": "t-token"})


def _task_item(guid="g1", assignee="ou_wr-20041110", collabs=None, summary="任务A"):
    return {
        "guid": guid,
        "assignee": assignee,
        "collaborator_ids": collabs or [],
        "summary": summary,
        "is_completed": True,
    }


def test_feishu_task_requires_credentials():
    collector = FeishuTaskCollector(None, None, ["ou_wr-20041110"], session=FakeClient([[]]))
    with pytest.raises(CredentialsMissingError):
        collector.collect(DAY)


def test_feishu_task_mapping():
    client = FakeFeishuClient(
        [{"code": 0, "data": {"items": [_task_item(collabs=["ou_xianzhe"])]}}]
    )
    collector = FeishuTaskCollector("id", "sec", ["ou_wr-20041110", "ou_xianzhe"], session=client)
    events = collector.collect(DAY)
    assert len(events) == 1
    assert events[0].author == "ou_wr-20041110"  # 经办人→author
    assert events[0].collaborators == ["ou_xianzhe"]  # 协作人→collaborators
    assert events[0].ref == "g1"
    assert client.calls[0]["json"] == {"app_id": "id", "app_secret": "sec"}


def test_feishu_message_mention_parsing():
    content = '{"text": "@咸哲 T-101 的接口契约帮我看看"}'
    item = {
        "message_id": "m1",
        "sender": {"id": "ou_wr-20041110"},
        "create_time": "1764518400000",
        "body": {"content": content},
    }
    client = FakeFeishuClient([{"code": 0, "data": {"items": [item]}}])
    collector = FeishuMessageCollector("id", "sec", "oc_group", session=client)
    events = collector.collect(DAY)
    assert events[0].collaborators == ["咸哲"]
    assert events[0].payload["task_id"] == "T-101"


def test_feishu_message_requires_group():
    client = FakeFeishuClient([{"code": 0, "data": {"items": []}}])
    with pytest.raises(CredentialsMissingError):
        FeishuMessageCollector("id", "sec", None, session=client).collect(DAY)
