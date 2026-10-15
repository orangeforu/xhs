> ⚠️ 历史文档（2026-10-15 架构改造前写成）：文中 scripts/ products/ docs/ 等路径为改造前位置，现行结构见根 CLAUDE.md。
# 上传操作指南（Gumroad ×2 + 面包多 ×1）

> 生成日期：2026-09-29。平台 UI 会改版，按钮文字若有出入按流程找对应位置即可。
> 全程约 40 分钟。三个都交审后就可以去干别的，审核期间把 Reddit 帖预填好。

## 开始前的文件清单（都在 `products/dist/`）

| 文件 | 用途 |
|---|---|
| `9to5-kit-en-bundle.zip` (117KB) | Gumroad $9 全套 |
| `workflow-01-free-sample-en.pdf` (32KB) | Gumroad 免费样张 |
| `cover-en-1280x720.png` / `thumb-en-600x600.png` | Gumroad 封面/缩略图 |
| `dagongren-ai-kit-cn.pdf` (191KB) | 面包多中文全套 |
| `cover-cn-800x800.png` | 面包多封面（也用作小红书笔记配图） |

文案来源：`products/ai-office-workflows/listing-gumroad.md` 和 `listing-mianbaoduo.md`

---

## A. Gumroad 产品 1：$9 全套（约 15 分钟）

1. 登录 gumroad.com → 顶部 **Products** → 右上 **New product**
2. 类型选 **Digital product**
3. 基本信息页：
   - **Name**：`The 9-to-5 AI Workflow Kit`（这是结账页短名）
   - **Price**：`9` USD
4. 进入产品编辑页，逐区块填：
   - **Content**（交付内容）：Add file / 拖入 → 选 `9to5-kit-en-bundle.zip`
   - **Cover**（封面 1280×720）：上传 `cover-en-1280x720.png`
   - **Thumbnail**（缩略图 600×600）：上传 `thumb-en-600x600.png`
   - **Description**（结账页描述）：打开 `listing-gumroad.md`，把代码块里的英文描述整段复制粘贴（Gumroad 编辑器是富文本，保留段落换行即可，不用管 markdown 符号）
5. Settings 里检查两处：
   - **Enable ratings**：打开（让买家能留评价，信任背书）
   - 成人内容：No
6. **payout 设置：全部跳过**（验证优先方案）。它会在后台黄条提醒"complete payout"——无视。若出现"不配 payout 不让发布"的硬拦截（正常情况不会），停下来回来找我
7. 右上 **Save** → 状态显示 **In review**（人工审核，几小时到 2 天）
8. 过审后：**Share** → 复制产品链接（形如 `你的域名.gumroad.com/l/xxxxx`）→ 记下来，Reddit 帖要用

## B. Gumroad 产品 2：免费样张（约 8 分钟）

1. 再建一个 **New product → Digital product**
2. **Name**：`Free Sample — The Weekly Update Workflow (9-to-5 AI Kit)`
3. **定价方式：选 "Pay what you want"（自定义价格），最低金额填 `0`** ← 关键一步，不是把价格设成 0
4. Content：上传 `workflow-01-free-sample-en.pdf`
5. 封面：用 `thumb-en-600x600.png`
6. 描述写三行即可：
   ```
   The free sample from The 9-to-5 AI Workflow Kit: the weekly update
   workflow (40 min → 10 min) with its 60-second audit.

   The full kit has 9 more — meeting notes, status emails, document
   summaries, spreadsheets, chase-ups, PPT outlines, resume bullets,
   skip-level prep, client triage.
   ```
   （产品 1 过审后，回到这里在末尾加一行 `Full kit: <产品1链接>`）
7. Save → 同样进审核

### 过审后的自测（重要）

用你自己的另一个邮箱，把**免费样张**下一单（$0 订单，无害）：
- [ ] 收到购买确认邮件
- [ ] 下载链接能打开、PDF 正常
- [ ] （这就把"购买→交付"链路验证完了）

⚠️ $9 产品**不要**自己下单测试（新账号自买付费品是风控红旗，免费品没事）。

## C. 面包多：中文版（约 15 分钟）

1. **mianbaoduo.com** → 注册（手机号或微信）
2. **实名认证**：上传身份证正反面 + 人脸验证。个人身份即可，不需要营业执照。⚠️ 不实名 = 收不了款，这步不能跳
3. 找 **发布作品 / 出售** 入口 → 类型选 **数字资料 / 虚拟商品**
4. 逐项填（全部从 `listing-mianbaoduo.md` 复制）：
   - 标题：`打工人AI提效工作流包｜10个提示词+防AI编造核查清单（周报/纪要/汇报/简历）`
   - 封面：`cover-cn-800x800.png`
   - 描述：抄 listing 里的描述块
   - 上传文件：`dagongren-ai-kit-cn.pdf`
   - 价格：`19.9`（页面如有"原价"栏填 `29.9` 做划线价）
   - 分类：效率/职场/模板类（按站内可选类目就近选）
5. 提交审核（面包多较快，几小时到 1 天）
6. 过审后复制购买链接 → **记下来。⚠️ 此链接只能出现在私信和微信里，绝不能出现在小红书笔记/评论区/简介（站外导流红线）**

## D. 小红书引流笔记（面包多过审后发）

这篇是手写引流笔记，**不走 pipeline**，直接在小红书 App 手动发：

1. 打开 `products/ai-office-workflows/launch-xhs-note.md`：
   - 把 `✍️【真人改写槽位1】` 换成你的真实经历（真实任务 + 真实耗时）
   - 正文部分整段复制
2. 配图：**第 1 张用 `cover-cn-800x800.png`**，第 2-3 张可截 PDF 内页（提示词块那两页最合适）
3. 发布设置：**勾选「笔记含 AI 辅助创作」**（正文已含 AI 辅助说明）
4. 发布后立刻发一条**置顶评论**（二选一，均不带链接）：
   - 无店铺：`完整版 10 个工作流 + 防坑清单整理好了，想要的扣【想要】，私信发你` → 私信里手动发面包多链接（一对一私信可以，不能群发）
   - 若已开小红书店铺：`完整版在主页店铺` + 笔记挂商品链接（平台内闭环，最稳）
5. 发布后 1 小时守评论区，真人逐条回复

## 交付链路验证总表（全部打勾才算"开张"）

- [ ] Gumroad $9 产品过审、链接可打开
- [ ] Gumroad 样张过审、自测 $0 下单 → 邮件 → 下载全通
- [ ] 面包多过审、实名收款可用
- [ ] 小红书笔记已发、置顶评论已发
- [ ] Reddit 账号开始养（每天在 r/productivity 评论 2-3 条，第三天发 `launch-reddit.md` 的帖子）

之后就是等数据。4 周/10 单对账，规则已写在 listing 和调研文档里。
