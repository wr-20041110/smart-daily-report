"""采集器基类（design.md 4.1 接口契约：请求计数上限、指数退避重试、日期窗口）。"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from datetime import time as dtime

from ..errors import CollectorError
from ..models import LOCAL_TZ, RawEvent

#: 单次采集对外请求数上限（design.md 非功能约束：≤ 20）
MAX_REQUESTS_PER_RUN = 20
#: 指数退避重试间隔（秒）：1 / 2 / 4
RETRY_DELAYS: tuple[float, ...] = (1.0, 2.0, 4.0)


def day_window(day: date) -> tuple[datetime, datetime]:
    """本地日 [00:00, 次日 00:00) 换算为 UTC 区间（design.md 4.1 契约）。"""
    start_local = datetime.combine(day, dtime.min, tzinfo=LOCAL_TZ)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


class BaseCollector(ABC):
    """采集器统一契约：collect(day) -> list[RawEvent]。"""

    name: str = ""

    def __init__(self) -> None:
        self._request_count = 0

    @abstractmethod
    def collect(self, day: date) -> list[RawEvent]:
        """采集 day（本地日）当日的原始事件，契约见 design.md 4.1。"""

    def _guard_request(self) -> None:
        """请求计数守卫：单轮超过上限即失败，防止触发平台限流。"""
        self._request_count += 1
        if self._request_count > MAX_REQUESTS_PER_RUN:
            raise CollectorError(
                f"{self.name} 采集单轮请求超过 {MAX_REQUESTS_PER_RUN} 次上限（防限流），"
                "请检查分页逻辑"
            )

    def _retry(self, fn: Callable, *args, **kwargs):
        """指数退避重试：首次失败后按 1s/2s/4s 重试 3 次，仍失败抛 CollectorError。"""
        last: Exception | None = None
        for attempt, delay in enumerate((*RETRY_DELAYS, 0)):
            try:
                return fn(*args, **kwargs)
            except CollectorError:
                raise  # 业务性失败（凭证缺失、请求超限）不重试
            except Exception as exc:  # noqa: BLE001 —— 网络类异常统一重试
                last = exc
                if attempt < len(RETRY_DELAYS):
                    time.sleep(delay)
        raise CollectorError(
            f"{self.name} 采集失败（重试 {len(RETRY_DELAYS)} 次后仍失败）："
            f"{type(last).__name__}: {last}"
        )
