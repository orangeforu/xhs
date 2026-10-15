# pulse — 执行模块（孵化台的生命力/心跳）

> 状态：🟢 v1 | 上架依据：**BOSS 直接授权（委托人特权）**，Rule of Two 豁免并记录在案（2026-10-15）
> 回应 BOSS 的"生命力"比喻：常驻器官=能力层，晨报=起床清单，journal=作息记录，周五复盘=体检。

## 是什么

每日 08:30 心跳：扫战局（cockpit/案例/98-debt/Cookie 鲜度）→ 生成**今日三件事+预警** →
落 `cockpit/journal/YYYY-MM-DD.md` → 推微信（Server酱）。

v1 原则：**纯确定性规则，不调 LLM**（可靠 > 聪明）。v2 候选：LLM 生成个性化简报、
每周二/四自动跑竞品监控（L0）、晚间收盘打卡。

## 组成

| 文件 | 作用 |
|---|---|
| `heartbeat.py` | 晨间作战简报生成器（journal 落盘 + 推送） |
| `push.py` | Server酱客户端（复用兄弟仓库 push.json 既有通道，不复制密钥） |
| `run_heartbeat.bat` | 计划任务入口（NO_PROXY 绕死代理） |

## 已知约束（重要）

- **Server酱免费额度 5 条/天，与排队号生意共享**——孵化台只发每日 1 条；额度被排队号
  报警挤占时推送失败但 **journal 照常落盘**（心跳不因通道死，次日自动恢复）。
  通道升级候选：pushplus（免费额度更高，push.json 的 provider 字段已支持三选一）
- 手动触发：`python capabilities/pulse/heartbeat.py`

## 注册每日心跳（计划任务）

> 需 BOSS 亲自执行（持久化机制，AI 不代注册）：

```
schtasks /Create /TN "incubator_pulse" /TR "D:\SoftWare\User\Vs\xhs\capabilities\pulse\run_heartbeat.bat" /SC DAILY /ST 08:30 /F
```

删除：`schtasks /Delete /TN "incubator_pulse" /F`。改时间：删了重建换 /ST。
