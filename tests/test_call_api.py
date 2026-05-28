import unittest
from unittest.mock import patch, MagicMock

from core.writer import _call_api, _extract_content


class TestCallApi(unittest.TestCase):
    """测试 LLM API 调用层。"""

    @patch("core.writer.requests.post")
    def test_successful_call(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"choices": [{"message": {"content": "hello"}}]}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        result = _call_api(messages=[{"role": "user", "content": "test"}], retries=1)
        self.assertEqual(result["choices"][0]["message"]["content"], "hello")

    @patch("core.writer.requests.post")
    def test_retry_on_429(self, mock_post):
        from requests.exceptions import HTTPError
        import requests

        # 第一次 429，第二次成功
        resp_429 = MagicMock()
        resp_429.status_code = 429
        resp_429.raise_for_status.side_effect = HTTPError(response=resp_429)

        resp_ok = MagicMock()
        resp_ok.status_code = 200
        resp_ok.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
        resp_ok.raise_for_status = MagicMock()

        mock_post.side_effect = [resp_429, resp_ok]

        result = _call_api(messages=[{"role": "user", "content": "test"}], retries=2)
        self.assertEqual(result["choices"][0]["message"]["content"], "ok")
        self.assertEqual(mock_post.call_count, 2)

    @patch("core.writer.requests.post")
    def test_retry_on_500(self, mock_post):
        from requests.exceptions import HTTPError

        resp_500 = MagicMock()
        resp_500.status_code = 500
        resp_500.raise_for_status.side_effect = HTTPError(response=resp_500)

        resp_ok = MagicMock()
        resp_ok.status_code = 200
        resp_ok.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
        resp_ok.raise_for_status = MagicMock()

        mock_post.side_effect = [resp_500, resp_ok]

        result = _call_api(messages=[{"role": "user", "content": "test"}], retries=2)
        self.assertEqual(result["choices"][0]["message"]["content"], "ok")

    @patch("core.writer.requests.post")
    def test_no_retry_on_400(self, mock_post):
        from requests.exceptions import HTTPError

        resp_400 = MagicMock()
        resp_400.status_code = 400
        resp_400.raise_for_status.side_effect = HTTPError(response=resp_400)

        mock_post.return_value = resp_400

        with self.assertRaises(HTTPError):
            _call_api(messages=[{"role": "user", "content": "test"}], retries=3)
        # 400 不重试，只调用 1 次
        self.assertEqual(mock_post.call_count, 1)

    @patch("core.writer.time.sleep")
    @patch("core.writer.requests.post")
    def test_retry_on_connection_error(self, mock_post, mock_sleep):
        from requests.exceptions import ConnectionError

        mock_post.side_effect = [
            ConnectionError("connection refused"),
            MagicMock(status_code=200, json=MagicMock(return_value={"choices": [{"message": {"content": "ok"}}]}), raise_for_status=MagicMock()),
        ]

        result = _call_api(messages=[{"role": "user", "content": "test"}], retries=2)
        self.assertEqual(result["choices"][0]["message"]["content"], "ok")

    def test_retries_zero_raises_runtime_error(self):
        with self.assertRaises(RuntimeError):
            _call_api(messages=[{"role": "user", "content": "test"}], retries=0)


class TestExtractContent(unittest.TestCase):
    """测试响应内容提取。"""

    def test_normal_response(self):
        data = {"choices": [{"message": {"content": "Hello"}}]}
        self.assertEqual(_extract_content(data), "Hello")

    def test_none_input(self):
        with self.assertRaises(ValueError):
            _extract_content(None)

    def test_missing_choices(self):
        with self.assertRaises(ValueError):
            _extract_content({})

    def test_missing_message(self):
        with self.assertRaises(ValueError):
            _extract_content({"choices": [{}]})

    def test_missing_content(self):
        with self.assertRaises(ValueError):
            _extract_content({"choices": [{"message": {}}]})

    def test_content_none(self):
        with self.assertRaises(ValueError):
            _extract_content({"choices": [{"message": {"content": None}}]})


if __name__ == "__main__":
    unittest.main()
