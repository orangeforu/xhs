from dataclasses import dataclass, field
from typing import Callable
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from core.config import get_logger
from core.writer import _call_api, _extract_content

logger = get_logger(__name__)


class MessageType(Enum):
    BRIEF = "brief"           # 选题 brief
    DRAFT = "draft"           # 笔记初稿/修改稿
    DESIGN = "design"         # 封面/内页设计方案
    REVIEW = "review"         # 审核报告
    REQUEST = "request"       # 请求其他 agent 做某事
    RESPONSE = "response"     # 响应请求
    DECISION = "decision"     # 主编决策
    COMMENT = "comment"       # 预设评论
    NOTIFY = "notify"         # 通知


@dataclass
class Message:
    from_agent: str
    to_agent: str | None = None   # None = broadcast
    msg_type: MessageType = MessageType.NOTIFY
    content: dict = field(default_factory=dict)
    round_num: int = 0

    def to_dict(self) -> dict:
        return {
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "msg_type": self.msg_type.value,
            "content": self.content,
            "round_num": self.round_num,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Message":
        return cls(
            from_agent=data["from_agent"],
            to_agent=data.get("to_agent"),
            msg_type=MessageType(data["msg_type"]),
            content=data["content"],
            round_num=data.get("round_num", 0),
        )


class MessageBus:
    """发布/订阅消息总线，支持广播和点对点通信（线程安全）。"""

    def __init__(self):
        self.subscribers: dict[str, list[Callable[[Message], None]]] = {}
        self.history: list[Message] = []
        self._lock = threading.Lock()

    def subscribe(self, agent_name: str, callback: Callable[[Message], None]):
        with self._lock:
            self.subscribers.setdefault(agent_name, []).append(callback)

    def unsubscribe(self, agent_name: str, callback: Callable[[Message], None] | None = None):
        """取消订阅。callback=None 时移除该 agent 的所有回调。"""
        with self._lock:
            if agent_name not in self.subscribers:
                return
            if callback is None:
                del self.subscribers[agent_name]
            else:
                self.subscribers[agent_name] = [
                    cb for cb in self.subscribers[agent_name] if cb is not callback
                ]
                if not self.subscribers[agent_name]:
                    del self.subscribers[agent_name]

    def publish(self, message: Message):
        with self._lock:
            self.history.append(message)
            # 构建 targets 和 callbacks 快照，避免锁外遍历时状态变化
            if message.to_agent is None:
                targets = [name for name in self.subscribers if name != message.from_agent]
            else:
                targets = [message.to_agent]
            # 复制每个 target 的 callbacks 列表
            callbacks_snapshot = {t: list(self.subscribers.get(t, [])) for t in targets}

        for target, callbacks in callbacks_snapshot.items():
            for callback in callbacks:
                try:
                    callback(message)
                except Exception as e:
                    logger.error("消息投递失败 %s -> %s: %s", message.from_agent, target, e)

    def get_history(
        self,
        from_agent: str | None = None,
        to_agent: str | None = None,
        msg_type: MessageType | None = None,
        round_num: int | None = None,
    ) -> list[Message]:
        with self._lock:
            result = list(self.history)
        if from_agent:
            result = [m for m in result if m.from_agent == from_agent]
        if to_agent:
            result = [m for m in result if m.to_agent == to_agent or m.to_agent is None]
        if msg_type:
            result = [m for m in result if m.msg_type == msg_type]
        if round_num is not None:
            result = [m for m in result if m.round_num == round_num]
        return result

    def get_last_message(
        self,
        from_agent: str | None = None,
        msg_type: MessageType | None = None,
    ) -> Message | None:
        history = self.get_history(from_agent=from_agent, msg_type=msg_type)
        return history[-1] if history else None


class BaseAgent:
    """所有 Agent 的基类。"""

    def __init__(self, name: str, system_prompt: str, bus: MessageBus):
        self.name = name
        self.system_prompt = system_prompt
        self.bus = bus
        self.session_memory: list[Message] = []  # 当前会话
        self._memory_cache: str | None = None  # 同一轮迭代内缓存
        self._memory_loaded: bool = False
        self._memory_lock = threading.Lock()  # 保护 _memory_cache 和 _memory_loaded
        bus.subscribe(name, self._on_message)

    def _on_message(self, message: Message):
        self.session_memory.append(message)
        self.handle(message)

    def handle(self, message: Message):
        """子类必须重写此方法。"""
        raise NotImplementedError(f"Agent {self.name} 未实现 handle 方法")

    def send(
        self,
        to_agent: str | None,
        msg_type: MessageType,
        content: dict,
        round_num: int = 0,
    ) -> Message:
        msg = Message(
            from_agent=self.name,
            to_agent=to_agent,
            msg_type=msg_type,
            content=content,
            round_num=round_num,
        )
        self.bus.publish(msg)
        self.session_memory.append(msg)
        return msg

    def think(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2500,
    ) -> str:
        """调用 LLM 进行推理，自动注入持久化记忆上下文（同轮迭代内缓存）。"""
        with self._memory_lock:
            if not self._memory_loaded:
                from core.agents.memory import AgentMemory
                memory = AgentMemory(self.name)
                self._memory_cache = memory.get_context()
                self._memory_loaded = True

        full_prompt = prompt
        if self._memory_cache:
            full_prompt = f"{self._memory_cache}\n\n---\n\n{prompt}"

        data = _call_api(
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": full_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return _extract_content(data)

    def reset_memory_cache(self):
        """重置记忆缓存，下次 think() 时重新从磁盘加载。用于新一轮迭代开始时。"""
        with self._memory_lock:
            self._memory_loaded = False
            self._memory_cache = None

    def think_parallel(
        self,
        prompts: list[tuple[str, float, int]],  # (prompt, temperature, max_tokens)
    ) -> list[str]:
        """并行调用多个 LLM 请求。失败的调用会抛出异常而非静默返回空字符串。"""
        results = [""] * len(prompts)
        errors: list[Exception | None] = [None] * len(prompts)

        def _call(idx: int, prompt: str, temp: float, max_tok: int):
            try:
                return idx, self.think(prompt, temperature=temp, max_tokens=max_tok), None
            except Exception as e:
                logger.error("并行 LLM 调用失败 [%d]: %s", idx, e)
                return idx, "", e

        with ThreadPoolExecutor(max_workers=min(4, len(prompts))) as executor:
            futures = {
                executor.submit(_call, i, p, t, m): i
                for i, (p, t, m) in enumerate(prompts)
            }
            for future in as_completed(futures):
                idx, result, err = future.result()
                results[idx] = result
                errors[idx] = err

        # 如果有任何调用失败，抛出聚合异常
        failed = [(i, e) for i, e in enumerate(errors) if e is not None]
        if failed:
            msgs = [f"[{i}]: {e}" for i, e in failed]
            raise RuntimeError(f"并行 LLM 调用有 {len(failed)} 个失败:\n" + "\n".join(msgs))

        return results
