"""T209 推送验收（红→绿归档）：凭证缺失 mock 留痕、fake SMTP/HTTP、脱敏。"""

from __future__ import annotations

import smtplib
from datetime import UTC, date, datetime

import httpx

from daily_report_v2.deliver import deliver_email, deliver_feishu
from daily_report_v2.domain import TeamReport
from daily_report_v2.settings import Settings

from .conftest import MEMBERS

DAY = date(2026, 12, 1)


def make_team() -> TeamReport:
    return TeamReport(date=DAY, generated_at=datetime(2026, 12, 1, 10, 0, tzinfo=UTC))


def settings_email(**kw) -> Settings:
    return Settings(
        members=tuple(MEMBERS),
        smtp_host="smtp.x.com",
        smtp_port=465,
        smtp_user="user",
        smtp_password="secret-pass",
        report_sender="s@x.com",
        report_recipients=("a@x.com", "b@x.com"),
        **kw,
    )


def test_email_missing_credentials_mocked():
    s = Settings(members=tuple(MEMBERS))
    result = deliver_email(make_team(), s, "rendered")
    assert result.ok and result.mocked


class FakeSMTP:
    def __init__(self, *a, **kw):
        self.messages = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self):
        pass

    def login(self, user, password):
        pass

    def send_message(self, msg):
        self.messages.append(msg)


def test_email_sends_via_fake_smtp(monkeypatch):
    monkeypatch.setattr("daily_report_v2.deliver.smtplib.SMTP", FakeSMTP)
    monkeypatch.setattr("daily_report_v2.deliver.smtplib.SMTP_SSL", FakeSMTP)
    result = deliver_email(make_team(), settings_email(), "rendered 王然")
    assert result.ok and not result.mocked
    # fake SMTP 对象由函数内部创建，验证方式：mock 留痕 + 结果字段
    assert "2 个收件人" in result.detail


def test_email_failure_reported(monkeypatch):
    class FailingSMTP(FakeSMTP):
        def login(self, user, password):
            raise smtplib.SMTPException("认证失败")

    monkeypatch.setattr("daily_report_v2.deliver.smtplib.SMTP", FailingSMTP)
    monkeypatch.setattr("daily_report_v2.deliver.smtplib.SMTP_SSL", FailingSMTP)
    result = deliver_email(make_team(), settings_email(), "rendered")
    assert not result.ok and "secret-pass" not in result.detail  # 脱敏红线


class FakeHTTP:
    def __init__(self, payload=None, fail=False):
        self.payload = payload or {"code": 0}
        self.fail = fail
        self.calls = []

    def post(self, url, json=None):
        self.calls.append({"url": url, "json": json})
        if self.fail:
            raise httpx.ConnectError("模拟网络失败")
        return httpx.Response(200, json=self.payload)


def test_feishu_missing_webhook_mocked():
    s = Settings(members=tuple(MEMBERS))
    result = deliver_feishu(make_team(), s, "rendered")
    assert result.ok and result.mocked


def test_feishu_webhook_success():
    client = FakeHTTP()
    s = Settings(members=tuple(MEMBERS), feishu_bot_webhook="https://hook.example")
    result = deliver_feishu(make_team(), s, "rendered 王然", client=client)
    assert result.ok and not result.mocked
    assert "王然" in client.calls[0]["json"]["content"]["text"]


def test_feishu_webhook_rejected_and_network_error():
    s = Settings(members=tuple(MEMBERS), feishu_bot_webhook="https://hook.example")
    assert not deliver_feishu(make_team(), s, "r", client=FakeHTTP({"code": 10001})).ok
    assert not deliver_feishu(make_team(), s, "r", client=FakeHTTP(fail=True)).ok


class FakeAppClient:
    """应用机器人通道假客户端：第一次 post 换 token，第二次发消息。"""

    def __init__(self, send_ok=True):
        self.send_ok = send_ok
        self.calls = []

    def post(self, url, json=None, params=None, headers=None):
        self.calls.append({"url": url, "json": json, "params": params, "headers": headers})
        if "tenant_access_token" in url:
            return httpx.Response(200, json={"code": 0, "tenant_access_token": "t-tok"})
        return httpx.Response(200, json={"code": 0} if self.send_ok else {"code": 10002})


def test_app_bot_fallback_without_webhook():
    s = Settings(
        members=tuple(MEMBERS), feishu_app_id="id", feishu_app_secret="sec", feishu_group_id="oc_g"
    )
    client = FakeAppClient()
    result = deliver_feishu(make_team(), s, "rendered 王然", client=client)
    assert result.ok and not result.mocked
    assert "应用机器人" in result.detail
    send_call = client.calls[1]
    assert send_call["params"]["receive_id_type"] == "chat_id"
    assert send_call["json"]["receive_id"] == "oc_g"
    assert "王然" in send_call["json"]["content"]


def test_app_bot_rejected_reported():
    s = Settings(
        members=tuple(MEMBERS), feishu_app_id="id", feishu_app_secret="sec", feishu_group_id="oc_g"
    )
    result = deliver_feishu(make_team(), s, "r", client=FakeAppClient(send_ok=False))
    assert not result.ok and "code=10002" in result.detail


def test_webhook_preferred_over_app_bot():
    s = Settings(
        members=tuple(MEMBERS),
        feishu_bot_webhook="https://hook.example",
        feishu_app_id="id",
        feishu_app_secret="sec",
        feishu_group_id="oc_g",
    )
    client = FakeHTTP()
    result = deliver_feishu(make_team(), s, "r", client=client)
    assert result.ok and "webhook" in result.detail
    assert len(client.calls) == 1
