"""领域模型（v2：frozen 不可变数据类，纯函数核心）。

契约语义与 design.md 3.1 等价；与 v1 的实现差异：
- 全部 frozen + slots，创建后不可变；
- collaborators 用 tuple（而非 v1 的 list）；
- 序列化走模块级函数 event_to_dict / event_from_dict（而非 v1 的方法）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    LOCAL_TZ = ZoneInfo("Asia/Shanghai")
except ZoneInfoNotFoundError:  # Windows 未装 tzdata 时退化为固定 +08:00
    LOCAL_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")

CATEGORY_ORDER = ("dev", "collab", "discuss")
CATEGORY_LABELS = {"dev": "开发", "collab": "协作", "discuss": "讨论"}
UNMAPPED_NAME = "未映射"


@dataclass(frozen=True, slots=True)
class Member:
    name: str
    github_username: str
    feishu_open_id: str
    email: str


@dataclass(frozen=True, slots=True)
class RawEvent:
    source: str
    event_type: str
    ref: str
    author: str
    occurred_at: datetime  # UTC 存储
    title: str
    url: str = ""
    collaborators: tuple[str, ...] = ()  # 协作者平台账号（不可变）
    payload: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def local_time(self) -> datetime:
        return self.occurred_at.astimezone(LOCAL_TZ)


@dataclass(frozen=True, slots=True)
class DailyReportEntry:
    date: date
    member_name: str
    category: str
    items: tuple[str, ...] = ()  # v2：不可变 tuple
    raw_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TeamReport:
    date: date
    entries: tuple[DailyReportEntry, ...] = ()
    members_without_events: tuple[str, ...] = ()
    missing_sources: tuple[str, ...] = ()
    generated_at: datetime | None = None
    mocked: bool = False


@dataclass(frozen=True, slots=True)
class PushResult:
    channel: str
    ok: bool
    mocked: bool
    detail: str


@dataclass(frozen=True, slots=True)
class PipelineResult:
    day: date
    collected: dict[str, int]
    missing_sources: tuple[str, ...]
    entry_count: int
    push_results: tuple[PushResult, ...]
    mocked: bool
    elapsed_seconds: float


def event_to_dict(ev: RawEvent) -> dict[str, Any]:
    """RawEvent → 存储字典（v2 函数式序列化）。"""
    return {
        "source": ev.source,
        "event_type": ev.event_type,
        "ref": ev.ref,
        "author": ev.author,
        "occurred_at": ev.occurred_at.isoformat(),
        "title": ev.title,
        "url": ev.url,
        "collaborators": list(ev.collaborators),
        "payload": ev.payload,
    }


def event_from_dict(d: dict[str, Any]) -> RawEvent:
    """存储字典 → RawEvent（occurred_at 归一到 UTC）。"""
    dt = datetime.fromisoformat(d["occurred_at"])
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return RawEvent(
        source=d["source"],
        event_type=d["event_type"],
        ref=d["ref"],
        author=d["author"],
        occurred_at=dt.astimezone(UTC),
        title=d["title"],
        url=d.get("url", ""),
        collaborators=tuple(d.get("collaborators", [])),
        payload=dict(d.get("payload", {})),
    )
