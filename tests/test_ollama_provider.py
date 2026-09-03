import json
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

from j_gamelqa.providers.ollama import OllamaProvider, OllamaProviderError


def http_response(payload):
    response = MagicMock()
    response.__enter__.return_value.read.return_value = json.dumps(
        payload
    ).encode("utf-8")
    return response


class OllamaProviderTests(unittest.TestCase):
    @patch("j_gamelqa.providers.ollama.urllib.request.urlopen")
    def test_provider_constructs_fixed_generation_request(self, mocked_urlopen):
        mocked_urlopen.return_value = http_response(
            {
                "model": "qwen3.5:9b",
                "response": '{"string_id":"DEV_001","issues":[]}',
                "done": True,
                "thinking": "",
            }
        )
        provider = OllamaProvider(
            "qwen3.5:9b",
            timeout_seconds=120,
            temperature=0,
            thinking=False,
            stream=False,
        )
        generation = provider.generate("test prompt")

        request = mocked_urlopen.call_args.args[0]
        request_payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(request.full_url, "http://127.0.0.1:11434/api/generate")
        self.assertEqual(request_payload["model"], "qwen3.5:9b")
        self.assertEqual(request_payload["options"]["temperature"], 0)
        self.assertIs(request_payload["think"], False)
        self.assertIs(request_payload["stream"], False)
        self.assertNotIn("format", request_payload)
        self.assertEqual(mocked_urlopen.call_args.kwargs["timeout"], 120)
        self.assertEqual(
            generation.raw_response,
            '{"string_id":"DEV_001","issues":[]}',
        )

    @patch("j_gamelqa.providers.ollama.urllib.request.urlopen")
    def test_connection_failure_is_provider_error(self, mocked_urlopen):
        mocked_urlopen.side_effect = urllib.error.URLError(
            ConnectionRefusedError("connection refused")
        )
        with self.assertRaises(OllamaProviderError) as raised:
            OllamaProvider("qwen3.5:9b").generate("prompt")
        self.assertEqual(raised.exception.category, "connection_error")

    @patch("j_gamelqa.providers.ollama.urllib.request.urlopen")
    def test_timeout_is_explicit_provider_error(self, mocked_urlopen):
        mocked_urlopen.side_effect = urllib.error.URLError(
            TimeoutError("timed out")
        )
        with self.assertRaises(OllamaProviderError) as raised:
            OllamaProvider("qwen3.5:9b").generate("prompt")
        self.assertEqual(raised.exception.category, "timeout")
