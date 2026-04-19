"""Tests for oauth_usage.py."""

import json
import unittest
from unittest.mock import patch

import oauth_usage


class _FakeHTTPResponse:
    def __init__(self, payload, status=200):
        self.status = status
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class TestOAuthUsageParsing(unittest.TestCase):
    def test_extracts_percentage_with_multiple_field_names(self):
        payload = {
            "windows": {
                "five_hour": {"utilization": 12.5},
                "seven_day": {"percentage": "37.8%"},
            }
        }
        parsed = oauth_usage._parse_usage_payload(payload)
        self.assertEqual(parsed["currentWindowPercentage"], 12.5)
        self.assertEqual(parsed["weeklyPercentage"], 37.8)

    def test_extracts_ratio_when_percent_missing(self):
        payload = {
            "five_hour": {"used": 25, "limit": 200},
            "seven_day": {"current": 300, "max": 1000},
        }
        parsed = oauth_usage._parse_usage_payload(payload)
        self.assertAlmostEqual(parsed["currentWindowPercentage"], 12.5)
        self.assertAlmostEqual(parsed["weeklyPercentage"], 30.0)


class TestOAuthUsageFetch(unittest.TestCase):
    def setUp(self):
        oauth_usage._USAGE_CACHE["last_success"] = None
        oauth_usage._USAGE_CACHE["expires_at"] = 0

    def test_returns_consistent_structure_when_token_missing(self):
        snapshot = oauth_usage.get_oauth_usage_snapshot(access_token="")
        self.assertIn("currentWindowPercentage", snapshot)
        self.assertIn("weeklyPercentage", snapshot)
        self.assertIn("source", snapshot)
        self.assertIn("raw", snapshot)
        self.assertIn("error", snapshot)

    def test_uses_cache_after_success(self):
        payload = {
            "five_hour": {"percent": 11},
            "seven_day": {"percent": 44},
        }
        with patch("oauth_usage.request.urlopen", return_value=_FakeHTTPResponse(payload)):
            first = oauth_usage.get_oauth_usage_snapshot(access_token="token", cache_ttl_seconds=60)
            second = oauth_usage.get_oauth_usage_snapshot(access_token="token", cache_ttl_seconds=60)

        self.assertEqual(first["currentWindowPercentage"], 11)
        self.assertEqual(second["weeklyPercentage"], 44)
        self.assertEqual(second["cache"], "hit")


if __name__ == "__main__":
    unittest.main()
