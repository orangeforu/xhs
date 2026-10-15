# 产品官网（Paddle 审核用）

三页静态站，零依赖、零构建、零跟踪。审核要求（产品页 + 定价页 + 隐私政策 + 服务条款 + 联系方式）全部覆盖。

```
products/website/
  index.html          # 产品主页（含定价区 + FAQ）
  privacy.html        # 隐私政策
  terms.html          # 服务条款
  sample/workflow-01.md  # 免费样张
```

## 上线前三处必改（搜 `TODO(BOSS)`）

| 位置 | 改什么 |
|---|---|
| `index.html` 两个 `href="#"` / `#pricing` 的购买按钮 | 换成 Paddle 过审后生成的 checkout 链接 |
| `index.html` 页脚 + `privacy.html` + `terms.html` 的 `support@example.com` | 换成真实联系邮箱（Paddle 审核要求站上有可联系邮箱） |
| （可选）样张链接 | 正式版可换成排版后的 PDF |

## 部署（三选一，都是免费的，5 分钟）

1. **Netlify Drop（最快）**：app.netlify.com/drop → 把 `products/website/` 整个文件夹拖进去 → 得到 `xxx.netlify.app` 子域名，可直接提审
2. **Vercel**：vercel.com/new → import 本仓库 → root directory 设为 `products/website`
3. **GitHub Pages**：本仓库 Settings → Pages → 选分支 + `/products/website` 目录

**域名**：先用免费子域名提审（社区实测可过）；有了首批销量再花 $10/年买个正经域名（如 `95aikit.com`），Vercel/Netlify 绑定即可。

## Paddle 提审要点

- 注册：paddle.com 卖家入驻，**护照**即可（个人）
- 网站审核看的是"完整真实性"：产品说明、定价、隐私、条款、联系方式齐全 → 本站已备
- 产品过审后，在 Paddle 后台建 Product（$9 一次性）→ 拿到 checkout 链接 → 回填本站两处按钮
- 提现：SWIFT 电汇到国内银行卡（~$15/笔）→ **攒到 $200+ 再提**
- 若拒审（小概率）：补材料重提，或切备选 Creem（creem.io，对个人更宽松，先小额自购测试提现链路）

## 上线后自测清单

- [ ] 三个页面全部能打开、无死链
- [ ] 用自己的卡真实购买一次（Paddle 沙盒或正式小额）→ 全链路：付款 → 邮件交付 → 下载
- [ ] 手机端打开不破版（本站已做响应式，抽查即可）
