# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 常用命令

```bash
# 交互式菜单（推荐入口）
python start.py

# CLI 直接操作
python pipeline.py --list                           # 列出选题池
python pipeline.py --index N                        # 按编号生成单篇
python pipeline.py --batch --max 3                  # 批量生成
streamlit run app.py                                # 启动审核工作台

# 代码质量
pytest                                              # 运行测试
black .                                             # 格式化
ruff check .                                        # Lint
mypy core/                                          # 类型检查
```

## 项目架构

小红书情感账号 AI 内容创作系统。自动生成图文笔记（封面 + 内页 + 审核 + 预设评论），配合 Streamlit 工作台完成审核-发布全流程。

### Multi-Agent 创作流水线

核心创作流程在 `core/agents/orchestrator.py` 中编排，7 个专家 Agent 通过 **MessageBus**（发布/订阅）协作：

```
TopicStrategist → EmotionalWriter → (CoverDesigner ∥ LayoutArtist ∥ ContentEditor)
                                                          ↓
                              ChiefEditor ← 决策 ← 审核报告
                                                          ↓
                                              CommunityManager（预设评论）
```

- **TopicStrategist**：增强选题 brief，补充角度和叙事策略。
- **EmotionalWriter**：LLM 写作，支持 4 种标题公式（问句式/概念解读式/观点冲击式/方法承诺式），按公式注入特化指令。
- **CoverDesigner**：提取封面信息（标题/小字/AI 绘画 prompt/视觉风格）。
- **LayoutArtist**：调用 `core/image_generator.py` 生成内页分页图。
- **ContentEditor**：LLM 审核，输出结构化报告（等级 S/A/B/C、问题列表、建议）。
- **ChiefEditor**：主编决策，最多 **5 轮迭代**。决策逻辑：
  - A 级直接通过；B 级 + issues ≤ 2 可通过。
  - 连续 3 轮同级（A/B）强制通过，防止审核死循环。
  - 5 轮后仍不达标则 **放弃**（`status: abandoned`）。
- **CommunityManager**：生成 5-8 条拟真预设评论。

每个 Agent 通过 `AgentMemory`（`core/agents/memory.py`）持久化跨会话记忆到 `data/agent_memory/`，记录成功/失败模式。

### 封面与内页生成

`core/image_generator.py` 负责全部图片渲染：

- **封面双方案**：
  1. **AI 绘画**：默认使用 Pollinations（免费），可选 DALL-E（需 `IMAGE_API_KEY`）。prompt 经过 `_sanitize_prompt` 自动替换阴冷关键词并追加温暖 safeguard。
  2. **模板合成**：纯 Pillow 代码渲染，7 种配色主题（`warm_grey`/`twilight`/`crimson`/`mist`/`cool`/`warm`/`blank`），动态计算字号防溢出。
- **内页分页**：先由 `_paginate_blocks` 计算排版分页（不渲染），得到准确总页数后多线程（`max_workers=4`）渲染。每页含渐变背景、视觉锚点、金句高亮块、页码。

### 关键兼容层

`pipeline.py` 保留了大量向后兼容的辅助函数（`_extract_cover_info`、`_extract_visual_style`、`_clean_md`等）。**`app.py` 依赖这些函数的正则逻辑来解析 `note.md`**。修改这些正则或 `note.md` 输出格式时，必须同步检查 `app.py` 中的解析逻辑。

### 数据持久化

`core/config.py` 提供原子写入 JSON（`tempfile.mkstemp` + `os.replace`）和跨平台文件锁（`fcntl`），防止并发损坏 `data/topics.json` 和 `data/performance.json`。

## 平台调性约束

- **陪伴感优先于分析感**：情感内容必须像闺蜜夜聊，禁止理性分析和下定义式表达。
- **封面生成策略**：只生成 AI 封面（`cover_ai.png`），不额外生成 `cover_chat`/`cover_warm` 等多风格模板封面。

## 环境依赖

- Python 3.10+，复制 `.env.example` 为 `.env` 并填写 `LLM_API_KEY`。
- 必须提供思源黑体字体：`assets/fonts/NotoSansSC-Regular.ttf` 和 `NotoSansSC-Bold.ttf`。缺失时按平台 fallback 系统黑体，但排版效果会下降。
- `data/topics.json` 为必选文件，缺失时程序直接报错。
