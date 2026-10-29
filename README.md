# 个人商业孵化台

> 培养"会挣钱的操盘手"的培养皿：案例是练习场，capabilities 是手艺，knowledge 是判断力，
> cockpit 是纪律与成绩单。每一单真金白银的实战都在给系统升级。

## 这是什么

通过真实案例（有止损线的挣钱实验）培养 AI 操盘手的项目。BOSS 是委托人与机会传感器，
Claude 是参谋部+执行工厂。宪法与铁律见 [CLAUDE.md](CLAUDE.md)，术语见 [GLOSSARY.md](GLOSSARY.md)。

## 一分钟看懂结构

```
cockpit/        调度台：总账·时间预算·状态灯·成绩单·授权台账（周五复盘的操作台）
capabilities/   能力货架：小红书采集/内容生产/闲鱼适配/市场调研/案例工具箱
ventures/       案例层：一条业务线一个目录（开案必填止损线）
knowledge/      知识库：从案例蒸馏的打法 + 决策拷问档案
assets/         资产登记：账号/Cookie/渠道（值不进 git）
98-debt/        技术债
```

## 当前战局

状态与最新核验结果只看 [cockpit/status.md](cockpit/status.md)，动作与回执只维护 [cockpit/actions.csv](cockpit/actions.csv)。

- [资料包案例](ventures/ai_workflow_kit/venture.md)：产品规格与阶段规则。
- [剪映案例](ventures/jianying_templates/venture.md)：准入、母版与经营验证。
- [账号线归档](ventures/xhs_account_v1/venture.md)：历史资产及复盘摘要。

## 完整手册

架构/运行机制/使用/维护/演化方向的唯一手册：[knowledge/design/孵化台手册.md](knowledge/design/孵化台手册.md)

## 快速上手（给未来的 Claude/协作者）

1. 读 CLAUDE.md（宪法）→ GLOSSARY.md（术语）→ cockpit/status.md（战局）——这是开场注入协议
2. 活能力测试：`pytest`
3. 站内采集：`python capabilities/xhs_crawler/verify_search.py`

## 存在的理由

GLM Coding Plan ¥118/月，自 2026-10 起由项目自己挣（cockpit/ledger.md 对账）。
