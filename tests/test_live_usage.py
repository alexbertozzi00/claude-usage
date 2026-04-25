"""Tests for live usage provider selection and payload parsing."""

import io
import json
import unittest
from unittest.mock import patch
from urllib.parse import urlparse

from live_usage import UsageBlock, UsageSnapshot, parse_usage_payload
from src.backend.routes.live_usage import handle_live_usage_get


class _FakeHandler:
    def __init__(self):
        self.status = None
        self.headers = {}
        self.wfile = io.BytesIO()

    def send_response(self, status):
        self.status = status

    def send_header(self, key, value):
        self.headers[key] = value

    def end_headers(self):
        return


class TestParseUsagePayload(unittest.TestCase):
    def test_parse_usage_payload_valid_blocks(self):
        payload = """
        Current session
        25% used
        Resets in 4h

        Current week (all models)
        80% used
        Resets Monday
        """
        snapshot = parse_usage_payload(payload, provider="codex")
        self.assertEqual(snapshot.provider, "codex")
        self.assertTrue(snapshot.ok)
        self.assertEqual(snapshot.current_session.used_percent, 25)
        self.assertEqual(snapshot.current_week.used_percent, 80)
        self.assertTrue(snapshot.validation["has_current_session"])
        self.assertTrue(snapshot.validation["has_current_week"])

    def test_parse_usage_payload_unknown_provider_fallback(self):
        snapshot = parse_usage_payload("", provider="unknown-tool")
        self.assertEqual(snapshot.provider, "claude")
        self.assertFalse(snapshot.ok)


class TestLiveUsageRoute(unittest.TestCase):
    def test_api_live_usage_forwards_provider_query(self):
        handler = _FakeHandler()
        parsed = urlparse("/api/live-usage?provider=codex")
        fake_snapshot = UsageSnapshot(
            provider="codex",
            ok=True,
            captured_at="25/04/2026 12:00:00",
            current_session=UsageBlock(used_percent=10, available_percent=90, resets_at=""),
            current_week=UsageBlock(used_percent=50, available_percent=50, resets_at=""),
            validation={"has_current_session": True, "has_current_week": True, "line_count": 10},
            raw_excerpt="",
            error="",
        )
        with patch("src.backend.routes.live_usage.capture_usage") as mock_capture:
            mock_capture.return_value = fake_snapshot
            handled = handle_live_usage_get(handler, parsed, {"json_dumps": json.dumps, "LIVE_USAGE_HTML": "<html></html>"})

        self.assertTrue(handled)
        self.assertEqual(handler.status, 200)
        mock_capture.assert_called_once_with(provider="codex")


if __name__ == "__main__":
    unittest.main()
