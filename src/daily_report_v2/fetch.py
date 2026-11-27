"""采集层（v2：注册表 + 函数式实现，design.md 附录 A）。

与 v1 的差异：
- v1 为 BaseCollector 抽象基类 + 子类；v2 为「名称 → 函数」注册表，新增数据源只追加注册项；
- 重试实现为 @with_retry 装饰器（v1 为基类方法）；
- mock 数据集为阶段二全新内容（50 条，12 条标注协作事件，另含 6 条考勤事件）。

契约语义（日期窗口/作者过滤/co-author 解析/请求上限/退避重试）与 design.md 4.1 一致。
"""

from __future__ import annotations

import functools
import json
import re
import time
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from datetime import time as dtime

import httpx

from .domain import LOCAL_TZ, RawEvent

MAX_REQUESTS_PER_RUN = 20
RETRY_DELAYS: tuple[float, ...] = (1.0, 2.0, 4.0)


class CollectorError(Exception):
    """采集层失败。"""


class CredentialsMissingError(CollectorError):
    """凭证缺失。"""


def day_window(day: date) -> tuple[datetime, datetime]:
    """本地日 [00:00, 次日 00:00) → UTC 区间。"""
    start_local = datetime.combine(day, dtime.min, tzinfo=LOCAL_TZ)
    return start_local.astimezone(UTC), (start_local + timedelta(days=1)).astimezone(UTC)


# --------------------------------------------------------------------------
# 注册表
# --------------------------------------------------------------------------

REGISTRY: dict[str, Callable[[date, object], list[RawEvent]]] = {}


def register(name: str):
    """注册采集函数：@register("github") def fetch_github(day, settings, ...)。"""

    def decorate(fn):
        REGISTRY[name] = fn
        return fn

    return decorate


# --------------------------------------------------------------------------
# 重试装饰器（指数退避 1s/2s/4s，业务性错误不重试）
# --------------------------------------------------------------------------


def with_retry(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        last: Exception | None = None
        for attempt, delay in enumerate((*RETRY_DELAYS, 0)):
            try:
                return fn(*args, **kwargs)
            except CollectorError:
                raise
            except Exception as exc:  # noqa: BLE001 —— 网络类异常统一重试
                last = exc
                if attempt < len(RETRY_DELAYS):
                    time.sleep(delay)
        raise CollectorError(
            f"{fn.__name__} 失败（重试 {len(RETRY_DELAYS)} 次后仍失败）："
            f"{type(last).__name__}: {last}"
        )

    return wrapper


class _RequestGuard:
    """单轮请求计数守卫（≤ MAX_REQUESTS_PER_RUN），v2 以组合替代继承。"""

    def __init__(self, name: str) -> None:
        self.name = name
        self.count = 0

    def tick(self) -> None:
        self.count += 1
        if self.count > MAX_REQUESTS_PER_RUN:
            raise CollectorError(f"{self.name} 采集单轮请求超过 {MAX_REQUESTS_PER_RUN} 次上限")


# --------------------------------------------------------------------------
# GitHub（真实模式）
# --------------------------------------------------------------------------

_COAUTHOR_RE = re.compile(r"^\s*Co-authored-by:\s*([^<]+?)\s*(?:<[^>]+>)?\s*$", re.M | re.I)


@register("github")
@with_retry
def fetch_github(day: date, settings, session: httpx.Client | None = None) -> list[RawEvent]:
    """拉取团队仓库当日提交；契约同 design.md 4.1（GitHubCollector）。"""
    token = getattr(settings, "github_token", None)
    repo = getattr(settings, "github_repo", "")
    if not token:
        raise CredentialsMissingError("GITHUB_TOKEN 未配置")
    usernames = {m.github_username for m in settings.members}
    client = session or httpx.Client(base_url="https://api.github.com", timeout=10.0)
    guard = _RequestGuard("github")
    start, end = day_window(day)
    params: dict = {
        "since": start.isoformat(),
        "until": end.isoformat(),
        "per_page": 100,
        "page": 1,
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    commits: list[dict] = []
    while True:
        guard.tick()
        resp = client.get(f"/repos/{repo}/commits", params=params, headers=headers)
        resp.raise_for_status()
        items = resp.json()
        if not isinstance(items, list):
            break
        commits.extend(items)
        if len(items) < 100:
            break
        params["page"] += 1

    events: list[RawEvent] = []
    for c in commits:
        login = ((c.get("author") or {}).get("login")) or ""
        if login not in usernames:
            continue
        message = (c.get("commit") or {}).get("message", "")
        title = message.strip().splitlines()[0] if message.strip() else "(无提交说明)"
        coauthors = tuple(
            m.group(1).strip()
            for m in _COAUTHOR_RE.finditer(message)
            if m.group(1).strip() != login
        )
        committer = (c.get("commit") or {}).get("committer") or {}
        occurred = _parse_iso(committer.get("date"))
        events.append(
            RawEvent(
                source="github",
                event_type="commit",
                ref=c.get("sha", ""),
                author=login,
                occurred_at=occurred,
                title=title,
                url=c.get("html_url", ""),
                collaborators=coauthors,
                payload={"sha": c.get("sha", "")[:8], "co_authored": bool(coauthors)},
            )
        )
    return events


# --------------------------------------------------------------------------
# 飞书（真实模式）：任务 / 消息 / 考勤
# --------------------------------------------------------------------------


@register("feishu_task")
@with_retry
def fetch_feishu_task(day: date, settings, session: httpx.Client | None = None) -> list[RawEvent]:
    """飞书任务流转采集；经办人→author、协作人→collaborators（R2 数据来源）。"""
    token = _tenant_token(settings, session)
    member_ids = {m.feishu_open_id for m in settings.members}
    client = session or httpx.Client(base_url="https://open.feishu.cn", timeout=10.0)
    guard = _RequestGuard("feishu_task")
    start, end = day_window(day)
    guard.tick()
    resp = client.get(
        "/open-apis/task/v2/tasks",
        params={
            "page_size": 50,
            "start_time": int(start.timestamp()),
            "end_time": int(end.timestamp()),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    body = resp.json()
    if body.get("code") != 0:
        raise CollectorError(f"飞书接口调用失败：code={body.get('code')} {body.get('msg')}")
    events = []
    for item in (body.get("data") or {}).get("items", []):
        assignee = item.get("assignee") or item.get("creator") or ""
        if assignee and assignee not in member_ids:
            continue
        guid = item.get("guid") or item.get("id") or ""
        events.append(
            RawEvent(
                source="feishu_task",
                event_type="task",
                ref=guid,
                author=assignee,
                occurred_at=_parse_any(item.get("completed_at") or item.get("updated_at")),
                title=item.get("summary") or "(无标题任务)",
                url=f"https://feishu.cn/task/{guid}",
                collaborators=tuple(item.get("collaborator_ids") or []),
                payload={
                    "status": item.get("status") or "",
                    "completed": item.get("is_completed", False),
                },
            )
        )
    return events


@register("feishu_message")
@with_retry
def fetch_feishu_message(
    day: date, settings, session: httpx.Client | None = None
) -> list[RawEvent]:
    """飞书群消息采集：解析 @提及与任务 ID 关联（R3 数据来源）。"""
    token = _tenant_token(settings, session)
    group_id = getattr(settings, "feishu_group_id", None)
    if not group_id:
        raise CredentialsMissingError("config.json 未配置 feishu.group_id")
    client = session or httpx.Client(base_url="https://open.feishu.cn", timeout=10.0)
    guard = _RequestGuard("feishu_message")
    start, end = day_window(day)
    guard.tick()
    resp = client.get(
        "/open-apis/im/v1/messages",
        params={
            "container_id_type": "chat",
            "container_id": group_id,
            "start_time": str(int(start.timestamp())),
            "end_time": str(int(end.timestamp())),
            "page_size": 50,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    body = resp.json()
    if body.get("code") != 0:
        raise CollectorError(f"飞书接口调用失败：code={body.get('code')} {body.get('msg')}")
    events = []
    for item in (body.get("data") or {}).get("items", []):
        content = json_loads_safe((item.get("body") or {}).get("content", "{}"))
        text = content.get("text", "")
        mentions = tuple(
            m for m in re.findall(r"@([^\s@，。！？,.!?]+)", text) if not m.startswith("所有人")
        )
        task_id = _find_task_id(text)
        events.append(
            RawEvent(
                source="feishu_message",
                event_type="message",
                ref=item.get("message_id", ""),
                author=(item.get("sender") or {}).get("id", ""),
                occurred_at=_parse_any(item.get("create_time")),
                title=text[:80] or "(非文本消息)",
                url=f"https://feishu.cn/msg/{item.get('message_id', '')}",
                collaborators=mentions,
                payload={"mentions": list(mentions), "task_id": task_id},
            )
        )
    return events


@register("feishu_attendance")
@with_retry
def fetch_feishu_attendance(
    day: date, settings, session: httpx.Client | None = None
) -> list[RawEvent]:
    """飞书考勤采集（第 4 周变更单 F12）：当日上/下午首末次打卡。

    真实模式走飞书考勤开放接口（attendance/v1），字段以开放平台文档为准；
    凭证缺失时由编排层回退 mock（v1.1 变更涟漪演练）。
    """
    token = _tenant_token(settings, session)
    member_ids = {m.feishu_open_id for m in settings.members}
    client = session or httpx.Client(base_url="https://open.feishu.cn", timeout=10.0)
    guard = _RequestGuard("feishu_attendance")
    start, end = day_window(day)
    guard.tick()
    resp = client.get(
        "/open-apis/attendance/v1/user_stats/query",
        params={
            "employee_type": "employee_id",
            "start_date": int(start.timestamp()),
            "end_date": int(end.timestamp()),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    body = resp.json()
    if body.get("code") != 0:
        raise CollectorError(f"飞书考勤接口调用失败：code={body.get('code')} {body.get('msg')}")
    events = []
    for stat in (body.get("data") or {}).get("user_stats", []):
        open_id = stat.get("user_id") or ""
        if open_id and open_id not in member_ids:
            continue
        for record in stat.get("records", []):
            kind = record.get("check_type", "")
            events.append(
                RawEvent(
                    source="feishu_attendance",
                    event_type="attendance",
                    ref=f"{open_id}:{record.get('check_time', '')}",
                    author=open_id,
                    occurred_at=_parse_any(record.get("check_time")),
                    title=f"考勤打卡（{_attendance_label(kind)}）",
                    payload={"period": kind, "location": record.get("location", "")},
                )
            )
    return events


#: tenant_access_token 应用级缓存（有效期 7199s，缓存 7000s 留余量）。
#: 避免每个采集器各自换 token，防止触发平台频率风控（21001）。
_TOKEN_CACHE: dict[str, tuple[str, float]] = {}


def _tenant_token(settings, session: httpx.Client | None) -> str:
    app_id = getattr(settings, "feishu_app_id", None)
    app_secret = getattr(settings, "feishu_app_secret", None)
    if not (app_id and app_secret):
        raise CredentialsMissingError("FEISHU_APP_ID / FEISHU_APP_SECRET 未配置")
    cached = _TOKEN_CACHE.get(app_id)
    if cached and time.monotonic() - cached[1] < 7000:
        return cached[0]
    client = session or httpx.Client(base_url="https://open.feishu.cn", timeout=10.0)
    resp = client.post(
        "/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": app_id, "app_secret": app_secret},
    )
    resp.raise_for_status()
    body = resp.json()
    if body.get("code") != 0:
        raise CredentialsMissingError(f"飞书凭证无效：code={body.get('code')} {body.get('msg')}")
    token = body["tenant_access_token"]
    _TOKEN_CACHE[app_id] = (token, time.monotonic())
    return token


# --------------------------------------------------------------------------
# Mock 数据集（阶段二全新内容：50 条事件 + 12 条标注协作 + 6 条考勤）
# --------------------------------------------------------------------------

_GH_COMMITS: list[tuple[str, str, list[str], int]] = [
    ("wr-20041110", "编写 T201 任务骨架与门禁脚本", [], 3),
    ("wr-20041110", "为规则引擎添加 R1 失败测试", ["xz0622"], 2),  # 协作 v2#1
    ("wr-20041110", "整理红绿循环记录模板", [], 1),
    ("wr-20041110", "修复 store 幂等重跑断言", [], 2),
    ("wr-20041110", "registry 注册考勤采集器", ["wjy-jjj"], 4),  # 协作 v2#2
    ("wr-20041110", "重构 fetch 重试装饰器", [], 3),
    ("wr-20041110", "补充 code-review 检查清单", [], 1),
    ("wr-20041110", "清理 pytest 临时目录", [], 2),
    ("xz0622", "编写 T204 GitHub 采集失败测试", [], 4),
    ("xz0622", "实现 synthesize 条目聚合", [], 5),
    ("xz0622", "为 deliver 添加脱敏断言", [], 2),
    ("xz0622", "修复时区边界回归用例", ["wr-20041110"], 2),  # 协作 v2#3
    ("Yin-bo-hong", "梳理 systematic-debugging 根因记录", [], 1),
    ("xz0622", "重构 pipeline 为函数组合", [], 4),
    ("Yin-bo-hong", "归档第 3 周站会记录", [], 1),
    ("wjy-jjj", "搭建 v2 目录与测试门禁", [], 3),
    ("wjy-jjj", "编写 T207 归属正确率测试", ["xz0622"], 3),  # 协作 v2#4
    ("Yin-bo-hong", "修复飞书消息 @ 解析", [], 2),
    ("Yin-bo-hong", "为 pipeline 添加降级出报断言", [], 2),
    ("Yin-bo-hong", "提交 T211 回归记录初稿", [], 1),
]

_FS_TASKS: list[tuple[str, str, list[str], str]] = [
    ("ou_wr-20041110", "review tasks-v2.md 任务粒度", [], "done"),
    ("ou_wr-20041110", "编写 TDD 红绿循环记录", ["ou_xz0622"], "done"),  # 协作 v2#5
    ("ou_wr-20041110", "核对 SC4 标注数据集", [], "done"),
    ("ou_wr-20041110", "整理隐含需求清单 v2", [], "done"),
    ("ou_xz0622", "绘制 v2 架构图", [], "done"),
    ("ou_xz0622", "code-review 互评 T204 提交", [], "done"),
    ("ou_xz0622", "red-team 评审 rules.py", ["ou_wr-20041110"], "done"),  # 协作 v2#6
    ("ou_xz0622", "梳理变更单影响面", [], "done"),
    ("ou_wjy-jjj", "搭建 ruff 静态门禁", [], "done"),
    ("ou_wjy-jjj", "配置 coverage 阈值", [], "done"),
    ("ou_wjy-jjj", "实现 store 三表结构", [], "done"),
    ("ou_wjy-jjj", "编写回归测试骨架", ["ou_yinbohong"], "doing"),  # 协作 v2#7
    ("ou_yinbohong", "设计考勤字段映射", ["ou_wjy-jjj"], "done"),  # 协作 v2#8
    ("ou_yinbohong", "归档 AI 使用日志", [], "done"),
    ("ou_yinbohong", "准备 v2 演示脚本", [], "doing"),
]

_FS_MESSAGES: list[tuple[str, str, list[str], str | None]] = [
    ("ou_wr-20041110", "晨会：今天按 executing-plans 逐任务推进", [], None),
    ("ou_wr-20041110", "@咸哲 T-201 骨架帮我评审", ["ou_xz0622"], "T-201"),  # 协作 v2#9
    ("ou_wr-20041110", "红绿循环记录已更新", [], None),
    ("ou_wr-20041110", "规则引擎还有 2 条用例要补", [], None),
    ("ou_xz0622", "T204 失败测试已提交", [], None),
    ("ou_xz0622", "systematic-debugging 记录模板放群文件了", [], None),
    ("ou_xz0622", "@王然 rules.py 评审意见 3 条", ["ou_wr-20041110"], "T-207"),  # 协作 v2#10
    ("ou_xz0622", "晚上 7 点半过一遍演示", [], None),
    ("ou_wjy-jjj", "store 幂等测试通过", [], None),
    ("ou_wjy-jjj", "@咸哲 T-209 脱敏断言过了吗", ["ou_xz0622"], "T-209"),  # 协作 v2#11
    ("ou_wjy-jjj", "ruff 0 告警了", [], None),
    ("ou_wjy-jjj", "CI 门禁跑通", [], None),
    ("ou_yinbohong", "考勤变更单影响面已梳理", [], None),
    ("ou_yinbohong", "@王峻羽 T-213 回归一起看", ["ou_wjy-jjj"], "T-213"),  # 协作 v2#12
    ("ou_yinbohong", "变更涟漪回归我来牵头", [], None),
]

_ATTENDANCE: list[tuple[str, str, str]] = [
    ("ou_wr-20041110", "09:02", "am_in"),
    ("ou_wr-20041110", "18:05", "pm_out"),
    ("ou_xz0622", "08:58", "am_in"),
    ("ou_xz0622", "17:59", "pm_out"),
    ("ou_wjy-jjj", "09:10", "am_in"),
    ("ou_wjy-jjj", "18:12", "pm_out"),
    ("ou_yinbohong", "09:15", "am_in"),
    ("ou_yinbohong", "18:20", "pm_out"),
]

#: 12 条标注协作事件（ref -> 应归属成员姓名），SC4 验收基准（v2 数据集）
EXPECTED_ATTRIBUTION_V2: dict[str, list[str]] = {
    "v2-gh-002": ["王然", "咸哲"],
    "v2-gh-005": ["王然", "王峻羽"],
    "v2-gh-012": ["咸哲", "王然"],
    "v2-gh-017": ["王峻羽", "咸哲"],
    "v2-ft-002": ["王然", "咸哲"],
    "v2-ft-007": ["咸哲", "王然"],
    "v2-ft-012": ["王峻羽", "尹博弘"],
    "v2-ft-013": ["尹博弘", "王峻羽"],
    "v2-fm-002": ["王然", "咸哲"],
    "v2-fm-007": ["咸哲", "王然"],
    "v2-fm-010": ["王峻羽", "咸哲"],
    "v2-fm-014": ["尹博弘", "王峻羽"],
}


def _utc(day: date, hour: int, minute: int) -> datetime:
    return datetime.combine(day, dtime(hour, minute), tzinfo=LOCAL_TZ).astimezone(UTC)


def build_mock_events_v2(day: date, include_attendance: bool = True) -> list[RawEvent]:
    """阶段二标准数据集（确定性生成，含变更单考勤事件）。"""
    events: list[RawEvent] = []
    for i, (author, title, coauthors, files) in enumerate(_GH_COMMITS):
        events.append(
            RawEvent(
                source="github",
                event_type="commit",
                ref=f"v2-gh-{i + 1:03d}",
                author=author,
                occurred_at=_utc(day, 9, 0) + timedelta(minutes=25 * i),
                title=title,
                url=f"https://github.com/team/smart-daily-report/commit/v2{i + 1:03d}",
                collaborators=tuple(coauthors),
                payload={"files": files, "co_authored": bool(coauthors)},
            )
        )
    for i, (assignee, title, collabs, status) in enumerate(_FS_TASKS):
        events.append(
            RawEvent(
                source="feishu_task",
                event_type="task",
                ref=f"v2-ft-{i + 1:03d}",
                author=assignee,
                occurred_at=_utc(day, 9, 30) + timedelta(minutes=20 * i),
                title=title,
                url=f"https://feishu.cn/task/{300 + i}",
                collaborators=tuple(collabs),
                payload={"status": status},
            )
        )
    for i, (speaker, title, mentions, task_id) in enumerate(_FS_MESSAGES):
        events.append(
            RawEvent(
                source="feishu_message",
                event_type="message",
                ref=f"v2-fm-{i + 1:03d}",
                author=speaker,
                occurred_at=_utc(day, 10, 0) + timedelta(minutes=20 * i),
                title=title,
                url=f"https://feishu.cn/msg/{400 + i}",
                collaborators=tuple(mentions),
                payload={"mentions": list(mentions), "task_id": task_id},
            )
        )
    if include_attendance:
        for i, (open_id, clock, period) in enumerate(_ATTENDANCE):
            hh, mm = clock.split(":")
            events.append(
                RawEvent(
                    source="feishu_attendance",
                    event_type="attendance",
                    ref=f"v2-att-{i + 1:03d}",
                    author=open_id,
                    occurred_at=_utc(day, int(hh), int(mm)),
                    title=f"考勤打卡（{_attendance_label(period)}）",
                    payload={"period": period},
                )
            )
    return events


@register("mock")
def fetch_mock(day: date, settings, **_) -> list[RawEvent]:
    """mock 场景入口：阶段二数据集（含考勤，变更涟漪后与真实源对齐）。"""
    return build_mock_events_v2(day, include_attendance=True)


def _attendance_label(period: str) -> str:
    return {"am_in": "上午上班", "pm_out": "下午下班"}.get(period, period)


# --------------------------------------------------------------------------
# 工具函数
# --------------------------------------------------------------------------


def _parse_iso(value) -> datetime:
    if not value:
        return datetime.now().astimezone()
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except ValueError:
        return datetime.now().astimezone()


def _parse_any(value) -> datetime:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=UTC)
    return _parse_iso(value)


def json_loads_safe(text: str) -> dict:
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return {}


def _find_task_id(text: str) -> str | None:
    m = re.search(r"\bT-\d{2,6}\b", text)
    return m.group(0) if m else None
