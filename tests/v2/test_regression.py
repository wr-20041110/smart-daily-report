"""T211/T214 全功能回归（变更涟漪后）：成功标准 SC1/SC3/SC5/SC7 逐条核对。"""

from __future__ import annotations

from daily_report_v2.pipeline import run_pipeline
from daily_report_v2.store import load_team_report, open_db

from .conftest import DAY


def test_full_regression_sc_checks(settings):
    # SC1/SC7：一键跑通 + 计时（mock 全流程 ≤ 10s）
    result = run_pipeline(DAY, settings, push=False)
    assert result.elapsed_seconds < 10

    # SC3/SC5：覆盖 3 名成员、分类齐全、SQLite 可查历史
    conn = open_db(settings.db_path)
    md = load_team_report(conn, DAY)
    assert md is not None
    for name in ("王然", "咸哲", "王峻羽"):
        assert f"## {name}" in md
    for label in ("开发", "协作", "讨论"):
        assert f"### {label}" in md

    # 变更涟漪 F12：考勤行出现在每位成员日报（T214 验收）
    assert md.count("考勤｜") == 3

    # 可追溯：每条个人条目携带 raw_refs
    rows = conn.execute("SELECT raw_refs FROM daily_reports").fetchall()
    assert rows and all(r[0] != "[]" for r in rows)
    conn.close()
