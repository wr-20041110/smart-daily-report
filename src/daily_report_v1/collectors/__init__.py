"""采集层：GitHub 提交 / 飞书任务 / 飞书消息 / Mock 数据源（design.md 4.1 接口契约）。"""

from .base import MAX_REQUESTS_PER_RUN, RETRY_DELAYS, BaseCollector, day_window
from .feishu import FeishuMessageCollector, FeishuTaskCollector
from .github import GitHubCollector
from .mock_data import MockCollector

__all__ = [
    "BaseCollector",
    "GitHubCollector",
    "FeishuTaskCollector",
    "FeishuMessageCollector",
    "MockCollector",
    "day_window",
    "MAX_REQUESTS_PER_RUN",
    "RETRY_DELAYS",
]
