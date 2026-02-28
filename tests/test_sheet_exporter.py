"""Unit tests for SheetExporter._build_html (no MIDI file or heavy deps needed)."""

import pytest

from tubechord.sheet_exporter import SheetExporter


def test_build_html_title_in_title_tag() -> None:
    exporter = SheetExporter(title="My Song")
    html = exporter._build_html(["<svg></svg>"])
    assert "<title>My Song</title>" in html


def test_build_html_title_in_h1() -> None:
    exporter = SheetExporter(title="My Song")
    html = exporter._build_html(["<svg></svg>"])
    assert "<h1>My Song</h1>" in html


def test_build_html_empty_title_no_h1() -> None:
    exporter = SheetExporter(title="")
    html = exporter._build_html(["<svg></svg>"])
    assert "<h1>" not in html


def test_build_html_default_title_no_h1() -> None:
    exporter = SheetExporter()
    html = exporter._build_html(["<svg></svg>"])
    assert "<h1>" not in html


def test_build_html_escapes_ampersand() -> None:
    exporter = SheetExporter(title="Fur & Feathers")
    html = exporter._build_html(["<svg></svg>"])
    assert "Fur &amp; Feathers" in html
    assert "Fur & Feathers" not in html.replace("&amp;", "ESCAPED")


def test_build_html_escapes_angle_brackets() -> None:
    exporter = SheetExporter(title="<Cool> Song")
    html = exporter._build_html(["<svg></svg>"])
    assert "&lt;Cool&gt; Song" in html


def test_build_html_single_page_div() -> None:
    exporter = SheetExporter(title="Test")
    html = exporter._build_html(["<svg>p1</svg>"])
    assert html.count('<div class="page">') == 1


def test_build_html_multiple_page_divs() -> None:
    exporter = SheetExporter(title="Test")
    html = exporter._build_html(["<svg>p1</svg>", "<svg>p2</svg>", "<svg>p3</svg>"])
    assert html.count('<div class="page">') == 3


def test_build_html_svg_content_present() -> None:
    exporter = SheetExporter(title="Test")
    html = exporter._build_html(["<svg>UNIQUE_MARKER</svg>"])
    assert "UNIQUE_MARKER" in html


def test_build_html_print_media_query_present() -> None:
    exporter = SheetExporter()
    html = exporter._build_html(["<svg></svg>"])
    assert "@media print" in html


def test_build_html_page_break_present() -> None:
    exporter = SheetExporter()
    html = exporter._build_html(["<svg></svg>"])
    assert "page-break-after: always" in html


def test_build_html_is_valid_html_skeleton() -> None:
    exporter = SheetExporter(title="Skeleton")
    html = exporter._build_html(["<svg></svg>"])
    assert html.startswith("<!DOCTYPE html>")
    assert "<html" in html
    assert "</html>" in html
    assert "<body>" in html
    assert "</body>" in html


# ---------------------------------------------------------------------------
# Integration tests — require a real .mid file and music21 + verovio installed.
# Skip these in CI unless explicitly opted in with -m integration.
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_export_creates_html_file(tmp_path: pytest.TempPathFactory) -> None:
    """Smoke test: export() produces a non-empty HTML file."""
    import os
    mid_files = [
        f for f in os.listdir(".")
        if f.endswith(".mid")
    ]
    if not mid_files:
        pytest.skip("No .mid file found in working directory for integration test.")

    out = tmp_path / "score.html"  # type: ignore[operator]
    exporter = SheetExporter(title="Integration Test")
    exporter.export(mid_files[0], str(out))

    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content
    assert "<svg" in content
