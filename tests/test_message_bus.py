import threading
import unittest

from core.agents.base import MessageBus, Message, MessageType


class TestMessageBus(unittest.TestCase):
    def setUp(self):
        self.bus = MessageBus()

    def test_subscribe_and_publish(self):
        received = []
        self.bus.subscribe("agent_a", lambda msg: received.append(msg))
        msg = Message(from_agent="agent_b", msg_type=MessageType.DRAFT, content={"text": "hello"})
        self.bus.publish(msg)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].content["text"], "hello")

    def test_broadcast(self):
        received_a = []
        received_b = []
        self.bus.subscribe("agent_a", lambda msg: received_a.append(msg))
        self.bus.subscribe("agent_b", lambda msg: received_b.append(msg))
        msg = Message(from_agent="agent_c", msg_type=MessageType.NOTIFY, content={})
        self.bus.publish(msg)
        # 广播不发给自己
        self.assertEqual(len(received_a), 1)
        self.assertEqual(len(received_b), 1)

    def test_point_to_point(self):
        received_a = []
        received_b = []
        self.bus.subscribe("agent_a", lambda msg: received_a.append(msg))
        self.bus.subscribe("agent_b", lambda msg: received_b.append(msg))
        msg = Message(from_agent="agent_c", to_agent="agent_a", msg_type=MessageType.REQUEST, content={})
        self.bus.publish(msg)
        self.assertEqual(len(received_a), 1)
        self.assertEqual(len(received_b), 0)

    def test_no_echo(self):
        received = []
        self.bus.subscribe("agent_a", lambda msg: received.append(msg))
        msg = Message(from_agent="agent_a", msg_type=MessageType.NOTIFY, content={})
        self.bus.publish(msg)
        # 不应该收到自己发的消息
        self.assertEqual(len(received), 0)

    def test_history(self):
        self.bus.publish(Message(from_agent="a", msg_type=MessageType.DRAFT, content={}))
        self.bus.publish(Message(from_agent="b", msg_type=MessageType.REVIEW, content={}))
        history = self.bus.get_history()
        self.assertEqual(len(history), 2)

    def test_history_filter(self):
        self.bus.publish(Message(from_agent="a", msg_type=MessageType.DRAFT, content={}))
        self.bus.publish(Message(from_agent="b", msg_type=MessageType.REVIEW, content={}))
        self.bus.publish(Message(from_agent="a", msg_type=MessageType.REVIEW, content={}))
        filtered = self.bus.get_history(from_agent="a")
        self.assertEqual(len(filtered), 2)
        filtered = self.bus.get_history(msg_type=MessageType.REVIEW)
        self.assertEqual(len(filtered), 2)

    def test_get_last_message(self):
        self.bus.publish(Message(from_agent="a", msg_type=MessageType.DRAFT, content={"n": 1}))
        self.bus.publish(Message(from_agent="a", msg_type=MessageType.DRAFT, content={"n": 2}))
        last = self.bus.get_last_message(from_agent="a", msg_type=MessageType.DRAFT)
        self.assertEqual(last.content["n"], 2)

    def test_thread_safety(self):
        """并发 publish 不应该崩溃。"""
        errors = []

        def publish_messages(agent_name, count):
            try:
                for i in range(count):
                    msg = Message(from_agent=agent_name, msg_type=MessageType.NOTIFY, content={"i": i})
                    self.bus.publish(msg)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=publish_messages, args=(f"agent_{t}", 50))
            for t in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)
        self.assertEqual(len(self.bus.history), 200)


class TestMessage(unittest.TestCase):
    def test_to_dict(self):
        msg = Message(from_agent="a", to_agent="b", msg_type=MessageType.DRAFT, content={"x": 1}, round_num=2)
        d = msg.to_dict()
        self.assertEqual(d["from_agent"], "a")
        self.assertEqual(d["to_agent"], "b")
        self.assertEqual(d["msg_type"], "draft")
        self.assertEqual(d["round_num"], 2)

    def test_from_dict(self):
        d = {"from_agent": "a", "to_agent": None, "msg_type": "review", "content": {}, "round_num": 0}
        msg = Message.from_dict(d)
        self.assertEqual(msg.from_agent, "a")
        self.assertEqual(msg.msg_type, MessageType.REVIEW)


if __name__ == "__main__":
    unittest.main()
