# CLAUDE.md — 个人商业孵化台宪法

> 本项目 = 培养"会挣钱的操盘手"的培养皿。案例是练习场，capabilities 是手艺，
> knowledge 是判断力，cockpit 是纪律与成绩单。每一单真金白银的实战都在给系统升级。
> 术语唯一定义处：[GLOSSARY.md](GLOSSARY.md)。

## 行为准则（四条，先于一切）

**1. Think Before Coding** —— 不臆测、不掩盖困惑、亮出权衡。实现前先说假设；有多种理解就摆出来；有更简单的做法就直说。

**2. Simplicity First** —— 用解决问题的最少代码，不写投机性功能。自问："资深工程师会不会觉得过度设计？"

**3. Surgical Changes** —— 只动必须动的，只清理自己制造的垃圾。匹配现有风格；发现无关死代码提一句，不擅自删。

**4. Goal-Driven Execution** —— 把任务转成可验证目标（先写验证，再做通过）。多步任务先列"步骤→验证"清单。

## 架构铁律（五条）

1. **Rule of Two**：能力上货架（`capabilities/`）的条件 = ≥2 个案例真实用过。案例内临时工具住案例 `tools/`
2. **单一信息源**：事实只在一处 canonical，别处放链接（状态只在 cockpit/status.md，术语只在 GLOSSARY.md）
3. **能力带健康检查**：每个能力有 README + 状态（依赖/Cookie/最近成功运行）
4. **案例带状态机**：见 GLOSSARY；状态只在周五复盘时更新
5. **蒸馏绑定周五复盘**：每个活跃案例每次复盘产出 ≥1 条 knowledge 或明确记"无可蒸馏"——绝不绑单一案例的机器（knowledge_base 遗址的死因）

## 宪法目标（约束即目标的一部分）

**最大化可持续的净现金流**；约束 = 合规红线（下）+ 平台规则 + 授权分级。
**终局中立**：不预设 AI/人类主导比，授权边界（`cockpit/authorization.md`）由战绩逐级搬动；BOSS 的受益权与 L3 投票权不可委托。

## 开场注入协议（每次会话处理业务前，防"失忆"）

1. 读 `cockpit/status.md` —— 当前战局：哪些线活着、什么状态
2. 读活跃案例的 `venture.md` —— 本线假设/止损线/进度
3. 相关主题先查 `knowledge/` —— 不重复交学费

## 目录导航

| 目录 | 是什么 | 详情 |
|---|---|---|
| `cockpit/` | 调度台：ledger(总账) / time-budget / status(状态灯) / report-card(成绩单) / authorization(授权台账) / journal(每日心跳简报) | 状态唯一汇总处 |
| `capabilities/` | 能力货架：`xhs_crawler`(站内采集) `xhs_content`(内容生产,现役=Claude直写+规范库,含休眠 legacy-pipeline) `xianyu_ops`(闲鱼适配器) `market_research`(调研) `venture_toolkit`(上架+记账) `pulse`(每日心跳=执行模块) | 索引见其 README.md |
| `ventures/` | 案例层：`ai_workflow_kit`(selling) `jianying_templates`(planning) `xhs_account_v1`(closed) + `_template/`(开案模板) | 一线一目录 |
| `knowledge/` | memory 机制 + playbooks(打法) + grill_records(决策拷问) + design(设计文档) | 只收跨案例结论 |
| `assets/` | 资产登记 registry.md（账号/Cookie/key/在售链接，值不进 git） | 周五查健康 |
| `98-debt/` | 技术债清单 | |

## 常用命令

```bash
# 能力：小红书站内采集（Cookie 已持久化 .cache/）
python capabilities/xhs_crawler/verify_search.py          # 站内搜索实测（原 verify_xhs_jianying）
python capabilities/xhs_crawler/xhs_auth_helper.py        # 登录/Cookie 管理

# 案例1 质检工具
python ventures/ai_workflow_kit/tools/test_workflows.py   # 10条工作流埋雷实测
python ventures/ai_workflow_kit/tools/fill_links.py <面包多链接>

# 代码质量（只测活能力；legacy 管线测试随代码封存）
pytest

# 每日心跳（执行模块；计划任务 08:30，需 BOSS 注册见 pulse/README.md）
python capabilities/pulse/heartbeat.py           # 手动触发：晨报→journal→微信

# 休眠的内容流水线（账号线遗产，重启条件见其 README）
# 见 capabilities/xhs_content/legacy-pipeline/README.md
```

## 合规红线（违反=立即停止并说明，无论多赶）

1. **小红书/闲鱼发布只能人工触发**（2026 平台处置 42 万 AI 托管账号；`scheduler` 类工具永不提供发布动作；禁止接入定时发布）
2. **预设评论默认禁用**（2026 严打 AI 批量互动）；笔记发布前必须替换 `✍️` 真人改写槽位——这是"AI 辅助"与"AI 托管"的分界线
3. **站外导流红线**：小红书站内绝不出现面包多/微信/外链（转化走评论区→私信）；闲鱼站内绝不出现微信/网盘/站外链接
4. **AI 辅助内容必须勾选标注**；不编造工具功能/数据；不夸大；不用极限词；不贩卖焦虑
5. **音乐版权**（剪映线）：只用 CC0/自购授权曲，绝不用流行歌
6. 商单/推广必须平台报备；机密（.env/Cookie/.cache/账号凭证）禁入 git

## 周五复盘流程（Cadence，~20 分钟，进化1.0：周五21:07自醒cron自动发起）

1. 更新 `cockpit/ledger.md`（本周各案例收入）+ `time-budget.md`（计划 vs 实际）
2. 逐活跃案例更新 `status.md` 状态灯；对照止损线
3. 蒸馏检查：每个活跃案例 ≥1 条 knowledge 或记"无可蒸馏"
4. `assets/registry.md` 健康检查（Cookie 到期/账号状态）
5. 记录下周计划；月度加记 `report-card.md`（能力新增/知识更新/idea→selling 天数）
6. **自续**：定时任务 7 天自动过期——复盘末尾重建下周自醒 cron（prompt 原样复制），这是分身自持的一部分

## 环境依赖

- Python 3.13+；`.env`（LLM_API_KEY/LLM_BASE_URL/LLM_MODEL，OpenAI 兼容）
- spider_xhs 运行时依赖 Node.js（根 `node_modules/crypto-js`；被死系统代理卡住时 NO_PROXY=* 或参考 capabilities/xhs_crawler/README）
- 字体：`capabilities/_shared/fonts/NotoSansSC-*.ttf`
- 兄弟仓库 `D:\SoftWare\User\Vs\xianyu`（排队号生意）：闲鱼能力的实际载体，对接文档见 `capabilities/xianyu_ops/`
