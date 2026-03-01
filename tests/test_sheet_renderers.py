"""Unit tests for renderers used by SheetExporter."""

from tubechord.sheet_models import ScoreDocument, VexflowMeasure, VexflowNote
from tubechord.sheet_renderers import VexflowMarkdownRenderer


def _sample_document() -> ScoreDocument:
    return ScoreDocument(
        title="Demo",
        time_signature="4/4",
        beats=4,
        beat_value=4,
        measures=[
            VexflowMeasure(
                treble=[VexflowNote(keys=["c/4"], duration="q", accidentals=[None])],
                bass=[VexflowNote(keys=["c/3"], duration="q", accidentals=[None])],
            )
        ],
    )


def test_vexflow_markdown_renderer_has_heading() -> None:
    renderer = VexflowMarkdownRenderer()
    content = renderer.render(title="My Song", score_document=_sample_document())
    assert content.startswith("# My Song")


def test_vexflow_markdown_renderer_includes_container_and_script() -> None:
    renderer = VexflowMarkdownRenderer()
    content = renderer.render(title="Song", score_document=_sample_document())
    assert '<div id="tubechord-score"></div>' in content
    assert 'id="tubechord-score-data"' in content
    assert 'type="module"' in content


def test_vexflow_markdown_renderer_includes_vexflow_import() -> None:
    renderer = VexflowMarkdownRenderer()
    content = renderer.render(title="Song", score_document=_sample_document())
    assert "cdn.jsdelivr.net/npm/vexflow" in content


def test_vexflow_markdown_renderer_embeds_score_payload() -> None:
    renderer = VexflowMarkdownRenderer()
    content = renderer.render(title="Song", score_document=_sample_document())
    assert '"time_signature":"4/4"' in content
    assert '"beat_value":4' in content
    assert '"keys":["c/4"]' in content
