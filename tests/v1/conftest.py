"""v1 测试公共夹具。"""

from __future__ import annotations

from datetime import date

import pytest

from daily_report_v1.config import Settings
from daily_report_v1.models import Member

DAY = date(2026, 11, 24)

MEMBERS = [
    Member("王然", "wr-20041110", "ou_wr-20041110", "wr-20041110@example.com"),
    Member("咸哲", "XianZhe727", "ou_XianZhe727", "XianZhe727@example.com"),
    Member("王峻羽", "wjy-jjj", "ou_wjy-jjj", "wjy-jjj@example.com"),
]


@pytest.fixture
def members() -> list[Member]:
    return list(MEMBERS)


@pytest.fixture
def settings(tmp_path) -> Settings:
    s = Settings(
        members=list(MEMBERS),
        github_repo="team/smart-daily-report",
        db_path=str(tmp_path / "reports.db"),
        mock=True,
        report_sender="report@example.com",
        report_recipients=["a@example.com"],
    )
    s.validate()
    return s
