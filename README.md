# XHS AI Content Generator

小红书情感账号 AI 内容创作系统。自动生成符合人设的图文笔记（封面 + 内页 + 审核 + 预设评论），配合 Streamlit 工作台完成审核-发布-采集全流程闭环。

## 功能

- **AI 笔记生成** - 基于选题池自动生成 500-800 字情感笔记，支持 4 种标题公式（问句式/概念解读式/观点冲击式/方法承诺式）
- **结构化审核** - LLM 按 15 项标准打分（S/A/B/C），C 级自动重写
- **封面生成** - 模板大字报封面为主（7 种配色主题，Pillow 渲染），AI 绘画可选（CTR 偏低，非主方案）
- **内页渲染** - 自动分页、居中排版、渐变背景、加粗支持
- **预设评论** - 生成 5-8 条拟真评论，发布后贴入评论区引导互动
- **自动发布** - 集成 spider_xhs，approved 笔记自动发布到小红书创作者平台，话题标签解析为真链接进流量池
- **数据采集** - 自动采集已发布笔记互动数据（赞/藏/评），更新 performance.json + S/A/B/C 评级
- **竞品分析** - 采集情感赛道爆款，分析标题公式/标签，反哺选题池
- **废笔记健康检查** - 三道防线拦截 LLM 思考链泄漏的废笔记（生成门禁 + 发布校验 + UI 标记）
- **熔断机制** - 连续 3 篇 C 级自动暂停发布
- **Streamlit 工作台** - 6 个 tab：待审核 / 选题池 / 创作标准 / 数据复盘 / 内容日历 / 一键发布助手

## 快速开始

### 环境要求

- Python 3.13+
- Node.js（spider_xhs 子模块用其生成请求签名）
- 思源黑体字体文件（`assets/fonts/NotoSansSC-Regular.ttf` 和 `NotoSansSC-Bold.ttf`）

### 安装

```bash
git clone https://github.com/orangeforu/xhs.git
cd xhs
pip install -r requirements.txt
git submodule update --init --recursive   # 拉取 spider_xhs 子模块
```

### 配置

```bash
cp .env.example .env
# 编辑 .env，填写你的 LLM API Key
```

主要环境变量：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `LLM_API_KEY` | LLM API 密钥（必填） | - |
| `LLM_BASE_URL` | API 地址 | `https://api.moonshot.cn/v1` |
| `LLM_MODEL` | 模型名称 | `kimi-k2-6` |
| `IMAGE_PROVIDER` | 图片后端 | `pollinations` |
| `IMAGE_API_KEY` | DALL-E API 密钥（可选） | - |
| `FOLLOWERS_TARGET` | 粉丝目标 | `1400` |
| `FOLLOWERS_CURRENT` | 当前粉丝数 | `900` |

### 使用

```bash
# 启动交互式菜单（推荐）
python start.py

# 或使用 Makefile
make start
```

交互式菜单提供：查看选题池 -> 生成笔记 -> 批量生成 -> 审核工作台，全程引导操作。

也可以直接使用 CLI：

```bash
python pipeline.py --list                           # 列出选题
python pipeline.py --index 0                        # 按编号生成
python pipeline.py --batch --max 3                  # 批量生成
streamlit run app.py                                # 审核工作台（6 个 tab）

# 发布与数据采集（spider_xhs 集成，首次需小红书 APP 扫码登录）
python scripts/auto_publish.py --dry-run            # 预览待发布笔记（不登录、不发布）
python scripts/auto_publish.py --limit 3            # 发布 approved/ 笔记到小红书
python scripts/fetch_performance.py                 # 采集互动数据，更新 performance.json
python scripts/competitor_analysis.py --save        # 竞品爆款分析，加入选题池
```

## 项目结构

```
├── start.py                # 交互式菜单入口（推荐）
├── pipeline.py             # CLI 内容生成流水线
├── generate_topics.py      # 选题池生成（情绪光谱均衡 + 搜索型问句配额）
├── app.py                  # Streamlit 审核工作台
├── core/
│   ├── config.py           # 配置、路径、JSON 读写（原子写 + 跨平台锁）、日志
│   ├── writer.py           # 底层 LLM 调用（OpenAI 兼容 + 重试 + reasoning 回退）
│   ├── agents/             # Multi-Agent 编排（7 个专家 + MessageBus）
│   │   ├── orchestrator.py     # 创作编排器
│   │   ├── chief_editor.py     # 主编决策（≤5 轮迭代 + 标签/健康门禁）
│   │   ├── emotional_writer.py # 情感写手（4 标题公式 / 7 结构）
│   │   ├── cover_designer.py   # 封面设计（配色 + AI 绘画 prompt）
│   │   ├── layout_artist.py    # 内页排版
│   │   ├── content_editor.py   # 内容审核（S/A/B/C 评级）
│   │   └── community_manager.py# 预设评论
│   ├── image/              # 图片渲染子包
│   │   ├── cover.py            # 封面生成（模板合成 + AI 绘画）
│   │   ├── inner_page.py       # 内页分页渲染
│   │   └── render.py           # 共享渲染工具（字体/渐变/排版）
│   ├── image_generator.py  # 向后兼容 re-export 入口
│   ├── topic_selector.py   # 选题智能推荐
│   ├── publish_helpers.py  # 发布数据/评级/熔断/标签真链接解析
│   └── utils.py            # 标签合规兜底 + 废笔记健康检查
├── scripts/                # spider_xhs 集成脚本
│   ├── auto_publish.py         # 自动发布到小红书
│   ├── fetch_performance.py    # 采集互动数据 + 熔断
│   ├── competitor_analysis.py  # 竞品爆款分析反哺选题
│   └── xhs_auth_helper.py      # Cookie 持久化登录
├── spider_xhs/             # 小红书 API 子模块（cv-cat/Spider_XHS）
├── tabs/                   # Streamlit 工作台分页（审核/发布/选题/看板/日历/标准）
├── prompts/                # Prompt 模板（.md）
├── data/
│   ├── topics.json         # 选题池
│   ├── performance.json    # 发布数据追踪
│   └── agent_memory/       # Agent 跨会话记忆
├── docs_agent/
│   ├── pending/              # 新生成未审核
│   ├── approved/             # 已审核通过，待发布
│   ├── published/            # 已发布，待录入数据
│   └── archived/             # 已发布且已录入数据
└── assets/
    └── fonts/              # 思源黑体字体文件
```

## 工作流程

1. 在 `data/topics.json` 中定义选题（话题、标题公式、互动目标、角度）
2. 运行 `python pipeline.py --index N` 生成笔记
3. 系统自动完成：AI 写作 -> 封面图 -> 内页图 -> LLM 审核（C 级自动重写）-> 废笔记健康检查 -> 生成预设评论
4. 在 Streamlit 工作台审核「通过」-> `approved/`
5. 自动发布：`auto_publish.py` 或 🚀tab 发布到小红书（标签解析为真话题链接）-> `published/`
6. 数据采集：`fetch_performance.py` 自动采集互动数据，更新 performance.json + 评级 + 熔断检查
7. 竞品分析：`competitor_analysis.py` 采集爆款反哺选题池，形成闭环

> 审核通过 ≠ 已发布。只有自动发布或用户确认"我发布了"才迁到 `published/`。

## 评分标准

| 等级 | 点赞 | 说明 |
|------|------|------|
| S | >1500 | 爆款 |
| A | 800-1500 | 优质 |
| B | 200-800 | 合格 |
| C | <200 | 不合格 |

连续 3 篇 C 级触发熔断，暂停发布并复盘。

## License

MIT
