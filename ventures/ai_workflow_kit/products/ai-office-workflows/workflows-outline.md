# 其余 9 条工作流大纲（生产清单）

> 格式对齐 workflow-01：Insight → Steps（含 prompt 模板）→ 60 秒 Audit → Failure Modes → 为什么有效。
> 来源列 = `data/topics.json` 对应选题（流水线已有素材/观点可提炼）。每条必须有**自己的 Audit 角度**——这是产品差异化，不能省。
> 生产方式：流水线出英文初稿（用 agent_writer 的结构思路）→ 人工质检（重点审 prompt 可用性 + Audit 是否真实）→ 人工实测一遍再入库。

| # | 标题（英文方向） | 来源选题 | 独有 Audit 角度 |
|---|---|---|---|
| 02 | Meeting Notes → Decisions, Owners, Deadlines (Not Transcript) | 会议纪要那篇 | AI 会发明"共识"——会上没达成的决定它会补全成达成了；核对每个 decision 是否真的有人说 |
| 03 | The Status Email That Stops "Any Updates?" Pings | 工作群"辛苦了"那篇 | AI 会写"on track"掩盖风险——审掉所有无证据的进度副词 |
| 04 | 100-Page Document → Exec Summary + Risks + Actions | 100页文件那篇 | 长文档摘要会漏"埋在附注里的条件"——prompt 强制引用页码，核对引用真实性 |
| 05 | Messy Spreadsheet → Clean Summary + Anomalies | 考勤/数据整理那篇 | AI 对数字表会"脑补"缺失值——任何汇总数字必须能在原表复算 |
| 06 | The Polite Chase-Up ("As Per My Last Email", Without the Passive Aggression) | 回复领导/消息话术那篇 | 语气审计：AI 写的追催要么太软要么太冲，给了 3 档语气刻度让用户选 |
| 07 | Blank Page → PPT Outline in 10 Minutes | AI做PPT实测那篇 | AI 会堆 bullet 不给论点——审"每页是否有且仅有一个 takeaway" |
| 08 | Resume Bullet Rewriter (What Did You *Actually* Do) | 简历那篇 | AI 会把职责写成成就（"responsible for"→"achieved"）——禁止无数字的成就句 |
| 09 | Read Your Manager's Mind: Pre-Loading Skip-Level Questions | 汇报思路那篇 | AI 只会出模板问题——要求它从你的 update 内容里反推 3 个最可能被追问的点 |
| 10 | Client Message Triage: What to Answer Now, What to Escalate, What to Ignore | 客户消息回复那篇 | AI 分诊会把"需要人工判断的"标成"可直接回"——分级必须带升级条件 |

## v2 备选变体（信号 1 提醒：卖给"正在赚钱的人"转化更好）

- for Freelancers：提案/报价/催款 3 件套（用同一 QA 框架）
- for Etsy/Shopify Sellers：listing 文案 + 客服回复（与线 B1 用户群重叠，互相导流）

## SKU 结构

- **Free**：workflow-01（本产品最好的示范，即营销证明）
- **$9 Full Kit**：workflow-02~10 + 全部 prompt 纯文本版（方便复制）+ 一页"通用 AI Audit Cheat Sheet"（把 10 条的 audit 规则合并成一张卡，这是复购口碑件）
- 上架 4 周 <10 单 → 不加 SKU，转 B1（见选品调研止损线）
