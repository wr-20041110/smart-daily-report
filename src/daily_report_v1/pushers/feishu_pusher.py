"""飞书机器人推送（proposal.md F8，design.md 4.4 契约）。

自定义机器人 Webhook：POST 文本消息（msg_type=text）；
凭证（Webhook URL）缺失时 mock 留痕，真实失败返回 ok=False。
"""

from __future__ import annotations

import httpx

from ..models import TeamReport
from .base import BasePusher, PushResult

#: 飞书文本消息体上限（字节），超出截断并加省略标记
_MAX_TEXT_BYTES = 140_000


class FeishuBotPusher(BasePusher):
    channel = "feishu"

    def __init__(self, webhook: str | None, session: httpx.Client | None = None) -> None:
        self.webhook = webhook
        self._client = session or httpx.Client(timeout=10.0)

    def push(self, team: TeamReport) -> PushResult:
        if not self.webhook:
            return PushResult(
                channel=self.channel,
                ok=True,
                mocked=True,
                detail=(
                    "FEISHU_BOT_WEBHOOK 未配置，mock 推送"
                    "（日报已留存 SQLite，配置凭证后自动真实发送）"
                ),
            )
        text = _truncate(team.to_markdown())
        try:
            resp = self._client.post(
                self.webhook, json={"msg_type": "text", "content": {"text": text}}
            )
            body = (
                resp.json()
                if resp.headers.get("content-type", "").startswith("application/json")
                else {}
            )
            if resp.status_code == 200 and body.get("code", body.get("StatusCode", 0)) == 0:
                return PushResult(
                    channel=self.channel, ok=True, mocked=False, detail="已推送至团队群"
                )
            return PushResult(
                channel=self.channel,
                ok=False,
                mocked=False,
                detail=f"推送被拒：HTTP {resp.status_code} code={body.get('code')}",
            )
        except httpx.HTTPError as exc:
            return PushResult(
                channel=self.channel,
                ok=False,
                mocked=False,
                detail=f"推送失败：{type(exc).__name__}（已脱敏）",
            )


def _truncate(text: str) -> str:
    data = text.encode("utf-8")
    if len(data) <= _MAX_TEXT_BYTES:
        return text
    cut = data[:_MAX_TEXT_BYTES].decode("utf-8", errors="ignore")
    return cut + "\n…（消息过长已截断，完整日报见邮件与 SQLite 历史）"
