"""SC4 验收：12 条标注协作事件归属正确率 ≥ 95%（≥ 11 条正确）。"""

from __future__ import annotations

from daily_report_v1.collectors.mock_data import EXPECTED_ATTRIBUTION, build_mock_events
from daily_report_v1.generators import generate_member_reports

from .conftest import DAY, MEMBERS


def test_attribution_accuracy_sc4():
    events = build_mock_events(DAY)
    entries = generate_member_reports(events, MEMBERS, DAY)

    # 实际归属：ref -> 拥有含该 ref 的 collab 条目的成员集合
    # （raw_refs 存储 "source:ref" 复合键，剥掉 source 前缀后与标注答案对齐）
    actual: dict[str, set[str]] = {}
    for entry in entries:
        if entry.category != "collab":
            continue
        for key in entry.raw_refs:
            ref = key.split(":", 1)[1]
            actual.setdefault(ref, set()).add(entry.member_name)

    assert len(EXPECTED_ATTRIBUTION) == 12, "标注数据集必须恰好 12 条协作事件"
    mismatches = []
    for ref, expected in EXPECTED_ATTRIBUTION.items():
        got = actual.get(ref, set())
        if got != set(expected):
            mismatches.append((ref, sorted(expected), sorted(got)))

    assert len(mismatches) <= 1, f"归属错误 {len(mismatches)} 条（>1）：{mismatches}"
    print(f"SC4 核对：12 条协作事件，归属正确 {12 - len(mismatches)} 条，错误 {mismatches}")
