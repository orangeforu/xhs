# {案例名} — venture.md

> 从本模板复制开案。**止损线与最小验证预算缺一不可**——没有就不开案（GLOSSARY: 案例状态机）。

```yaml
name: 
status: idea          # idea→researching→planning→executing→selling→maintenance→closed（仅周五复盘时更新）
opened:               # 开案日期
idea_source:          # 点子来源（BOSS观察/竞品扫描/数据洞察/复盘推导）——BOSS 是重要传感器，此处留痕
hypothesis:           # 一句话：赌什么成立就能挣钱
target_user: 
pricing_model: 
min_validation_budget:    # 必填：时间上限(h) + 现金上限(¥)
stop_loss:                # 必填：什么信号出现即关线（要可观测，如"N周<X询盘"）
```

## 目录约定

```
venture.md     # 本文件（状态与赌注）
research.md    # 调研（公网+站内实测，只收带证据结论）
plan.md        # 执行计划（阶段/关键步骤/AI与人的分工）
ledger.md      # 案例流水（日期/事件/金额/渠道来源必填）
content/       # 产出物（笔记草稿/物料/产品文件）
tools/         # 案例内临时工具（Rule of Two 未满足前的练习本）
postmortem.md  # 关单时必写（关单条件见 GLOSSARY）
```

## 关单检查单（closed 前全勾）

- [ ] postmortem.md 已写（为什么成/败、下次怎么改）
- [ ] 蒸馏 ≥1 条 knowledge（跨案例结论，或明确的负知识）
- [ ] cockpit/status.md 状态灯已熄
- [ ] 资产归还登记（账号/在售链接停用或移交，更新 assets/registry.md）
