"""规范守护脚本（第 4 周自检工具）：检查"改了代码未改规范"。

检查点（对应课程附录 E 第 4 周思考题"规范守护 CI 应设在哪三个检查点"）：
  1. 采集源名称：代码注册表（v1 采集器 / v2 REGISTRY）必须出现在 proposal.md 与 design.md；
  2. 变更单关键词：feishu_attendance 在规范（proposal/design/tasks-v2）与代码/测试中同时存在；
  3. 红线检查：代码中不得出现硬编码凭证赋值（token/password/secret 常量赋值）。

用法：python tools/spec_guard.py [--fail]
退出码 0 = 一致；退出码 1 = 发现不一致（--fail 时失败，默认只报告）。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPECS = ROOT / "specs"
SRC = ROOT / "src"
TESTS = ROOT / "tests"

SOURCES_V1 = {"github", "feishu_task", "feishu_message", "feishu_attendance"}
SOURCES_V2 = set()  # 从 v2 注册表动态提取

_HARDCODE_RE = re.compile(
    r"(github_token|feishu_app_secret|smtp_password|tenant_access_token)\s*=\s*[\"'][^\"']+[\"']",
    re.I,
)


def collect_sources_v2() -> set[str]:
    for line in (SRC / "daily_report_v2" / "fetch.py").read_text(encoding="utf-8").splitlines():
        m = re.search(r'@register\("([\w_]+)"\)', line)
        if m and m.group(1) != "mock":
            SOURCES_V2.add(m.group(1))
    return SOURCES_V2


def check1() -> list[str]:
    """采集源名称在 proposal 与 design 中出现。"""
    proposal = (SPECS / "proposal.md").read_text(encoding="utf-8")
    design = (SPECS / "design.md").read_text(encoding="utf-8")
    problems = []
    for src in sorted(SOURCES_V1 | collect_sources_v2()):
        if src not in proposal:
            problems.append(f"proposal.md 未提及采集源 {src}")
        if src not in design:
            problems.append(f"design.md 未提及采集源 {src}")
    return problems


def check2() -> list[str]:
    """变更单关键词在规范与代码/测试中同步存在。"""
    keyword = "feishu_attendance"
    problems = []
    for f in ("proposal.md", "design.md", "tasks-v2.md"):
        text = (SPECS / f).read_text(encoding="utf-8")
        if keyword not in text:
            problems.append(f"{f} 缺少变更单关键词 {keyword}")
    code_hits = sum(
        keyword in p.read_text(encoding="utf-8", errors="ignore")
        for p in (SRC / "daily_report_v2").rglob("*.py")
    )
    test_hits = sum(
        keyword in p.read_text(encoding="utf-8", errors="ignore")
        for p in (TESTS / "v2").rglob("*.py")
    )
    if code_hits == 0:
        problems.append("src/daily_report_v2 无考勤实现（代码未同步）")
    if test_hits == 0:
        problems.append("tests/v2 无考勤测试（回归未同步）")
    return problems


def check3() -> list[str]:
    """红线：代码中无硬编码凭证。"""
    problems = []
    for path in SRC.rglob("*.py"):
        for i, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if _HARDCODE_RE.search(line) and "getenv" not in line:
                problems.append(f"{path.relative_to(ROOT)}:{i} 疑似硬编码凭证：{line.strip()[:60]}")
    return problems


def main(argv: list[str]) -> int:
    fail = "--fail" in argv
    all_problems = check1() + check2() + check3()
    print("规范守护自检（spec_guard）")
    for label, fn in (("1. 采集源与规范一致", check1), ("2. 变更单同步", check2), ("3. 凭证红线", check3)):
        problems = fn()
        status = "通过" if not problems else f"{len(problems)} 项不一致"
        print(f"  {label}: [{status}]")
        for p in problems:
            print(f"    - {p}")
    return 1 if (fail and all_problems) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
