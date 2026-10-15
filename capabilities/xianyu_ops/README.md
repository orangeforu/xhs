# xianyu_ops — 闲鱼能力适配器

> 状态：🟢 | 实体在兄弟仓库 `D:\SoftWare\User\Vs\xianyu`（排队号生意，有自己的 AGENTS.md 协议——改动须遵循其流程）
> 本目录只放对接知识，不含代码。两仓库各自演进，永不合并（已定决策）。

## 可借用的实体（在兄弟仓库）

| 实体 | 用法 | 注意 |
|---|---|---|
| `publisher.py` | CDP 驱动 Chrome 填闲鱼发布表单，人扫码确认（L2） | 系统代理死时 CDP 连不上——它自带 ProxyHandler({}) 绕过 |
| 闲鱼机器人（vendor/XianyuAutoAgent） | 7×24 AI 客服，prompts 多产品分支（2026-10-09 已加 AI 资料包分支） | 改话术=动其在线业务，走其 AGENTS.md；重启用 start_bot_noproxy.bat（NO_PROXY） |
| `cdp_grab_cookie.py` | 从调试 Chrome 抓 Cookie 回写机器人 .env | 需人在 Chrome 里过滑块 |
| watcher/微信推送 | 事件→微信提醒 | 借鉴形态：未来孵化台的"连接器"原型 |

## 踩过的坑

- 机器人连续重启会触发闲鱼风控 RGV587——冷却 10 分钟+过滑块（sg cookie）后恢复
- 发布二维码没人扫=整条管线白干——L2 任务必须有"人真的确认了"的回执（案例1 的教训）
