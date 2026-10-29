# pulse — 确定性每日心跳

## 部署事实与边界

**部署尚未验证；本机未找到任务。** 这是已有检查结论，不是此次实施执行了任务查询。此次仅修改代码并离线测试，未注册、删除或触发真实计划任务，未读取真实凭证或发送通知。

本模块是独立的 Python / Windows 每日心跳，**与周五 AI cron 独立**，不共享运行回执。代码存在、安装命令返回成功或 journal 存在，都不能证明通知已送达，更不代表自动永续。任务是否能找到 Python、账户是否登录、网络与通道是否可用，仍需另行授权后验证。没有修改账号权限、商业状态或 L3 授权。

## 输入与提醒规则

- 唯一行动、截止与完成回执源：`cockpit/actions.csv`。字段为 `action_id,venture,status,owner,opened_on,due_on,next_action,evidence,decision_scope`；`action_id` 唯一，`opened_on` 为 `YYYY-MM-DD`，`due_on` 可空，否则同样必须是合法日期。
- `status` 仅允许 `pending/blocked/done/cancelled`；只提醒前两种中明确 `due_on <= today + 14 天` 的行动。没有下界，逾期会持续提醒；不从正文中的日期猜截止，也不读取 `98-debt` 或 Cookie 凭证。
- `venture` 可为 `governance`；否则必须匹配现有 `ventures/<案例>/venture.md`。跳过 `_template`、未知案例、关闭案例以及无法可靠识别状态的案例。
- 案例状态只取 `venture.md` 开头 YAML front matter 或首个 fenced YAML 块的顶层 `status`。支持标准状态枚举、单/双引号及行尾注释，不从正文或嵌套键猜测；重复字段、别名、多行状态或未支持的写法按无效元数据跳过并提示。
- 今日事项：按截止日排序的逾期/到期行动在前，`cockpit/status.md` 的未勾选周焦点在后，合计最多 3 项。另列完整到期清单；周五不会插入更高优先级的虚构截止。
- 无效 CSV、坏日期、坏状态、重复 ID、未知案例等仅产生固定安全警告码，不回显坏输入。journal 中非 `YYYY-MM-DD.md` 文件或未来日期会跳过并提示。
- 本模块不更新行动状态；生成的 journal 不是完成证据。实际发送尝试前更新当天生成简报，显式重试也重新从输入生成。

## 运行与送达回执

直接预览（不写任何文件、不加载推送配置、不访问网络）：

```sh
python -B capabilities/pulse/heartbeat.py --dry-run
```

常规入口 `run_heartbeat.bat` 默认使用 `python`，可通过 `PYTHON_EXE` 指定解释器的完整路径（只填可执行文件，不带额外参数）。路径相对脚本所在目录解析，支持含空格路径；同步等待，返回 Python 的退出码。普通运行的脱敏 stdout/stderr 追加至 `.cache/pulse/pulse.log`；`--dry-run` 直接显示预览，不创建日志。日志需按本机策略人工归档，不保证无限运行。

常规发送会读取 `.cache/pulse_push.json`；仅当文件不存在时，回退到仓库同级 `xianyu/push.json`。支持 `serverchan/pushplus/wecom`，配置含 `provider` 和 `key`。专属配置损坏时不静默回退，不在日志中输出配置内容。导入模块与 dry-run 都不加载配置。缺配置返回非零并保存失败状态，不会发送 HTTP。

持久化控制文件：

- `.cache/pulse_last_run.json`：原子替换，保存开始/结束时间、日期、状态、送达判定、安全错误码和输入警告码；不保存标题、正文、URL、token 或异常原文。
- 状态为 `running/succeeded/failed/delivery_unknown`；发送前先持久化 `delivery=unknown`，只有有效的服务商成功回执才标记 `succeeded/delivered`。这里的成功是服务商接受，不等于人已阅读。
- 同日成功重跑不发送，即使传 `--retry` 也不重复发送。同日已知失败默认拒绝重发；人工修复后可显式运行 `python -B capabilities/pulse/heartbeat.py --retry`。跨日已知失败可重新尝试。
- 超时、HTTP 异常、回执格式不明或发送中断一律视为**送达未知**，返回非零，要求人工核对服务商与接收端；跨日及 `--retry` 也不能绕过。不能把网络异常当作“肯定没发”。
- `.cache/pulse.lock` 用排他创建避免并发消费；不自动抢占或清理遗留锁。锁冲突返回非零且不覆盖持锁者的状态。请人工确认没有在运行的进程、核对送达结果、保留回执备份后，再决定如何恢复；勿直接反复重试或删状态。
- 状态损坏时落盘脱敏的未知状态并阻止发送。文件系统无法写入时返回非零；无法保证落盘的机器故障必须人工检查。若发送后最终状态写入失败，发送前的未知回执仍用于阻止重复。

## 安装脚本（本次未执行）

`安装每日心跳.bat`没有硬编码盘符。保留资源管理器双击入口，双击后须明确选择Y才创建本机每日08:30的`incubator_pulse`；选N或关闭不安装。也支持本人明确传`--install`。不覆盖已有任务、不提权、不自动触发任务。确认前先核对Python解释器。尚未验证真实注册、账户环境及通知送达，不宣称已经部署。

## 离线验证

```sh
python -B -m pytest -p no:cacheprovider tests/test_pulse.py tests/test_pulse_runtime.py
```

测试输入、配置、状态、日志均使用临时目录，HTTP 使用 mocks，禁止真实网络。批处理做编码/换行与路径静态检查，并在 Windows 临时目录用假 heartbeat 验证含空格路径、同步退出码、日志追加及 dry-run 不落盘；真实定时任务和通知链路未测试。
