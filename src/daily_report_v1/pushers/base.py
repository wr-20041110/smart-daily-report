"""推送器契约（design.md 4.4）。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..models import TeamReport


@dataclass
class PushResult:
    """单通道推送结果。mocked=True 表示凭证缺失、仅本地留痕。"""

    channel: str  # "email" / "feishu"
    ok: bool
    mocked: bool
    detail: str  # 脱敏后的摘要（不得含任何凭证）


class BasePusher(ABC):
    """推送器统一契约：push(TeamReport) -> PushResult，任何情况不抛出。"""

    channel: str = ""

    @abstractmethod
    def push(self, team: TeamReport) -> PushResult:
        """推送团队日报；凭证缺失 mock 留痕，真实失败返回 ok=False（design.md 4.4）。"""
