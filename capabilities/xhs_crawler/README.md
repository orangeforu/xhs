# xhs_crawler — 小红书站内采集

> 状态：🟢 | Cookie：PC 端已持久化（仓库根 .cache/xhs_pc_cookie.json，2026-10-15 扫码）| 依赖：Node.js（根 node_modules/crypto-js）

## 入口

- `verify_search.py`：站内搜索实测（关键词×排序批量采集，互动数据+详情价格信号提取）。原 verify_xhs_jianying，2026-10 剪映调研中诞生，已服务调研+监控两场景
- `xhs_auth_helper.py`：登录与 Cookie 管理（PC/创作者双端，QR 存大图自动弹出）

## 调用

```bash
python capabilities/xhs_crawler/verify_search.py   # 默认四组搜索，改脚本内 SEARCHES 配置
```

## 已知坑（踩过的）

- 系统代理死掉（127.0.0.1:33210 不在）会让 requests 全挂，伪装成 Cookie 失效——启动前 NO_PROXY=* 或修代理
- 详情接口必须带搜索结果里的 xsec_token，否则 data 空
- spider_xhs 源码在 vendor/（vendored，2026-09 弃子模块），签名依赖 node crypto-js
