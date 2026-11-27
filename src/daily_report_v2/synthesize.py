"""日报编排（v2：纯函数组合；契约语义同 design.md 4.2，实现从零编写）。

与 v1 的差异：
- 归属判定与条目聚合分离（rules.py 产出 Attribution，本模块只做聚合与排版）；
- 团队日报渲染为独立纯函数 render_team_report（v1 为 TeamReport 方法）；
- 变更单 F12：考勤事件聚合为"考勤"一行，置于成员「开发」分类顶部（T214）。
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime

from .domain import (
    CATEGORY_LABELS,
    CATEGORY_ORDER,
    UNMAPPED_NAME,
    DailyReportEntry,
    Member,
    RawEvent,
    TeamReport,
)
from .rules import Attribution

_ATTENDANCE_LABEL = {"am_in": "上午上班", "pm_out": "下午下班"}


def account_to_name(account: str, members: list[Member]) -> str | None:
    """平台账号 → 成员姓名：GitHub 用户名 / 飞书 open_id / 姓名直配。"""
    gh = {m.github_username: m.name for m in members}
    fs = {m.feishu_open_id: m.name for m in members}
    names = {m.name for m in members}
    return gh.get(account) or fs.get(account) or (account if account in names else None)


def build_entries(
    events: list[RawEvent],
    attributions: list[Attribution],
    members: list[Member],
    day: date,
) -> list[DailyReportEntry]:
    """事件 + 归属记录 → 个人日报条目（聚合与排版）。"""
    buckets: dict[tuple[str, str], dict[str, str]] = defaultdict(dict)
    raw_refs: dict[tuple[str, str], set[str]] = defaultdict(set)

    # 1) 协同归属事件 → collab 条目（发起人 + 协作者各一条）
    for attr in attributions:
        ev = attr.event
        ref = f"{ev.source}:{ev.ref}"
        line = _line(ev)
        author_name = account_to_name(ev.author, members)
        collab_names = [n for c in ev.collaborators if (n := account_to_name(c, members))]
        participants = [n for n in [author_name, *collab_names] if n]
        author_label = author_name or f"未知账号({ev.author})"
        collab_label = "、".join(collab_names) if collab_names else f"未知账号({ev.collaborators})"
        if not participants:
            buckets[(UNMAPPED_NAME, "collab")][ref] = line
            raw_refs[(UNMAPPED_NAME, "collab")].add(ref)
            continue
        for name in participants:
            text = (
                f"{line}｜你发起，协作：{collab_label}"
                if name == author_name
                else f"{line}｜发起人：{author_label}，你参与"
            )
            buckets[(name, "collab")][ref] = text
            raw_refs[(name, "collab")].add(ref)

    # 2) 考勤事件 → 成员「开发」分类顶部的"考勤"行（变更单 F12）
    attendance: dict[str, list[tuple[datetime, str]]] = defaultdict(list)
    for ev in events:
        if ev.source == "feishu_attendance":
            name = account_to_name(ev.author, members) or UNMAPPED_NAME
            label = _ATTENDANCE_LABEL.get(
                ev.payload.get("period", ""), ev.payload.get("period", "")
            )
            attendance[name].append((ev.local_time, label))
            raw_refs[(name, "dev")].add(f"{ev.source}:{ev.ref}")
    for name, stamps in attendance.items():
        if stamps:
            parts = "、".join(f"{t:%H:%M} {label}" for t, label in sorted(stamps))
            buckets[(name, "dev")]["attendance"] = f"考勤｜{parts}"

    # 3) 非协同事件 → dev / discuss（去重兜底）
    seen: set[tuple[str, str]] = set()
    for ev in sorted(events, key=lambda e: e.occurred_at):
        key = (ev.source, ev.ref)
        if key in seen:
            continue
        seen.add(key)
        ref = f"{ev.source}:{ev.ref}"
        name = account_to_name(ev.author, members)
        if ev.source in ("github", "feishu_task"):
            buckets[(name or UNMAPPED_NAME, "dev")][ref] = _line(ev)
            raw_refs[(name or UNMAPPED_NAME, "dev")].add(ref)
        elif ev.source == "feishu_message":
            buckets[(name or UNMAPPED_NAME, "discuss")][ref] = _line(ev)
            raw_refs[(name or UNMAPPED_NAME, "discuss")].add(ref)
        else:  # feishu_attendance 已在步骤 2 聚合为考勤行；未知源兜底按 dev 处理
            if ev.source != "feishu_attendance":
                buckets[(name or UNMAPPED_NAME, "dev")][ref] = _line(ev)
                raw_refs[(name or UNMAPPED_NAME, "dev")].add(ref)

    entries = []
    for member, category in sorted(
        buckets,
        key=lambda k: (
            k[0] == UNMAPPED_NAME,
            _member_index(k[0], members),
            CATEGORY_ORDER.index(k[1]),
        ),
    ):
        entries.append(
            DailyReportEntry(
                date=day,
                member_name=member,
                category=category,
                items=tuple(buckets[(member, category)].values()),
                raw_refs=tuple(sorted(raw_refs[(member, category)])),
            )
        )
    return entries


def make_team_report(
    entries: list[DailyReportEntry],
    members: list[Member],
    missing_sources: list[str],
    day: date,
    mocked: bool,
) -> TeamReport:
    """条目 → 团队日报（无事件成员显式标注，SC9）。"""
    names_with_entries = {e.member_name for e in entries if e.items}
    return TeamReport(
        date=day,
        entries=tuple(entries),
        members_without_events=tuple(m.name for m in members if m.name not in names_with_entries),
        missing_sources=tuple(missing_sources),
        generated_at=datetime.now().astimezone(),
        mocked=mocked,
    )


def render_team_report(team: TeamReport) -> str:
    """团队日报 → Markdown 全文（与 v1 输出格式对齐，供两版对比；实现独立编写）。"""
    lines = [f"# 团队日报 · {team.date.isoformat()}"]
    lines.append("> 数据来源：GitHub 提交 / 飞书任务 / 飞书消息 / 飞书考勤")
    lines.append(
        f"> 缺失数据源：{'、'.join(team.missing_sources)}（已降级，无数据）"
        if team.missing_sources
        else "> 缺失数据源：无"
    )
    if team.generated_at:
        stamp = team.generated_at.astimezone().strftime("%Y-%m-%d %H:%M:%S")
        mock_note = "｜Mock 模式：数据为内置模拟数据" if team.mocked else ""
        lines.append(f"> 生成时间：{stamp}{mock_note}")
    lines.append("")
    for entry in team.entries:
        lines.append(f"## {entry.member_name}")
        if not entry.items:
            lines.append("- 今日无记录")
            continue
        lines.append(f"### {CATEGORY_LABELS.get(entry.category, entry.category)}")
        lines.extend(f"- {item}" for item in entry.items)
        lines.append("")
    for name in team.members_without_events:
        lines.append(f"## {name}")
        lines.append("- 今日无记录")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _line(ev: RawEvent) -> str:
    t = ev.local_time.strftime("%H:%M")
    link = f"（{ev.url}）" if ev.url else ""
    return f"{t} {ev.title}{link}"


def _member_index(name: str, members: list[Member]) -> int:
    for i, m in enumerate(members):
        if m.name == name:
            return i
    return len(members)
