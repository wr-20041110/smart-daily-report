"""T7/T8 推送层验收：凭证缺失 mock 留痕、真实发送参数、失败不抛出、日志脱敏。"""

from __future__ import annotations

import smtplib
from datetime import UTC, date, datetime

import httpx
import pytest

from daily_report_v1.models import DailyReportEntry, TeamReport
from daily_report_v1.pushers import EmailPusher, FeishuBotPusher

DAY = date(2026, 11, 24)


def make_team() -> TeamReport:
    return TeamReport(
        date=DAY,
        entries=[
            DailyReportEntry(
                date=DAY, member_name="王然", category="dev", items=["- 09:00 修复归属去重"]
            )
        ],
        generated_at=datetime(2026, 11, 24, 10, 0, tzinfo=UTC),
    )


# ---- 邮件 ----


def test_email_missing_credentials_mocked():
    pusher = EmailPusher(None, 465, None, None, "s@x.com", ["a@x.com"])
    result = pusher.push(make_team())
    assert result.ok and result.mocked and "mock" in result.detail


class FakeSMTP:
    sent: list = []

    def __init__(self, host, port, timeout=None, raise_on=None):
        FakeSMTP.sent.append(self)
        self._raise = raise_on

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self):
        pass

    def login(self, user, password):
        if self._raise:
            raise smtplib.SMTPException("认证失败")

    def send_message(self, msg):
        self.msg = msg


@pytest.fixture
def smtp(monkeypatch):
    FakeSMTP.sent = []
    monkeypatch.setattr("daily_report_v1.pushers.email_pusher.smtplib.SMTP", FakeSMTP)
    monkeypatch.setattr("daily_report_v1.pushers.email_pusher.smtplib.SMTP_SSL", FakeSMTP)


def test_email_sends_team_report(smtp):
    pusher = EmailPusher(
        "smtp.x.com", 465, "user", "secret-pass", "s@x.com", ["a@x.com", "b@x.com"]
    )
    result = pusher.push(make_team())
    assert result.ok and not result.mocked
    msg = FakeSMTP.sent[0].msg
    assert msg["To"] == "a@x.com, b@x.com"
    assert f"团队日报 · {DAY.isoformat()}" in msg["Subject"]
    assert "王然" in msg.get_content()
    assert "secret-pass" not in msg.get_content()  # 脱敏红线


def test_email_failure_reported_not_raised(monkeypatch):
    class FailingSMTP(FakeSMTP):
        def login(self, user, password):
            raise smtplib.SMTPException("认证失败")

    monkeypatch.setattr("daily_report_v1.pushers.email_pusher.smtplib.SMTP", FailingSMTP)
    monkeypatch.setattr("daily_report_v1.pushers.email_pusher.smtplib.SMTP_SSL", FailingSMTP)
    pusher = EmailPusher("smtp.x.com", 465, "user", "secret-pass", "s@x.com", ["a@x.com"])
    result = pusher.push(make_team())
    assert not result.ok and not result.mocked
    assert "secret-pass" not in result.detail


# ---- 飞书机器人 ----


def test_feishu_missing_webhook_mocked():
    result = FeishuBotPusher(None).push(make_team())
    assert result.ok and result.mocked


class FakeWebhookClient:
    def __init__(self, payload=None, fail=False):
        self.payload = payload or {"code": 0}
        self.fail = fail
        self.calls = []

    def post(self, url, json=None):
        self.calls.append({"url": url, "json": json})
        if self.fail:
            raise httpx.ConnectError("模拟网络失败")
        return httpx.Response(200, json=self.payload)

    def close(self):
        pass


def test_feishu_webhook_success():
    client = FakeWebhookClient()
    result = FeishuBotPusher("https://hook.example", session=client).push(make_team())
    assert result.ok and not result.mocked
    body = client.calls[0]["json"]
    assert body["msg_type"] == "text"
    assert "王然" in body["content"]["text"]


def test_feishu_webhook_rejected():
    client = FakeWebhookClient(payload={"code": 10001})
    result = FeishuBotPusher("https://hook.example", session=client).push(make_team())
    assert not result.ok and "code=10001" in result.detail


def test_feishu_webhook_network_error():
    result = FeishuBotPusher("https://hook.example", session=FakeWebhookClient(fail=True)).push(
        make_team()
    )
    assert not result.ok


class FakeAppBotClient:
    """应用机器人通道假客户端：第一次 post 换 token，第二次发消息。"""

    def __init__(self, send_ok=True):
        self.send_ok = send_ok
        self.calls = []

    def post(self, url, json=None, params=None, headers=None):
        self.calls.append({"url": url, "json": json, "params": params, "headers": headers})
        if "tenant_access_token" in url:
            return httpx.Response(200, json={"code": 0, "tenant_access_token": "t-tok"})
        return httpx.Response(200, json={"code": 0} if self.send_ok else {"code": 10002})

    def close(self):
        pass


def test_app_bot_push_success_without_webhook():
    client = FakeAppBotClient()
    pusher = FeishuBotPusher(None, "id", "sec", "oc_group", session=client)
    result = pusher.push(make_team())
    assert result.ok and not result.mocked
    assert "应用机器人" in result.detail
    send_call = client.calls[1]
    assert send_call["params"]["receive_id_type"] == "chat_id"
    assert send_call["json"]["receive_id"] == "oc_group"
    assert send_call["json"]["msg_type"] == "text"
    assert send_call["headers"]["Authorization"] == "Bearer t-tok"


def test_app_bot_rejected_reported():
    client = FakeAppBotClient(send_ok=False)
    result = FeishuBotPusher(None, "id", "sec", "oc_group", session=client).push(make_team())
    assert not result.ok and "code=10002" in result.detail


def test_webhook_preferred_over_app_bot():
    client = FakeWebhookClient()
    pusher = FeishuBotPusher("https://hook.example", "id", "sec", "oc_group", session=client)
    result = pusher.push(make_team())
    assert result.ok and "webhook" in result.detail
    assert len(client.calls) == 1  # 未走 token 通道
