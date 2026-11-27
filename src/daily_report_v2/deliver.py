"""推送通道（v2：注册表 + 函数式；契约语义同 design.md 4.4，实现从零编写）。

凭证缺失 mock 留痕（ok=True, mocked=True）；真实失败 ok=False 不抛出；detail 一律脱敏。
"""

from __future__ import annotations

import smtplib
from collections.abc import Callable
from email.message import EmailMessage

import httpx

from .domain import PushResult, TeamReport

PUSHER_REGISTRY: dict[str, Callable] = {}


def register_pusher(name: str):
    def decorate(fn):
        PUSHER_REGISTRY[name] = fn
        return fn

    return decorate


@register_pusher("email")
def deliver_email(
    team: TeamReport,
    settings,
    rendered: str,
    smtp: smtplib.SMTP | None = None,
) -> PushResult:
    """SMTP 发送团队日报；SMTP 参数来自 Settings（环境变量注入）。"""
    if not settings.is_smtp_ready:
        return PushResult(
            channel="email",
            ok=True,
            mocked=True,
            detail="SMTP 凭证未配置，mock 推送（日报已留存 SQLite，配置凭证后自动真实发送）",
        )
    recipients = list(settings.report_recipients)
    if not recipients:
        return PushResult(channel="email", ok=False, mocked=False, detail="收件人列表为空")

    msg = EmailMessage()
    msg["Subject"] = f"团队日报 · {team.date.isoformat()}"
    msg["From"] = settings.report_sender or settings.smtp_user
    msg["To"] = ", ".join(recipients)
    msg.set_content(rendered)

    try:
        if smtp is None:
            if settings.smtp_port == 465:
                smtp = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15)
            else:
                smtp = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15)
                smtp.starttls()
            with smtp:
                smtp.login(settings.smtp_user, settings.smtp_password)
                smtp.send_message(msg)
        else:
            smtp.send_message(msg)
    except (OSError, smtplib.SMTPException) as exc:
        return PushResult(
            channel="email",
            ok=False,
            mocked=False,
            detail=f"发送失败：{type(exc).__name__}（已脱敏，详见日志）",
        )
    return PushResult(
        channel="email", ok=True, mocked=False, detail=f"已发送至 {len(recipients)} 个收件人"
    )


@register_pusher("feishu")
def deliver_feishu(
    team: TeamReport,
    settings,
    rendered: str,
    client: httpx.Client | None = None,
) -> PushResult:
    """飞书推送（webhook 优先，缺失时回退应用机器人 API，均缺失则 mock 留痕）。"""
    webhook = settings.feishu_bot_webhook
    if webhook:
        return _deliver_via_webhook(webhook, rendered, client)
    if settings.feishu_app_id and settings.feishu_app_secret and settings.feishu_group_id:
        return _deliver_via_app_bot(settings, rendered, client)
    return PushResult(
        channel="feishu",
        ok=True,
        mocked=True,
        detail=(
            "飞书推送凭证未配置（webhook 或应用机器人），mock 推送"
            "（日报已留存 SQLite，配置凭证后自动真实发送）"
        ),
    )


def _deliver_via_webhook(webhook: str, rendered: str, client: httpx.Client | None) -> PushResult:
    text = _truncate(rendered)
    try:
        http = client or httpx.Client(timeout=10.0)
        resp = http.post(webhook, json={"msg_type": "text", "content": {"text": text}})
        body = (
            resp.json()
            if resp.headers.get("content-type", "").startswith("application/json")
            else {}
        )
        if resp.status_code == 200 and body.get("code", body.get("StatusCode", 0)) == 0:
            return PushResult(channel="feishu", ok=True, mocked=False, detail="已推送至团队群（webhook）")
        return PushResult(
            channel="feishu",
            ok=False,
            mocked=False,
            detail=f"推送被拒：HTTP {resp.status_code} code={body.get('code')}",
        )
    except httpx.HTTPError as exc:
        return PushResult(
            channel="feishu",
            ok=False,
            mocked=False,
            detail=f"推送失败：{type(exc).__name__}（已脱敏）",
        )


def _deliver_via_app_bot(settings, rendered: str, client: httpx.Client | None) -> PushResult:
    text = _truncate(rendered)
    try:
        http = client or httpx.Client(timeout=10.0)
        token_resp = http.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": settings.feishu_app_id, "app_secret": settings.feishu_app_secret},
        )
        token_body = token_resp.json()
        if token_body.get("code") != 0:
            return PushResult(
                channel="feishu",
                ok=False,
                mocked=False,
                detail=f"应用凭证无效：code={token_body.get('code')}",
            )
        resp = http.post(
            "https://open.feishu.cn/open-apis/im/v1/messages",
            params={"receive_id_type": "chat_id"},
            json={
                "receive_id": settings.feishu_group_id,
                "msg_type": "text",
                "content": _json_text({"text": text}),
            },
            headers={"Authorization": f"Bearer {token_body['tenant_access_token']}"},
        )
        body = (
            resp.json()
            if resp.headers.get("content-type", "").startswith("application/json")
            else {}
        )
        if resp.status_code == 200 and body.get("code") == 0:
            return PushResult(channel="feishu", ok=True, mocked=False, detail="已推送至团队群（应用机器人）")
        return PushResult(
            channel="feishu",
            ok=False,
            mocked=False,
            detail=f"推送被拒：HTTP {resp.status_code} code={body.get('code')}",
        )
    except httpx.HTTPError as exc:
        return PushResult(
            channel="feishu",
            ok=False,
            mocked=False,
            detail=f"推送失败：{type(exc).__name__}（已脱敏）",
        )


def _json_text(payload: dict) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False)


def _truncate(text: str, limit: int = 140_000) -> str:
    data = text.encode("utf-8")
    if len(data) <= limit:
        return text
    return (
        data[:limit].decode("utf-8", errors="ignore")
        + "\n…（消息过长已截断，完整日报见邮件与 SQLite 历史）"
    )
