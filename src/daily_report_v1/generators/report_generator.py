"""日报生成与协同归属（design.md 4.2 契约与 5 协同归属规则）。

分类规则：
  dev     ← 无协作人的 GitHub 提交 / 无协作人的飞书任务（本人为作者）
  discuss ← 飞书消息（本人发言）
  collab  ← 三类协同事件（R1 共同提交 / R2 协作任务 / R3 群内 @ 关联任务）
           R3 消息同时为发言者生成 discuss 条目（同一事件两类归属，不冲突）

协同归属：
  R1 共同提交：commit 含 Co-authored-by → 作者 + 共同作者
  R2 协作任务：任务含协作人 → 经办人 + 协作人
  R3 群内 @：消息 @ 他人且关联任务（payload.task_id）→ 发言者 + 被 @ 者

未知账号事件不丢弃，归入「未映射」伪成员条目（design.md 4.2 契约）。
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, datetime

from ..models import (
    CATEGORY_ORDER,
    UNMAPPED_NAME,
    DailyReportEntry,
    Member,
    RawEvent,
    TeamReport,
)

_TASK_ID_RE = re.compile(r"\bT-\d{2,6}\b")


def generate_member_reports(
    events: list[RawEvent],
    members: list[Member],
    day: date,
) -> list[DailyReportEntry]:
    """事件 → 个人日报条目聚合（契约见 design.md 4.2）。"""
    gh_map = {m.github_username: m.name for m in members}
    fs_map = {m.feishu_open_id: m.name for m in members}
    name_set = {m.name for m in members}

    def map_name(account: str) -> str | None:
        return (
            gh_map.get(account) or fs_map.get(account) or (account if account in name_set else None)
        )

    # (成员, 分类) -> {行文本，保持插入序}
    buckets: dict[tuple[str, str], dict[str, str]] = defaultdict(dict)
    raw_refs: dict[tuple[str, str], set[str]] = defaultdict(set)
    seen: set[tuple[str, str]] = set()

    for ev in sorted(events, key=lambda e: e.occurred_at):
        key = (ev.source, ev.ref)
        if key in seen:
            continue  # 去重兜底（采集层已按 (source, ref) 唯一）
        seen.add(key)
        ref = f"{ev.source}:{ev.ref}"
        line = _format_line(ev)
        author_name = map_name(ev.author)
        collab_names = [n for c in ev.collaborators if (n := map_name(c))]

        if ev.source in ("github", "feishu_task"):
            if collab_names or ev.collaborators:
                _add_collab(buckets, raw_refs, ev, author_name, collab_names, line, ref)
            else:
                _add(buckets, raw_refs, author_name, "dev", line, ref)
        elif ev.source == "feishu_message":
            _add(buckets, raw_refs, author_name, "discuss", line, ref)
            if ev.collaborators and (ev.payload.get("task_id") or _TASK_ID_RE.search(ev.title)):
                # R3：@ 提及且关联任务 → 协作讨论
                _add_collab(buckets, raw_refs, ev, author_name, collab_names, line, ref)
        else:  # 未知来源兜底：按普通开发事件处理
            _add(buckets, raw_refs, author_name, "dev", line, ref)

    entries: list[DailyReportEntry] = []
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
                items=list(buckets[(member, category)].values()),
                raw_refs=sorted(raw_refs[(member, category)]),
            )
        )
    return entries


def build_team_report(
    entries: list[DailyReportEntry],
    members: list[Member],
    missing_sources: list[str],
    day: date,
) -> TeamReport:
    """个人条目 → 团队日报编排（契约见 design.md 4.2）。"""
    names_with_entries = {e.member_name for e in entries if e.items}
    without = [m.name for m in members if m.name not in names_with_entries]
    return TeamReport(
        date=day,
        entries=entries,
        members_without_events=without,
        missing_sources=list(missing_sources),
        generated_at=datetime.now().astimezone(),
    )


def _add(buckets, raw_refs, member, category, line, ref) -> None:
    if member is None:
        member = UNMAPPED_NAME
    buckets[(member, category)][ref] = line
    raw_refs[(member, category)].add(ref)


def _add_collab(buckets, raw_refs, ev, author_name, collab_names, line, ref) -> None:
    """协同事件：发起人与协作者各得一条 collab 条目（design.md 5 归属实现要点）。"""
    author_label = author_name if author_name else f"未知账号({ev.author})"
    collab_label = "、".join(collab_names) if collab_names else f"未知账号({ev.collaborators})"
    participants = [n for n in [author_name, *collab_names] if n is not None]
    if not participants:
        # 参与者均为未知账号 → 归入「未映射」协作条目，事件不丢弃（design.md 4.2）
        buckets[(UNMAPPED_NAME, "collab")][ref] = line
        raw_refs[(UNMAPPED_NAME, "collab")].add(ref)
        return
    for name in participants:
        if name == author_name:
            text = f"{line}｜你发起，协作：{collab_label}"
        else:
            text = f"{line}｜发起人：{author_label}，你参与"
        buckets[(name, "collab")][ref] = text
        raw_refs[(name, "collab")].add(ref)


def _format_line(ev: RawEvent) -> str:
    t = ev.local_time.strftime("%H:%M")
    link = f"（{ev.url}）" if ev.url else ""
    return f"{t} {ev.title}{link}"


def _member_index(name: str, members: list[Member]) -> int:
    for i, m in enumerate(members):
        if m.name == name:
            return i
    return len(members)
