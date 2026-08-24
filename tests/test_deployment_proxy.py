from __future__ import annotations

import urllib.error
import urllib.request
import unittest

from open_trajectory_harness.deployment_proxy import (
    DeploymentReceiptCollector,
    SanitizedResponsesProxy,
    _SseLineBuffer,
)


class DeploymentProxyTests(unittest.TestCase):
    def test_collector_keeps_only_allowlisted_header_fields(self) -> None:
        collector = DeploymentReceiptCollector()
        collector.record("effective_model", "gpt-test")
        collector.record("cookie", "secret")
        self.assertEqual(
            collector.snapshot(),
            [{"kind": "effective_model", "value": "gpt-test"}],
        )
        self.assertEqual(collector.errors(), ["receipt failed its allowlist schema"])

    def test_chunked_sse_receipts_model_and_response_identity(self) -> None:
        collector = DeploymentReceiptCollector()
        parser = _SseLineBuffer(collector)
        parser.feed(b'data: {"type":"response.created","response":{"id":"resp-')
        parser.feed(b'1","model":"gpt-test"}}\n\n')
        parser.finish()
        self.assertEqual(
            collector.snapshot(),
            [
                {"kind": "effective_model", "value": "gpt-test"},
                {"kind": "response_id", "value": "resp-1"},
            ],
        )

    def test_malformed_sse_records_only_a_generic_error(self) -> None:
        collector = DeploymentReceiptCollector()
        collector.feed_sse_line(b"data: {private malformed bytes")
        self.assertEqual(collector.snapshot(), [])
        self.assertEqual(
            collector.errors(),
            ["response stream contained malformed JSON data"],
        )

    def test_proxy_rejects_paths_outside_backend_api(self) -> None:
        with SanitizedResponsesProxy() as proxy:
            invalid_url = proxy.base_url.replace("/backend-api/", "/outside/")
            with self.assertRaises(urllib.error.HTTPError) as context:
                urllib.request.urlopen(invalid_url, timeout=2)
        self.assertEqual(context.exception.code, 404)
        self.assertEqual(proxy.collector.request_count(), 0)


if __name__ == "__main__":
    unittest.main()
