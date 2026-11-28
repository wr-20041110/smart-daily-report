"""生成报告（B 组）：03-技术调研报告、04-系统分析报告。运行：python tools/gen_reports_b.py"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reportkit import Report, T  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "docs" / "reports"


# --------------------------------------------------------------------------
# 03 技术调研报告
# --------------------------------------------------------------------------


def build_tech_survey() -> str:
    r = Report(str(OUT / "03-技术调研报告.docx"), "技术调研报告")
    r.h1("第1章 调研背景与范围")
    r.p("本项目需要访问 GitHub REST API 与飞书开放平台（任务/消息/考勤），存储日报历史，"
        "推送邮件与群消息，并以 pytest 保障质量。调研范围：HTTP 客户端、存储方案、开放平台接入、"
        "推送通道、测试与静态检查工具五类技术；结论与 design.md 的 ADR-001～004 一一对应。")

    r.h1("第2章 候选技术对比")
    r.h2("2.1 HTTP 客户端")
    r.table("HTTP 客户端对比", T("候选", "连接池", "重试语义", "同步/异步", "生态"),
            [T("httpx（选定）", "内建", "显式、可插拔", "双接口", "活跃，官方文档示例常用"),
             T("requests", "内建", "依赖 urllib3 内部参数", "同步为主", "最大"),
             T("urllib（标准库）", "无", "需手工封装", "同步", "零依赖")])
    r.h2("2.2 存储")
    r.table("存储方案对比", T("候选", "部署", "去重/幂等", "按日期查询", "并发写"),
            [T("SQLite（选定）", "零部署、单文件", "UNIQUE 约束天然支持", "SQL 直查", "单写者"),
             T("JSON 文件", "零部署", "需手写", "需手写", "需加锁"),
             T("MySQL/PostgreSQL", "需服务器", "支持", "支持", "支持")])
    r.h2("2.3 开放平台接入")
    r.table("开放平台对比", T("候选", "任务 API", "消息 API", "机器人推送", "考勤 API"),
            [T("飞书（选定）", "task/v2", "im/v1", "自定义机器人 webhook", "attendance/v1"),
             T("钉钉", "有", "有", "有", "有"),
             T("企业微信", "较弱", "有", "有", "有")])
    r.p("选定飞书：课程场景要求（任务流转与群消息）、团队日常工作在飞书；钉钉/企业微信作为备选记录于 ADR 备选项。")
    r.h2("2.4 推送通道")
    r.table("推送通道对比", T("候选", "成本", "鉴权", "触达"),
            [T("SMTP 邮件（选定）", "个人邮箱授权码", "用户名+授权码", "全员收件箱"),
             T("飞书自定义机器人（选定）", "零成本", "webhook URL", "团队群"),
             T("SendGrid/邮件服务商", "订阅费", "API Key", "高送达率")])
    r.h2("2.5 测试与静态检查")
    r.table("测试工具对比", T("候选", "定位"),
            [T("pytest（选定）", "fixture/monkeypatch 生态最全，课程示例统一"),
             T("unittest", "标准库，功能基础"),
             T("flake8/ruff（选定 ruff）", "ruff 速度快一个数量级且可自动修复，单工具覆盖 lint+format")])

    r.h1("第3章 关键技术验证（PoC 记录）")
    r.h3("3.1 PoC-1：httpx 连接池与超时")
    r.p("最小实验：httpx.Client 复用连接连续请求 20 次与逐次新建连接对比，验证连接池生效；"
        "设置 timeout=10 后对无响应端点抛出 ReadTimeout。结论：满足设计约束（≤20 请求/轮、超时可控）。")
    r.h3("3.2 PoC-2：SQLite 幂等写入")
    r.p("最小实验：INSERT OR IGNORE + UNIQUE(source, ref) 重复插入同事件，行数不增长；"
        "INSERT OR REPLACE 同日期重写团队日报。结论：幂等重跑可依赖数据库约束实现，无需应用层加锁。")
    r.h3("3.3 PoC-3：时区换算")
    r.p("最小实验：本地日 2026-11-24（Asia/Shanghai）换算 UTC 区间为 11-23T16:00Z～11-24T16:00Z，"
        "与 GitHub commits API since/until 实测一致；Windows 需 tzdata 包（已在依赖中按平台条件引入）。"
        "结论：UTC 存储 + 本地展示方案可行（SC12）。")
    r.h3("3.4 PoC-4：飞书机器人文本消息")
    r.p("最小实验：自定义机器人 webhook 发送 text 消息，验证响应 code=0 判定与超长截断策略"
        "（140KB 上限）。结论：Markdown 全文以纯文本发送可行，超长时截断并提示查看邮件/SQLite。")

    r.h1("第4章 选型结论")
    r.table("选型结论与 ADR 对应", T("决策", "ADR", "核心理由"),
            [T("httpx", "ADR-001", "连接池与超时原语直接满足 ≤20 请求约束；重试语义显式"),
             T("SQLite（sqlite3）", "ADR-002", "零部署；UNIQUE 约束天然支持去重与幂等"),
             T("凭证环境变量注入", "ADR-003", "课程红线：凭证禁入库；config.json 仅存非敏感配置"),
             T("重试 3 次+降级出报+凭证缺失 mock", "ADR-004", "单源故障不阻断全局；显式标注保证数据诚实"),
             T("pytest + ruff", "工程实践", "课程门禁要求；静态扫描清零")])
    r.p("完整 ADR（状态/背景/备选项/决策/理由）见 design.md 第 6 章，红队评审意见与回应见 docs/records/04-红队评审单.md。")

    r.h1("第5章 风险与约束")
    r.table("风险与约束", T("风险", "影响", "预案"),
            [T("飞书应用审核未通过", "任务/消息/考勤无真实数据", "mock 数据源先行，凭证就绪后切换（数据源可替换契约）"),
             T("GitHub API 限流", "采集失败", "只读 Token、请求计数守卫、指数退避"),
             T("平台账号映射不一致", "归属错挂", "config.json 维护三平台账号映射表，未映射账号单列"),
             T("Windows 时区库缺失", "ZoneInfo 报错", "tzdata 条件依赖 + 固定 +08:00 兜底"),
             T("凭证泄露", "安全红线", ".gitignore 排除 .env；日志脱敏；审计脚本定期 grep")])
    return r.save()


# --------------------------------------------------------------------------
# 04 系统分析报告
# --------------------------------------------------------------------------


def build_system_analysis() -> str:
    r = Report(str(OUT / "04-系统分析报告.docx"), "系统分析报告")
    r.h1("第1章 分析概述与技术目标")
    r.p("本报告完成系统级分析：四层架构与模块划分、对象与类建模、数据结构设计、接口约定与测试方案。"
        "技术目标：① 数据源可替换（同契约新增采集源）；② 归属规则可解释可追溯；③ 全流程可一键运行、"
        "可降级出报；④ 质量门禁（pytest 全绿、ruff 清零、核心逻辑覆盖率 ≥85%）。")

    r.h1("第2章 系统架构与模块划分")
    r.h2("2.1 四层结构")
    r.p("按课程要求构建“采集层 → 生成层 → 推送层 → 主编排入口”四层，外加共享基础层"
        "（模型/配置/存储/异常）。数据流：采集层产出 RawEvent → 生成层产出 DailyReportEntry 与 "
        "TeamReport → 存储层落库 → 推送层发送；任何一层失败不影响已完成环节（降级出报）。")
    r.fig("系统分层架构图", "design.md 第 1 章文字图；类图见 specs/uml/class.puml")
    r.h2("2.2 模块职责")
    r.table("模块职责（v1/v2 对照）", T("模块", "v1（类）", "v2（函数）", "职责"),
            [T("采集-GitHub", "GitHubCollector", "fetch_github", "当日提交归一化"),
             T("采集-飞书任务", "FeishuTaskCollector", "fetch_feishu_task", "任务流转+协作人"),
             T("采集-飞书消息", "FeishuMessageCollector", "fetch_feishu_message", "@提及+任务关联"),
             T("采集-考勤(v1.1)", "—", "fetch_feishu_attendance", "当日打卡记录"),
             T("生成-归属", "report_generator", "rules.py", "R1/R2/R3 规则管道"),
             T("生成-编排", "report_generator", "synthesize.py", "条目聚合+团队日报"),
             T("推送", "EmailPusher/FeishuBotPusher", "deliver_email/deliver_feishu", "邮件/机器人"),
             T("编排", "orchestrator", "pipeline.py", "四层串联+PipelineResult")])
    r.p("v2 与 v1 的架构差异（注册表+规则管道、纯函数核心、frozen 数据类）见 design.md 附录 A，"
        "两阶段对比分析见项目总结报告第 2 章。")

    r.h1("第3章 对象与类建模")
    r.fig("类图（v1）", "PlantUML 工具绘制，源文件 specs/uml/class.puml",
          png=str(OUT / "figures" / "class.png"))
    r.p("核心类：Member（成员与平台账号映射）、RawEvent（采集层统一事件格式）、DailyReportEntry"
        "（个人条目，携带 raw_refs 可追溯）、TeamReport（团队日报）、Settings（配置与凭证）、"
        "BaseCollector/BasePusher（契约基类，v1）、PipelineResult（全流程汇总）。")
    r.h2("3.1 关键序列")
    r.fig("主编排时序图", "PlantUML 工具绘制，源文件 specs/uml/sequence.puml",
          png=str(OUT / "figures" / "sequence.png"))
    r.p("主编排时序：配置管理员启动 CLI → Orchestrator 加载 Settings → 逐源 collect（凭证齐全走真实接口，"
        "否则 mock）→ 生成层聚合与归属 → 编排团队日报 → SQLite 落库（幂等）→ 逐通道推送 → "
        "输出 PipelineResult。生成/存储失败时退出码 1 且不推送。")

    r.h1("第4章 数据结构设计")
    r.fig("ER 图", "PlantUML 工具绘制，源文件 specs/uml/er.puml",
          png=str(OUT / "figures" / "er.png"))
    r.h2("4.1 SQLite 表结构")
    r.table("raw_events（原始事件）", T("字段", "类型", "说明"),
            [T("source/event_type/ref", "TEXT", "来源/类型/源内唯一引用"), T("author", "TEXT", "发起人平台账号"),
             T("occurred_at", "TEXT", "UTC ISO-8601"), T("title/url", "TEXT", "摘要与链接"),
             T("collaborators/payload", "TEXT", "JSON：协同人/附加信息"), T("UNIQUE(source, ref)", "约束", "去重与幂等")])
    r.table("daily_reports（个人日报条目）", T("字段", "说明"),
            [T("report_date/member_name/category", "日期/成员/分类（dev·collab·discuss）"),
             T("content", "条目文本（多行）"), T("raw_refs", "JSON：支撑条目的 source:ref 列表（可追溯）"),
             T("UNIQUE(report_date, member_name, category)", "同成员同分类同日一条（重跑覆盖）")])
    r.table("team_reports（团队日报）", T("字段", "说明"),
            [T("report_date", "日期（UNIQUE）"), T("content", "团队日报全文"),
             T("missing_sources", "JSON：降级缺失源"), T("generated_at", "生成时间")])
    r.p("完整建表 SQL 见 design.md 3.2；实现见 src/daily_report_v1/storage.py 与 src/daily_report_v2/store.py（两版独立编写）。")

    r.h1("第5章 接口约定")
    r.p("函数级契约完整定义于 design.md 第 4 章。核心契约摘要：")
    r.bullet("采集：collect(day) -> list[RawEvent]——UTC 区间换算、≤20 请求、重试 3 次退避、凭证缺失抛异常；")
    r.bullet("生成：generate_member_reports(events, members, day) -> list[DailyReportEntry]——去重兜底、"
             "分类规则（dev/collab/discuss）、未知账号不丢弃单列“未映射”；")
    r.bullet("编排：build_team_report(...) -> TeamReport——成员顺序排版、无记录成员标注、缺失源标注；")
    r.bullet("存储：init_db/save_raw_events/save_reports/load_team_report——全参数化、幂等；")
    r.bullet("推送：push(TeamReport) -> PushResult——凭证缺失 mock 留痕、失败不抛出、detail 脱敏；")
    r.bullet("编排：run_pipeline(day, settings) -> PipelineResult——各层状态与耗时汇总。")
    r.p("v2 以注册表（REGISTRY/PUSHER_REGISTRY）与纯函数实现同一契约（design.md 附录 A.2 模块映射表）。")

    r.h1("第6章 测试方案")
    r.p("测试策略：从验收标准导出（proposal SC1–SC12 → 测试用例），分四层：")
    r.table("测试方案", T("层级", "对象", "v1 用例数", "v2 用例数", "关键用例"),
            [T("单元-模型/配置/存储", "T2/T202-T203", "6", "9", "幂等去重、往返一致"),
             T("单元-采集", "T3-T5/T204-T206", "11", "11", "日期窗口、co-author 解析、重试守卫"),
             T("单元-生成/规则", "T6/T207-T208", "13", "14", "R1/R2/R3、SC4 正确率 12/12"),
             T("单元-推送/编排", "T7-T9/T209-T210", "10", "13", "脱敏、降级出报、幂等重跑"),
             T("集成/回归", "T10/T211+T214", "2", "4", "端到端计时 ≤10s、考勤行×3（变更单）")])
    r.p("实测结果：v1 共 46 用例全绿、总覆盖率 92%（生成层 94%）；v2 共 56 用例全绿、总覆盖率 93%"
        "（规则 100%、编排 91%）；ruff 静态扫描两版均 0 告警。逐条验收核对见 docs/records/13-验收核对记录.md。")
    return r.save()


if __name__ == "__main__":
    print(build_tech_survey())
    print(build_system_analysis())
