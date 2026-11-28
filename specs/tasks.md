# 智能日报生成器 · 任务清单（tasks.md）

| 项 | 内容 |
| --- | --- |
| 版本 | v1（阶段一 · SDD 规范驱动） |
| 关联规范 | proposal.md、design.md |
| 执行方式 | AI 按本清单逐任务生成实现，开发工程师逐条审查 diff 后提交；一次提交对应一个任务 |
| 执行顺序 | 见 2. 依赖图；T1→T2 串行，T3/T4/T5 可并行（无共享文件） |

## 1. 任务清单

### T1 项目结构与配置骨架
- **交付物**：仓库目录结构、pyproject.toml（或 requirements.txt）、.gitignore、.env.example、config.example.json
- **验收标准**：
  - `python -m daily_report_v1 --help` 可执行并输出帮助
  - ruff 静态扫描 0 告警；`import daily_report_v1` 无警告
  - .env.example 列出全部环境变量名且不含真实值；.gitignore 含 .env、*.db、__pycache__
- **依赖**：无
- **预估**：1h

### T2 共享基础层（models / config / storage / errors）
- **交付物**：models.py、config.py、storage.py、errors.py 及对应单元测试
- **验收标准**：
  - Member 字段齐全且 name 唯一校验；RawEvent 可用 dict 构造并序列化
  - Settings 从环境变量读取凭证、从 config.json 读取成员清单；凭证缺失不抛异常（返回 None）
  - init_db 幂等建表（连跑两次不报错）；save/load 往返一致；(source, ref) 重复写入被忽略
  - 单元测试全绿，storage 语句覆盖率 ≥ 90%
- **依赖**：T1
- **预估**：2h

### T3 GitHub 提交采集
- **交付物**：collectors/github.py + tests/test_github_collector.py
- **验收标准**：
  - 按 design.md 4.1 契约实现（日期区间 UTC 换算、请求计数 ≤ 20、3 次退避重试、凭证缺失抛 CredentialsMissingError）
  - 单测覆盖：日期过滤（含边界 00:00/24:00）、作者过滤、co-author 解析、限流重试（monkeypatch 模拟 2 次失败后成功）
  - mock 模式返回内置 GitHub 事件集（≥ 20 条，含 4 条 Co-authored-by 协作提交）
- **依赖**：T2
- **预估**：3h

### T4 飞书任务采集
- **交付物**：collectors/feishu.py（任务部分）+ tests/test_feishu_task_collector.py
- **验收标准**：
  - 按 4.1 契约实现；任务字段映射：经办人→author、协作人→collaborators、状态变更→payload
  - 单测覆盖：协作人解析（多协作人、空协作人）、日期过滤、重试降级
  - mock 模式返回内置任务事件集（≥ 15 条，含 4 条协作任务）
- **依赖**：T2
- **预估**：3h

### T5 飞书消息采集
- **交付物**：collectors/feishu.py（消息部分）+ tests/test_feishu_message_collector.py
- **验收标准**：
  - 按 4.1 契约实现；@提及解析（多人 @、无 @）、任务关联识别（payload.task_id）
  - 单测覆盖：@解析、日期过滤、重试降级
  - mock 模式返回内置消息事件集（≥ 15 条，含 4 条 @协作消息）
- **依赖**：T2
- **预估**：3h

### T6 日报生成与协同归属（核心）
- **交付物**：generators/report_generator.py + tests/test_generator.py + tests/test_attribution.py
- **验收标准**：
  - generate_member_reports / build_team_report 严格满足 design.md 4.2 契约
  - 三条归属规则 R1/R2/R3 各至少 3 条断言用例
  - **归属正确率验收**：对 mock 标准数据集 12 条标注协作事件，正确归属 ≥ 11 条（对应 SC4）
  - 边界：无事件成员进入 members_without_events；未知账号事件进"未映射"条目；同一 (source,ref) 去重
  - 生成层语句覆盖率 ≥ 85%（对应 G7）
- **依赖**：T2、T3、T4、T5（依赖其 mock 数据集）
- **预估**：4h

### T7 邮件推送
- **交付物**：pushers/email_pusher.py + tests/test_email_pusher.py
- **验收标准**：
  - 按 4.4 契约实现；SMTP 凭证缺失返回 PushResult(ok=True, mocked=True)
  - 邮件正文与团队日报一致；日志脱敏（授权码不出现）
  - 单测以 fake SMTP（monkeypatch smtplib.SMTP）验证调用参数与正文
- **依赖**：T2、T6
- **预估**：2h

### T8 飞书机器人推送
- **交付物**：pushers/feishu_pusher.py + tests/test_feishu_pusher.py
- **验收标准**：
  - 按 4.4 契约实现；凭证缺失 mock 留痕
  - 消息体 ≤ 飞书限制（文本消息 150KB），Markdown 文本转飞书文本消息
  - 单测以 fake HTTP（monkeypatch）验证请求体与鉴权头
- **依赖**：T2、T6
- **预估**：2h

### T9 主编排入口
- **交付物**：orchestrator.py + __main__.py + tests/test_orchestrator.py
- **验收标准**：
  - CLI 参数 --date / --mock / --no-push 行为符合 design.md 4.5
  - 采集→生成→存储→推送全链路串联；PipelineResult 汇总各层状态与耗时
  - 任一源失败 → 降级出报（missing_sources 标注）；生成层失败 → 退出码 1 且不推送
  - 运行两次同日期 → 第二次幂等（事件不重复入库、日报覆盖更新）
- **依赖**：T3–T8
- **预估**：2h

### T10 集成测试与验收核对
- **交付物**：tests/test_integration.py、验收核对记录（docs/records/13-验收核对记录.md）
- **验收标准**：
  - mock 模式全流程端到端测试：断言日报含 4 名成员、分类齐全、SQLite 可查历史、推送留痕
  - 计时断言全流程 ≤ 10 秒（SC7）
  - 逐条核对 proposal.md 成功标准 SC1–SC12，形成核对表（通过/未通过/证据）
  - 覆盖率报告：生成层 ≥ 85%（G7）
- **依赖**：T9
- **预估**：2h

## 2. 依赖图（执行顺序）

```
T1 ──→ T2 ──┬──→ T3 ──┐
             ├──→ T4 ──┼──→ T6 ──┬──→ T7 ──┐
             └──→ T5 ──┘          ├──→ T8 ──┼──→ T9 ──→ T10
                                  └─────────┘
```

- **串行**：T1→T2（基础层先行）；T3/T4/T5 完成后才能 T6（生成层依赖三源数据集）
- **并行组**：{T3, T4, T5}（三个采集模块无共享文件）；{T7, T8}（两个推送通道无共享文件）
- **关键路径**：T1→T2→T4→T6→T9→T10 ≈ 14h

## 3. 工时汇总

| 任务 | 预估 | 实际（人时） |
| --- | --- | --- |
| T1 项目结构 | 1h | 1.5h |
| T2 共享基础层 | 2h | 2.5h |
| T3 GitHub 采集 | 3h | 4h |
| T4 飞书任务采集 | 3h | 4h |
| T5 飞书消息采集 | 3h | 3.5h |
| T6 日报生成与归属 | 4h | 5h |
| T7 邮件推送 | 2h | 2.5h |
| T8 飞书推送 | 2h | 2.5h |
| T9 主编排 | 2h | 2.5h |
| T10 集成测试 | 2h | 2h |
| **合计** | **24h** | **30h** |
