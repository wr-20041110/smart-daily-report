"""共享数据模型（design.md 3.1 实体定义）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    LOCAL_TZ = ZoneInfo("Asia/Shanghai")
except ZoneInfoNotFoundError:  # 无系统时区库时（未装 tzdata 的 Windows）退化为固定 +08:00
    LOCAL_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")

#: 分类：dev 开发 / collab 协作 / discuss 讨论（design.md 4.2 分类规则）
CATEGORY_ORDER = ("dev", "collab", "discuss")
CATEGORY_LABELS = {"dev": "开发", "collab": "协作", "discuss": "讨论"}
UNMAPPED_NAME = "未映射"  # 非团队成员账号事件归入的伪成员（design.md 4.2）


@dataclass(frozen=True)
class Member:
    """团队成员（design.md 3.1）。"""

    name: str
    github_username: str
    feishu_open_id: str
    email: str


@dataclass
class RawEvent:
    """原始事件：采集层从各数据源拿到的统一格式记录（design.md 3.1）。"""

    source: str  # github / feishu_task / feishu_message
    event_type: str
    ref: str  # 源内唯一引用；同一 (source, ref) 去重
    author: str  # 平台账号（GitHub 用户名或飞书 open_id）
    occurred_at: datetime  # UTC 存储（design.md 非功能约束-时区）
    title: str
    url: str = ""
    collaborators: list[str] = field(default_factory=list)  # 协同人平台账号列表
    payload: dict[str, Any] = field(default_factory=dict)

    @property
    def local_time(self) -> datetime:
        """本地时间（Asia/Shanghai），用于展示。"""
        return self.occurred_at.astimezone(LOCAL_TZ)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "event_type": self.event_type,
            "ref": self.ref,
            "author": self.author,
            "occurred_at": self.occurred_at.isoformat(),
            "title": self.title,
            "url": self.url,
            "collaborators": self.collaborators,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> RawEvent:
        return cls(
            source=d["source"],
            event_type=d["event_type"],
            ref=d["ref"],
            author=d["author"],
            occurred_at=datetime.fromisoformat(d["occurred_at"]),
            title=d["title"],
            url=d.get("url", ""),
            collaborators=list(d.get("collaborators", [])),
            payload=dict(d.get("payload", {})),
        )


@dataclass
class DailyReportEntry:
    """个人日报条目：一名成员一个分类一条（design.md 3.1）。"""

    date: date
    member_name: str
    category: str  # dev / collab / discuss
    items: list[str] = field(default_factory=list)  # 可读条目，每条一行
    raw_refs: list[str] = field(default_factory=list)  # 支撑条目的 (source:ref)，可追溯


@dataclass
class TeamReport:
    """团队日报（design.md 3.1）。"""

    date: date
    entries: list[DailyReportEntry] = field(default_factory=list)
    members_without_events: list[str] = field(default_factory=list)  # SC9
    missing_sources: list[str] = field(default_factory=list)  # SC2/G6 降级标注
    generated_at: datetime | None = None
    mocked: bool = False

    def to_markdown(self) -> str:
        """生成邮件与飞书共用的团队日报全文（design.md 4.2 build_team_report 契约）。"""
        lines = [f"# 团队日报 · {self.date.isoformat()}"]
        sources = "GitHub 提交 / 飞书任务 / 飞书消息"
        lines.append(f"> 数据来源：{sources}")
        if self.missing_sources:
            lines.append(f"> 缺失数据源：{'、'.join(self.missing_sources)}（已降级，无数据）")
        else:
            lines.append("> 缺失数据源：无")
        if self.generated_at:
            stamp = self.generated_at.astimezone(LOCAL_TZ).strftime("%Y-%m-%d %H:%M:%S")
            mock_note = "｜Mock 模式：数据为内置模拟数据" if self.mocked else ""
            lines.append(f"> 生成时间：{stamp}{mock_note}")
        lines.append("")

        for entry in self.entries:
            lines.append(f"## {entry.member_name}")
            if not entry.items:
                lines.append("- 今日无记录")
                continue
            lines.append(f"### {CATEGORY_LABELS.get(entry.category, entry.category)}")
            lines.extend(f"- {item}" for item in entry.items)
            lines.append("")
        for name in self.members_without_events:
            lines.append(f"## {name}")
            lines.append("- 今日无记录")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"
