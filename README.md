# XHS AI Content Generator

小红书情感账号 AI 内容创作系统。自动生成符合人设的图文笔记（封面 + 内页 + 审核 + 预设评论），配合 Streamlit 工作台完成审核-发布全流程。

## 功能

- **AI 笔记生成** — 基于选题池自动生成 500-800 字情感笔记，支持 4 种标题公式（问句式/概念解读式/观点冲击式/方法承诺式）
- **结构化审核** — LLM 按 15 项标准打分（S/A/B/C），C 级自动重写
- **封面生成** — Pollinations / DALL-E 多后端 AI 绘画 + 5 种模板风格 fallback
- **内页渲染** — 自动分页、居中排版、渐变背景、加粗支持
- **预设评论** — 生成 5-8 条拟真评论，发布后手动贴入评论区引导互动
- **Streamlit 工作台** — 待审核笔记预览、一键发布/打回、选题池管理、数据复盘看板
- **熔断机制** — 连续 3 篇 C 级自动暂停发布

## 快速开始

### 环境要求

- Python 3.13+
- 思源黑体字体文件（`assets/fonts/NotoSansSC-Regular.ttf` 和 `NotoSansSC-Bold.ttf`）

### 安装

```bash
git clone https://github.com/orangeforu/xhs.git
cd xhs
pip install -r requirements.txt
```

### 配置

```bash
cp .env.example .env
# 编辑 .env，填写你的 LLM API Key
```

主要环境变量：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `LLM_API_KEY` | LLM API 密钥（必填） | — |
| `LLM_BASE_URL` | API 地址 | `https://api.moonshot.cn/v1` |
| `LLM_MODEL` | 模型名称 | `kimi-k2-6` |
| `IMAGE_PROVIDER` | 图片后端 | `pollinations` |
| `IMAGE_API_KEY` | DALL-E API 密钥（可选） | — |
| `FOLLOWERS_TARGET` | 粉丝目标 | `1400` |
| `FOLLOWERS_CURRENT` | 当前粉丝数 | `900` |

### 使用

```bash
# 启动交互式菜单（推荐）
python start.py

# 或使用 Makefile
make start
```

交互式菜单提供：查看选题池 → 生成笔记 → 批量生成 → 审核工作台，全程引导操作。

也可以直接使用 CLI：

```bash
python pipeline.py --list                           # 列出选题
python pipeline.py --index 0                        # 按编号生成
python pipeline.py --batch --max 3                  # 批量生成
streamlit run app.py                                # 审核工作台
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
│   │   ├── chief_editor.py     # 主编决策（≤5 轮迭代）
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
│   ├── publish_helpers.py  # 发布数据/评级/熔断
│   └── utils.py            # 标签合规兜底等工具
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
3. 系统自动完成：AI 写作 → 提取封面信息 → 生成封面图 → 生成内页图 → LLM 审核 → C 级自动重写 → 生成预设评论
4. 在 Streamlit 工作台中审核、修改、发布
5. 发布后在数据复盘 Tab 录入点赞/收藏/评论数据，系统自动评级

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
