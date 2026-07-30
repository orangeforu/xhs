# 知识库（knowledge_base）

跨会话沉淀可复用的**定性**模式。与 `data/agent_memory/`（每个 Agent 最近 10 条 numeric
模式）互补：这里存的是人类可读、可检索、可复用的结构化模板，跨 Agent、跨会话共享。

## 5 类记录

| 目录 | 类型 | 写入时机 | 关键字段 |
|---|---|---|---|
| `pattern/` | 已验证有效的结构模板 | ChiefEditor 审核通过（publish） | grade, title, title_formula, visual_style, series, tags |
| `review/` | 失败复盘 | ChiefEditor 放弃（abandon） | what_failed, why, fix_next_time, grade |
| `topic/` | 选题洞察 | 评论挖掘 / 竞品分析 | source_note, confidence |
| `account/` | 账号体检结论 | 账号诊断脚本 | 定位 / 人设 / 内容支柱 / 红线 |
| `action/` | 执行动作记录 | 发布 / 采数 / 复盘 | 动作类型 / 结果 |

## 记录格式

每个文件 = YAML frontmatter + markdown 正文：

```markdown
---
id: 20260730120000_pattern
type: pattern
status: active
created_at: 2026-07-30T12:00:00
summary: S级模式：分手后该不该删微信
grade: S
title_formula: 问句式
visual_style: crimson
series: 互联网打工人的深夜
tags: [问句式, 互联网打工人的深夜]
---

正文：证据 / 细节 / 可复用点。
```

## 检索 SOP（TopicStrategist 自动执行）

1. 按 brief 的 `title_formula` / `series` / `pillar` 作为 tags 检索 `pattern/`
2. 命中不足时回退到全部 `active` pattern
3. 注入 prompt 作为「可复用 pattern - 借鉴结构，不要照抄内容」

## 废弃规则

已验证失效的 pattern 标记为 `status: deprecated`（`core.knowledge_base.deprecate`），
**不直接删除**，保留可复盘。`search_records(status="active")` 默认只返回 active。

## 入库策略

运行时记录含真实账号数据，不入 git（见 `.gitignore`）。本 README 与各目录 `.gitkeep`
保留骨架。
