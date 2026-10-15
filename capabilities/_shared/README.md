# _shared — 公共设施

跨能力共享的最底层模块（Rule of Two 达标才进来）。

| 文件 | 说明 | 使用方 |
|---|---|---|
| `note_schema.py` | NoteRecord：小红书笔记统一 schema（from_api_detail 解析互动数据） | xhs_crawler（活跃）、案例3 fetch_performance（遗产） |
| `fonts/` | 思源黑体 Regular/Bold（图片渲染用，缺失时降级系统黑体） | 各图片生成场景 |

未来候选（尚未达到 Rule of Two，先留在各案例）：原子写 JSON+文件锁（legacy core/config）、LLM API 调用层（legacy core/writer、test_workflows 各有一份实现）。
