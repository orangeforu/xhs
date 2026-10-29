# ai_workflow_kit — 打工人 AI 提效工作流包

```yaml
name: ai_workflow_kit
status: selling           # selling：面包多已上架；闲鱼 listing 待扫码确认
opened: 2026-09-29
idea_source: BOSS 决策（被动收入路线转向，选品调研选定数字资产线）
hypothesis: 面向非技术岗的「提示词+防编造核查」工作流包，以差异化 QA 层在 ¥19.9 价格带可持续卖出
target_user: 运营/产品/行政/财务/HR（非技术岗打工人）
pricing_model: 面包多 ¥19.9（前50单早鸟，后 ¥29.9）｜闲鱼 ¥15.9｜Gumroad EN $9
min_validation_budget: 30h + ¥300
stop_loss: 上架 4 周（至 2026-10-27）<10 单 → 中文版不加内容，主力转 B1（Etsy 卖家工具）
```

## 核验与执行入口（2026-10-29）

- 产品：10工作流及中文v1.0已形成；旧“10/10通过”与若干对照组卖点证据不成立，现以[修订QA报告](products/ai-office-workflows/qa/QA-REPORT.md)为准。本轮静态纠错未重新运行API、未修改已售产品承诺。
- 当前业务状态看[状态灯](../../cockpit/status.md)；渠道核验及10-27到期复盘只维护[actions.csv](../../cockpit/actions.csv)的KIT-CHANNEL和KIT-REVIEW，不另复制待办。
- 草稿从[产品索引](products/ai-office-workflows/README.md)进入；文案修订不等于已发布，`tools/fill_links.py`只回填草稿，不能证明在售或成交。
- 账本：案例流水保留历史记录，汇总口径见[总账](../../cockpit/ledger.md)；`docs/回本计划_codingplan.md`是历史资料，不再回写经营事实。

**10-27阶段节点已到期，但销售证据不足。** 上方原止损规则作为评审依据保留；不得用“没有回填”替代“少于10单”或自动转B1。先取得渠道有效上线日、订单与结算记录，再提交BOSS决定，未经L3确认不新开业务线。

## 目录

```
venture.md  docs/(调研+回本计划)  products/(ai-office-workflows+website+dist)  tools/(test_workflows+fill_links)
```
