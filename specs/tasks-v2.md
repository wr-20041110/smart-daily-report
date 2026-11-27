# 智能日报生成器 · 任务清单 v2（tasks-v2.md）

| 项 | 内容 |
| --- | --- |
| 版本 | v2（阶段二 · Superpowers 工作流驱动） |
| 关联规范 | proposal.md、design.md（继承其 ADR 结论与接口契约，作为"设计经验"带入，**不复用 v1 代码**） |
| 方法论 | 本阶段起专一使用 Superpowers 工作流：writing-plans（本清单）→ executing-plans（逐任务执行）→ TDD（红→绿→重构）→ systematic-debugging（缺陷根因）→ code-review（合并前互评），不再混用其他方法 |
| 提交纪律 | 一次提交对应一个任务，message 格式 `feat|fix|test|docs: [任务编号] 一句话说明`；每次合并前执行 code-review 工作流 |
| 架构决策（与 v1 的差异） | v1 为"继承式分层类架构"（Collector/Pusher 基类 + 子类）；v2 重新设计为"注册表 + 规则管道"纯函数架构（见 design.md 附录 A"v2 架构补充"），代码全部从零编写 |

## 1. 初始任务清单（第 3 周）

### T201 项目结构与测试门禁
- **交付物**：src/daily_report_v2/ 目录、模块骨架、pytest/ruff/coverage 门禁配置复用
- **验收标准**：
  - `python -m daily_report_v2 --help` 可执行
  - ruff 静态扫描 0 告警（PEP 8 自查）
  - CI 门禁命令（pytest + ruff）本地跑通
- **依赖**：无
- **预估**：1h

### T202 领域模型与配置（红→绿）
- **交付物**：domain.py（frozen dataclasses）、settings.py + tests/v2/test_domain.py、test_settings.py
- **验收标准**：
  - 实体字段与 v1 契约一致（Member/RawEvent/DailyReportEntry/TeamReport 语义等价）
  - 测试先于实现：先写失败测试再实现（TDD 红绿循环记录见 docs/records/16-TDD红绿循环记录.md）
  - 模块语句覆盖率 ≥ 90%
- **依赖**：T201
- **预估**：2h

### T203 存储层（SQLite，红→绿）
- **交付物**：store.py + tests/v2/test_store.py
- **验收标准**：
  - 复用 ADR-002 结论：三表结构与唯一约束同 design.md 3.2；实现全新编写
  - 幂等建表、事件去重、按日期查询——各断言 ≥ 3 条
- **依赖**：T202
- **预估**：2h

### T204 GitHub 采集器（红→绿）
- **交付物**：fetch.py（github 部分）+ tests/v2/test_fetch_github.py
- **验收标准**：
  - 与 v1 相同的契约（日期窗口、作者过滤、co-author 解析、≤20 请求、退避重试），实现方式不同（注册表函数式）
  - 失败测试先行；mock 事件集同 proposal 约定（20 条含 4 协作）
- **依赖**：T202
- **预估**：3h

### T205 飞书任务采集器（红→绿）
- **交付物**：fetch.py（task 部分）+ tests/v2/test_fetch_feishu_task.py
- **验收标准**：同 T204 模式（15 条含 4 协作任务）
- **依赖**：T202
- **预估**：3h

### T206 飞书消息采集器（红→绿）
- **交付物**：fetch.py（message 部分）+ tests/v2/test_fetch_feishu_message.py
- **验收标准**：同 T204 模式（15 条含 4 @协作消息）
- **依赖**：T202
- **预估**：3h

### T207 归属规则引擎（红→绿，核心）
- **交付物**：rules.py（注册表 + 规则管道）+ tests/v2/test_rules.py
- **验收标准**：
  - R1/R2/R3 各 ≥ 3 条断言；12 条标注协作事件归属正确率 ≥ 95%（对应 SC4）
  - 规则以注册表注册，新增规则不改核心逻辑（开放封闭）
- **依赖**：T204、T205、T206
- **预估**：4h

### T208 日报编排（红→绿）
- **交付物**：synthesize.py + tests/v2/test_synthesize.py
- **验收标准**：
  - 条目聚合与团队日报排版与 proposal 成功标准 SC3/SC9 一致
  - Markdown 模板输出与 v1 格式对齐（两版对比基准）
- **依赖**：T207
- **预估**：2h

### T209 推送通道（红→绿）
- **交付物**：deliver.py（邮件 + 飞书）+ tests/v2/test_deliver.py
- **验收标准**：
  - 凭证缺失 mock 留痕、失败不抛出、日志脱敏（同 v1 契约）
  - 单测以 fake SMTP / fake HTTP 验证
- **依赖**：T208
- **预估**：2h

### T210 主编排管道与 CLI（红→绿）
- **交付物**：pipeline.py + cli.py + tests/v2/test_pipeline.py
- **验收标准**：
  - 采集→生成→存储→推送全链路；降级出报；幂等重跑
  - CLI 参数与 v1 对齐（--date/--mock/--no-push），便于两版对比演示
- **依赖**：T203、T204–T206、T209
- **预估**：2h

### T211 全功能回归与静态门禁
- **交付物**：tests/v2/test_regression.py、覆盖率报告、ruff 记录
- **验收标准**：
  - mock 全流程 ≤ 10s；全部成功标准 SC1–SC12 逐条核对通过
  - 生成/规则模块语句覆盖率 ≥ 85%
- **依赖**：T210
- **预估**：2h

## 2. 变更单新增任务（第 4 周 · 变更涟漪演练）

教师下发需求变更单：**新增飞书考勤数据采集模块**（对应教材 7.5 节 v1.1 场景）。
按 proposal → design → tasks → 代码 → 回归顺序自上而下同步修改；任何一处规范与代码未同步记为缺陷。

### T212 规范同步（proposal/design）
- **交付物**：proposal.md 范围新增 F12（考勤采集）、"不做什么 X3"移除并改注；design.md 新增考勤采集器契约与字段映射；本文件新增任务
- **验收标准**：规范与代码一一对应，双轨一致性检查通过（规范守护脚本输出 0 差异）
- **依赖**：T211
- **预估**：1h

### T213 考勤采集器（红→绿）
- **交付物**：fetch.py（attendance 部分，注册表项 `feishu_attendance`）+ tests/v2/test_fetch_attendance.py
- **验收标准**：
  - 采集当日打卡记录（上午/下午首末次），归入 `dev` 分类"考勤"子条目
  - mock 考勤事件集 6 条（3 成员 × 2 次打卡）
- **依赖**：T212
- **预估**：3h

### T214 生成层扩展 + 全量回归
- **交付物**：synthesize.py 考勤条目支持、回归测试全量执行记录
- **验收标准**：
  - 变更后全部既有测试不回归；考勤条目出现在每人日报头部
  - 回归报告归档（docs/records/09-变更涟漪演练记录.md）
- **依赖**：T213
- **预估**：2h

## 3. 依赖图与并行组

```
T201 → T202 → T203 ──────────────────────┐
        └→ {T204, T205, T206}（可并行）→ T207 → T208 → T209 ─┐
                                                              ├→ T210 → T211 → T212 → T213 → T214
                                                              └────────────┘
```

- **并行组**：{T204, T205, T206}（三个采集器无共享文件，可用子智能体并行执行）；其余串行
- **共享文件（pipeline.py / synthesize.py）相关任务一律串行**（executing-plans 纪律）

## 4. 工时汇总（阶段二，与 v1 对比基准）

| 任务 | 预估 | 实际（阶段二结束回填） |
| --- | --- | --- |
| T201 骨架与门禁 | 1h | |
| T202 领域模型 | 2h | |
| T203 存储层 | 2h | |
| T204–T206 三采集器 | 9h | |
| T207 规则引擎 | 4h | |
| T208 编排 | 2h | |
| T209 推送 | 2h | |
| T210 管道与 CLI | 2h | |
| T211 回归与门禁 | 2h | |
| T212–T214 变更涟漪 | 6h | |
| **合计** | **32h** | （v1 合计 24h，对比分析见项目总结报告第 2 章） |
