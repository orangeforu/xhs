# 98-debt — 技术债与遗留

> 记了就要排期，不排期就明说"不还"。每条带影响评估。

| # | 债 | 影响 | 处置意向 |
|---|---|---|---|
| 1 | spider_xhs vendored 后无上游同步机制（2026-09 弃子模块时引入） | 平台接口变动时需手修 | 观察项：接口稳就不还 |
| 2 | mcp_server.py（legacy）依赖 fastmcp 不在 requirements | 重启 legacy 时会 pip 失败 | 已记入 legacy README；不单独还 |
| 3 | 案例1 闲鱼 listing 扫码确认悬置（2026-10-09 起） | 在售状态未知，影响账本真实性 | 周五复盘第一问 |
| 4 | 案例1 面包多链接未回填 | 弹药库 6 处占位无法发出 | fill_links 一条命令，等链接 |
| 5 | legacy 管线的 data/ 路径已随案例3 迁移，若重启需重指 | 只影响 legacy 重启 | 已写入 legacy README 重启注意 |
| 6 | 剪映线"AI 样片生成"能力缺口（可灵/即梦调用） | 案例内临时工具先顶着 | Rule of Two 后评估上货架 |
| 7 | GLM 季付到期（约 2026-12）前项目收入须转正 | ¥118/月 自付目标 | cockpit/ledger 盯 |
| 8 | pyproject ruff 配置为旧式顶层键（deprecation 警告，功能不受影响） | 无 | 下次动 pyproject 时顺手迁移到 [tool.ruff.lint] |
| 9 | build_pdfs.py（并行会话产物）1 处 UP031 percent-format | 无 | 不动他人风格，留给其作者 |
| 10 | pulse 计划任务待 BOSS 亲自注册（持久化机制 AI 不代办，命令在 pulse/README.md） | 未注册前心跳靠手动 | 周五前注册 |
| 11 | Server酱 5 条/天与排队号共享，可能互相挤占 | 晨报偶发静默（journal 仍落盘） | 观察 1 周，挤占频繁则切 pushplus |
