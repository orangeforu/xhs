# GLOSSARY — 术语地图（唯一定义处）

> 单一信息源原则：本文件是以下术语的**唯一**定义处，其他文档引用不重复定义。
> 改术语先改这里。灵感来源：Fulu.DataCenter 的 GLOSSARY-MAP 模式。

## 核心术语

| 术语 | 定义 | 不是什么 |
|---|---|---|
| **能力（capability）** | 可复用的手艺：`capabilities/` 下自包含目录（README+入口+依赖+健康检查），被 ≥2 个案例真实用过才可上货架（Rule of Two） | 不是"任何脚本"。案例内临时工具住案例的 `tools/`，不住货架 |
| **案例（venture）** | 一条业务线的一生：`ventures/` 下一个目录，带状态机（见下），含调研/计划/流水/复盘全档案 | 不是"一个产品/SKU"。SKU 是案例内的产物 |
| **知识（knowledge）** | 从 ≥1 个案例蒸馏出的跨案例可复用结论，存 `knowledge/`（memory 机制 + playbooks + grill_records） | 不是"资料收集"。单案例细节留在案例内 |
| **调度台（cockpit）** | 跨案例的纪律层：总账/时间预算/状态灯/成绩单/授权台账。`status.md` 是各线状态**唯一**汇总处 | 不是内容存储 |
| **资产（asset）** | 娇贵的共享家当：账号/Cookie/实名/API key/在售链接，登记 `assets/registry.md`（值不进 git） | 不是普通文件 |
| **BOSS** | 唯一委托人与受益人：受益权 + L3 投票权不可委托。角色演化方向=操作员→董事会 | 不是"执行器之一"（见 authorization.md） |

## 案例状态机

```
idea → researching → planning → executing → selling → maintenance → closed
                                  ↘ (验证失败) closed
```

- 状态转换**只在周五复盘时**由 AI 更新，记入 `cockpit/status.md` 与案例 `venture.md`
- `closed` 的关单条件：必写 postmortem.md + 必蒸馏 ≥1 条 knowledge
- 新案必填：**止损线**、**最小验证预算**（缺一不开案）

## 收入口径

- **收入** = 实际到账（平台结算口径），预付款未交付不计
- **月固定成本** = 订阅等刚性支出（当前：GLM Coding Plan ¥118/月），记 `cockpit/ledger.md`
- **案例净贡献** = 案例收入 − 该案例直接成本（工具/素材/推广）

## 授权分级（L0-L3）

| 级 | 含义 | 台账 |
|---|---|---|
| L0 | AI 全自动，无需告知 | `cockpit/authorization.md` |
| L1 | AI 做，周五复盘报备 | 同上 |
| L2 | BOSS 一键确认（扫码/点击） | 同上 |
| L3 | 必须与 BOSS 讨论：开线/砍线/定价/花钱超阈值 | **永久保留，不可下放** |
