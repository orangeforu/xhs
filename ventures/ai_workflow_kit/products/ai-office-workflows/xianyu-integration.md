# 闲鱼项目复用方案（兄弟仓库 D:\SoftWare\User\Vs\xianyu，2026-10-09 评估）

> 那边是**在跑的排队号生意**（webapp 8010 在线、7×24 机器人、看门狗），有自己的
> AGENTS.md 协议（先方案后干/改后冒烟/话术属红线域）。本文件在 xhs 侧准备好一切，
> 把对那边仓库的侵入压到最小。

## 复用评估

| 组件 | 结论 |
|---|---|
| `publisher.py`（CDP 自动发布器） | ✅ **零改动直接用**：通用 CLI，复用其已登录 Chrome profile，人工过滑块/扫码 |
| `vendor/XianyuAutoAgent`（7×24 AI 客服） | ⚠️ 满脑子排队号话术——我们的买家来问会被"到店叫号入座"糊弄，**必须处理**（见两路线） |
| watcher / webapp / 调度台 | ❌ 排队号专用，不碰 |

## 路线 A：同账号混挂（发布最快，但要动他们的机器人）

1. 用 publisher 直接发我们的 listing（命令见下）
2. 按他们 AGENTS.md 协议给机器人 prompts 加"第二商品分支"（草稿见下，
   classify 不用动，default/price/tech 三个 prompt 各加一段）
3. 他们的流程：写方案到 docs/01-plans → 改 → `python tests/smoke.py` → 重启 bot → 实弹验证

**代价**：动在跑的业务；好处：零新账号，发布今天就能完成。

## 路线 B：小号隔离（最干净，推荐）

1. 复制 `publisher.py` 到 xhs 侧（`scripts/xianyu_publisher.py`），改 `PROFILE`
   指向 `D:\SoftWare\User\Vs\xhs\.chrome_profile_xhs`
2. 首次扫码登录小号，之后发布同路线 A
3. 排队号机器人零影响；我们的买家如果量小，客服可以人工回（初期单量下人工完全够）

**代价**：需要一个第二淘宝/闲鱼账号 + 首次扫码；好处：两个生意互不干扰。

## 发布命令（两条路线通用；路线 B 换脚本路径）

```bash
python D:/SoftWare/User/Vs/xianyu/publisher.py \
  --title "AI提示词工作流资料包打工人周报纪要汇报提效模板防AI编造清单" \
  --body "$(cat products/ai-office-workflows/xianyu-body.txt)" \
  --price 15.9 \
  --images "D:\SoftWare\User\Vs\xhs\products\dist\cover-cn-800x800.png"
```

（多行描述放 `xianyu-body.txt`，内容取 `listing-xianyu.md` 描述块。）

## 机器人话术分支草稿（路线 A 用，按其 default_prompt.txt 风格：短句/业务事实/禁语）

```
【第二商品：AI资料包分支】（若买家咨询的是"AI提示词/工作流/资料包/模板"，非排队号）
1. 商品：10个职场AI工作流PDF（周报/纪要/汇报/简历等），¥15.9买断
2. 交付：拍下后闲鱼聊天直接发PDF文件，秒发
3. 售后：觉得不值说一声直接退，不用理由
4. 禁语：不出现"网盘/链接/加微信/站外"，交付只在闲鱼聊天内完成
5. 问"有用吗/值吗"：回"10条每条带60秒核查清单，用着不值直接退"
6. 此类咨询不走排队号话术，不确定就回"我确认下马上答复你"
```

## 决策点（待 BOSS）

- 同账号（路线 A，快但要动他们机器人）还是小号（路线 B，干净要多一次扫码）？
- 若路线 B 且无小号：路线 A 是唯一路径，机器人分支改造必须做
