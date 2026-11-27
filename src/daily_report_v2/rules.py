"""协同归属规则引擎（v2：规则注册表 + 纯函数，design.md 5 / 附录 A.1）。

每条规则：RawEvent → Attribution | None，命中即产出（发起人在前 + 协作者）。
新增规则 = 追加一个纯函数并加入 RULES 元组，不改动核心逻辑（开放封闭）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .domain import RawEvent

_TASK_ID_RE = re.compile(r"\bT-\d{2,6}\b")


@dataclass(frozen=True, slots=True)
class Attribution:
    """一条协同归属记录：事件 + 参与者平台账号（发起人在前）+ 规则名（可追溯）。"""

    event: RawEvent
    participants: tuple[str, ...]
    rule: str


def rule_coauthored_commit(ev: RawEvent) -> Attribution | None:
    """R1 共同提交：GitHub commit 含 Co-authored-by。"""
    if ev.source == "github" and ev.collaborators:
        return Attribution(ev, (ev.author, *ev.collaborators), "R1")
    return None


def rule_collaborative_task(ev: RawEvent) -> Attribution | None:
    """R2 协作任务：飞书任务含协作人。"""
    if ev.source == "feishu_task" and ev.collaborators:
        return Attribution(ev, (ev.author, *ev.collaborators), "R2")
    return None


def rule_mention_with_task(ev: RawEvent) -> Attribution | None:
    """R3 群内 @：消息 @ 他人且关联任务（payload.task_id 或正文任务 ID）。"""
    if ev.source == "feishu_message" and ev.collaborators:
        if ev.payload.get("task_id") or _TASK_ID_RE.search(ev.title):
            return Attribution(ev, (ev.author, *ev.collaborators), "R3")
    return None


#: 规则管道：顺序应用，命中即产出（一事件至多命中一条规则）
RULES: tuple = (rule_coauthored_commit, rule_collaborative_task, rule_mention_with_task)


def apply_rules(events: list[RawEvent]) -> list[Attribution]:
    """对事件列表顺序应用规则管道；同一 (source, ref) 去重兜底。"""
    seen: set[tuple[str, str]] = set()
    result: list[Attribution] = []
    for ev in events:
        key = (ev.source, ev.ref)
        if key in seen:
            continue
        seen.add(key)
        for rule in RULES:
            attr = rule(ev)
            if attr is not None:
                result.append(attr)
                break
    return result
