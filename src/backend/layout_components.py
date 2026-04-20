"""
layout_components.py - Shared layout context helpers used by dashboard pages.
"""

from html import escape


def build_app_header_context(
    title,
    subtitle="",
    back_href="/",
    back_label="← Voltar ao painel",
    show_back_link=True,
    right_html="",
):
    """Build escaped context values for header rendering."""
    safe_title = escape(title or "ClaudeFlow")
    safe_subtitle = escape(subtitle or "")
    safe_back_href = escape(back_href or "/")
    safe_back_label = escape(back_label or "← Voltar ao painel")
    subtitle_html = f'<div class="app-header-subtitle">{safe_subtitle}</div>' if safe_subtitle else ""
    back_html = f'<a class="app-back-link" href="{safe_back_href}">{safe_back_label}</a>' if show_back_link else ""
    right_block = f'<div class="app-header-right">{right_html}</div>' if right_html else ""

    return {
        "title": safe_title,
        "subtitle_html": subtitle_html,
        "back_html": back_html,
        "right_block": right_block,
    }


def build_app_footer_context():
    """Build footer context for shared pages."""
    return {
        "copyright": "Alexandre Bertozzi ©2026",
    }
