# Superpowers 技能库（阶段二工作流）

> 课程要求：Superpowers 技能库由**配置管理员**负责安装与更新（指导书第三部分"技能库"条目：
> 自行到 GitHub 下载安装，安装方法见仓库 README；验收方式：能列出并调用其中任一技能）。

## 安装步骤（配置管理员执行）

```bash
# 1. 克隆到 Claude Code 用户级技能目录（以官方仓库 README 为准）
git clone https://github.com/obra/superpowers.git ~/.claude/skills/superpowers
# 国内网络受阻时：使用镜像 / 代理，或将压缩包下载后解压到同一目录

# 2. 验证：开新会话输入 /skills 或让 AI 列出可用技能，确认 6 大工作流可见
```

## 本课程使用的六个核心工作流

| 工作流 | 本项目的使用时机 | 使用留痕 |
| --- | --- | --- |
| brainstorming | 需求澄清提问（阶段一起点借鉴其提问法） | docs/records/01-需求澄清问答记录.md |
| writing-plans | 从规范拆任务清单 | specs/tasks-v2.md（T201–T214） |
| executing-plans | 逐任务执行，一次提交一个任务 | git 提交历史（message 含任务编号） |
| test-driven-development | 红→绿→重构循环 | docs/records/16-TDD红绿循环记录.md |
| systematic-debugging | 缺陷根因记录 | 缺陷 D1–D3 记录（09-变更涟漪演练记录.md） |
| code-review | 每次合并前互评 | 04-红队评审单、站会记录中的互评条目 |

## 说明

- 本目录不随技能库本体入库（第三方仓库体积与授权原因）；仅保留本安装说明。
- 若组员环境无外网，可由配置管理员将技能库打包分发，按上述目录解压即可。
- 技能拆解笔记（前导练习 5.1.3）见 docs/records/05-技能拆解笔记.md。
