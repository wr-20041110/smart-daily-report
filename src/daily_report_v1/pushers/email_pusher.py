"""邮件推送（proposal.md F7，design.md 4.4 契约）。

凭证缺失时 mock 留痕（ok=True, mocked=True），真实失败返回 ok=False；
日志与 PushResult.detail 一律脱敏，授权码不得出现。
"""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

from ..models import TeamReport
from .base import BasePusher, PushResult


class EmailPusher(BasePusher):
    channel = "email"

    def __init__(
        self,
        host: str | None,
        port: int,
        user: str | None,
        password: str | None,
        sender: str,
        recipients: list[str],
    ) -> None:
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.sender = sender
        self.recipients = list(recipients)

    def push(self, team: TeamReport) -> PushResult:
        if not (self.host and self.user and self.password):
            return PushResult(
                channel=self.channel,
                ok=True,
                mocked=True,
                detail="SMTP 凭证未配置，mock 推送（日报已留存 SQLite，配置凭证后自动真实发送）",
            )
        if not self.recipients:
            return PushResult(channel=self.channel, ok=False, mocked=False, detail="收件人列表为空")

        msg = EmailMessage()
        msg["Subject"] = f"团队日报 · {team.date.isoformat()}"
        msg["From"] = self.sender or self.user
        msg["To"] = ", ".join(self.recipients)
        msg.set_content(team.to_markdown())

        try:
            if self.port == 465:
                server = smtplib.SMTP_SSL(self.host, self.port, timeout=15)
            else:
                server = smtplib.SMTP(self.host, self.port, timeout=15)
                server.starttls()
            with server:
                server.login(self.user, self.password)
                server.send_message(msg)
        except (OSError, smtplib.SMTPException) as exc:  # 网络/认证/协议错误
            return PushResult(
                channel=self.channel,
                ok=False,
                mocked=False,
                detail=f"发送失败：{type(exc).__name__}（已脱敏，详见日志）",
            )
        return PushResult(
            channel=self.channel,
            ok=True,
            mocked=False,
            detail=f"已发送至 {len(self.recipients)} 个收件人",
        )
