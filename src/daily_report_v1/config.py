"""配置加载（design.md 模块职责：共享-配置，ADR-003 凭证环境变量注入）。"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from .errors import ConfigError
from .models import Member


@dataclass
class Settings:
    """统一配置对象：成员清单与仓库信息来自 config.json（可入库），凭证来自环境变量（禁入库）。"""

    members: list[Member] = field(default_factory=list)
    github_repo: str = ""
    github_token: str | None = None
    feishu_app_id: str | None = None
    feishu_app_secret: str | None = None
    feishu_group_id: str | None = None
    feishu_bot_webhook: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 465
    smtp_user: str | None = None
    smtp_password: str | None = None
    report_sender: str = ""
    report_recipients: list[str] = field(default_factory=list)
    db_path: str = "data/reports.db"
    mock: bool = False  # CLI --mock 显式指定

    @property
    def is_github_ready(self) -> bool:
        return bool(self.github_token and self.github_repo)

    @property
    def is_feishu_ready(self) -> bool:
        return bool(self.feishu_app_id and self.feishu_app_secret)

    @property
    def is_smtp_ready(self) -> bool:
        return bool(self.smtp_host and self.smtp_user and self.smtp_password)

    def validate(self) -> None:
        """成员 name 唯一校验（tasks.md T2 验收标准）。"""
        names = [m.name for m in self.members]
        if not names:
            raise ConfigError("成员清单为空：请检查 config.json 的 members 字段")
        if len(set(names)) != len(names):
            raise ConfigError(f"成员姓名必须唯一，当前为：{names}")
        for m in self.members:
            if not (m.github_username and m.feishu_open_id and m.email):
                raise ConfigError(f"成员 {m.name} 的账号映射字段不完整（见 config.example.json）")


def load_settings(config_path: str | Path | None = None, mock: bool = False) -> Settings:
    """从 config.json + 环境变量构建 Settings（tasks.md T2 验收标准）。"""
    path = Path(config_path) if config_path else Path("config.json")
    if not path.exists():
        raise ConfigError(
            f"未找到配置文件 {path}：请复制 config.example.json 为 config.json 并填写成员清单"
        )
    with path.open(encoding="utf-8") as f:
        raw = json.load(f)

    members = [
        Member(
            name=m["name"],
            github_username=m["github_username"],
            feishu_open_id=m["feishu_open_id"],
            email=m["email"],
        )
        for m in raw.get("members", [])
    ]
    report = raw.get("report", {})
    settings = Settings(
        members=members,
        github_repo=raw.get("team", {}).get("repo", ""),
        github_token=os.getenv("GITHUB_TOKEN"),
        feishu_app_id=os.getenv("FEISHU_APP_ID"),
        feishu_app_secret=os.getenv("FEISHU_APP_SECRET"),
        feishu_group_id=raw.get("feishu", {}).get("group_id"),
        feishu_bot_webhook=os.getenv("FEISHU_BOT_WEBHOOK"),
        smtp_host=os.getenv("SMTP_HOST"),
        smtp_port=int(os.getenv("SMTP_PORT", "465")),
        smtp_user=os.getenv("SMTP_USER"),
        smtp_password=os.getenv("SMTP_PASSWORD"),
        report_sender=report.get("sender", ""),
        report_recipients=list(report.get("recipients", [])),
        db_path=raw.get("db_path", "data/reports.db"),
        mock=mock,
    )
    settings.validate()
    return settings
