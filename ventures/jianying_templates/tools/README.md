# tools — 本线脚本说明

> 前三个脚本做“取证与复算”；后两个脚本只在本地绘制素材和示意图。所有脚本都不发布、不代登录、不估算收入。
> 运行环境：Python 3.13+；采集脚本依赖 `capabilities/xhs_crawler` 的已保存 PC Cookie 与 Node 依赖。

## 一览

| 脚本 | 作用 | 输入 | 输出 | 是否会覆盖 |
|---|---|---|---|---|
| `collect_direction_research.py` | 六方向有界只读采样（24 组查询，取前 10 条，每方向最多 2 条详情） | 已保存的小红书 PC 登录态 | `data/direction_research_20261028.json` / `.csv` | 否，已存在即报错 |
| `summarize_direction_research.py` | 合并去重、校验标签覆盖、算方向×排序中位数 | 上面的 JSON＋`direction_content_labels_20261028.csv` | `data/direction_summary_20261028.json` / `.csv`（含输入 SHA-256） | 否 |
| `export_native_comparison.py` | 把手工观测的原生模板样本导出为对比表 | `data/native_template_samples_20261028.json`（`batch == "user_six_links"`，断言 6 条） | `data/native_template_comparison_20261028.csv` | 否 |

## 今晚练习素材（不需要用户运行代码）

`prepare_first_template_practice.py`使用Pillow离线绘制8张几何PNG和来源清单，打包到`practice_20261029/first_template_practice.zip`。目录非空即拒绝覆盖；不使用照片、音乐或字体，不产生剪映工程，不替用户剪辑。现有素材已生成，直接按[今晚操作卡](../今晚第一条_剪映Windows一对一操作_20261029.md)使用即可。

## 发布流程示意图（不需要用户运行代码）

`draw_publish_guide.py`用Pillow绘制6张原创示意图（路线、14秒时间线、图层、槽位配置、五输入、审核循环），输出到`guides/20261029/`并写`manifest.json`（尺寸、用途、SHA-256）。图示使用系统字体渲染，仅作文档说明，不是剪映界面截图，也不含平台素材。目录非空即拒绝覆盖；重画前先归档旧图。文档见[模板发布全流程](../模板发布全流程_图文步骤_20261029.md)。

```bash
cd ventures/jianying_templates
python tools/draw_publish_guide.py
```

## 复现步骤（仅前三个研究脚本）

```bash
cd ventures/jianying_templates

# 1) 采集（需要有效 Cookie；代理卡住时先 NO_PROXY=*）
python tools/collect_direction_research.py

# 2) 人工/辅助标注 213 条内容类型后，复算汇总
python tools/summarize_direction_research.py

# 3) 离线导出原生样本对比（不联网）
python tools/export_native_comparison.py
```

## 设计约束（改脚本前先读）

- **只读**：不调用写接口、不发帖、不评论、不关注；不替换登录态，不在输出里写 Cookie/xsec token。
- **失败即停**：采集遇到第一个接口失败就结束并标记 `stopped_early`，不重试轰炸。
- **不覆盖**：输出文件存在就拒绝运行；要重跑先手动改名或移到归档。
- **不改口径**：缺失值保持 `None`/空，不用 0 顶替；不把互动量换算成销量或收益。
- **标签必须全量**：汇总脚本断言“去重后的每条笔记都有标签”，缺一条就失败——防止用部分标注冒充全量。
- **可追溯**：汇总文件写入输入 JSON 与标签 CSV 的 SHA-256，便于确认报告对应哪版数据。

## 明确不做

- 不做按方向的模板检索（原生分享页没有列表入口）。
- 不推断付费状态、发布时间、素材数量或作者收益。
- 不生成任何“赛道收益排名”。
