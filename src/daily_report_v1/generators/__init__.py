"""生成层：个人日报生成、协同归属、团队日报编排（design.md 4.2 / 5）。"""

from .report_generator import build_team_report, generate_member_reports

__all__ = ["generate_member_reports", "build_team_report"]
