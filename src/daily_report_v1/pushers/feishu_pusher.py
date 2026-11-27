"""飞书机器人推送（proposal.md F8，design.md 4.4 契约）。

两条真实通道（webhook 优先，缺失时回退应用机器人 API）：
- 自定义机器人 Webhook（企业版组织可用）：POST 文本消息；
- 应用机器人发消息 API（个人版组织无自定义机器人时的通道）：
  tenant_access_token → POST /open-apis/im/v1/messages（receive_id_type=chat_id）；
两条通道都缺失时 mock 留痕，真实失败返回 ok=False。
"""

from __future__ import annotations

import json

import httpx

from ..models import TeamReport
from .base import BasePusher, PushResult

#: 飞书文本消息体上限（字节），超出截断并加省略标记
_MAX_TEXT_BYTES = 140_000


class FeishuBotPusher(BasePusher):
    channel = "feishu"

    def __init__(
        self,
        webhook: str | None,
        app_id: str | None = None,
        app_secret: str | None = None,
        group_id: str | None = None,
        session: httpx.Client | None = None,
    ) -> None:
        self.webhook = webhook
        self.app_id = app_id
        self.app_secret = app_secret
        self.group_id = group_id
        self._client = session or httpx.Client(timeout=10.0)

    def push(self, team: TeamReport) -> PushResult:
        if self.webhook:
            return self._push_via_webhook(team)
        if self.app_id and self.app_secret and self.group_id:
            return self._push_via_app_bot(team)
        return PushResult(
            channel=self.channel,
            ok=True,
            mocked=True,
            detail=(
                "飞书推送凭证未配置（webhook 或应用机器人），mock 推送"
                "（日报已留存 SQLite，配置凭证后自动真实发送）"
            ),
        )

    def _push_via_webhook(self, team: TeamReport) -> PushResult:
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
                    channel=self.channel, ok=True, mocked=False, detail="已推送至团队群（webhook）"
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

    def _push_via_app_bot(self, team: TeamReport) -> PushResult:
        text = _truncate(team.to_markdown())
        try:
            token_resp = self._client.post(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": self.app_id, "app_secret": self.app_secret},
            )
            token_body = token_resp.json()
            if token_body.get("code") != 0:
                return PushResult(
                    channel=self.channel,
                    ok=False,
                    mocked=False,
                    detail=f"应用凭证无效：code={token_body.get('code')}",
                )
            resp = self._client.post(
                "https://open.feishu.cn/open-apis/im/v1/messages",
                params={"receive_id_type": "chat_id"},
                json={
                    "receive_id": self.group_id,
                    "msg_type": "text",
                    "content": json.dumps({"text": text}, ensure_ascii=False),
                },
                headers={"Authorization": f"Bearer {token_body['tenant_access_token']}"},
            )
            body = (
                resp.json()
                if resp.headers.get("content-type", "").startswith("application/json")
                else {}
            )
            if resp.status_code == 200 and body.get("code") == 0:
                return PushResult(
                    channel=self.channel,
                    ok=True,
                    mocked=False,
                    detail="已推送至团队群（应用机器人）",
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
