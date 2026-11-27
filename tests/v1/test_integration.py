"""T10 集成测试：mock 全流程端到端（proposal.md 成功标准 SC1/SC3/SC5/SC7）。"""

from __future__ import annotations

from daily_report_v1.orchestrator import run_pipeline
from daily_report_v1.storage import init_db, load_team_report

from .conftest import DAY


def test_full_pipeline_sc1_sc3_sc5_sc7(settings):
    # SC1/SC7：一键跑通 + 计时（mock 全流程 ≤ 10s）
    result = run_pipeline(DAY, settings, push=False)
    assert result.elapsed_seconds < 10

    # SC3/SC5：日报覆盖 3 名成员、分类齐全、SQLite 可查历史
    conn = init_db(settings.db_path)
    md = load_team_report(conn, DAY)
    assert md is not None
    for name in ("王然", "咸哲", "王峻羽", "尹博弘"):
        assert f"## {name}" in md
    for label in ("开发", "协作", "讨论"):
        assert f"### {label}" in md
    # 每条个人条目可追溯（design.md 非功能约束-可追溯）
    rows = conn.execute("SELECT member_name, category, raw_refs FROM daily_reports").fetchall()
    assert rows and all(r[2] != "[]" for r in rows)
    conn.close()
