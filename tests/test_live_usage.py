from live_usage import _snapshot_from_clean_text


def test_snapshot_parses_standard_layout():
    text = """
Current session
████ 1% used
Resets 8pm (America/Sao_Paulo)

Current week (all models)
████ 51% used
Resets Apr 24, 11am (America/Sao_Paulo)
"""
    snap = _snapshot_from_clean_text(text)
    assert snap.ok is True
    assert snap.current_session.used_percent == 1
    assert snap.current_week.used_percent == 51
    assert "America/Sao_Paulo" in snap.current_session.resets_at


def test_snapshot_parses_fallback_layout_without_headings():
    text = """
Status Config Usage Stats
1% used
Resets 8pm (America/Sao_Paulo)
51% used
Resets Apr 24, 11am (America/Sao_Paulo)
"""
    snap = _snapshot_from_clean_text(text)
    assert snap.ok is True
    assert snap.current_session.used_percent == 1
    assert snap.current_week.used_percent == 51
