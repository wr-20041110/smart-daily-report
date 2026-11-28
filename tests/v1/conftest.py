"""v1 测试公共夹具。"""

from __future__ import annotations

from datetime import date

import pytest

from daily_report_v1.config import Settings
from daily_report_v1.models import Member

DAY = date(2026, 11, 24)

MEMBERS = [
    Member("王然", "wr-20041110", "ou_9fb641793dcb3547d8d1c4e655b7e589", "wr-20041110@example.com"),
    Member("咸哲", "xz0622", "ou_1285ac40fd873adf31e91d930be504b3", "xz0622@example.com"),
    Member("王峻羽", "wjy-jjj", "ou_5e774c1fe692bb17cd0d4f7a0dd93076", "wjy-jjj@example.com"),
    Member(
        "尹博弘", "Yin-bo-hong", "ou_234449d3b4e94f58f064f33dbd2736c0", "20233159@stu.ccut.edu.cn"
    ),
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
