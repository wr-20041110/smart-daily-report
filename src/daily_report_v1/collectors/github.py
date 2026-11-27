"""GitHub 提交采集（proposal.md F1，design.md 4.1 契约）。

真实模式：GitHub REST API  GET /repos/{repo}/commits?since=&until=
- since/until 按本地日（Asia/Shanghai）换算为 UTC 区间（design.md 非功能约束-时区）
- 仅保留团队成员的提交（作者用户名过滤）
- 解析提交信息中的 Co-authored-by 尾注（协同归属规则 R1 数据来源）
- 请求计数守卫 + 指数退避重试（BaseCollector）
"""

from __future__ import annotations

import re
from datetime import date

import httpx

from ..errors import CredentialsMissingError
from ..models import RawEvent
from .base import BaseCollector, day_window

#: "Co-authored-by: 名字 <邮箱>" 尾注（每行一个共同作者）
_COAUTHOR_RE = re.compile(r"^\s*Co-authored-by:\s*([^<]+?)\s*(?:<[^>]+>)?\s*$", re.M | re.I)


class GitHubCollector(BaseCollector):
    name = "github"

    def __init__(
        self,
        repo: str,
        token: str | None,
        usernames: list[str],
        session: httpx.Client | None = None,
        base_url: str = "https://api.github.com",
    ) -> None:
        super().__init__()
        self.repo = repo
        self.token = token
        self.usernames = set(usernames)
        self._client = session or httpx.Client(base_url=base_url, timeout=10.0)

    def collect(self, day: date) -> list[RawEvent]:
        if not self.token:
            raise CredentialsMissingError("GITHUB_TOKEN 未配置")
        start, end = day_window(day)
        commits = self._fetch_commits(start.isoformat(), end.isoformat())
        events: list[RawEvent] = []
        for commit in commits:
            login = ((commit.get("author") or {}).get("login")) or ""
            if login not in self.usernames:
                continue  # 非团队成员提交不采集（design.md 4.1 契约）
            message = (commit.get("commit") or {}).get("message", "")
            title = message.strip().splitlines()[0] if message.strip() else "(无提交说明)"
            coauthors = [m.group(1).strip() for m in _COAUTHOR_RE.finditer(message)]
            sha = commit.get("sha", "")
            events.append(
                RawEvent(
                    source=self.name,
                    event_type="commit",
                    ref=sha,
                    author=login,
                    occurred_at=_parse_time((commit.get("commit") or {}).get("committer")),
                    title=title,
                    url=commit.get("html_url", ""),
                    collaborators=[c for c in coauthors if c != login],
                    payload={"sha": sha[:8], "co_authored": bool(coauthors)},
                )
            )
        return events

    def _fetch_commits(self, since: str, until: str) -> list[dict]:
        """分页拉取区间内提交；每页一个请求（计数守卫），页间失败按基类策略重试。"""
        params: dict = {"since": since, "until": until, "per_page": 100, "page": 1}
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        commits: list[dict] = []
        while True:
            self._guard_request()
            page = self._retry(
                self._client.get, f"/repos/{self.repo}/commits", params=params, headers=headers
            )
            page.raise_for_status()
            items = page.json()
            if not isinstance(items, list):
                break
            commits.extend(items)
            if len(items) < 100:
                break
            params["page"] += 1
        return commits


def _parse_time(committer: dict | None):
    """提交时间解析：GitHub 返回 ISO-8601 UTC；异常时回退当前时间（不影响主流程）。"""
    from datetime import datetime

    if committer and committer.get("date"):
        try:
            return datetime.fromisoformat(committer["date"].replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now().astimezone()
