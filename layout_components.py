"""
layout_components.py - Shared HTML layout fragments used by dashboard pages.
"""

from html import escape


def render_app_header(title, subtitle="", back_href="/", back_label="← Voltar ao painel", show_back_link=True, right_html=""):
    """Render a lightweight shared page header."""
    safe_title = escape(title or "ClaudeFlow")
    safe_subtitle = escape(subtitle or "")
    safe_back_href = escape(back_href or "/")
    safe_back_label = escape(back_label or "← Voltar ao painel")
    subtitle_html = f'<div class="app-header-subtitle">{safe_subtitle}</div>' if safe_subtitle else ""
    back_html = f'<a class="app-back-link" href="{safe_back_href}">{safe_back_label}</a>' if show_back_link else ""
    right_block = f'<div class="app-header-right">{right_html}</div>' if right_html else ""

    return (
        '<header class="app-header">'
        '<div class="app-header-main">'
        '<a class="app-logo-link" href="/" aria-label="Ir para o dashboard">'
        '<img class="app-logo" src="/images/logomarca.png" alt="Painel de Uso do Claude Code">'
        "</a>"
        f'<h1 class="app-header-title">{safe_title}</h1>'
        f"{subtitle_html}"
        "</div>"
        f"{right_block}"
        f"{back_html}"
        "</header>"
    )


def render_app_footer():
    """Render shared footer for all pages."""
    return (
        '<footer class="app-footer">'
        '<div class="app-footer-content">'
        "<p>"
        'GitHub: <a href="https://github.com/alexbertozzi00/claude-usage" target="_blank">'
        "https://github.com/alexbertozzi00/claude-usage</a><br>"
        "Fork por: Alexandre Bertozzi &nbsp;&middot;&nbsp; Licença: MIT"
        "</p>"
        "</div>"
        "</footer>"
    )
