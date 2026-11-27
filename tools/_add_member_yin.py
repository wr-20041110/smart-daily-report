"""一次性脚本：团队扩至 4 人（新增尹博弘），重写 v1/v2 mock 数据集与 config。"""

import io
import json
import re

YIN = {
    "name": "尹博弘",
    "github_username": "Yin-bo-hong",
    "feishu_open_id": "ou_【替换为真实飞书 open_id】",
    "email": "20233159@stu.ccut.edu.cn",
}

# ============ v1 mock_data.py ============
f = "src/daily_report_v1/collectors/mock_data.py"
src = io.open(f, encoding="utf-8").read()
src = src.replace(
    "内置标准数据集（场景 standard）：3 名成员 × 3 数据源共 50 条事件，",
    "内置标准数据集（场景 standard）：4 名成员 × 3 数据源共 50 条事件，",
)
src = src.replace(
    "  王峻羽 github=wjy-jjj    feishu=ou_wjy-jjj",
    "  王峻羽 github=wjy-jjj    feishu=ou_wjy-jjj\n  尹博弘 github=Yin-bo-hong feishu=ou_yinbohong",
)

commits = '''_COMMITS: list[tuple[str, str, list[str], int]] = [
    ("wr-20041110", "修复日报生成模块归属去重问题", [], 4),
    ("wr-20041110", "新增飞书任务采集器重试逻辑", ["xz0622"], 6),  # 协作#1
    ("wr-20041110", "更新团队成员配置清单", [], 2),
    ("wr-20041110", "整理 README 与快速开始文档", [], 1),
    ("wr-20041110", "为存储层补充幂等重跑测试", ["wjy-jjj"], 3),  # 协作#2
    ("wr-20041110", "优化协同归属规则 R3 的解析", [], 5),
    ("wr-20041110", "修正时区换算边界用例", [], 2),
    ("wr-20041110", "重构推送层日志脱敏", [], 4),
    ("xz0622", "完成 design.md 接口契约评审", [], 2),
    ("xz0622", "新增 httpx 连接池配置", [], 3),
    ("xz0622", "实现 GitHub 采集日期窗口", [], 5),
    ("xz0622", "修复 mock 数据集时区问题", ["wr-20041110"], 2),  # 协作#3
    ("Yin-bo-hong", "补充 ER 图与表结构说明", [], 1),
    ("xz0622", "调整重试退避策略为 1s/2s/4s", [], 2),
    ("Yin-bo-hong", "为飞书任务采集增加字段映射测试", [], 3),
    ("wjy-jjj", "搭建 pytest 与 coverage 门禁", [], 4),
    ("wjy-jjj", "实现团队日报 Markdown 模板", ["xz0622"], 6),  # 协作#4
    ("Yin-bo-hong", "修复成员映射未知账号处理", [], 2),
    ("Yin-bo-hong", "增加主流程幂等性检查", [], 3),
    ("Yin-bo-hong", "提交验收核对记录初稿", [], 1),
]'''
src = re.sub(r"_COMMITS: list\[tuple\[str, str, list\[str\], int\]\] = \[.*?\n\]", commits, src, count=1, flags=re.S)

tasks = '''_TASKS: list[tuple[str, str, list[str], str]] = [
    ("ou_wr-20041110", "评审 proposal.md 范围条目", [], "done"),
    ("ou_wr-20041110", "编写需求澄清问答记录", ["ou_xz0622"], "done"),  # 协作#5
    ("ou_wr-20041110", "核对成功标准可度量性", [], "done"),
    ("ou_wr-20041110", "整理隐含需求清单", [], "done"),
    ("ou_xz0622", "绘制用例图与泳道图", [], "done"),
    ("ou_xz0622", "撰写 ADR-001/002 初稿", [], "done"),
    ("ou_xz0622", "红队评审 design.md", ["ou_wr-20041110"], "done"),  # 协作#6
    ("ou_xz0622", "梳理非功能约束清单", [], "done"),
    ("ou_wjy-jjj", "搭建仓库目录与 git 规范", [], "done"),
    ("ou_wjy-jjj", "配置 ruff 静态扫描", [], "done"),
    ("ou_wjy-jjj", "实现存储层 init_db", [], "done"),
    ("ou_wjy-jjj", "编写集成测试骨架", ["ou_yinbohong"], "doing"),  # 协作#7
    ("ou_yinbohong", "设计 SQLite 表结构", ["ou_wjy-jjj"], "done"),  # 协作#8
    ("ou_yinbohong", "归档组内 AI 使用日志", [], "done"),
    ("ou_yinbohong", "准备阶段评审会演示脚本", [], "doing"),
]'''
src = re.sub(r"_TASKS: list\[tuple\[str, str, list\[str\], str\]\] = \[.*?\n\]", tasks, src, count=1, flags=re.S)

messages = '''_MESSAGES: list[tuple[str, str, list[str], str | None]] = [
    ("ou_wr-20041110", "晨会同步：今天先过 proposal 范围", [], None),
    ("ou_wr-20041110", "@咸哲 T-101 的接口契约帮我看看", ["ou_xz0622"], "T-101"),  # 协作#9
    ("ou_wr-20041110", "调研结论已更新到文档", [], None),
    ("ou_wr-20041110", "mock 数据集还要补 2 条协作事件", [], None),
    ("ou_xz0622", "用例图初版已提交", [], None),
    ("ou_xz0622", "红队评审问题清单发群里了", [], None),
    ("ou_xz0622", "@王然 design.md 3.2 表结构已改好", ["ou_wr-20041110"], "T-102"),  # 协作#10
    ("ou_xz0622", "晚上 7 点过一遍演示", [], None),
    ("ou_wjy-jjj", "数据库幂等测试通过", [], None),
    ("ou_wjy-jjj", "@咸哲 T-105 时区用例过了吗", ["ou_xz0622"], "T-105"),  # 协作#11
    ("ou_wjy-jjj", "tag 和提交规范已整理", [], None),
    ("ou_wjy-jjj", "CI 门禁跑通了", [], None),
    ("ou_yinbohong", "飞书凭证审核还在等", [], None),
    ("ou_yinbohong", "@王峻羽 T-107 回归用例一起看", ["ou_wjy-jjj"], "T-107"),  # 协作#12
    ("ou_yinbohong", "明天评审会材料我来整理", [], None),
]'''
src = re.sub(r"_MESSAGES: list\[tuple\[str, str, list\[str\], str \| None\]\] = \[.*?\n\]", messages, src, count=1, flags=re.S)

expected = '''EXPECTED_ATTRIBUTION: dict[str, list[str]] = {
    "mock-gh-002": ["王然", "咸哲"],
    "mock-gh-005": ["王然", "王峻羽"],
    "mock-gh-012": ["咸哲", "王然"],
    "mock-gh-017": ["王峻羽", "咸哲"],
    "mock-ft-002": ["王然", "咸哲"],
    "mock-ft-007": ["咸哲", "王然"],
    "mock-ft-012": ["王峻羽", "尹博弘"],
    "mock-ft-013": ["尹博弘", "王峻羽"],
    "mock-fm-002": ["王然", "咸哲"],
    "mock-fm-007": ["咸哲", "王然"],
    "mock-fm-010": ["王峻羽", "咸哲"],
    "mock-fm-014": ["尹博弘", "王峻羽"],
}'''
src = re.sub(r"EXPECTED_ATTRIBUTION: dict\[str, list\[str\]\] = \{.*?\n\}", expected, src, count=1, flags=re.S)
io.open(f, "w", encoding="utf-8", newline="\n").write(src)
print("v1 mock_data.py updated")

# ============ v2 fetch.py ============
f = "src/daily_report_v2/fetch.py"
src = io.open(f, encoding="utf-8").read()

gh = '''_GH_COMMITS: list[tuple[str, str, list[str], int]] = [
    ("wr-20041110", "编写 T201 任务骨架与门禁脚本", [], 3),
    ("wr-20041110", "为规则引擎添加 R1 失败测试", ["xz0622"], 2),  # 协作 v2#1
    ("wr-20041110", "整理红绿循环记录模板", [], 1),
    ("wr-20041110", "修复 store 幂等重跑断言", [], 2),
    ("wr-20041110", "registry 注册考勤采集器", ["wjy-jjj"], 4),  # 协作 v2#2
    ("wr-20041110", "重构 fetch 重试装饰器", [], 3),
    ("wr-20041110", "补充 code-review 检查清单", [], 1),
    ("wr-20041110", "清理 pytest 临时目录", [], 2),
    ("xz0622", "编写 T204 GitHub 采集失败测试", [], 4),
    ("xz0622", "实现 synthesize 条目聚合", [], 5),
    ("xz0622", "为 deliver 添加脱敏断言", [], 2),
    ("xz0622", "修复时区边界回归用例", ["wr-20041110"], 2),  # 协作 v2#3
    ("Yin-bo-hong", "梳理 systematic-debugging 根因记录", [], 1),
    ("xz0622", "重构 pipeline 为函数组合", [], 4),
    ("Yin-bo-hong", "归档第 3 周站会记录", [], 1),
    ("wjy-jjj", "搭建 v2 目录与测试门禁", [], 3),
    ("wjy-jjj", "编写 T207 归属正确率测试", ["xz0622"], 3),  # 协作 v2#4
    ("Yin-bo-hong", "修复飞书消息 @ 解析", [], 2),
    ("Yin-bo-hong", "为 pipeline 添加降级出报断言", [], 2),
    ("Yin-bo-hong", "提交 T211 回归记录初稿", [], 1),
]'''
src = re.sub(r"_GH_COMMITS: list\[tuple\[str, str, list\[str\], int\]\] = \[.*?\n\]", gh, src, count=1, flags=re.S)

fs_tasks = '''_FS_TASKS: list[tuple[str, str, list[str], str]] = [
    ("ou_wr-20041110", "review tasks-v2.md 任务粒度", [], "done"),
    ("ou_wr-20041110", "编写 TDD 红绿循环记录", ["ou_xz0622"], "done"),  # 协作 v2#5
    ("ou_wr-20041110", "核对 SC4 标注数据集", [], "done"),
    ("ou_wr-20041110", "整理隐含需求清单 v2", [], "done"),
    ("ou_xz0622", "绘制 v2 架构图", [], "done"),
    ("ou_xz0622", "code-review 互评 T204 提交", [], "done"),
    ("ou_xz0622", "red-team 评审 rules.py", ["ou_wr-20041110"], "done"),  # 协作 v2#6
    ("ou_xz0622", "梳理变更单影响面", [], "done"),
    ("ou_wjy-jjj", "搭建 ruff 静态门禁", [], "done"),
    ("ou_wjy-jjj", "配置 coverage 阈值", [], "done"),
    ("ou_wjy-jjj", "实现 store 三表结构", [], "done"),
    ("ou_wjy-jjj", "编写回归测试骨架", ["ou_yinbohong"], "doing"),  # 协作 v2#7
    ("ou_yinbohong", "设计考勤字段映射", ["ou_wjy-jjj"], "done"),  # 协作 v2#8
    ("ou_yinbohong", "归档 AI 使用日志", [], "done"),
    ("ou_yinbohong", "准备 v2 演示脚本", [], "doing"),
]'''
src = re.sub(r"_FS_TASKS: list\[tuple\[str, str, list\[str\], str\]\] = \[.*?\n\]", fs_tasks, src, count=1, flags=re.S)

fs_messages = '''_FS_MESSAGES: list[tuple[str, str, list[str], str | None]] = [
    ("ou_wr-20041110", "晨会：今天按 executing-plans 逐任务推进", [], None),
    ("ou_wr-20041110", "@咸哲 T-201 骨架帮我评审", ["ou_xz0622"], "T-201"),  # 协作 v2#9
    ("ou_wr-20041110", "红绿循环记录已更新", [], None),
    ("ou_wr-20041110", "规则引擎还有 2 条用例要补", [], None),
    ("ou_xz0622", "T204 失败测试已提交", [], None),
    ("ou_xz0622", "systematic-debugging 记录模板放群文件了", [], None),
    ("ou_xz0622", "@王然 rules.py 评审意见 3 条", ["ou_wr-20041110"], "T-207"),  # 协作 v2#10
    ("ou_xz0622", "晚上 7 点半过一遍演示", [], None),
    ("ou_wjy-jjj", "store 幂等测试通过", [], None),
    ("ou_wjy-jjj", "@咸哲 T-209 脱敏断言过了吗", ["ou_xz0622"], "T-209"),  # 协作 v2#11
    ("ou_wjy-jjj", "ruff 0 告警了", [], None),
    ("ou_wjy-jjj", "CI 门禁跑通", [], None),
    ("ou_yinbohong", "考勤变更单影响面已梳理", [], None),
    ("ou_yinbohong", "@王峻羽 T-213 回归一起看", ["ou_wjy-jjj"], "T-213"),  # 协作 v2#12
    ("ou_yinbohong", "变更涟漪回归我来牵头", [], None),
]'''
src = re.sub(r"_FS_MESSAGES: list\[tuple\[str, str, list\[str\], str \| None\]\] = \[.*?\n\]", fs_messages, src, count=1, flags=re.S)

attendance = '''_ATTENDANCE: list[tuple[str, str, str]] = [
    ("ou_wr-20041110", "09:02", "am_in"),
    ("ou_wr-20041110", "18:05", "pm_out"),
    ("ou_xz0622", "08:58", "am_in"),
    ("ou_xz0622", "17:59", "pm_out"),
    ("ou_wjy-jjj", "09:10", "am_in"),
    ("ou_wjy-jjj", "18:12", "pm_out"),
    ("ou_yinbohong", "09:15", "am_in"),
    ("ou_yinbohong", "18:20", "pm_out"),
]'''
src = re.sub(r"_ATTENDANCE: list\[tuple\[str, str, str\]\] = \[.*?\n\]", attendance, src, count=1, flags=re.S)

expected2 = '''EXPECTED_ATTRIBUTION_V2: dict[str, list[str]] = {
    "v2-gh-002": ["王然", "咸哲"],
    "v2-gh-005": ["王然", "王峻羽"],
    "v2-gh-012": ["咸哲", "王然"],
    "v2-gh-017": ["王峻羽", "咸哲"],
    "v2-ft-002": ["王然", "咸哲"],
    "v2-ft-007": ["咸哲", "王然"],
    "v2-ft-012": ["王峻羽", "尹博弘"],
    "v2-ft-013": ["尹博弘", "王峻羽"],
    "v2-fm-002": ["王然", "咸哲"],
    "v2-fm-007": ["咸哲", "王然"],
    "v2-fm-010": ["王峻羽", "咸哲"],
    "v2-fm-014": ["尹博弘", "王峻羽"],
}'''
src = re.sub(r"EXPECTED_ATTRIBUTION_V2: dict\[str, list\[str\]\] = \{.*?\n\}", expected2, src, count=1, flags=re.S)
io.open(f, "w", encoding="utf-8", newline="\n").write(src)
print("v2 fetch.py updated")

# ============ config 增加尹博弘 ============
for cf in ("config.json", "config.example.json"):
    cfg = json.load(io.open(cf, encoding="utf-8"))
    if not any(m["name"] == "尹博弘" for m in cfg["members"]):
        cfg["members"].append(YIN)
    io.open(cf, "w", encoding="utf-8", newline="\n").write(
        json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
print("config.json / config.example.json 已增加尹博弘")
