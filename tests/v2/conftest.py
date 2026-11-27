"""v2 测试公共夹具（与 v1 的 conftest 独立编写，不互相引用）。"""

from __future__ import annotations

from datetime import date

import pytest

from daily_report_v2.domain import Member
from daily_report_v2.settings import Settings

DAY = date(2026, 12, 1)

MEMBERS = [
    Member("王然", "wr-20041110", "ou_wr-20041110", "wr-20041110@example.com"),
    Member("咸哲", "xz0622", "ou_xz0622", "xz0622@example.com"),
    Member("王峻羽", "wjy-jjj", "ou_wjy-jjj", "wjy-jjj@example.com"),
    Member("尹博弘", "Yin-bo-hong", "ou_yinbohong", "20233159@stu.ccut.edu.cn"),
]


@pytest.fixture
def members() -> list[Member]:
    return list(MEMBERS)


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        members=tuple(MEMBERS),
        github_repo="team/smart-daily-report",
        db_path=str(tmp_path / "reports.db"),
        mock=True,
        report_sender="report@example.com",
        report_recipients=("a@example.com",),
    )


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.headers = {"content-type": "application/json"}

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx

            raise httpx.HTTPStatusError(
                "err", request=httpx.Request("GET", "http://x"), response=self
            )

    def json(self):
        return self._payload


class FakeClient:
    """记录调用的假 httpx.Client；pages 依次返回，fail_times 次网络失败。"""

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
            import httpx

            raise httpx.ConnectError("模拟网络失败")
        return FakeResponse(self.pages.pop(0))

    def post(self, url, json=None):
        self.calls.append({"url": url, "json": json})
        return FakeResponse({"code": 0, "tenant_access_token": "t-token"})


@pytest.fixture
def fake_client():
    return FakeClient
