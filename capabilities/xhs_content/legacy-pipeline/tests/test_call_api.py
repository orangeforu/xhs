import unittest
from unittest.mock import patch, MagicMock

import requests

from core.writer import _call_api, _extract_content, DEFAULT_MODEL


class TestCallApi(unittest.TestCase):
    """测试 LLM API 调用层（core.writer）。"""

    def _success_resp(self, content="ok"):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"choices": [{"message": {"content": content}}]}
        resp.raise_for_status = MagicMock()
        return resp

    def _http_error(self, status_code):
        err_resp = MagicMock()
        err_resp.status_code = status_code
        error = requests.exceptions.HTTPError(response=err_resp)
        error.response = err_resp
        return error

    # --- 成功路径 ---

    @patch("core.writer.requests.post")
    def test_successful_call(self, mock_post):
        mock_post.return_value = self._success_resp("hello")
        result = _call_api(messages=[{"role": "user", "content": "test"}], retries=1)
        self.assertEqual(result["choices"][0]["message"]["content"], "hello")
        self.assertEqual(mock_post.call_count, 1)

    @patch("core.writer.requests.post")
    def test_success_first_attempt(self, mock_post):
        mock_post.return_value = self._success_resp("hello")
        result = _call_api(messages=[{"role": "user", "content": "hi"}])
        self.assertEqual(result["choices"][0]["message"]["content"], "hello")
        self.assertEqual(mock_post.call_count, 1)

    # --- 参数透传 ---

    @patch("core.writer.requests.post")
    def test_passes_model(self, mock_post):
        mock_post.return_value = self._success_resp()
        _call_api(messages=[{"role": "user", "content": "x"}], model="gpt-4")
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["json"]["model"], "gpt-4")

    @patch("core.writer.requests.post")
    def test_uses_default_model_when_none(self, mock_post):
        mock_post.return_value = self._success_resp()
        _call_api(messages=[{"role": "user", "content": "x"}])
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["json"]["model"], DEFAULT_MODEL)

    @patch("core.writer.requests.post")
    def test_passes_temperature(self, mock_post):
        mock_post.return_value = self._success_resp()
        _call_api(messages=[], temperature=0.3)
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["json"]["temperature"], 0.3)

    @patch("core.writer.requests.post")
    def test_passes_max_tokens(self, mock_post):
        mock_post.return_value = self._success_resp()
        _call_api(messages=[], max_tokens=1000)
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["json"]["max_tokens"], 1000)

    @patch("core.writer.requests.post")
    def test_messages_passed_correctly(self, mock_post):
        mock_post.return_value = self._success_resp()
        msgs = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hello"},
        ]
        _call_api(messages=msgs)
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["json"]["messages"], msgs)

    @patch("core.writer.requests.post")
    def test_url_construction(self, mock_post):
        mock_post.return_value = self._success_resp()
        _call_api(messages=[{"role": "user", "content": "hi"}])
        url = mock_post.call_args[0][0]
        self.assertIn("/chat/completions", url)

    @patch("core.writer.requests.post")
    def test_authorization_header(self, mock_post):
        mock_post.return_value = self._success_resp()
        _call_api(messages=[{"role": "user", "content": "hi"}])
        headers = mock_post.call_args[1]["headers"]
        self.assertIn("Authorization", headers)
        self.assertTrue(headers["Authorization"].startswith("Bearer "))

    @patch("core.writer.requests.post")
    def test_timeout_is_tuple(self, mock_post):
        # writer.py 用 (connect, read) 元组超时 (10, 120)
        mock_post.return_value = self._success_resp()
        _call_api(messages=[])
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["timeout"], (10, 120))

    # --- 重试：可重试状态码 ---

    @patch("core.writer.time.sleep")
    @patch("core.writer.requests.post")
    def test_retry_on_429(self, mock_post, mock_sleep):
        mock_post.side_effect = [self._http_error(429), self._success_resp("ok")]
        result = _call_api(messages=[{"role": "user", "content": "test"}], retries=2)
        self.assertEqual(result["choices"][0]["message"]["content"], "ok")
        self.assertEqual(mock_post.call_count, 2)
        mock_sleep.assert_called_once()  # 抖动退避，只验证调用次数

    @patch("core.writer.time.sleep")
    @patch("core.writer.requests.post")
    def test_retry_on_500(self, mock_post, mock_sleep):
        mock_post.side_effect = [self._http_error(500), self._success_resp("ok")]
        result = _call_api(messages=[{"role": "user", "content": "test"}], retries=2)
        self.assertEqual(result["choices"][0]["message"]["content"], "ok")
        self.assertEqual(mock_post.call_count, 2)

    @patch("core.writer.time.sleep")
    @patch("core.writer.requests.post")
    def test_retry_on_502(self, mock_post, mock_sleep):
        mock_post.side_effect = [self._http_error(502), self._success_resp()]
        _call_api(messages=[], retries=2)
        self.assertEqual(mock_post.call_count, 2)

    @patch("core.writer.time.sleep")
    @patch("core.writer.requests.post")
    def test_retry_on_503(self, mock_post, mock_sleep):
        mock_post.side_effect = [self._http_error(503), self._success_resp()]
        _call_api(messages=[], retries=2)
        self.assertEqual(mock_post.call_count, 2)

    # --- 重试：不可重试状态码立即失败 ---

    @patch("core.writer.time.sleep")
    @patch("core.writer.requests.post")
    def test_no_retry_on_400(self, mock_post, mock_sleep):
        mock_post.side_effect = self._http_error(400)
        with self.assertRaises(requests.exceptions.HTTPError):
            _call_api(messages=[{"role": "user", "content": "test"}], retries=3)
        self.assertEqual(mock_post.call_count, 1)
        mock_sleep.assert_not_called()

    @patch("core.writer.time.sleep")
    @patch("core.writer.requests.post")
    def test_raises_on_401_immediately(self, mock_post, mock_sleep):
        mock_post.side_effect = self._http_error(401)
        with self.assertRaises(requests.exceptions.HTTPError):
            _call_api(messages=[], retries=3)
        self.assertEqual(mock_post.call_count, 1)
        mock_sleep.assert_not_called()

    @patch("core.writer.time.sleep")
    @patch("core.writer.requests.post")
    def test_raises_on_403_immediately(self, mock_post, mock_sleep):
        mock_post.side_effect = self._http_error(403)
        with self.assertRaises(requests.exceptions.HTTPError):
            _call_api(messages=[], retries=3)
        self.assertEqual(mock_post.call_count, 1)
        mock_sleep.assert_not_called()

    # --- 重试：连接/超时错误 ---

    @patch("core.writer.time.sleep")
    @patch("core.writer.requests.post")
    def test_retry_on_connection_error(self, mock_post, mock_sleep):
        mock_post.side_effect = [
            requests.exceptions.ConnectionError("connection refused"),
            self._success_resp("ok"),
        ]
        result = _call_api(messages=[{"role": "user", "content": "test"}], retries=2)
        self.assertEqual(result["choices"][0]["message"]["content"], "ok")
        self.assertEqual(mock_post.call_count, 2)

    @patch("core.writer.time.sleep")
    @patch("core.writer.requests.post")
    def test_retry_on_timeout(self, mock_post, mock_sleep):
        mock_post.side_effect = [
            requests.exceptions.Timeout("timed out"),
            self._success_resp("ok"),
        ]
        result = _call_api(messages=[], retries=2)
        self.assertIn("choices", result)

    # --- 重试：耗尽与自定义次数 ---

    @patch("core.writer.time.sleep")
    @patch("core.writer.requests.post")
    def test_raises_after_all_retries_exhausted(self, mock_post, mock_sleep):
        mock_post.side_effect = self._http_error(503)
        with self.assertRaises(requests.exceptions.HTTPError):
            _call_api(messages=[], retries=2)
        self.assertEqual(mock_post.call_count, 2)

    @patch("core.writer.time.sleep")
    @patch("core.writer.requests.post")
    def test_custom_retries_count(self, mock_post, mock_sleep):
        mock_post.side_effect = self._http_error(500)
        with self.assertRaises(requests.exceptions.HTTPError):
            _call_api(messages=[], retries=5)
        self.assertEqual(mock_post.call_count, 5)

    def test_retries_zero_raises_runtime_error(self):
        with self.assertRaises(RuntimeError):
            _call_api(messages=[{"role": "user", "content": "test"}], retries=0)


class TestExtractContent(unittest.TestCase):
    """测试响应内容提取。"""

    def test_normal_response(self):
        data = {"choices": [{"message": {"content": "Hello"}}]}
        self.assertEqual(_extract_content(data), "Hello")

    def test_returns_full_content(self):
        long = "x" * 5000
        data = {"choices": [{"message": {"content": long}}]}
        self.assertEqual(_extract_content(data), long)

    def test_empty_string_content(self):
        data = {"choices": [{"message": {"content": ""}}]}
        self.assertEqual(_extract_content(data), "")

    def test_none_input(self):
        with self.assertRaises(ValueError):
            _extract_content(None)

    def test_string_input(self):
        with self.assertRaises(ValueError):
            _extract_content("not a dict")

    def test_missing_choices(self):
        with self.assertRaises(ValueError):
            _extract_content({})

    def test_choices_none(self):
        with self.assertRaises(ValueError):
            _extract_content({"choices": None})

    def test_choices_empty_list(self):
        with self.assertRaises(ValueError):
            _extract_content({"choices": []})

    def test_missing_message(self):
        with self.assertRaises(ValueError):
            _extract_content({"choices": [{}]})

    def test_missing_content(self):
        with self.assertRaises(ValueError):
            _extract_content({"choices": [{"message": {}}]})

    def test_content_none(self):
        with self.assertRaises(ValueError):
            _extract_content({"choices": [{"message": {"content": None}}]})

    def test_multiple_choices_uses_first(self):
        data = {"choices": [
            {"message": {"content": "first"}},
            {"message": {"content": "second"}},
        ]}
        self.assertEqual(_extract_content(data), "first")

    def test_reasoning_content_fallback(self):
        # writer.py 特性：content 为空时回退到 reasoning_content（推理模型）
        data = {"choices": [{"message": {"content": None, "reasoning_content": "thinking..."}}]}
        self.assertEqual(_extract_content(data), "thinking...")


if __name__ == "__main__":
    unittest.main()
