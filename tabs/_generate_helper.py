"""页内生成笔记的共享辅助模块。

封装 pipeline 调用 + 日志捕获 + 结果展示，供 topics.py / review.py / app.py 复用，
避免三处重复 import pipeline，并统一进度提示与失败兜底。

不改动 pipeline.py 与 core/，仅 import 调用。
"""

import logging
from typing import Any

import streamlit as st

# 根 logger — 各 Agent 的 logger.info 都会冒泡到这里
_ROOT_LOGGER = logging.getLogger()
_LOG_FMT = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")


class _StreamlitLogHandler(logging.Handler):
    """捕获生成期间的日志到列表，并可选地推送到一个 st.empty 做伪实时进度。

    status_container: 一个 st.empty() 占位符。emit 时把最近若干行写进去，
    让用户在生成期间就能看到日志在增长（覆盖式刷新，非追加，避免无限长）。
    """

    def __init__(self, status_container=None, max_lines: int = 12):
        super().__init__(level=logging.INFO)
        self.setFormatter(_LOG_FMT)
        self.records: list[str] = []
        self.status_container = status_container
        self.max_lines = max_lines

    def emit(self, record: logging.LogRecord) -> None:
        try:
            line = self.format(record)
        except Exception:
            line = record.getMessage()
        self.records.append(line)
        if self.status_container is not None:
            try:
                tail = "\n".join(self.records[-self.max_lines :])
                self.status_container.code(tail, language="text")
            except Exception:
                # UI 不可用时（如线程内）静默降级，只保留 records
                pass


def check_api_key() -> bool:
    """生成前校验 LLM_API_KEY。缺失则 st.error 并返回 False。"""
    from core.config import LLM_API_KEY

    if not LLM_API_KEY:
        st.error("⚠️ 未配置 LLM_API_KEY。请在项目根目录的 `.env` 填写后再生成。")
        return False
    return True


def generate_with_progress(
    topic: str | None = None,
    index: int | None = None,
    smart: bool = False,
    status_container=None,
) -> tuple[dict | None, list[str]]:
    """页内单篇生成入口。

    返回 (result, log_records)。result 为 pipeline.generate 的返回值：
    - status="completed" 成功
    - status="abandoned" 被主编放弃
    - None 生成失败/异常
    """
    import pipeline

    handler = _StreamlitLogHandler(status_container=status_container)
    _ROOT_LOGGER.addHandler(handler)
    try:
        result = pipeline.generate(topic=topic, index=index, smart=smart)
    except Exception as e:
        result = None
        handler.records.append(f"[ERROR] 生成过程异常: {e}")
    finally:
        _ROOT_LOGGER.removeHandler(handler)
    return result, handler.records


def batch_generate_with_progress(
    max_count: int | None = None,
    smart: bool = False,
    status_container=None,
) -> tuple[int, int, int, list[str]]:
    """页内批量生成（串行，避免线程安全问题）。

    不走 pipeline.batch_generate 的线程池，而是循环调 pipeline.generate。
    返回 (success, abandoned, failed, all_log_records)。
    """
    import pipeline
    from core.config import load_topics_json
    from core.topic_selector import smart_batch

    topics_data = load_topics_json()
    topic_pool = topics_data.get("topics", [])

    # 选出待生成的选题
    if smart:
        briefs = smart_batch(count=max_count or len(topic_pool), topic_pool=topic_pool)
    else:
        briefs = [t for t in topic_pool if t.get("status", "not_started") == "not_started"]
        if max_count:
            briefs = briefs[:max_count]

    if not briefs:
        st.warning("没有可生成的选题（所有选题都已生成或发布）。先去📚选题池加几个选题吧。")
        return 0, 0, 0, []

    all_records: list[str] = []
    success = abandoned = failed = 0
    total = len(briefs)

    for i, brief in enumerate(briefs, 1):
        topic_name = brief["topic"]
        if status_container is not None:
            try:
                status_container.info(f"批量生成 {i}/{total}：{topic_name}")
            except Exception:
                pass

        result, logs = generate_with_progress(topic=topic_name, status_container=status_container)
        all_records.extend(logs)
        all_records.append(f"{'=' * 40}")

        status = result.get("status") if result else None
        if status == "completed":
            success += 1
        elif status == "abandoned":
            abandoned += 1
        else:
            failed += 1

    return success, abandoned, failed, all_records


def render_result(result: dict | None, records: list[str], topic_label: str = "") -> None:
    """统一展示生成结果 + 日志回放。

    在调用方已用 st.status 包裹的场景下，本函数负责最终的成功/失败提示。
    """
    status = result.get("status") if result else None

    if status == "completed":
        review = result.get("review", {}) or {}
        grade = review.get("grade", "B")
        rounds = result.get("rounds", 1)
        label = f"「{topic_label}」" if topic_label else ""
        st.success(f"✅ {label}生成完成！共迭代 {rounds} 轮，最终等级 {grade}。切到「📝待审核笔记」tab 查看。")
    elif status == "abandoned":
        reason = result.get("reason", "未知原因") if result else "未知原因"
        label = f"「{topic_label}」" if topic_label else ""
        st.warning(f"⚠️ {label}被主编放弃：{reason}。可换个选题或调整修改意见后重试。")
    else:
        label = f"「{topic_label}」" if topic_label else ""
        st.error(f"❌ {label}生成失败，请查看下方日志排查。")

    if records:
        with st.expander("📜 生成日志", expanded=False):
            st.code("\n".join(records), language="text")
