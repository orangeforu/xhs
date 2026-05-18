from dataclasses import dataclass, field
from typing import Any, Callable
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

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
    """发布/订阅消息总线，支持广播和点对点通信。"""

    def __init__(self):
        self.subscribers: dict[str, list[Callable[[Message], None]]] = {}
        self.history: list[Message] = []

    def subscribe(self, agent_name: str, callback: Callable[[Message], None]):
        self.subscribers.setdefault(agent_name, []).append(callback)

    def publish(self, message: Message):
        self.history.append(message)
        targets = []
        if message.to_agent is None:
            targets = [name for name in self.subscribers if name != message.from_agent]
        else:
            targets = [message.to_agent]

        for target in targets:
            for callback in self.subscribers.get(target, []):
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
        """调用 LLM 进行推理，自动注入持久化记忆上下文。"""
        from core.agents.memory import AgentMemory
        memory = AgentMemory(self.name)
        memory_context = memory.get_context()

        full_prompt = prompt
        if memory_context:
            full_prompt = f"{memory_context}\n\n---\n\n{prompt}"

        data = _call_api(
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": full_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return _extract_content(data)

    def think_parallel(
        self,
        prompts: list[tuple[str, float, int]],  # (prompt, temperature, max_tokens)
    ) -> list[str]:
        """并行调用多个 LLM 请求。"""
        results = [""] * len(prompts)

        def _call(idx: int, prompt: str, temp: float, max_tok: int):
            try:
                return idx, self.think(prompt, temperature=temp, max_tokens=max_tok)
            except Exception as e:
                logger.error("并行 LLM 调用失败 [%d]: %s", idx, e)
                return idx, ""

        with ThreadPoolExecutor(max_workers=min(4, len(prompts))) as executor:
            futures = {
                executor.submit(_call, i, p, t, m): i
                for i, (p, t, m) in enumerate(prompts)
            }
            for future in as_completed(futures):
                idx, result = future.result()
                results[idx] = result

        return results
