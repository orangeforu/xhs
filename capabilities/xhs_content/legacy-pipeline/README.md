# legacy-pipeline — 休眠的内容流水线（账号线遗产，2026-09 停产）

> 状态：⚪ 休眠（conftest 垫片保可跑，零改动封存）。设计经验已蒸馏至
> `knowledge/playbooks/`（multi-agent 编排）。**本文件同时保存旧 CLAUDE.md 中
> 仍有档案价值的技术知识。**

## 重启条件（Rule of Two 之外的显式约定）

单案例内容需求 **≥5 篇/周**，且 Claude 直写成为质量/成本瓶颈时，评估重启。
重启前必读：下方"仍在生效的知识"与 `tests/`（28 个测试是行为规格书）。

## 这是什么（一段话）

7 专家 Agent（TopicStrategist→EmotionalWriter→(CoverDesigner∥LayoutArtist∥ContentEditor)→ChiefEditor→CommunityManager）经 MessageBus（发布/订阅，9 种消息类型）协作的图文笔记流水线；ChiefEditor 最多 5 轮迭代（A 级过/B 级 issues≤2 过/连续 3 轮同级强制过/5 轮不达标放弃）；AgentMemory 跨会话持久化（data/agent_memory/）。配套 Streamlit 6-tab 审核台（app.py）与发布/采数脚本（已随案例3迁至 ventures/xhs_account_v1/scripts/）。

## 仍在生效的知识（重启时直接复用）

- **废笔记健康检查**（防 LLM 思考链泄漏，glm 系模型 `Let me analyze...` 混入 content）：`core/utils.py: check_note_health`——特征词 ≥2 处 + 英文占比异常（英文词>20 且>中文字×0.5）三道防线（生成拦截/发布前校验）。实测 49 处特征词废稿精准拦截、正常中文笔记无误判
- **凡 prompt 写了但 LLM 不稳定遵守的规则，一律代码兜底**（标签净化 sanitize_tags、健康检查皆是此模式的实例）
- **封面：模板大字报 > AI 绘画**（AI 封面 CTR 实测偏低：塑料感+文字可读性差）；Pillow 渲染 7 配色主题+动态字号防溢出；产物名 cover_ai.png 为历史命名
- **内页分页**：先 `_paginate_blocks` 算分页不渲染 → 得准确页数 → 多线程渲染（max_workers=4）
- **app.py ↔ pipeline.py 兼容层**：app.py 依赖 pipeline 的 `_extract_cover_info/_extract_visual_style/_clean_md` 正则解析 note.md——改任一侧必须同步另一侧
- **调度器刻意不提供发布动作**（合规红线，见根 CLAUDE.md）

## 运行（休眠状态仍可手动唤醒）

```bash
cd capabilities/xhs_content/legacy-pipeline
python -m pytest tests/          # 遗产测试（行为规格）
python pipeline.py --list        # 选题池
streamlit run app.py             # 审核台
```

注意：data/（topics.json/performance.json/agent_memory）已随案例3迁至
`ventures/xhs_account_v1/data/`——重启时需把 data 路径指回或复制。
