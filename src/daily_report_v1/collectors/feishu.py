"""飞书任务与群消息采集（proposal.md F2/F3，design.md 4.1 契约）。

真实模式走飞书开放平台 API：
- tenant_access_token：POST /open-apis/auth/v3/tenant_access_token/internal
- 任务流转：GET /open-apis/task/v2/tasks（经办人→author、协作人→collaborators、状态→payload）
- 群消息：GET /open-apis/im/v1/messages（@提及解析、任务 ID 关联识别）

字段映射以飞书开放平台文档为准（凭证就绪后按环境实测调整映射字段名）；
mock 模式（凭证缺失时由编排层使用 MockCollector）保证主流程不受凭证影响。
"""

from __future__ import annotations

import json
import re
import time
from datetime import UTC, date, datetime

import httpx

from ..errors import CredentialsMissingError
from ..models import RawEvent
from .base import BaseCollector, day_window

#: 消息正文中的 @提及（飞书消息 content.text 内联展示名）
_MENTION_RE = re.compile(r"@([^\s@，。！？,.!?]+)")

#: tenant_access_token 应用级缓存（有效期 7199s，缓存 7000s 留余量）
_TOKEN_CACHE: dict[str | None, tuple[str, float]] = {}


class _FeishuBase(BaseCollector):
    """飞书采集公共部分：租户凭证与 token 获取。"""

    def __init__(
        self,
        app_id: str | None,
        app_secret: str | None,
        session: httpx.Client | None = None,
        base_url: str = "https://open.feishu.cn",
    ) -> None:
        super().__init__()
        self.app_id = app_id
        self.app_secret = app_secret
        self._client = session or httpx.Client(base_url=base_url, timeout=10.0)

    def _require_credentials(self) -> None:
        if not (self.app_id and self.app_secret):
            raise CredentialsMissingError("FEISHU_APP_ID / FEISHU_APP_SECRET 未配置")

    def _tenant_token(self) -> str:
        self._require_credentials()
        # 应用级缓存（有效期 7199s，缓存 7000s 留余量），避免频繁换取触发平台风控（21001）
        cached = _TOKEN_CACHE.get(self.app_id)
        if cached and time.monotonic() - cached[1] < 7000:
            return cached[0]
        self._guard_request()
        resp = self._retry(
            self._client.post,
            "/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": self.app_id, "app_secret": self.app_secret},
        )
        resp.raise_for_status()
        body = resp.json()
        if body.get("code") != 0:
            raise CredentialsMissingError(
                f"飞书凭证无效：code={body.get('code')} {body.get('msg')}"
            )
        token = body["tenant_access_token"]
        _TOKEN_CACHE[self.app_id] = (token, time.monotonic())
        return token

    def _get(self, url: str, token: str, params: dict | None = None) -> dict:
        self._guard_request()
        resp = self._retry(
            self._client.get,
            url,
            params=params,
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        body = resp.json()
        if body.get("code") != 0:
            raise CredentialsMissingError(
                f"飞书接口调用失败：code={body.get('code')} {body.get('msg')}"
            )
        return body.get("data") or {}


class FeishuTaskCollector(_FeishuBase):
    """飞书任务流转采集：经办人→author，协作人→collaborators，状态变更→payload（R2 数据来源）。"""

    name = "feishu_task"

    def __init__(
        self,
        app_id: str | None,
        app_secret: str | None,
        member_open_ids: list[str],
        session: httpx.Client | None = None,
    ) -> None:
        super().__init__(app_id, app_secret, session)
        self.member_open_ids = set(member_open_ids)

    def collect(self, day: date) -> list[RawEvent]:
        token = self._tenant_token()
        start, end = day_window(day)
        data = self._get(
            "/open-apis/task/v2/tasks",
            token,
            params={
                "page_size": 50,
                "start_time": int(start.timestamp()),
                "end_time": int(end.timestamp()),
            },
        )
        events: list[RawEvent] = []
        for item in data.get("items", []):
            assignee = item.get("assignee") or item.get("creator") or ""
            if assignee and assignee not in self.member_open_ids:
                continue  # 非团队成员任务不采集
            collabs = [c for c in (item.get("collaborator_ids") or [])]
            guid = item.get("guid") or item.get("id") or ""
            events.append(
                RawEvent(
                    source=self.name,
                    event_type="task",
                    ref=guid,
                    author=assignee,
                    occurred_at=_parse_ms(item.get("completed_at") or item.get("updated_at")),
                    title=item.get("summary") or "(无标题任务)",
                    url=f"https://feishu.cn/task/{guid}",
                    collaborators=collabs,
                    payload={
                        "status": item.get("status") or "",
                        "completed": item.get("is_completed", False),
                    },
                )
            )
        return events


class FeishuMessageCollector(_FeishuBase):
    """飞书群消息采集：解析 @提及（R3 数据来源）与任务 ID 关联。"""

    name = "feishu_message"

    def __init__(
        self,
        app_id: str | None,
        app_secret: str | None,
        group_id: str | None,
        session: httpx.Client | None = None,
    ) -> None:
        super().__init__(app_id, app_secret, session)
        self.group_id = group_id

    def collect(self, day: date) -> list[RawEvent]:
        if not self.group_id:
            raise CredentialsMissingError("config.json 未配置 feishu.group_id")
        token = self._tenant_token()
        start, end = day_window(day)
        data = self._get(
            "/open-apis/im/v1/messages",
            token,
            params={
                "container_id_type": "chat",
                "container_id": self.group_id,
                "start_time": str(int(start.timestamp())),
                "end_time": str(int(end.timestamp())),
                "page_size": 50,
            },
        )
        events: list[RawEvent] = []
        for item in data.get("items", []):
            content = json.loads(item.get("body", {}).get("content", "{}"))
            text = content.get("text", "")
            mentions = [m for m in _MENTION_RE.findall(text) if not m.startswith("所有人")]
            task_id = _find_task_id(text)
            events.append(
                RawEvent(
                    source=self.name,
                    event_type="message",
                    ref=item.get("message_id", ""),
                    author=(item.get("sender") or {}).get("id", ""),
                    occurred_at=_parse_ms(item.get("create_time")),
                    title=text[:80] or "(非文本消息)",
                    url=f"https://feishu.cn/msg/{item.get('message_id', '')}",
                    collaborators=mentions,  # 真实模式为展示名，生成层按姓名回退匹配
                    payload={"mentions": mentions, "task_id": task_id},
                )
            )
        return events


def _find_task_id(text: str) -> str | None:
    """从消息正文识别任务 ID（形如 T-101）。"""
    m = re.search(r"\bT-\d{2,6}\b", text)
    return m.group(0) if m else None


def _parse_ms(value) -> datetime:
    if not value:
        return datetime.now().astimezone()
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=UTC)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now().astimezone()
