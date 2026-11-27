"""T202 配置验收（红→绿归档）：build_settings 纯函数、凭证注入、唯一性校验。"""

from __future__ import annotations

import pytest

from daily_report_v2.settings import ConfigError, build_settings

RAW = {
    "team": {"repo": "team/repo"},
    "members": [
        {
            "name": "王然",
            "github_username": "wangran",
            "feishu_open_id": "ou_1",
            "email": "a@x.com",
        },
        {
            "name": "咸哲",
            "github_username": "xianzhe",
            "feishu_open_id": "ou_2",
            "email": "b@x.com",
        },
    ],
    "feishu": {"group_id": "oc_g"},
    "report": {"sender": "s@x.com", "recipients": ["r@x.com"]},
    "db_path": "data/r.db",
}


def test_env_credentials_injected():
    s = build_settings(RAW, {"GITHUB_TOKEN": "tok", "FEISHU_APP_ID": "id", "SMTP_PASSWORD": "pw"})
    assert s.github_token == "tok"
    assert s.feishu_app_id == "id"
    assert s.smtp_password == "pw"  # 凭证只经 env 注入，不落 config.json


def test_missing_credentials_are_none():
    s = build_settings(RAW, {})
    assert s.github_token is None and s.feishu_app_secret is None
    assert not s.is_github_ready and not s.is_feishu_ready and not s.is_smtp_ready


def test_duplicate_member_names_rejected():
    raw = {"members": RAW["members"] * 2}
    with pytest.raises(ConfigError, match="唯一"):
        build_settings(raw, {})


def test_empty_members_rejected():
    with pytest.raises(ConfigError, match="为空"):
        build_settings({"members": []}, {})


def test_incomplete_member_fields_rejected():
    raw = {
        "members": [
            {"name": "王然", "github_username": "", "feishu_open_id": "ou", "email": "a@x.com"}
        ]
    }
    with pytest.raises(ConfigError, match="不完整"):
        build_settings(raw, {})
