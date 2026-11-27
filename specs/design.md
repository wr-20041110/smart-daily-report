# 智能日报生成器 · 架构设计（design.md）

| 项 | 内容 |
| --- | --- |
| 版本 | v1（阶段一 · SDD 规范驱动） |
| 关联文档 | proposal.md（范围与成功标准）、tasks.md（任务拆解）、UML 附件（specs/uml/） |
| UML 附件 | usecase.puml、swimlane.puml、class.puml、er.puml、sequence.puml |

## 1. 系统架构

按课程要求构建"采集层 → 生成层 → 推送层 → 主编排入口"四层结构，外加共享基础层：

```
┌─────────────────────────────────────────────────────────┐
│  主编排入口 orchestrator.py（CLI：--date --mock --no-push）│
├──────────────┬──────────────┬────────────────────────────┤
│   采集层      │    生成层      │          推送层             │
│ collectors/  │ generators/   │         pushers/           │
│ ┌──────────┐ │ ┌──────────┐ │  ┌─────────────────────┐  │
│ │ GitHub   │ │ │ 个人日报  │ │  │ email_pusher (SMTP) │  │
│ │ 提交采集  │─┤ │ 生成+    │─┤  ├─────────────────────┤  │
│ ├──────────┤ │ │ 协同归属  │ │  │ feishu_pusher(机器人)│  │
│ │ 飞书任务  │ │ ├──────────┤ │  └─────────────────────┘  │
│ │ 采集      │─┤ │ 团队日报  │ │                            │
│ ├──────────┤ │ │ 编排      │ │                            │
│ │ 飞书消息  │ │ └──────────┘ │                            │
│ │ 采集      │─┤              │                            │
│ └──────────┘ │              │                            │
├──────────────┴──────────────┴────────────────────────────┤
│  共享基础层：models.py（数据模型）/ config.py（配置与凭证）  │
│             storage.py（SQLite 存储）/ errors.py（异常体系）│
└─────────────────────────────────────────────────────────┘
```

数据流：采集层产出 `RawEvent` 列表 → 生成层产出 `DailyReportEntry` 列表与 `TeamReport` → 存储层落库（可追溯）→ 推送层发送。任何一层失败不影响已完成的环节（降级出报）。

## 2. 模块职责

| 模块 | 文件 | 职责边界（一句话） |
| --- | --- | --- |
| 共享-数据模型 | src/daily_report_v1/models.py | 定义 Member / RawEvent / DailyReportEntry / TeamReport 等数据结构，不含业务逻辑 |
| 共享-配置 | src/daily_report_v1/config.py | 读取环境变量（凭证）与 config.json（成员清单），提供统一 Settings 对象 |
| 共享-存储 | src/daily_report_v1/storage.py | SQLite 建表、原始事件与日报历史写入、按日期查询 |
| 共享-异常 | src/daily_report_v1/errors.py | 定义采集、生成、推送、存储四类异常 |
| 采集-GitHub | collectors/github.py | 调 GitHub API 拉取当日提交并归一化为 RawEvent，含请求计数与退避重试 |
| 采集-飞书任务 | collectors/feishu.py（任务部分） | 调飞书开放平台拉取任务流转记录，含协作人字段 |
| 采集-飞书消息 | collectors/feishu.py（消息部分） | 拉取团队群当日消息，解析 @提及 |
| 采集-Mock | collectors/mock_data.py | 内置 3 名成员 × 3 数据源的模拟事件集（含 12 条标注协作事件，供归属正确率验收） |
| 生成 | generators/report_generator.py | 事件→个人条目聚合、协同归属规则、团队日报编排与模板排版 |
| 推送-邮件 | pushers/email_pusher.py | SMTP 发送团队日报（凭证缺失时 mock 留痕） |
| 推送-飞书 | pushers/feishu_pusher.py | 飞书机器人发送团队日报（凭证缺失时 mock 留痕） |
| 编排 | orchestrator.py | CLI 入口，串联四层，汇总 PipelineResult（各层状态、耗时、异常） |

## 3. 数据模型

### 3.1 实体

**Member（成员）**

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| name | str | 非空、团队内唯一 |
| github_username | str | 非空、映射 GitHub 提交作者 |
| feishu_open_id | str | 非空、映射飞书用户 |
| email | str | 非空、日报推送地址 |

**RawEvent（原始事件，采集层统一格式）**

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| source | str | `github` / `feishu_task` / `feishu_message` / `feishu_attendance`（v1.1 预留） |
| event_type | str | 源内事件类型（commit / task / message / …） |
| ref | str | 源内唯一引用（commit SHA / task GUID / message ID），同一 (source, ref) 去重 |
| author | str | 事件发起人（平台账号） |
| occurred_at | datetime | UTC 存储，展示转本地 |
| title | str | 一句话摘要 |
| url | str | 源内可追溯链接 |
| collaborators | list[str] | 协同人平台账号列表（可为空） |
| payload | dict | 源特有附加信息（文件数、状态变更、@提及人等） |

**DailyReportEntry（个人日报条目）**

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| date | date | 日报日期 |
| member_name | str | 归属成员 |
| category | str | `dev`（开发）/ `collab`（协作）/ `discuss`（讨论） |
| items | list[str] | 该分类下的可读条目（每条一行） |
| raw_refs | list[str] | 支撑条目的 (source, ref) 列表，可追溯 |

**TeamReport（团队日报）**

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| date | date | 日报日期 |
| entries | list[DailyReportEntry] | 全员条目（按成员、分类有序） |
| members_without_events | list[str] | 当日无记录成员（SC9） |
| missing_sources | list[str] | 降级的数据源（SC2/G6） |
| generated_at | datetime | 生成时间 |

### 3.2 SQLite 表结构（ER 图见 specs/uml/er.puml）

```sql
CREATE TABLE IF NOT EXISTS raw_events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source        TEXT NOT NULL,            -- github / feishu_task / feishu_message
    event_type    TEXT NOT NULL,
    ref           TEXT NOT NULL,
    author        TEXT NOT NULL,
    occurred_at   TEXT NOT NULL,            -- ISO-8601 UTC
    title         TEXT NOT NULL,
    url           TEXT,
    collaborators TEXT NOT NULL DEFAULT '[]',  -- JSON 数组
    payload       TEXT NOT NULL DEFAULT '{}',  -- JSON 对象
    collected_at  TEXT NOT NULL,
    UNIQUE(source, ref)
);

CREATE TABLE IF NOT EXISTS daily_reports (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    report_date TEXT NOT NULL,             -- YYYY-MM-DD
    member_name TEXT NOT NULL,
    category    TEXT NOT NULL,             -- dev / collab / discuss
    content     TEXT NOT NULL,             -- 条目文本（多行）
    raw_refs    TEXT NOT NULL DEFAULT '[]',
    created_at  TEXT NOT NULL,
    UNIQUE(report_date, member_name, category)
);

CREATE TABLE IF NOT EXISTS team_reports (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    report_date  TEXT NOT NULL UNIQUE,
    content      TEXT NOT NULL,            -- 团队日报全文
    missing_sources TEXT NOT NULL DEFAULT '[]',
    generated_at TEXT NOT NULL
);
```

## 4. 接口契约（函数级）

### 4.1 采集层

```python
class BaseCollector(ABC):
    name: str                                   # 如 "github"

    @abstractmethod
    def collect(self, day: date) -> list[RawEvent]:
        """采集 day（本地日）当日的原始事件。
        契约：
        - 入参 day 为本地日期；内部转换为 [day 00:00, day+1 00:00)（Asia/Shanghai）查询区间
        - 返回该区间内、作者属于团队成员的事件；顺序不做保证
        - 失败重试 3 次（指数退避 1s/2s/4s）后抛出 CollectorError
        - 单次调用对外请求数 ≤ 20（超限抛 CollectorError，防止触发平台限流）
        - 凭证缺失时抛 CredentialsMissingError（由编排层决定是否回退 mock）"""

class GitHubCollector(BaseCollector):
    def __init__(self, repo: str, token: str | None, session: httpx.Client, clock: Callable[[], datetime])

class FeishuTaskCollector(BaseCollector): ...
class FeishuMessageCollector(BaseCollector): ...
class MockCollector(BaseCollector):
    """内置模拟数据源；data_key 指定场景（'standard'），共 3 成员 × 3 源 ≈ 60 条事件，含 12 条标注协作事件。"""
```

### 4.2 生成层

```python
def generate_member_reports(
    events: list[RawEvent],
    members: list[Member],
    day: date,
) -> list[DailyReportEntry]:
    """契约：
    - 去重：同一 (source, ref) 只计一次（采集层兜底，此处再兜底）
    - 成员映射：事件作者/协同人按平台账号映射为成员姓名；未知账号事件不丢弃，单列"未映射"条目
    - 分类规则：
        dev     ← github commit（本人为作者）
        discuss ← feishu_message（本人被 @ 或本人发言）
        collab  ← 三类协同事件（见 4.4 协同归属规则）
    - 每名成员每个分类至多一条 DailyReportEntry；成员当日无事件时不生成该成员条目
    - 条目文本：按时间升序，每条事件一行「HH:MM 标题（链接）」"""

def build_team_report(
    entries: list[DailyReportEntry],
    members: list[Member],
    missing_sources: list[str],
    day: date,
) -> TeamReport:
    """契约：
    - 按成员配置顺序、dev/collab/discuss 分类顺序排版
    - 无事件成员进入 members_without_events（SC9）
    - 缺失数据源在报告头部显式标注（SC2）
    - 生成完整 Markdown 文本（邮件与飞书共用）"""
```

### 4.3 存储层

```python
def init_db(path: Path) -> sqlite3.Connection     # 建表（幂等）
def save_raw_events(conn, events: list[RawEvent]) -> None
def save_reports(conn, entries: list[DailyReportEntry], team: TeamReport) -> None
def load_team_report(conn, day: date) -> str | None   # 按日期查询历史（G5）
```

### 4.4 推送层

```python
@dataclass
class PushResult:
    channel: str        # "email" / "feishu"
    ok: bool
    mocked: bool        # True = 凭证缺失 mock 留痕
    detail: str

class BasePusher(ABC):
    channel: str
    @abstractmethod
    def push(self, team: TeamReport) -> PushResult
    """契约：
    - 凭证缺失：返回 ok=True, mocked=True（mock 推送），不得抛异常
    - 真实推送失败：返回 ok=False 并附错误摘要，由编排层汇总（不阻断其他推送通道）
    - 推送内容与日志一律脱敏（token、授权码不出现在 detail 与日志）"""

class EmailPusher(BasePusher): ...
class FeishuBotPusher(BasePusher): ...
```

### 4.5 主编排入口

```python
@dataclass
class PipelineResult:
    day: date
    collected: dict[str, int]       # 源 → 事件数
    missing_sources: list[str]
    entry_count: int
    push_results: list[PushResult]
    mocked: bool                    # 整体是否 mock 运行
    elapsed_seconds: float

def run_pipeline(day: date, settings: Settings) -> PipelineResult
```

CLI：`python -m daily_report_v1 [--date YYYY-MM-DD] [--mock] [--no-push]`
- 缺省：凭证齐全走真实数据源；任一必需凭证缺失 → 全部回退 mock 并在输出显式标注
- 退出码：0 成功（含降级出报）；1 生成层或存储层失败（数据不完整不推送）

## 5. 协同归属规则（生成层核心，对应 G3）

| 规则 | 触发条件 | 归属 |
| --- | --- | --- |
| R1 共同提交 | GitHub commit 含 `Co-authored-by:` 尾注（每行一个账号） | 作者 + 全部共同作者 |
| R2 协作任务 | 飞书任务含协作人（collaborators 字段非空） | 经办人 + 全部协作人 |
| R3 群内 @ | 群消息 @ 了他人且关联任务（payload.task_id 非空或正文含任务 ID） | 发言者 + 被 @ 者（视被 @ 者为协作参与） |

归属实现要点：一次事件可为多名成员生成 collab 条目；同一事件对同一成员只出现一次；collab 条目在原始发起人名下记"你发起的协作"，在协作者名下记"你参与的协作"。

## 6. 技术选型（ADR）

### ADR-001 选择 httpx 作为 HTTP 客户端

- **状态**：已接受（2026-11 王然/咸哲评审通过，红队评审单见 docs/records/04-红队评审单.md）
- **背景**：需要同时访问 GitHub REST API 与飞书开放平台 API；需要超时、重试、连接复用；课程环境 Python 3.12+。
- **备选项**：
  - A. httpx：现代 API、同步/异步双接口、超时与重试原语完善
  - B. requests：生态最大，但同步接口为主、连接池配置较繁琐
  - C. urllib（标准库）：零依赖，但无连接池、重试/超时需手工封装，代码噪音大
- **决策**：选 A（httpx）。同步接口 + `httpx.Client` 连接复用；后续如需异步可平滑升级。
- **理由**：连接池与超时默认值直接满足非功能约束（≤20 请求/轮），避免手工封装 urllib 的维护成本；GitHub 与飞书官方文档示例均以 httpx/requests 为主，社区资料充分。弃用 requests 是因其重试语义需依赖 urllib3 内部参数，行为不如 httpx 显式。

### ADR-002 选择 SQLite（标准库 sqlite3）作为日报历史存储

- **状态**：已接受
- **背景**：需要保存日报历史与原始事件，支持按日期查询；课程要求 SQLite。
- **备选项**：
  - A. SQLite：零部署、单文件、事务可靠，标准库自带
  - B. JSON 文件存储：实现最简单，但并发写、查询、去重约束都要手工实现
  - C. MySQL/PostgreSQL：能力强，但课程环境无服务器，部署成本与单团队场景不匹配
- **决策**：选 A。数据规模（日 ~200 事件、3 成员日报）远小于 SQLite 上限。
- **理由**：`UNIQUE` 约束天然支持事件去重与幂等重跑；单文件便于随仓库演示与备份；标准库满足课程"SQLite（标准库 sqlite3 即可）"约束。否决 JSON 存储：按日期查询与 (source,ref) 唯一性都需要手写，等于重造数据库。

### ADR-003 凭证一律环境变量注入，config.json 只存非敏感配置

- **状态**：已接受
- **背景**：课程红线——凭证严禁写入代码或提交仓库；成员清单与仓库地址等非敏感配置需要团队共享。
- **备选项**：
  - A. 环境变量 + config.json 分离：敏感走 env，共享配置走版本库
  - B. 全部放 config.json：单一配置点，但凭证入库风险不可接受
  - C. 密钥管理服务（如 keyring）：单机体验好，但跨平台与 CI 不可移植
- **决策**：选 A。`GITHUB_TOKEN / FEISHU_APP_ID / FEISHU_APP_SECRET / SMTP_*` 走环境变量；`config.json` 只含成员清单、仓库名、群 ID、收件人列表。
- **理由**：满足课程验收方式（出示环境变量配置但不显示值）；config.json 可直接入库供全组共享；CI 中注入环境变量即可跑测试。否决 C：引入平台相关的额外依赖，收益不足以抵消复杂度。

### ADR-004 采集失败"重试 3 次指数退避 + 降级出报"，凭证缺失回退 mock

- **状态**：已接受
- **背景**：外部平台限流、网络抖动、飞书审核未通过都会发生；课程要求"凭证未就绪时先接 mock 保证主流程可跑"。
- **备选项**：
  - A. 失败重试后降级出报（缺失源显式标注），凭证缺失自动 mock
  - B. 任一源失败即整体失败退出
  - C. 失败静默跳过（不标注）
- **决策**：选 A。
- **理由**：日报价值在于"今天有报"，单源故障不应阻断全局（对应成功标准 SC2/G6）；显式标注缺失源保证读者不被误导。否决 B：把外部平台故障放大为系统故障；否决 C：静默缺失违背"数据诚实"，读者无法区分"没数据"与"没采集"。

## 7. 非功能性约束

| 类别 | 约束 | 实现方式 |
| --- | --- | --- |
| 性能 | mock 全流程 ≤ 10s；单源单轮请求 ≤ 20 | 请求计数断言；连接复用；SQLite 批量写入 |
| 可靠性 | 采集失败重试 3 次（1s/2s/4s 指数退避）后降级 | BaseCollector 统一退避装饰器 |
| 安全 | 密钥仅环境变量；日志脱敏；SQL 参数化 | config.py 统一读取；日志过滤器；storage 全参数化 |
| 数据一致性 | 事件 (source, ref) 唯一；重跑幂等 | SQLite UNIQUE 约束 + INSERT OR IGNORE |
| 可追溯 | 每条日报条目携带 raw_refs，可回溯原始事件 | DailyReportEntry.raw_refs |
| 可维护性 | 数据源可替换（同 BaseCollector 契约） | 新增采集源 = 新增一个 Collector 类 + 注册 |
| 时区 | 事件 UTC 存储，本地时间展示（Asia/Shanghai） | 采集层统一转 UTC；生成层转本地 |

---

## 附录 A：v2 架构补充（阶段二 · Superpowers 工作流，变更涟漪产物）

阶段二从零重做时，继承本文件 ADR 结论与接口契约作为"设计经验"，但**不复用 v1 任何源码**，
并按下述新架构重新实现（对比分析见项目总结报告第 2 章）：

### A.1 v2 架构：注册表 + 规则管道（纯函数核心）

与 v1 的"继承式分层类架构"（Collector/Pusher 抽象基类 + 子类）不同，v2 采用：

- **注册表**：采集器与推送器以「名称 → 工厂函数」注册（`fetch.py` / `deliver.py` 顶部 `REGISTRY` 字典），
  新增数据源 = 注册一个新函数 + 一个测试文件，不改任何既有核心代码（开放封闭）；
- **规则管道**：协同归属规则 R1/R2/R3 实现为独立纯函数列表（`rules.py` 的 `RULES`），
  对每条事件顺序应用，命中即产出归属记录——新增规则追加列表项即可；
- **纯函数核心**：`synthesize.py` / `rules.py` 全部为无状态纯函数，输入输出即契约，测试无需 mock；
- **管道编排**：`pipeline.py` 以数据流串联各阶段，与 v1 的 Orchestrator 类等价但以函数组合实现。

### A.2 模块映射（v1 → v2）

| v1（类） | v2（函数式） | 说明 |
| --- | --- | --- |
| collectors/github.py GitHubCollector | fetch.py `fetch_github()` | 注册表项 `"github"` |
| collectors/feishu.py FeishuTaskCollector | fetch.py `fetch_feishu_task()` | 注册表项 `"feishu_task"` |
| collectors/feishu.py FeishuMessageCollector | fetch.py `fetch_feishu_message()` | 注册表项 `"feishu_message"` |
| collectors/mock_data.py MockCollector | fetch.py `fetch_mock()` | 注册表项按 mock 场景生成 |
| generators/report_generator.py | rules.py + synthesize.py | 归属规则与条目聚合分离 |
| pushers/ | deliver.py `deliver_email()` / `deliver_feishu()` | 注册表项 `"email"` / `"feishu"` |
| orchestrator.py run_pipeline() | pipeline.py `run_pipeline()` | 函数组合 |

### A.3 变更单（第 4 周）：新增考勤采集

- proposal.md 范围新增 **F12 飞书考勤采集**（采集当日打卡记录，归入个人日报"开发"分类的"考勤"子条目）；"不做什么" X3 移除并改注"已于 v1.1 变更单实施"；
- 本文件新增契约：`fetch_feishu_attendance()`（注册表项 `"feishu_attendance"`）——入参 day，返回 `source="feishu_attendance"` 的打卡事件（上/下午首末次共 4 字段入 payload）；
- tasks-v2.md 新增 T212–T214；数据模型不变（RawEvent 的 source 字段新增枚举值，payload 承载打卡明细）。
