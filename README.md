# 智能日报生成器（Smart Daily Report Generator）

软件工程职业技能实践课程设计项目。让日报从成员的真实工作数据中"自动长出来"：
GitHub 提交、飞书任务流转、群消息三源采集 → 个人日报生成与**协同成果自动归属** →
团队日报编排 → 邮件 + 飞书机器人推送 → SQLite 历史留存。

按课程要求，同一项目用两种方法论完整实现两遍：

| 版本 | 目录 | 方法论 | 阶段 | Tag |
| --- | --- | --- | --- | --- |
| v1-SDD | `src/daily_report_v1/` | SDD 六阶段工作流（阶段一 11.2–11.15）（proposal → design → 接口契约 → tasks → 代码生成 → 验证） | 第 1–2 周 | `v1-sdd` |
| v2-Superpowers | `src/daily_report_v2/` | Superpowers 工作流（阶段二 11.16–11.26）（writing-plans / executing-plans / TDD / systematic-debugging / code-review） | 第 3–4 周 | `v2-superpowers` |

## 项目成员与角色轮换

成员：王然、咸哲、王峻羽、尹博弘（4 人组：其中 1 人兼任测试工程师与配置管理员两个角色，兼任组合随周轮换）

| 周次 | 王然 | 咸哲 | 王峻羽 | 尹博弘 |
| --- | --- | --- | --- | --- |
| 第 1 周 11.2–11.6（侧重需求） | 需求分析师 | 架构师 | 开发工程师 | 测试&配置管理员（兼任） |
| 第 2 周 11.9–11.13（侧重架构/开发） | 测试&配置管理员（兼任） | 开发工程师 | 需求分析师 | 架构师 |
| 第 3 周 11.16–11.20（侧重开发/测试） | 架构师 | 需求分析师 | 测试&配置管理员（兼任） | 开发工程师 |
| 第 4 周 11.23–11.26（全员交付） | 开发工程师 | 测试&配置管理员（兼任） | 架构师 | 需求分析师 |

四周结束后每人至少担任过两个角色（本表每人 4 个）；轮换记录见 `docs/records/06-角色轮换记录.md`。

## 快速开始

```bash
# 1. 安装依赖（uv 首选；无 uv 时 pip 兜底）
uv sync                        # 或：pip install -r requirements.txt

# 2. 配置
cp config.example.json config.json   # 填写成员清单（非敏感，可入库）
cp .env.example .env                  # 填写凭证（红线：.env 严禁入库）

# 3. 一键运行（无凭证时自动进入 mock 模式，主流程照常可跑）
uv run python -m daily_report_v1 --date 2026-11-26
#   或：PYTHONPATH=src python -m daily_report_v1 --date 2026-11-26
#   参数：--mock 强制模拟数据；--no-push 跳过推送；--date 指定日期（默认今天）

# 4. 测试与静态扫描（CI 门禁同款命令）
uv run pytest -q
uv run ruff check src tests
uv run coverage run --source=src -m pytest -q && uv run coverage report
```

日报历史留存于 `data/reports.db`（SQLite）：`raw_events` 原始事件（可追溯）、
`daily_reports` 个人日报条目、`team_reports` 团队日报全文。

## 目录结构

```
specs/               三份核心规范 + UML 附件（"人类的领地"，规范与代码同库管理）
  proposal.md        目标/背景/范围/成功标准/术语（阶段一基线；第 4 周变更单后同步更新）
  design.md          四层架构/模块职责/数据模型/接口契约/4 份 ADR/非功能约束
  tasks.md           v1 任务清单（T1–T10，含依赖图与工时）
  tasks-v2.md        v2 任务清单（Superpowers 阶段，含变更单新增任务）
  uml/               PlantUML 工具绘制：用例图/泳道图/类图/ER 图/时序图
src/daily_report_v1/ v1-SDD：分层类架构（collectors/generators/pushers/orchestrator）
src/daily_report_v2/ v2-Superpowers：注册表 + 规则管道架构（从零重写，不复用 v1 代码）
tests/v1/  tests/v2/  pytest 测试（v2 为 TDD 红→绿→重构产出）
docs/reports/        6 份 Word 报告（业务调研/需求分析/技术调研/系统分析/系统设计/项目总结）
docs/records/        过程留痕：需求澄清问答、隐含需求清单、红队评审单、技能拆解笔记、
                     角色轮换、AI 使用日志、站会记录、变更涟漪演练、规范审计、答辩追问清单
config.example.json  成员清单与仓库配置模板（复制为 config.json 使用）
.env.example         凭证环境变量模板（凭证一律环境变量注入，严禁入库）
```

## 三条铁律（课程要求）

1. **规格先行**：先写规范（specs/）再生成代码；代码与规范冲突时改代码或走规范变更流程。
2. **小步提交**：一次提交对应一个可验证交付物；v2 提交 message 格式 `feat|fix|test|docs: [任务编号] 一句话说明`。
3. **证据留痕**：AI 使用、评审、决策全程记录于 `docs/records/`，每周日归档。

## 注意事项

- 凭证（GitHub Token / 飞书应用凭证 / SMTP 授权码）**只允许**经环境变量注入，出现硬编码按红线处理。
- 飞书应用审核未通过不必阻塞：mock 数据源保证主流程可跑，凭证就绪后切换真实接口（接口契约已按"数据源可替换"设计）。
- 本仓库由配置管理员负责初始化与分支规范；每位成员提交前请设置自己的 git 身份（`git config user.name/user.email`），提交记录将作为个人贡献系数依据。
