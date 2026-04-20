"""Tests for cli.py - pricing, formatting, and cost calculation."""

import unittest
import tempfile
import os
from pathlib import Path
from cli import get_pricing, calc_cost, fmt, fmt_cost, fmt_date, fmt_timestamp, PRICING
from cli import build_insights
from src.backend.scanner import get_db, init_db, upsert_sessions, insert_turns


class TestGetPricing(unittest.TestCase):
    def test_exact_model_match(self):
        p = get_pricing("claude-opus-4-6")
        self.assertEqual(p["input"], 5.00)
        self.assertEqual(p["output"], 25.00)

    def test_all_known_models_have_pricing(self):
        for model in ("claude-opus-4-6", "claude-opus-4-5",
                       "claude-sonnet-4-6", "claude-sonnet-4-5",
                       "claude-haiku-4-5", "claude-haiku-4-6"):
            p = get_pricing(model)
            self.assertGreater(p["input"], 0, f"Missing input price for {model}")
            self.assertGreater(p["output"], 0, f"Missing output price for {model}")

    def test_prefix_match(self):
        # A model name with a suffix should still match the base
        p = get_pricing("claude-sonnet-4-6-20260401")
        self.assertEqual(p["input"], 3.00)
        self.assertEqual(p["output"], 15.00)

    def test_substring_match_opus(self):
        p = get_pricing("new-opus-5-model")
        self.assertEqual(p["input"], 5.00)
        self.assertEqual(p["output"], 25.00)

    def test_substring_match_sonnet(self):
        p = get_pricing("custom-sonnet-variant")
        self.assertEqual(p["input"], 3.00)
        self.assertEqual(p["output"], 15.00)

    def test_substring_match_haiku(self):
        p = get_pricing("experimental-haiku-fast")
        self.assertEqual(p["input"], 1.00)
        self.assertEqual(p["output"], 5.00)

    def test_substring_match_case_insensitive(self):
        p = get_pricing("Claude-Opus-Next")
        self.assertEqual(p["input"], 5.00)

    def test_prefix_takes_precedence_over_substring(self):
        # Exact prefix match should win over substring fallback
        p = get_pricing("claude-opus-4-6-preview")
        self.assertEqual(p["input"], 5.00)
        self.assertEqual(p["output"], 25.00)

    def test_unknown_model_returns_none(self):
        self.assertIsNone(get_pricing("glm-5.1"))
        self.assertIsNone(get_pricing("gpt-4o"))
        self.assertIsNone(get_pricing("some-unknown-model"))

    def test_none_model_returns_none(self):
        self.assertIsNone(get_pricing(None))

    def test_empty_string_returns_none(self):
        self.assertIsNone(get_pricing(""))


class TestCalcCost(unittest.TestCase):
    def test_basic_cost_calculation(self):
        # 1M input tokens of Sonnet at $3/MTok = $3.00
        cost = calc_cost("claude-sonnet-4-6", 1_000_000, 0, 0, 0)
        self.assertAlmostEqual(cost, 3.00)

    def test_output_tokens(self):
        # 1M output tokens of Sonnet at $15/MTok = $15.00
        cost = calc_cost("claude-sonnet-4-6", 0, 1_000_000, 0, 0)
        self.assertAlmostEqual(cost, 15.00)

    def test_cache_read_discount(self):
        # Cache read = 10% of input price
        # 1M cache_read of Opus at $5 * 0.10 = $0.50
        cost = calc_cost("claude-opus-4-6", 0, 0, 1_000_000, 0)
        self.assertAlmostEqual(cost, 0.50)

    def test_cache_creation_premium(self):
        # Cache creation = 125% of input price
        # 1M cache_creation of Opus at $5 * 1.25 = $6.25
        cost = calc_cost("claude-opus-4-6", 0, 0, 0, 1_000_000)
        self.assertAlmostEqual(cost, 6.25)

    def test_combined_cost(self):
        cost = calc_cost("claude-haiku-4-5",
                         inp=500_000, out=100_000,
                         cache_read=200_000, cache_creation=50_000)
        expected = (
            500_000 * 1.00 / 1_000_000 +   # input
            100_000 * 5.00 / 1_000_000 +    # output
            200_000 * 1.00 * 0.10 / 1_000_000 +  # cache read
            50_000 * 1.00 * 1.25 / 1_000_000     # cache creation
        )
        self.assertAlmostEqual(cost, expected)

    def test_zero_tokens(self):
        cost = calc_cost("claude-opus-4-6", 0, 0, 0, 0)
        self.assertEqual(cost, 0.0)

    def test_unknown_model_costs_zero(self):
        cost = calc_cost("glm-5.1", 1_000_000, 500_000, 100_000, 50_000)
        self.assertEqual(cost, 0.0)

    def test_non_anthropic_model_costs_zero(self):
        cost = calc_cost("gpt-4o", 1_000_000, 500_000, 0, 0)
        self.assertEqual(cost, 0.0)


class TestFmt(unittest.TestCase):
    def test_millions(self):
        self.assertEqual(fmt(1_500_000), "1.50M")
        self.assertEqual(fmt(1_000_000), "1.00M")

    def test_thousands(self):
        self.assertEqual(fmt(1_500), "1.5K")
        self.assertEqual(fmt(1_000), "1.0K")

    def test_small_numbers(self):
        self.assertEqual(fmt(999), "999")
        self.assertEqual(fmt(0), "0")


class TestFmtCost(unittest.TestCase):
    def test_formatting(self):
        self.assertEqual(fmt_cost(3.0), "$3.0000")
        self.assertEqual(fmt_cost(0.0001), "$0.0001")
        self.assertEqual(fmt_cost(0), "$0.0000")


class TestDateFormatting(unittest.TestCase):
    def test_fmt_date_iso_to_br(self):
        self.assertEqual(fmt_date("2026-04-19"), "19/04/2026")

    def test_fmt_timestamp_iso_to_br(self):
        self.assertEqual(
            fmt_timestamp("2026-04-19T13:45:59Z"),
            "19/04/2026 13:45:59"
        )


class TestPricingConsistency(unittest.TestCase):
    """Ensure CLI pricing matches known Anthropic API rates."""

    def test_opus_pricing(self):
        for model in ("claude-opus-4-6", "claude-opus-4-5"):
            p = get_pricing(model)
            self.assertEqual(p["input"], 5.00, f"{model} input price wrong")
            self.assertEqual(p["output"], 25.00, f"{model} output price wrong")

    def test_sonnet_pricing(self):
        for model in ("claude-sonnet-4-6", "claude-sonnet-4-5"):
            p = get_pricing(model)
            self.assertEqual(p["input"], 3.00, f"{model} input price wrong")
            self.assertEqual(p["output"], 15.00, f"{model} output price wrong")

    def test_haiku_pricing(self):
        for model in ("claude-haiku-4-5", "claude-haiku-4-6"):
            p = get_pricing(model)
            self.assertEqual(p["input"], 1.00, f"{model} input price wrong")
            self.assertEqual(p["output"], 5.00, f"{model} output price wrong")


class TestBuildInsights(unittest.TestCase):
    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmpfile.close()
        self.db_path = Path(self.tmpfile.name)
        conn = get_db(self.db_path)
        init_db(conn)
        sessions = [{
            "session_id": "sess-insight-1", "project_name": "acme/api",
            "first_timestamp": "2026-04-18T10:00:00Z",
            "last_timestamp": "2026-04-18T11:00:00Z",
            "git_branch": "main", "model": "claude-sonnet-4-6",
            "total_input_tokens": 3000, "total_output_tokens": 1000,
            "total_cache_read": 600, "total_cache_creation": 50,
            "turn_count": 3,
        }]
        upsert_sessions(conn, sessions)
        turns = [
            {
                "session_id": "sess-insight-1", "timestamp": "2026-04-18T10:20:00Z",
                "model": "claude-sonnet-4-6", "input_tokens": 1000,
                "output_tokens": 400, "cache_read_tokens": 300,
                "cache_creation_tokens": 20, "tool_name": None, "cwd": "/tmp",
            },
            {
                "session_id": "sess-insight-1", "timestamp": "2026-04-18T10:50:00Z",
                "model": "claude-sonnet-4-6", "input_tokens": 2000,
                "output_tokens": 600, "cache_read_tokens": 300,
                "cache_creation_tokens": 30, "tool_name": None, "cwd": "/tmp",
            },
        ]
        insert_turns(conn, turns)
        conn.commit()
        conn.close()

    def tearDown(self):
        os.unlink(self.db_path)

    def test_build_insights_with_data(self):
        conn = get_db(self.db_path)
        insights = build_insights(conn, window_days=30)
        conn.close()
        self.assertTrue(insights["has_data"])
        self.assertEqual(insights["sessions"], 1)
        self.assertEqual(insights["turns"], 2)
        self.assertEqual(insights["top_model"], "claude-sonnet-4-6")
        self.assertEqual(insights["top_project"], "acme/api")
        self.assertAlmostEqual(insights["cache_ratio"], 0.2)
        self.assertGreaterEqual(len(insights["recommendations"]), 2)

    def test_build_insights_no_data_in_window(self):
        conn = get_db(self.db_path)
        insights = build_insights(conn, window_days=0)
        conn.close()
        self.assertFalse(insights["has_data"])


if __name__ == "__main__":
    unittest.main()


class TestExport(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "usage.db"
        self.output_base = Path(self.tmpdir.name) / "reports" / "usage_report"
        conn = get_db(self.db_path)
        init_db(conn)
        sessions = [
            {
                "session_id": "sess-exp-1", "project_name": "acme/api",
                "first_timestamp": "2026-04-17T08:00:00Z",
                "last_timestamp": "2026-04-17T09:00:00Z",
                "git_branch": "main", "model": "claude-sonnet-4-6",
                "total_input_tokens": 1200, "total_output_tokens": 600,
                "total_cache_read": 100, "total_cache_creation": 50,
                "turn_count": 2,
            },
            {
                "session_id": "sess-exp-2", "project_name": "acme/web",
                "first_timestamp": "2026-04-12T08:00:00Z",
                "last_timestamp": "2026-04-12T09:00:00Z",
                "git_branch": "main", "model": "claude-haiku-4-5",
                "total_input_tokens": 800, "total_output_tokens": 100,
                "total_cache_read": 50, "total_cache_creation": 10,
                "turn_count": 1,
            },
        ]
        upsert_sessions(conn, sessions)
        turns = [
            {
                "session_id": "sess-exp-1", "timestamp": "2026-04-17T08:10:00Z",
                "model": "claude-sonnet-4-6", "input_tokens": 700,
                "output_tokens": 400, "cache_read_tokens": 100,
                "cache_creation_tokens": 30, "tool_name": None, "cwd": "/tmp",
            },
            {
                "session_id": "sess-exp-1", "timestamp": "2026-04-17T08:30:00Z",
                "model": "claude-sonnet-4-6", "input_tokens": 500,
                "output_tokens": 200, "cache_read_tokens": 0,
                "cache_creation_tokens": 20, "tool_name": None, "cwd": "/tmp",
            },
            {
                "session_id": "sess-exp-2", "timestamp": "2026-04-12T08:15:00Z",
                "model": "claude-haiku-4-5", "input_tokens": 800,
                "output_tokens": 100, "cache_read_tokens": 50,
                "cache_creation_tokens": 10, "tool_name": None, "cwd": "/tmp",
            },
        ]
        insert_turns(conn, turns)
        conn.commit()
        conn.close()

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_export_json_structure_and_totals(self):
        import cli
        original = cli.DB_PATH
        cli.DB_PATH = self.db_path
        try:
            cli.cmd_export(format="json", period="7d", output=str(self.output_base))
        finally:
            cli.DB_PATH = original

        data = __import__("json").loads(self.output_base.with_suffix(".json").read_text(encoding="utf-8"))
        self.assertIn("schema_version", data)
        self.assertIn("period", data)
        self.assertIn("kpis", data)
        self.assertIn("comparison_previous_period", data)
        self.assertIn("top_models", data)
        self.assertIn("top_projects", data)
        self.assertIn("alerts", data)

        total_models_inp = sum(item["input_tokens"] for item in data["top_models"])
        self.assertEqual(total_models_inp, data["kpis"]["input_tokens"])

    def test_export_markdown_contains_required_sections(self):
        import cli
        original = cli.DB_PATH
        cli.DB_PATH = self.db_path
        try:
            cli.cmd_export(format="md", period="7d", output=str(self.output_base))
        finally:
            cli.DB_PATH = original

        markdown = self.output_base.with_suffix(".md").read_text(encoding="utf-8")
        self.assertIn("## KPIs", markdown)
        self.assertIn("## Top modelos", markdown)
        self.assertIn("## Top projetos", markdown)
        self.assertIn("## Alertas", markdown)

    def test_export_db_not_found_raises_system_exit(self):
        import cli
        original = cli.DB_PATH
        cli.DB_PATH = Path(self.tmpdir.name) / "missing.db"
        try:
            with self.assertRaises(SystemExit):
                cli.cmd_export(format="json", period="7d", output=str(self.output_base))
        finally:
            cli.DB_PATH = original

    def test_export_without_data(self):
        import cli
        empty_db = Path(self.tmpdir.name) / "empty.db"
        conn = get_db(empty_db)
        init_db(conn)
        conn.commit()
        conn.close()

        original = cli.DB_PATH
        cli.DB_PATH = empty_db
        try:
            cli.cmd_export(format="json", period="7d", output=str(self.output_base))
        finally:
            cli.DB_PATH = original

        data = __import__("json").loads(self.output_base.with_suffix(".json").read_text(encoding="utf-8"))
        self.assertEqual(data["kpis"]["turns"], 0)
        self.assertEqual(data["top_models"], [])
        self.assertIn("Nenhuma sessão", " ".join(data["alerts"]))
