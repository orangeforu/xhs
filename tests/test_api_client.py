import unittest
from unittest.mock import MagicMock, patch

import requests

from core.api_client import _call_api, _extract_content, DEFAULT_MODEL, DEFAULT_BASE_URL, DEFAULT_API_KEY


# --- _extract_content ---

class TestExtractContent(unittest.TestCase):
    def test_normal_response(self):
        data = {"choices": [{"message": {"content": "Hello world"}}]}
        self.assertEqual(_extract_content(data), "Hello world")

    def test_returns_full_content(self):
        long = "x" * 5000
        data = {"choices": [{"message": {"content": long}}]}
        self.assertEqual(_extract_content(data), long)

    def test_empty_string_content(self):
        data = {"choices": [{"message": {"content": ""}}]}
        self.assertEqual(_extract_content(data), "")

    def test_none_input(self):
        with self.assertRaises(ValueError) as ctx:
            _extract_content(None)
        self.assertIn("非 dict 类型", str(ctx.exception))

    def test_string_input(self):
        with self.assertRaises(ValueError):
            _extract_content("not a dict")

    def test_empty_dict(self):
        with self.assertRaises(ValueError) as ctx:
            _extract_content({})
        self.assertIn("缺少 choices", str(ctx.exception))

    def test_choices_none(self):
        with self.assertRaises(ValueError) as ctx:
            _extract_content({"choices": None})
        self.assertIn("缺少 choices", str(ctx.exception))

    def test_choices_empty_list(self):
        with self.assertRaises(ValueError) as ctx:
            _extract_content({"choices": []})
        self.assertIn("缺少 choices", str(ctx.exception))

    def test_choice_item_none(self):
        data = {"choices": [None]}
        with self.assertRaises(AttributeError):
            _extract_content(data)

    def test_no_message_key(self):
        data = {"choices": [{}]}
        with self.assertRaises(ValueError) as ctx:
            _extract_content(data)
        self.assertIn("缺少 content", str(ctx.exception))

    def test_message_content_none(self):
        data = {"choices": [{"message": {"content": None}}]}
        with self.assertRaises(ValueError) as ctx:
            _extract_content(data)
        self.assertIn("缺少 content", str(ctx.exception))

    def test_no_content_key(self):
        data = {"choices": [{"message": {}}]}
        with self.assertRaises(ValueError) as ctx:
            _extract_content(data)
        self.assertIn("缺少 content", str(ctx.exception))

    def test_multiple_choices_uses_first(self):
        data = {"choices": [
            {"message": {"content": "first"}},
            {"message": {"content": "second"}},
        ]}
        self.assertEqual(_extract_content(data), "first")

    def test_extra_fields_ignored(self):
        data = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        self.assertEqual(_extract_content(data), "ok")


# --- _call_api ---

class TestCallApi(unittest.TestCase):
    def _success_resp(self, content="ok"):
        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"choices": [{"message": {"content": content}}]}
        return resp

    @patch("core.api_client.requests.post")
    def test_success_first_attempt(self, mock_post):
        mock_post.return_value = self._success_resp("hello")
        result = _call_api(messages=[{"role": "user", "content": "hi"}])
        self.assertEqual(result["choices"][0]["message"]["content"], "hello")
        self.assertEqual(mock_post.call_count, 1)

    @patch("core.api_client.requests.post")
    def test_passes_model(self, mock_post):
        mock_post.return_value = self._success_resp()
        _call_api(messages=[{"role": "user", "content": "x"}], model="gpt-4")
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["json"]["model"], "gpt-4")

    @patch("core.api_client.requests.post")
    def test_uses_default_model_when_none(self, mock_post):
        mock_post.return_value = self._success_resp()
        _call_api(messages=[{"role": "user", "content": "x"}])
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["json"]["model"], DEFAULT_MODEL)

    @patch("core.api_client.requests.post")
    def test_passes_temperature(self, mock_post):
        mock_post.return_value = self._success_resp()
        _call_api(messages=[], temperature=0.3)
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["json"]["temperature"], 0.3)

    @patch("core.api_client.requests.post")
    def test_passes_max_tokens(self, mock_post):
        mock_post.return_value = self._success_resp()
        _call_api(messages=[], max_tokens=1000)
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["json"]["max_tokens"], 1000)

    @patch("core.api_client.requests.post")
    def test_url_construction(self, mock_post):
        mock_post.return_value = self._success_resp()
        _call_api(messages=[{"role": "user", "content": "hi"}])
        url = mock_post.call_args[0][0]
        self.assertIn("/chat/completions", url)

    @patch("core.api_client.requests.post")
    def test_authorization_header(self, mock_post):
        mock_post.return_value = self._success_resp()
        _call_api(messages=[{"role": "user", "content": "hi"}])
        headers = mock_post.call_args[1]["headers"]
        self.assertIn("Authorization", headers)
        self.assertTrue(headers["Authorization"].startswith("Bearer "))

    @patch("core.api_client.requests.post")
    def test_timeout_set(self, mock_post):
        mock_post.return_value = self._success_resp()
        _call_api(messages=[])
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["timeout"], 120)

    @patch("core.api_client.time.sleep")
    @patch("core.api_client.requests.post")
    def test_retry_on_429_then_success(self, mock_post, mock_sleep):
        err_resp = MagicMock()
        err_resp.status_code = 429
        error = requests.exceptions.HTTPError(response=err_resp)
        error.response = err_resp
        mock_post.side_effect = [error, self._success_resp("recovered")]
        result = _call_api(messages=[{"role": "user", "content": "hi"}])
        self.assertEqual(result["choices"][0]["message"]["content"], "recovered")
        self.assertEqual(mock_post.call_count, 2)
        mock_sleep.assert_called_once_with(1)

    @patch("core.api_client.time.sleep")
    @patch("core.api_client.requests.post")
    def test_retry_on_500_then_success(self, mock_post, mock_sleep):
        err_resp = MagicMock()
        err_resp.status_code = 500
        error = requests.exceptions.HTTPError(response=err_resp)
        error.response = err_resp
        mock_post.side_effect = [error, self._success_resp("ok")]
        result = _call_api(messages=[])
        self.assertIn("choices", result)
        mock_sleep.assert_called_once_with(1)

    @patch("core.api_client.time.sleep")
    @patch("core.api_client.requests.post")
    def test_retry_on_502(self, mock_post, mock_sleep):
        err_resp = MagicMock()
        err_resp.status_code = 502
        error = requests.exceptions.HTTPError(response=err_resp)
        error.response = err_resp
        mock_post.side_effect = [error, self._success_resp()]
        _call_api(messages=[])
        self.assertEqual(mock_post.call_count, 2)

    @patch("core.api_client.time.sleep")
    @patch("core.api_client.requests.post")
    def test_retry_on_503(self, mock_post, mock_sleep):
        err_resp = MagicMock()
        err_resp.status_code = 503
        error = requests.exceptions.HTTPError(response=err_resp)
        error.response = err_resp
        mock_post.side_effect = [error, self._success_resp()]
        _call_api(messages=[])
        self.assertEqual(mock_post.call_count, 2)

    @patch("core.api_client.time.sleep")
    @patch("core.api_client.requests.post")
    def test_raises_on_400_immediately(self, mock_post, mock_sleep):
        err_resp = MagicMock()
        err_resp.status_code = 400
        error = requests.exceptions.HTTPError(response=err_resp)
        error.response = err_resp
        mock_post.side_effect = error
        with self.assertRaises(requests.exceptions.HTTPError):
            _call_api(messages=[])
        self.assertEqual(mock_post.call_count, 1)
        mock_sleep.assert_not_called()

    @patch("core.api_client.time.sleep")
    @patch("core.api_client.requests.post")
    def test_raises_on_401_immediately(self, mock_post, mock_sleep):
        err_resp = MagicMock()
        err_resp.status_code = 401
        error = requests.exceptions.HTTPError(response=err_resp)
        error.response = err_resp
        mock_post.side_effect = error
        with self.assertRaises(requests.exceptions.HTTPError):
            _call_api(messages=[])
        self.assertEqual(mock_post.call_count, 1)

    @patch("core.api_client.time.sleep")
    @patch("core.api_client.requests.post")
    def test_raises_on_403_immediately(self, mock_post, mock_sleep):
        err_resp = MagicMock()
        err_resp.status_code = 403
        error = requests.exceptions.HTTPError(response=err_resp)
        error.response = err_resp
        mock_post.side_effect = error
        with self.assertRaises(requests.exceptions.HTTPError):
            _call_api(messages=[])
        self.assertEqual(mock_post.call_count, 1)

    @patch("core.api_client.time.sleep")
    @patch("core.api_client.requests.post")
    def test_retry_on_connection_error(self, mock_post, mock_sleep):
        mock_post.side_effect = [
            requests.exceptions.ConnectionError("refused"),
            self._success_resp("ok"),
        ]
        result = _call_api(messages=[])
        self.assertIn("choices", result)
        self.assertEqual(mock_post.call_count, 2)

    @patch("core.api_client.time.sleep")
    @patch("core.api_client.requests.post")
    def test_retry_on_timeout(self, mock_post, mock_sleep):
        mock_post.side_effect = [
            requests.exceptions.Timeout("timed out"),
            self._success_resp("ok"),
        ]
        result = _call_api(messages=[])
        self.assertIn("choices", result)

    @patch("core.api_client.time.sleep")
    @patch("core.api_client.requests.post")
    def test_exponential_backoff(self, mock_post, mock_sleep):
        err_resp = MagicMock()
        err_resp.status_code = 500
        error = requests.exceptions.HTTPError(response=err_resp)
        error.response = err_resp
        mock_post.side_effect = [error, error, self._success_resp()]
        _call_api(messages=[], retries=3)
        calls = [c.args[0] for c in mock_sleep.call_args_list]
        self.assertEqual(calls, [1, 2])

    @patch("core.api_client.time.sleep")
    @patch("core.api_client.requests.post")
    def test_raises_after_all_retries_exhausted(self, mock_post, mock_sleep):
        err_resp = MagicMock()
        err_resp.status_code = 503
        error = requests.exceptions.HTTPError(response=err_resp)
        error.response = err_resp
        mock_post.side_effect = error
        with self.assertRaises(requests.exceptions.HTTPError):
            _call_api(messages=[], retries=2)
        self.assertEqual(mock_post.call_count, 2)

    @patch("core.api_client.time.sleep")
    @patch("core.api_client.requests.post")
    def test_custom_retries_count(self, mock_post, mock_sleep):
        err_resp = MagicMock()
        err_resp.status_code = 500
        error = requests.exceptions.HTTPError(response=err_resp)
        error.response = err_resp
        mock_post.side_effect = error
        with self.assertRaises(requests.exceptions.HTTPError):
            _call_api(messages=[], retries=5)
        self.assertEqual(mock_post.call_count, 5)

    @patch("core.api_client.time.sleep")
    @patch("core.api_client.requests.post")
    def test_messages_passed_correctly(self, mock_post, mock_sleep):
        mock_post.return_value = self._success_resp()
        msgs = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hello"},
        ]
        _call_api(messages=msgs)
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["json"]["messages"], msgs)


# --- Module constants ---

class TestModuleConstants(unittest.TestCase):
    def test_default_model_is_string(self):
        self.assertIsInstance(DEFAULT_MODEL, str)

    def test_default_base_url_is_string(self):
        self.assertIsInstance(DEFAULT_BASE_URL, str)

    def test_default_base_url_has_chat_completions(self):
        self.assertIn("v1", DEFAULT_BASE_URL)


if __name__ == "__main__":
    unittest.main()
