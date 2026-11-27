"""Mock 数据源（proposal.md F11 / tasks.md T3-T5 验收标准）。

内置标准数据集（场景 standard）：3 名成员 × 3 数据源共 50 条事件，
其中 12 条标注协作事件（4 共同提交 + 4 协作任务 + 4 @协作消息），
标注答案见 EXPECTED_ATTRIBUTION，用于成功标准 SC4 的归属正确率验收。

平台账号（占位，替换为真实账号后重跑即可）：
  王然   github=wr-20041110      feishu=ou_wr-20041110
  咸哲   github=XianZhe727      feishu=ou_XianZhe727
  王峻羽 github=wjy-jjj    feishu=ou_wjy-jjj
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
    ("wr-20041110", "新增飞书任务采集器重试逻辑", ["XianZhe727"], 6),  # 协作#1
    ("wr-20041110", "更新团队成员配置清单", [], 2),
    ("wr-20041110", "整理 README 与快速开始文档", [], 1),
    ("wr-20041110", "为存储层补充幂等重跑测试", ["wjy-jjj"], 3),  # 协作#2
    ("wr-20041110", "优化协同归属规则 R3 的解析", [], 5),
    ("wr-20041110", "修正时区换算边界用例", [], 2),
    ("wr-20041110", "重构推送层日志脱敏", [], 4),
    ("XianZhe727", "完成 design.md 接口契约评审", [], 2),
    ("XianZhe727", "新增 httpx 连接池配置", [], 3),
    ("XianZhe727", "实现 GitHub 采集日期窗口", [], 5),
    ("XianZhe727", "修复 mock 数据集时区问题", ["wr-20041110"], 2),  # 协作#3
    ("XianZhe727", "补充 ER 图与表结构说明", [], 1),
    ("XianZhe727", "调整重试退避策略为 1s/2s/4s", [], 2),
    ("XianZhe727", "为飞书任务采集增加字段映射测试", [], 3),
    ("wjy-jjj", "搭建 pytest 与 coverage 门禁", [], 4),
    ("wjy-jjj", "实现团队日报 Markdown 模板", ["XianZhe727"], 6),  # 协作#4
    ("wjy-jjj", "修复成员映射未知账号处理", [], 2),
    ("wjy-jjj", "增加主流程幂等性检查", [], 3),
    ("wjy-jjj", "提交验收核对记录初稿", [], 1),
]

# (经办人 open_id, 标题, 协作人 open_id 列表, 状态)
_TASKS: list[tuple[str, str, list[str], str]] = [
    ("ou_wr-20041110", "评审 proposal.md 范围条目", [], "done"),
    ("ou_wr-20041110", "编写需求澄清问答记录", ["ou_XianZhe727"], "done"),  # 协作#5
    ("ou_wr-20041110", "核对成功标准可度量性", [], "done"),
    ("ou_wr-20041110", "整理隐含需求清单", [], "done"),
    ("ou_wr-20041110", "准备阶段评审会演示脚本", ["ou_wjy-jjj"], "doing"),  # 协作#6
    ("ou_XianZhe727", "绘制用例图与泳道图", [], "done"),
    ("ou_XianZhe727", "撰写 ADR-001/002 初稿", [], "done"),
    ("ou_XianZhe727", "红队评审 design.md", ["ou_wr-20041110"], "done"),  # 协作#7
    ("ou_XianZhe727", "梳理非功能约束清单", [], "done"),
    ("ou_XianZhe727", "设计 SQLite 表结构", ["ou_wjy-jjj"], "done"),  # 协作#8
    ("ou_wjy-jjj", "搭建仓库目录与 git 规范", [], "done"),
    ("ou_wjy-jjj", "配置 ruff 静态扫描", [], "done"),
    ("ou_wjy-jjj", "实现存储层 init_db", [], "done"),
    ("ou_wjy-jjj", "编写集成测试骨架", [], "doing"),
    ("ou_wjy-jjj", "归档组内 AI 使用日志", [], "done"),
]

# (发言者 open_id, 消息摘要, @提及 open_id 列表, 关联任务 ID 或 None)
_MESSAGES: list[tuple[str, str, list[str], str | None]] = [
    ("ou_wr-20041110", "晨会同步：今天先过 proposal 范围", [], None),
    ("ou_wr-20041110", "@咸哲 T-101 的接口契约帮我看看", ["ou_XianZhe727"], "T-101"),  # 协作#9
    ("ou_wr-20041110", "调研结论已更新到文档", [], None),
    ("ou_wr-20041110", "mock 数据集还要补 2 条协作事件", [], None),
    ("ou_wr-20041110", "@王峻羽 T-103 集成测试一起修", ["ou_wjy-jjj"], "T-103"),  # 协作#10
    ("ou_XianZhe727", "用例图初版已提交", [], None),
    ("ou_XianZhe727", "红队评审问题清单发群里了", [], None),
    ("ou_XianZhe727", "@王然 design.md 3.2 表结构已改好", ["ou_wr-20041110"], "T-102"),  # 协作#11
    ("ou_XianZhe727", "晚上 7 点过一遍演示", [], None),
    ("ou_XianZhe727", "飞书凭证审核还在等", [], None),
    ("ou_wjy-jjj", "数据库幂等测试通过", [], None),
    ("ou_wjy-jjj", "@咸哲 T-105 时区用例过了吗", ["ou_XianZhe727"], "T-105"),  # 协作#12
    ("ou_wjy-jjj", "tag 和提交规范已整理", [], None),
    ("ou_wjy-jjj", "CI 门禁跑通了", [], None),
    ("ou_wjy-jjj", "明天评审会材料我来整理", [], None),
]

#: 12 条协作事件的标注答案：ref -> 应归属的成员姓名（成功标准 SC4 验收基准）
EXPECTED_ATTRIBUTION: dict[str, list[str]] = {
    "mock-gh-002": ["王然", "咸哲"],
    "mock-gh-005": ["王然", "王峻羽"],
    "mock-gh-012": ["咸哲", "王然"],
    "mock-gh-017": ["王峻羽", "咸哲"],
    "mock-ft-002": ["王然", "咸哲"],
    "mock-ft-005": ["王然", "王峻羽"],
    "mock-ft-008": ["咸哲", "王然"],
    "mock-ft-010": ["咸哲", "王峻羽"],
    "mock-fm-002": ["王然", "咸哲"],
    "mock-fm-005": ["王然", "王峻羽"],
    "mock-fm-008": ["咸哲", "王然"],
    "mock-fm-012": ["王峻羽", "咸哲"],
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
