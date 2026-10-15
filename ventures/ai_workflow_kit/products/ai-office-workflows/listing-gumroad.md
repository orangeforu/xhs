# Gumroad 上架物料（复制即用）

> **2026-09-29 方案更新（验证优先）**：PayPal 大陆收款死路 → 提款管道后置。**现在不配置 payout 直接上架销售**，余额留在 Gumroad，先验证"有没有人肯付 $9"。
> 三条红线：① 自然流量慢慢卖，绝不刷单/自买多单（新号+未验证状态是风控高危画像）；② 验证期 4 周/10 单为决策点，不无限拖；③ 余额当"可能沉没的验证成本"看，信号（转化率/买家地域）才是主要产出。
> 验证成功 → 届时义乌个体户+贝宝商户配置提款（余额可取），或新销售迁 Paddle（官网已备）。

## 上传清单（文件已就绪）

| 产品 | 定价 | 上传文件 | 说明 |
|---|---|---|---|
| 全套 Kit | **$9**（划线 $14） | `products/dist/9to5-kit-en-bundle.zip` | PDF + markdown 源文件；产品图用官网首页截图或 PDF 首页 |
| 免费样张 | **$0+**（自定义价格） | `products/dist/workflow-01-free-sample-en.pdf` | 收邮箱 + 收集"值不值"信号；样张最后一页已带全套引导 |

⚠️ Gumroad 产品发布要过人工审核队列（1-2 天），趁早提交。

## 标题（A/B 二选一起号，跑 2 周看转化）

- **A（推荐）**: The 9-to-5 AI Workflow Kit — 10 copy-paste workflows + the audit checklists that stop AI from making things up
- **B（更短）**: Stop Doing Busywork — 10 AI Workflows for Office Jobs (with anti-BS checklists)

## 一句话副标题

> Prompts are free. Knowing when the AI is lying to you isn't.

## 产品描述

```
You don't need another 500-prompt mega pack.

You need 10 workflows for the actual work that eats your week — weekly
updates, meeting notes, status emails, document summaries, messy
spreadsheets, chase-ups, PPT outlines — each one built around a simple
truth the prompt sellers never mention:

AI doesn't invent content. It invents CAUSALITY.

It will merge two unrelated events into a cause-and-effect chain that
never happened, because chains read better than lists. It will write
"on track" over a slipping deadline. It will turn "responsible for"
into "achieved." And your manager will notice before you do.

Every workflow in this kit has three parts:

  1. THE PROMPT — copy-paste, with [PLACEHOLDERS], works in any chat
     LLM (ChatGPT, Claude, Gemini — no subscriptions or plugins needed)
  2. THE 60-SECOND AUDIT — a specific checklist for what THIS workflow's
     output gets wrong, so you catch it before your boss does
  3. FAILURE MODES — the exact ways the AI will try to ruin this task,
     and the one-line fix for each

Plus: the Anti-BS Cheat Sheet — all 10 audit checklists condensed to
one printable page. Pin it next to your monitor.

WHAT'S INSIDE
  ✓ 10 workflows (PDF + raw markdown, copy-paste friendly)
  ✓ 1 printable Anti-BS Cheat Sheet
  ✓ Lifetime updates (new workflows added free — price goes up as the
    kit grows, yours never does)

WHO IT'S FOR
Ops, PMs, admins, finance analysts, marketing coordinators — anyone
whose week dies in a thousand small documents. No technical skills
needed. If you can paste text, you're qualified.

WHO IT'S NOT FOR
Prompt engineers. You already know this stuff.

REFUND
30 days, no questions. If the audits don't save you at least one
embarrassment, it's free.
```

## 定价与发布节奏

| 项 | 值 | 说明 |
|---|---|---|
| 定价 | **$9**（划线价 $14） | 竞品 $3-7 但无 QA 层；$9 是"认真但不高冷"锚点 |
| Free sample | workflow-01 单独 $0+ 页 | Gumroad 支持付费意愿定价（$0 / 自定义），做邮件列表钩子 |
| 首发渠道 | Gumroad → Payhip / Etsy 二铺 | 同一文件零边际成本 |

## 上架前 BOSS 待办（必须本人操作）

1. Gumroad 开号 + 绑 PayPal（中国个人开发者可提现路径）
2. PDF 排版：workflow-01 + 02-10 成稿后用统一模板导出（`.md` → PDF，模板待做，一次性工作）
3. 封面图 1280×720：大字 "9-to-5 AI Workflow Kit" + 副标 "with anti-BS checklists"，风格延续大字报封面（`core/image` 模板可改造复用）
4. 上线第 1 周：把 workflow-01 投到 r/productivity、r/artificial、HackerNews Show HN 试水（注意各社区自我推广规则，先评论互动再发）
