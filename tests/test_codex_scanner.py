"""Tests for Codex layered ingestion MVP."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codex_scanner import scan_codex_usage
from live_usage import UsageBlock, UsageSnapshot
from cli import parse_codex_scan_args


class TestCodexScanner(unittest.TestCase):
    def test_uses_local_logs_as_primary_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            logs_dir = root / ".codex"
            logs_dir.mkdir(parents=True)
            log_file = logs_dir / "session.jsonl"
            log_file.write_text(
                json.dumps({
                    "timestamp": "2026-04-25T10:00:00Z",
                    "session_id": "codex-s1",
                    "model": "codex-pro",
                    "input_tokens": 120,
                    "output_tokens": 45,
                }) + "\n",
                encoding="utf-8",
            )

            with patch("codex_scanner.capture_usage") as mock_capture:
                result = scan_codex_usage(logs_dirs=[logs_dir])
            self.assertEqual(result["source"], "local_logs")
            self.assertEqual(result["events"], 1)
            self.assertEqual(result["totals"]["input_tokens"], 120)
            mock_capture.assert_not_called()

    def test_fallbacks_to_cli_when_no_logs(self):
        snapshot = UsageSnapshot(
            provider="codex",
            ok=True,
            captured_at="25/04/2026 10:00:00",
            current_session=UsageBlock(used_percent=20, available_percent=80, resets_at=""),
            current_week=UsageBlock(used_percent=40, available_percent=60, resets_at=""),
            validation={"has_current_session": True, "has_current_week": True, "line_count": 4},
            raw_excerpt="",
            error="",
        )
        with tempfile.TemporaryDirectory() as tmp:
            with patch("codex_scanner.capture_usage", return_value=snapshot) as mock_capture:
                result = scan_codex_usage(logs_dirs=[Path(tmp)])
        self.assertEqual(result["source"], "cli_usage")
        self.assertEqual(result["events"], 0)
        self.assertIsNotNone(result["cli_snapshot"])
        mock_capture.assert_called_once()

    def test_manual_import_as_last_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            import_file = root / "manual.csv"
            import_file.write_text(
                "timestamp,session_id,model,input_tokens,output_tokens\n"
                "2026-04-25T11:00:00Z,codex-manual-1,codex-mini,30,12\n",
                encoding="utf-8",
            )
            failed_snapshot = UsageSnapshot(
                provider="codex",
                ok=False,
                captured_at="25/04/2026 10:00:00",
                current_session=UsageBlock(),
                current_week=UsageBlock(),
                validation={},
                raw_excerpt="",
                error="codex indisponível",
            )
            with patch("codex_scanner.capture_usage", return_value=failed_snapshot):
                result = scan_codex_usage(logs_dirs=[root / "missing"], manual_import_file=import_file)
        self.assertEqual(result["source"], "manual_import")
        self.assertEqual(result["events"], 1)
        self.assertEqual(result["totals"]["output_tokens"], 12)


class TestCodexCliArgs(unittest.TestCase):
    def test_parse_codex_scan_args(self):
        parsed = parse_codex_scan_args([
            "--codex-dir", "/tmp/codex",
            "--import-file", "manual.json",
            "--output", "report.json",
        ])
        self.assertEqual(parsed["codex_dir"], "/tmp/codex")
        self.assertEqual(parsed["import_file"], "manual.json")
        self.assertEqual(parsed["output"], "report.json")

    def test_parse_codex_scan_args_rejects_unknown(self):
        with self.assertRaises(ValueError):
            parse_codex_scan_args(["--unknown", "x"])

    def test_parse_codex_scan_args_no_db_flag(self):
        parsed = parse_codex_scan_args(["--no-db"])
        self.assertTrue(parsed["no_db"])


if __name__ == "__main__":
    unittest.main()
