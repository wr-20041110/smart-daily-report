"""Mock 数据源（proposal.md F11 / tasks.md T3-T5 验收标准）。

内置标准数据集（场景 standard）：4 名成员 × 3 数据源共 50 条事件，
其中 12 条标注协作事件（4 共同提交 + 4 协作任务 + 4 @协作消息），
标注答案见 EXPECTED_ATTRIBUTION，用于成功标准 SC4 的归属正确率验收。

平台账号（占位，替换为真实账号后重跑即可）：
  王然   github=wr-20041110      feishu=ou_9fb641793dcb3547d8d1c4e655b7e589
  咸哲   github=xz0622      feishu=ou_1285ac40fd873adf31e91d930be504b3
  王峻羽 github=wjy-jjj    feishu=ou_5e774c1fe692bb17cd0d4f7a0dd93076
  尹博弘 github=Yin-bo-hong feishu=ou_234449d3b4e94f58f064f33dbd2736c0
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from datetime import time as dtime

from ..errors import CollectorError
from ..models import LOCAL_TZ, RawEvent
from .base import BaseCollector

#: 三源事件数量（tasks.md T3/T4/T5 验收标准）
MOCK_COUNTS = {"github": 20, "feishu_task": 15, "feishu_message": 15}

# (作者 GitHub 用户名, 标题, 共同作者, 变更文件数)
_COMMITS: list[tuple[str, str, list[str], int]] = [
    ("wr-20041110", "修复日报生成模块归属去重问题", [], 4),
    ("wr-20041110", "新增飞书任务采集器重试逻辑", ["xz0622"], 6),  # 协作#1
    ("wr-20041110", "更新团队成员配置清单", [], 2),
    ("wr-20041110", "整理 README 与快速开始文档", [], 1),
    ("wr-20041110", "为存储层补充幂等重跑测试", ["wjy-jjj"], 3),  # 协作#2
    ("wr-20041110", "优化协同归属规则 R3 的解析", [], 5),
    ("wr-20041110", "修正时区换算边界用例", [], 2),
    ("wr-20041110", "重构推送层日志脱敏", [], 4),
    ("xz0622", "完成 design.md 接口契约评审", [], 2),
    ("xz0622", "新增 httpx 连接池配置", [], 3),
    ("xz0622", "实现 GitHub 采集日期窗口", [], 5),
    ("xz0622", "修复 mock 数据集时区问题", ["wr-20041110"], 2),  # 协作#3
    ("Yin-bo-hong", "补充 ER 图与表结构说明", [], 1),
    ("xz0622", "调整重试退避策略为 1s/2s/4s", [], 2),
    ("Yin-bo-hong", "为飞书任务采集增加字段映射测试", [], 3),
    ("wjy-jjj", "搭建 pytest 与 coverage 门禁", [], 4),
    ("wjy-jjj", "实现团队日报 Markdown 模板", ["xz0622"], 6),  # 协作#4
    ("Yin-bo-hong", "修复成员映射未知账号处理", [], 2),
    ("Yin-bo-hong", "增加主流程幂等性检查", [], 3),
    ("Yin-bo-hong", "提交验收核对记录初稿", [], 1),
]

# (经办人 open_id, 标题, 协作人 open_id 列表, 状态)
_TASKS: list[tuple[str, str, list[str], str]] = [
    ("ou_9fb641793dcb3547d8d1c4e655b7e589", "评审 proposal.md 范围条目", [], "done"),
    (
        "ou_9fb641793dcb3547d8d1c4e655b7e589",
        "编写需求澄清问答记录",
        ["ou_1285ac40fd873adf31e91d930be504b3"],
        "done",
    ),  # 协作#5
    ("ou_9fb641793dcb3547d8d1c4e655b7e589", "核对成功标准可度量性", [], "done"),
    ("ou_9fb641793dcb3547d8d1c4e655b7e589", "整理隐含需求清单", [], "done"),
    ("ou_1285ac40fd873adf31e91d930be504b3", "绘制用例图与泳道图", [], "done"),
    ("ou_1285ac40fd873adf31e91d930be504b3", "撰写 ADR-001/002 初稿", [], "done"),
    (
        "ou_1285ac40fd873adf31e91d930be504b3",
        "红队评审 design.md",
        ["ou_9fb641793dcb3547d8d1c4e655b7e589"],
        "done",
    ),  # 协作#6
    ("ou_1285ac40fd873adf31e91d930be504b3", "梳理非功能约束清单", [], "done"),
    ("ou_5e774c1fe692bb17cd0d4f7a0dd93076", "搭建仓库目录与 git 规范", [], "done"),
    ("ou_5e774c1fe692bb17cd0d4f7a0dd93076", "配置 ruff 静态扫描", [], "done"),
    ("ou_5e774c1fe692bb17cd0d4f7a0dd93076", "实现存储层 init_db", [], "done"),
    (
        "ou_5e774c1fe692bb17cd0d4f7a0dd93076",
        "编写集成测试骨架",
        ["ou_234449d3b4e94f58f064f33dbd2736c0"],
        "doing",
    ),  # 协作#7
    (
        "ou_234449d3b4e94f58f064f33dbd2736c0",
        "设计 SQLite 表结构",
        ["ou_5e774c1fe692bb17cd0d4f7a0dd93076"],
        "done",
    ),  # 协作#8
    ("ou_234449d3b4e94f58f064f33dbd2736c0", "归档组内 AI 使用日志", [], "done"),
    ("ou_234449d3b4e94f58f064f33dbd2736c0", "准备阶段评审会演示脚本", [], "doing"),
]

# (发言者 open_id, 消息摘要, @提及 open_id 列表, 关联任务 ID 或 None)
_MESSAGES: list[tuple[str, str, list[str], str | None]] = [
    ("ou_9fb641793dcb3547d8d1c4e655b7e589", "晨会同步：今天先过 proposal 范围", [], None),
    (
        "ou_9fb641793dcb3547d8d1c4e655b7e589",
        "@咸哲 T-101 的接口契约帮我看看",
        ["ou_1285ac40fd873adf31e91d930be504b3"],
        "T-101",
    ),  # 协作#9
    ("ou_9fb641793dcb3547d8d1c4e655b7e589", "调研结论已更新到文档", [], None),
    ("ou_9fb641793dcb3547d8d1c4e655b7e589", "mock 数据集还要补 2 条协作事件", [], None),
    ("ou_1285ac40fd873adf31e91d930be504b3", "用例图初版已提交", [], None),
    ("ou_1285ac40fd873adf31e91d930be504b3", "红队评审问题清单发群里了", [], None),
    (
        "ou_1285ac40fd873adf31e91d930be504b3",
        "@王然 design.md 3.2 表结构已改好",
        ["ou_9fb641793dcb3547d8d1c4e655b7e589"],
        "T-102",
    ),  # 协作#10
    ("ou_1285ac40fd873adf31e91d930be504b3", "晚上 7 点过一遍演示", [], None),
    ("ou_5e774c1fe692bb17cd0d4f7a0dd93076", "数据库幂等测试通过", [], None),
    (
        "ou_5e774c1fe692bb17cd0d4f7a0dd93076",
        "@咸哲 T-105 时区用例过了吗",
        ["ou_1285ac40fd873adf31e91d930be504b3"],
        "T-105",
    ),  # 协作#11
    ("ou_5e774c1fe692bb17cd0d4f7a0dd93076", "tag 和提交规范已整理", [], None),
    ("ou_5e774c1fe692bb17cd0d4f7a0dd93076", "CI 门禁跑通了", [], None),
    ("ou_234449d3b4e94f58f064f33dbd2736c0", "飞书凭证审核还在等", [], None),
    (
        "ou_234449d3b4e94f58f064f33dbd2736c0",
        "@王峻羽 T-107 回归用例一起看",
        ["ou_5e774c1fe692bb17cd0d4f7a0dd93076"],
        "T-107",
    ),  # 协作#12
    ("ou_234449d3b4e94f58f064f33dbd2736c0", "明天评审会材料我来整理", [], None),
]

#: 12 条协作事件的标注答案：ref -> 应归属的成员姓名（成功标准 SC4 验收基准）
EXPECTED_ATTRIBUTION: dict[str, list[str]] = {
    "mock-gh-002": ["王然", "咸哲"],
    "mock-gh-005": ["王然", "王峻羽"],
    "mock-gh-012": ["咸哲", "王然"],
    "mock-gh-017": ["王峻羽", "咸哲"],
    "mock-ft-002": ["王然", "咸哲"],
    "mock-ft-007": ["咸哲", "王然"],
    "mock-ft-012": ["王峻羽", "尹博弘"],
    "mock-ft-013": ["尹博弘", "王峻羽"],
    "mock-fm-002": ["王然", "咸哲"],
    "mock-fm-007": ["咸哲", "王然"],
    "mock-fm-010": ["王峻羽", "咸哲"],
    "mock-fm-014": ["尹博弘", "王峻羽"],
}


def _utc(day: date, hour: int, minute: int) -> datetime:
    local = datetime.combine(day, dtime(hour, minute), tzinfo=LOCAL_TZ)
    return local.astimezone(UTC)


def build_mock_events(day: date) -> list[RawEvent]:
    """为指定日期构造标准数据集（确定性：同一日期两次调用结果一致）。"""
    events: list[RawEvent] = []
    for i, (author, title, coauthors, files) in enumerate(_COMMITS):
        events.append(
            RawEvent(
                source="github",
                event_type="commit",
                ref=f"mock-gh-{i + 1:03d}",
                author=author,
                occurred_at=_utc(day, 9, 0) + timedelta(minutes=25 * i),
                title=title,
                url=f"https://github.com/team/smart-daily-report/commit/mock{i + 1:03d}",
                collaborators=list(coauthors),
                payload={"files": files, "co_authored": bool(coauthors)},
            )
        )
    for i, (assignee, title, collabs, status) in enumerate(_TASKS):
        events.append(
            RawEvent(
                source="feishu_task",
                event_type="task",
                ref=f"mock-ft-{i + 1:03d}",
                author=assignee,
                occurred_at=_utc(day, 9, 30) + timedelta(minutes=20 * i),
                title=title,
                url=f"https://feishu.cn/task/{100 + i}",
                collaborators=list(collabs),
                payload={"status": status},
            )
        )
    for i, (speaker, title, mentions, task_id) in enumerate(_MESSAGES):
        events.append(
            RawEvent(
                source="feishu_message",
                event_type="message",
                ref=f"mock-fm-{i + 1:03d}",
                author=speaker,
                occurred_at=_utc(day, 10, 0) + timedelta(minutes=20 * i),
                title=title,
                url=f"https://feishu.cn/msg/{200 + i}",
                collaborators=list(mentions),
                payload={"mentions": list(mentions), "task_id": task_id},
            )
        )
    return events


class MockCollector(BaseCollector):
    """内置模拟数据源：无外部凭证时全流程可跑（proposal.md F11）。"""

    def __init__(self, source: str, data_key: str = "standard") -> None:
        super().__init__()
        if source not in MOCK_COUNTS:
            raise CollectorError(f"未知 mock 数据源：{source}（可选：{sorted(MOCK_COUNTS)}）")
        if data_key != "standard":
            raise CollectorError(f"未知 mock 场景：{data_key}（当前仅提供 standard）")
        self.name = source
        self.data_key = data_key

    def collect(self, day: date) -> list[RawEvent]:
        """返回指定日期、本数据源的事件（契约同 design.md 4.1，无网络请求）。"""
        return [e for e in build_mock_events(day) if e.source == self.name]
