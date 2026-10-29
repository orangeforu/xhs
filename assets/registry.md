# 资产登记表（registry · 周五复盘查健康 · 值不进 git）

> 本表登记资产及历史观察，不作为实时健康面板。旧记录中的在线/有效只对应当时，当前核验结果看[cockpit/status.md](../cockpit/status.md)，动作回执看[actions.csv](../cockpit/actions.csv)。本轮未重验Cookie或外仓服务。

| 资产 | 类型 | 状态 | 到期/风险 | 使用方 | 备注 |
|---|---|---|---|---|---|
| 小红书 PC 端 Cookie | 凭证(.cache/xhs_pc_cookie.json) | 🟢 2026-10-15 扫码 | 通常数周，失效自动重扫 | xhs_crawler | 账号：橘子味悠米 |
| 小红书创作者端 Cookie | 凭证(.cache/xhs_creator_cookie.json) | ❓ 待验证 | — | 案例3 遗产脚本 | 长期未用，用前先跑 xhs_auth_helper --creator |
| 小红书账号（867粉，橘子味悠米） | 账号 | ⚪ 封存（不注销） | 复活需 L3 | 案例3（封存） | BOSS 实名 |
| 剪映创作者账号 | 账号 | 待核验；见[cockpit状态](../cockpit/status.md) | 不默认具备发布或付费权限 | 案例2 | 七项准入及工单回执只维护[actions](../cockpit/actions.csv)；账号身份变更仍需L3 |
| 面包多店铺 | 渠道 | 🟡 已上架（购买链接未回填） | — | 案例1 | BOSS 实名；链接拿到跑 fill_links |
| 闲鱼（淘宝账号） | 渠道 | 🟢 共享排队号生意账号 | 平台风控敏感 | 案例1/2 + 兄弟仓库 | publisher/机器人已打通 |
| Gumroad | 渠道 | 🔲 未提审 | — | 案例1 EN 线 | 需 BOSS 注册操作 |
| LLM API（DeepSeek） | API key(.env) | 🟢 | 余额自查 | 各案例质检/内容 | — |
| GLM Coding Plan | 订阅 | 🟢 本季度有效 | **到期即项目自付目标** | 开发本身 | ¥118/月 固定成本 |
| 思源黑体 | 素材 | 🟢 | — | 图片渲染 | capabilities/_shared/fonts |
| Server酱微信通道 | 通道 | 🟢 复用 xianyu/push.json（不复制密钥） | **免费 5 条/天两仓共享** | pulse 晨报 1 条/天 | 升级候选 pushplus |
| 兄弟仓库 xianyu（排队号） | 外部资产 | 🟢 webapp 8010 在线 | 有自己的 AGENTS 协议 | xianyu_ops 适配 | 永不合并（已定） |
