"""配置加载（v2：纯函数 build_settings + 薄 IO 壳；ADR-003 结论继承）。

与 v1 的差异：Settings 为 frozen；构建逻辑拆成纯函数 build_settings(raw, env)，
测试可注入任意 env 映射，无需 monkeypatch os.getenv。
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from .domain import Member


class ConfigError(Exception):
    """配置加载或校验失败。"""


@dataclass(frozen=True, slots=True)
class Settings:
    members: tuple[Member, ...] = ()
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
    report_recipients: tuple[str, ...] = ()
    db_path: str = "data/reports.db"
    mock: bool = False

    @property
    def is_github_ready(self) -> bool:
        # 仓库名含【占位符未替换视为未就绪，保持 mock 模式（演示防护）
        repo_ok = bool(self.github_repo) and "【" not in (self.github_repo or "")
        return bool(self.github_token and repo_ok)

    @property
    def is_feishu_ready(self) -> bool:
        # 群 ID 含【占位符未替换视为未就绪，保持 mock 模式（演示防护）
        group_ok = bool(self.feishu_group_id) and "【" not in (self.feishu_group_id or "")
        return bool(self.feishu_app_id and self.feishu_app_secret) and group_ok

    @property
    def is_smtp_ready(self) -> bool:
        return bool(self.smtp_host and self.smtp_user and self.smtp_password)


def build_settings(raw: dict, env: Mapping[str, str], mock: bool = False) -> Settings:
    """纯函数：config.json 字典 + 环境变量映射 → Settings（含成员唯一性校验）。"""
    members = tuple(
        Member(
            name=m["name"],
            github_username=m["github_username"],
            feishu_open_id=m["feishu_open_id"],
            email=m["email"],
        )
        for m in raw.get("members", [])
    )
    names = [m.name for m in members]
    if not names:
        raise ConfigError("成员清单为空：请检查 config.json 的 members 字段")
    if len(set(names)) != len(names):
        raise ConfigError(f"成员姓名必须唯一，当前为：{names}")
    for m in members:
        if not (m.github_username and m.feishu_open_id and m.email):
            raise ConfigError(f"成员 {m.name} 的账号映射字段不完整（见 config.example.json）")

    report = raw.get("report", {})
    return Settings(
        members=members,
        github_repo=raw.get("team", {}).get("repo", ""),
        github_token=env.get("GITHUB_TOKEN") or None,
        feishu_app_id=env.get("FEISHU_APP_ID") or None,
        feishu_app_secret=env.get("FEISHU_APP_SECRET") or None,
        feishu_group_id=raw.get("feishu", {}).get("group_id") or None,
        feishu_bot_webhook=env.get("FEISHU_BOT_WEBHOOK") or None,
        smtp_host=env.get("SMTP_HOST") or None,
        smtp_port=int(env.get("SMTP_PORT", "465")),
        smtp_user=env.get("SMTP_USER") or None,
        smtp_password=env.get("SMTP_PASSWORD") or None,
        report_sender=report.get("sender", ""),
        report_recipients=tuple(report.get("recipients", [])),
        db_path=raw.get("db_path", "data/reports.db"),
        mock=mock,
    )


def load_settings(config_path: str | Path | None = None, mock: bool = False) -> Settings:
    """薄 IO 壳：读 config.json + os.environ 后委托 build_settings。"""
    _load_dotenv()
    path = Path(config_path) if config_path else Path("config.json")
    if not path.exists():
        raise ConfigError(
            f"未找到配置文件 {path}：请复制 config.example.json 为 config.json 并填写成员清单"
        )
    with path.open(encoding="utf-8") as f:
        raw = json.load(f)
    return build_settings(raw, os.environ, mock=mock)


def _load_dotenv(path: str | Path | None = None) -> None:
    """读取 .env（KEY=VALUE 行）注入环境变量；已存在的环境变量优先，凭证仍不落代码。"""
    dotenv = Path(path) if path else Path(".env")
    if not dotenv.exists():
        return
    for line in dotenv.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())
