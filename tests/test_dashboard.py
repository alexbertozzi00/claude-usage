"""Tests for dashboard.py - API endpoint and data retrieval."""

import json
import os
import sqlite3
import tempfile
import threading
import unittest
import urllib.request
from datetime import timezone, timedelta
from unittest.mock import patch
from pathlib import Path

from scanner import get_db, init_db, upsert_sessions, insert_turns
from dashboard import (
    get_dashboard_data,
    get_sessions_for_hour,
    get_session_history,
    rename_session,
    DashboardHandler,
    HTML_TEMPLATE,
    _format_timestamp,
)

try:
    from http.server import HTTPServer
except ImportError:
    HTTPServer = None


class TestGetDashboardData(unittest.TestCase):
    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmpfile.close()
        self.db_path = Path(self.tmpfile.name)
        conn = get_db(self.db_path)
        init_db(conn)
        # Insert sample data
        sessions = [{
            "session_id": "sess-abc123", "project_name": "user/myproject",
            "first_timestamp": "2026-04-08T09:00:00Z",
            "last_timestamp": "2026-04-08T10:00:00Z",
            "git_branch": "main", "model": "claude-sonnet-4-6",
            "total_input_tokens": 5000, "total_output_tokens": 2000,
            "total_cache_read": 500, "total_cache_creation": 200,
            "turn_count": 10,
        }]
        upsert_sessions(conn, sessions)
        turns = [{
            "session_id": "sess-abc123", "timestamp": "2026-04-08T09:30:00Z",
            "model": "claude-sonnet-4-6", "input_tokens": 500,
            "output_tokens": 200, "cache_read_tokens": 50,
            "cache_creation_tokens": 20, "has_tool_marker": 0, "tool_name": None, "cwd": "/tmp",
        }]
        insert_turns(conn, turns)
        conn.commit()
        conn.close()

    def tearDown(self):
        os.unlink(self.db_path)

    def test_returns_valid_structure(self):
        data = get_dashboard_data(db_path=self.db_path)
        self.assertIn("all_models", data)
        self.assertIn("daily_by_model", data)
        self.assertIn("hourly_by_model", data)
        self.assertIn("project_daily", data)
        self.assertIn("sessions_all", data)
        self.assertIn("generated_at", data)

    def test_project_daily_populated(self):
        data = get_dashboard_data(db_path=self.db_path)
        self.assertGreater(len(data["project_daily"]), 0)
        row = data["project_daily"][0]
        self.assertEqual(row["project"], "myproject")
        self.assertIn("day", row)
        self.assertIn("model", row)
        self.assertIn("output", row)

    def test_models_populated(self):
        data = get_dashboard_data(db_path=self.db_path)
        self.assertIn("claude-sonnet-4-6", data["all_models"])

    def test_sessions_populated(self):
        data = get_dashboard_data(db_path=self.db_path)
        self.assertEqual(len(data["sessions_all"]), 1)
        session = data["sessions_all"][0]
        self.assertEqual(session["project"], "myproject")
        self.assertEqual(session["model"], "claude-sonnet-4-6")
        self.assertEqual(session["input"], 5000)
        self.assertEqual(session["custom_name"], "")

    def test_daily_by_model_populated(self):
        data = get_dashboard_data(db_path=self.db_path)
        self.assertGreater(len(data["daily_by_model"]), 0)
        day = data["daily_by_model"][0]
        self.assertIn("day", day)
        self.assertIn("model", day)
        self.assertIn("input", day)

    def test_hourly_by_model_populated(self):
        data = get_dashboard_data(db_path=self.db_path)
        self.assertGreater(len(data["hourly_by_model"]), 0)
        hour = data["hourly_by_model"][0]
        self.assertIn("day", hour)
        self.assertIn("hour", hour)
        self.assertIn("turns", hour)

    def test_hourly_buckets_use_local_timezone(self):
        data = get_dashboard_data(
            db_path=self.db_path,
            local_tz=timezone(timedelta(hours=-3)),
        )
        hourly = data["hourly_by_model"][0]
        self.assertEqual(hourly["day"], "2026-04-08")
        self.assertEqual(hourly["hour"], "06")

    def test_get_sessions_for_hour(self):
        data = get_sessions_for_hour("09", cutoff="2026-04-01", models=["claude-sonnet-4-6"], db_path=self.db_path)
        self.assertNotIn("error", data)
        self.assertEqual(data["hour"], "09")
        self.assertEqual(len(data["sessions"]), 1)
        self.assertEqual(data["sessions"][0]["session_id_full"], "sess-abc123")

    def test_get_sessions_for_hour_with_timestamp_cutoff(self):
        data = get_sessions_for_hour(
            "09",
            cutoff_ts="2026-04-08T09:15:00Z",
            models=["claude-sonnet-4-6"],
            db_path=self.db_path,
        )
        self.assertNotIn("error", data)
        self.assertEqual(data["hour"], "09")
        self.assertEqual(data["cutoff_ts"], "2026-04-08T09:15:00Z")
        self.assertEqual(len(data["sessions"]), 1)

    def test_get_sessions_for_hour_uses_local_timezone(self):
        data = get_sessions_for_hour(
            "06",
            cutoff="2026-04-01",
            models=["claude-sonnet-4-6"],
            db_path=self.db_path,
            local_tz=timezone(timedelta(hours=-3)),
        )
        self.assertNotIn("error", data)
        self.assertEqual(len(data["sessions"]), 1)
        self.assertEqual(data["sessions"][0]["session_id_full"], "sess-abc123")

    def test_hourly_ignores_tool_marker_turns(self):
        conn = get_db(self.db_path)
        upsert_sessions(conn, [{
            "session_id": "sess-tool-only",
            "project_name": "user/myproject",
            "first_timestamp": "2026-04-08T09:10:00Z",
            "last_timestamp": "2026-04-08T09:10:00Z",
            "git_branch": "main",
            "model": "claude-sonnet-4-6",
            "total_input_tokens": 100,
            "total_output_tokens": 50,
            "total_cache_read": 0,
            "total_cache_creation": 0,
            "turn_count": 1,
        }])
        insert_turns(conn, [{
            "session_id": "sess-tool-only",
            "timestamp": "2026-04-08T09:10:00Z",
            "model": "claude-sonnet-4-6",
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
            "has_tool_marker": 1,
            "tool_name": "Read",
            "cwd": "/tmp",
        }])
        conn.commit()
        conn.close()

        data = get_dashboard_data(db_path=self.db_path)
        total_turns = sum(r["turns"] for r in data["hourly_by_model"])
        self.assertEqual(total_turns, 1)

        hour_data = get_sessions_for_hour("09", cutoff="2026-04-01", models=["claude-sonnet-4-6"], db_path=self.db_path)
        session_ids = {s["session_id_full"] for s in hour_data["sessions"]}
        self.assertNotIn("sess-tool-only", session_ids)

    def test_missing_db_returns_error(self):
        data = get_dashboard_data(db_path=Path("/nonexistent/path/usage.db"))
        self.assertIn("error", data)

    def test_session_id_truncated(self):
        data = get_dashboard_data(db_path=self.db_path)
        session = data["sessions_all"][0]
        self.assertEqual(len(session["session_id"]), 8)
    def test_session_id_full_present(self):
        data = get_dashboard_data(db_path=self.db_path)
        session = data["sessions_all"][0]
        self.assertEqual(session["session_id_full"], "sess-abc123")

    def test_session_duration_calculated(self):
        data = get_dashboard_data(db_path=self.db_path)
        session = data["sessions_all"][0]
        # 1 hour = 60 minutes
        self.assertEqual(session["duration_min"], 60.0)

    def test_dates_are_formatted_ddmmyyyy(self):
        data = get_dashboard_data(db_path=self.db_path)
        session = data["sessions_all"][0]
        self.assertEqual(session["last"], "08/04/2026 10:00:00")
        self.assertRegex(data["generated_at"], r"\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}")


class TestTimestampFormatting(unittest.TestCase):
    def test_converts_utc_to_local_timezone_when_aware(self):
        formatted = _format_timestamp(
            "2026-04-19T20:12:00Z",
            local_tz=timezone(timedelta(hours=-3)),
        )

        self.assertEqual(formatted, "19/04/2026 17:12:00")

class TestSessionHistory(unittest.TestCase):
    def setUp(self):
        self.session_id = "sess-history-123"
        self.tmpdb = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmpdb.close()
        self.db_path = Path(self.tmpdb.name)

        self.tmpjsonl = tempfile.NamedTemporaryFile(
            suffix=".jsonl", delete=False, mode="w", encoding="utf-8"
        )
        records = [
            {
                "type": "user",
                "sessionId": self.session_id,
                "timestamp": "2026-04-08T09:00:00Z",
                "message": {"content": [{"type": "text", "text": "Olá, Claude"}]},
            },
            {
                "type": "assistant",
                "sessionId": self.session_id,
                "timestamp": "2026-04-08T09:00:01Z",
                "message": {
                    "id": "msg-1",
                    "content": [{"type": "text", "text": "Resposta parcial"}],
                },
            },
            {
                "type": "assistant",
                "sessionId": self.session_id,
                "timestamp": "2026-04-08T09:00:02Z",
                "message": {
                    "id": "msg-1",
                    "content": [{"type": "text", "text": "Resposta final"}],
                },
            },
        ]
        for record in records:
            self.tmpjsonl.write(json.dumps(record) + "\n")
        self.tmpjsonl.close()

        conn = get_db(self.db_path)
        init_db(conn)
        conn.execute(
            "INSERT INTO processed_files (path, mtime, lines) VALUES (?, ?, ?)",
            (self.tmpjsonl.name, os.path.getmtime(self.tmpjsonl.name), len(records)),
        )
        conn.commit()
        conn.close()

    def tearDown(self):
        os.unlink(self.db_path)
        os.unlink(self.tmpjsonl.name)

    def test_get_session_history_returns_entries(self):
        data = get_session_history(self.session_id, db_path=self.db_path)
        self.assertNotIn("error", data)
        self.assertEqual(data["session_id"], self.session_id)
        self.assertEqual(len(data["entries"]), 2)
        self.assertEqual(data["entries"][0]["role"], "user")
        self.assertEqual(data["entries"][0]["timestamp"], "08/04/2026 09:00:00")
        self.assertIn("Resposta final", data["entries"][1]["text"])
        self.assertEqual(data["custom_name"], "")

    def test_get_session_history_missing_session(self):
        data = get_session_history("sess-unknown", db_path=self.db_path)
        self.assertIn("error", data)


class TestDashboardHTTP(unittest.TestCase):
    """Integration test: start server and make HTTP requests."""

    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), DashboardHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever)
        cls.thread.daemon = True
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_index_returns_html(self):
        url = f"http://127.0.0.1:{self.port}/"
        with urllib.request.urlopen(url) as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("text/html", resp.headers["Content-Type"])

    def test_api_data_returns_json(self):
        url = f"http://127.0.0.1:{self.port}/api/data"
        with urllib.request.urlopen(url) as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("application/json", resp.headers["Content-Type"])
            data = json.loads(resp.read())
            # Should have expected keys (or error if no DB)
            self.assertTrue("all_models" in data or "error" in data)

    def test_hour_page_returns_html(self):
        url = f"http://127.0.0.1:{self.port}/hour/09"
        try:
            with urllib.request.urlopen(url) as resp:
                self.assertEqual(resp.status, 200)
                self.assertIn("text/html", resp.headers["Content-Type"])
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 404)

    def test_api_rescan_returns_json(self):
        url = f"http://127.0.0.1:{self.port}/api/rescan"
        req = urllib.request.Request(url, method="POST")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("application/json", resp.headers["Content-Type"])
            data = json.loads(resp.read())
            self.assertIn("new", data)
            self.assertIn("updated", data)
            self.assertIn("skipped", data)

    def test_template_mentions_rename_api(self):
        self.assertIn("/api/session/rename", HTML_TEMPLATE)

    def test_template_mentions_sessions_pagination(self):
        self.assertIn('id="sessions-pager"', HTML_TEMPLATE)
        self.assertIn("setSessionsPage", HTML_TEMPLATE)

    def test_template_formats_long_session_duration_in_hours(self):
        self.assertIn("formatSessionDuration", HTML_TEMPLATE)
        self.assertIn("durationMin >= 60", HTML_TEMPLATE)
        self.assertIn("toFixed(1)} h", HTML_TEMPLATE)

    def test_template_mentions_auto_refresh_toggle(self):
        self.assertIn('id="refresh-toggle-input"', HTML_TEMPLATE)
        self.assertIn("onAutoRefreshToggle", HTML_TEMPLATE)
        self.assertIn("ccu:autoRefreshPaused", HTML_TEMPLATE)

    def test_template_mentions_auto_refresh_paused_status(self):
        self.assertIn("Atualização automática: pausada", HTML_TEMPLATE)
        self.assertIn("Atualização automática: ativa", HTML_TEMPLATE)

    def test_template_mentions_hourly_activity_explanation(self):
        self.assertIn("Atividade por Hora", HTML_TEMPLATE)
        self.assertIn("média de tokens", HTML_TEMPLATE)
        self.assertIn("Ajuda sobre atividade por hora", HTML_TEMPLATE)
        self.assertIn("chart-title-row", HTML_TEMPLATE)
        self.assertIn("/hour/", HTML_TEMPLATE)

    def test_404_for_unknown_path(self):
        url = f"http://127.0.0.1:{self.port}/nonexistent"
        try:
            urllib.request.urlopen(url)
            self.fail("Expected 404")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 404)


class TestRenameSession(unittest.TestCase):
    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmpfile.close()
        self.db_path = Path(self.tmpfile.name)
        conn = get_db(self.db_path)
        init_db(conn)
        upsert_sessions(conn, [{
            "session_id": "sess-rename-123",
            "project_name": "user/myproject",
            "first_timestamp": "2026-04-08T09:00:00Z",
            "last_timestamp": "2026-04-08T10:00:00Z",
            "git_branch": "main",
            "model": "claude-sonnet-4-6",
            "total_input_tokens": 1,
            "total_output_tokens": 1,
            "total_cache_read": 0,
            "total_cache_creation": 0,
            "turn_count": 1,
        }])
        conn.commit()
        conn.close()

    def tearDown(self):
        os.unlink(self.db_path)

    def test_rename_success(self):
        result, code = rename_session("sess-rename-123", "Nova sessão", db_path=self.db_path)
        self.assertEqual(code, 200)
        self.assertTrue(result["ok"])
        self.assertEqual(result["custom_name"], "Nova sessão")

    def test_rename_clear_name(self):
        rename_session("sess-rename-123", "Nome temporário", db_path=self.db_path)
        result, code = rename_session("sess-rename-123", "", db_path=self.db_path)
        self.assertEqual(code, 200)
        self.assertIsNone(result["custom_name"])

    def test_rename_nonexistent_session(self):
        result, code = rename_session("sess-inexistente", "Nome", db_path=self.db_path)
        self.assertEqual(code, 404)
        self.assertFalse(result["ok"])

    def test_rename_too_long(self):
        result, code = rename_session("sess-rename-123", "a" * 81, db_path=self.db_path)
        self.assertEqual(code, 400)
        self.assertFalse(result["ok"])


class TestHTMLTemplate(unittest.TestCase):
    def test_template_is_valid_html(self):
        self.assertIn("<!DOCTYPE html>", HTML_TEMPLATE)
        self.assertIn("</html>", HTML_TEMPLATE)

    def test_template_has_esc_function(self):
        """Verify XSS protection is present (PR #10)."""
        self.assertIn("function esc(", HTML_TEMPLATE)

    def test_template_has_chart_js(self):
        self.assertIn("chart.js", HTML_TEMPLATE.lower())

    def test_template_has_substring_matching(self):
        """Verify getPricing falls back to substring match for unknown models."""
        self.assertIn("m.includes('opus')", HTML_TEMPLATE)
        self.assertIn("m.includes('sonnet')", HTML_TEMPLATE)
        self.assertIn("m.includes('haiku')", HTML_TEMPLATE)

    def test_unknown_models_return_null(self):
        """Verify getPricing returns null for non-Anthropic models."""
        self.assertIn("return null;", HTML_TEMPLATE)

    def test_template_has_session_link(self):
        self.assertIn("session-link", HTML_TEMPLATE)

    def test_template_has_session_navigation_link(self):
        self.assertIn("encodeURIComponent(s.session_id_full)", HTML_TEMPLATE)

    def test_template_declares_renaming_session_state(self):
        self.assertIn("const renamingSessions = new Set();", HTML_TEMPLATE)

    def test_template_has_insights_section(self):
        self.assertIn("Insights Acionáveis", HTML_TEMPLATE)
        self.assertIn("id=\"insights-list\"", HTML_TEMPLATE)
        self.assertIn("function renderInsights(", HTML_TEMPLATE)


class TestPricingParity(unittest.TestCase):
    """Verify CLI and dashboard pricing tables stay in sync."""

    def _extract_js_pricing(self):
        """Extract pricing values from the dashboard JS PRICING object."""
        import re
        prices = {}
        for match in re.finditer(
            r"'(claude-[^']+)':\s*\{\s*input:\s*([\d.]+),\s*output:\s*([\d.]+)",
            HTML_TEMPLATE
        ):
            model, inp, out = match.group(1), float(match.group(2)), float(match.group(3))
            prices[model] = {"input": inp, "output": out}
        return prices

    def test_all_cli_models_in_dashboard(self):
        from cli import PRICING as CLI_PRICING
        js_prices = self._extract_js_pricing()
        for model in CLI_PRICING:
            self.assertIn(model, js_prices, f"{model} missing from dashboard JS")

    def test_prices_match(self):
        from cli import PRICING as CLI_PRICING
        js_prices = self._extract_js_pricing()
        for model in CLI_PRICING:
            self.assertAlmostEqual(
                CLI_PRICING[model]["input"], js_prices[model]["input"],
                msg=f"{model} input price mismatch"
            )
            self.assertAlmostEqual(
                CLI_PRICING[model]["output"], js_prices[model]["output"],
                msg=f"{model} output price mismatch"
            )


if __name__ == "__main__":
    unittest.main()
