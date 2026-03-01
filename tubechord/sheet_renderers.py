"""Renderer implementations for sheet music output formats."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import asdict
from typing import Any, cast

from tubechord.sheet_models import ScoreDocument


def _escape_html(text: str) -> str:
    """Escape the three characters that are unsafe in HTML text content."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class SheetRenderer(ABC):
    """Abstract sheet renderer."""

    @property
    @abstractmethod
    def default_extension(self) -> str:
        """Default filename extension for this renderer."""

    @abstractmethod
    def render(
        self,
        *,
        title: str,
        musicxml_bytes: bytes | None = None,
        score_document: ScoreDocument | None = None,
    ) -> str:
        """Render output into a file content string."""


class VerovioHtmlRenderer(SheetRenderer):
    """Render MusicXML bytes into a self-contained HTML document with inline SVG."""

    # Verovio A4 layout constants (verovio abstract units; ~1 unit ≈ 0.1 mm)
    _PAGE_HEIGHT: int = 2970  # A4 portrait height
    _PAGE_WIDTH: int = 2100  # A4 portrait width
    _SCALE: int = 40  # 40% — fits grand staff comfortably on A4
    _PAGE_MARGIN: int = 100  # uniform margin on all four sides

    @property
    def default_extension(self) -> str:
        return ".html"

    def render(
        self,
        *,
        title: str,
        musicxml_bytes: bytes | None = None,
        score_document: ScoreDocument | None = None,
    ) -> str:
        if musicxml_bytes is None:
            raise ValueError("musicxml_bytes is required for HTML rendering.")

        svgs = self.render_svgs(musicxml_bytes)
        return self.build_html(title, svgs)

    def render_svgs(self, musicxml_bytes: bytes) -> list[str]:
        """
        Render a MusicXML document to a list of SVG strings via verovio.

        Raises:
            ValueError: If verovio cannot load the MusicXML data.
        """
        import verovio

        tk = verovio.toolkit()
        tk.setOptions(
            {
                "pageHeight": self._PAGE_HEIGHT,
                "pageWidth": self._PAGE_WIDTH,
                "scale": self._SCALE,
                "pageMarginTop": self._PAGE_MARGIN,
                "pageMarginBottom": self._PAGE_MARGIN,
                "pageMarginLeft": self._PAGE_MARGIN,
                "pageMarginRight": self._PAGE_MARGIN,
                "adjustPageHeight": True,
                "font": "Leipzig",
            }
        )

        loaded: bool = tk.loadData(musicxml_bytes.decode("utf-8"))
        if not loaded:
            raise ValueError("verovio could not load the MusicXML data.")

        page_count: int = tk.getPageCount()
        return [self._render_page_svg(tk, page_no) for page_no in range(1, page_count + 1)]

    def _render_page_svg(self, toolkit: Any, page_no: int) -> str:
        """
        Render one page to SVG with compatibility for multiple verovio bindings.

        Some versions accept keyword arguments, while others only accept
        positional arguments.
        """
        try:
            return cast(str, toolkit.renderToSVG(pageNo=page_no, xmlDeclaration=False))
        except TypeError:
            try:
                return cast(str, toolkit.renderToSVG(page_no, False))
            except TypeError:
                return cast(str, toolkit.renderToSVG(page_no))

    def build_html(self, title: str, svgs: list[str]) -> str:
        """
        Wrap a list of SVG strings in a self-contained HTML document.

        Each SVG is placed in its own ``.page`` div. The stylesheet includes
        both screen styles (white cards on a grey background) and print styles
        (``page-break-after: always`` per page, no drop shadows).
        """
        title_safe = _escape_html(title)
        heading = f"  <h1>{title_safe}</h1>\n" if title else ""
        pages = "\n".join(f'  <div class="page">{svg}</div>' for svg in svgs)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title_safe}</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; }}
    body {{
      font-family: Georgia, serif;
      background: #f0f0f0;
      margin: 0;
      padding: 2rem;
    }}
    h1 {{
      text-align: center;
      font-size: 1.6rem;
      margin-bottom: 2rem;
      color: #222;
    }}
    .page {{
      background: #fff;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
      margin: 0 auto 3rem;
      max-width: 860px;
      padding: 1rem;
    }}
    .page svg {{
      display: block;
      width: 100%;
      height: auto;
    }}
    @media print {{
      body {{
        background: #fff;
        padding: 0;
        margin: 0;
      }}
      h1 {{
        margin-top: 1rem;
      }}
      .page {{
        box-shadow: none;
        page-break-after: always;
        max-width: 100%;
        padding: 0;
        margin: 0;
      }}
      .page:last-child {{
        page-break-after: avoid;
      }}
    }}
  </style>
</head>
<body>
{heading}{pages}
</body>
</html>"""


class VexflowMarkdownRenderer(SheetRenderer):
    """Render a score document into Markdown with an embedded VexFlow script."""

    @property
    def default_extension(self) -> str:
        return ".md"

    def render(
        self,
        *,
        title: str,
        musicxml_bytes: bytes | None = None,
        score_document: ScoreDocument | None = None,
    ) -> str:
        if score_document is None:
            raise ValueError("score_document is required for md-vexflow rendering.")

        title_safe = _escape_html(title)
        score_json = json.dumps(asdict(score_document), separators=(",", ":"))
        score_json = score_json.replace("</", "<\\/")

        return f"""# {title_safe}

This Markdown uses embedded JavaScript + VexFlow. Open it in a Markdown viewer that allows script execution.

<style>
  #tubechord-score {{
    display: grid;
    gap: 1.25rem;
    margin-top: 1rem;
  }}
  .tubechord-measure {{
    border: 1px solid #d8d8d8;
    border-radius: 8px;
    background: #ffffff;
    padding: 0.5rem;
    overflow-x: auto;
  }}
</style>

<div id="tubechord-score"></div>
<script id="tubechord-score-data" type="application/json">{score_json}</script>
<script type="module">
  import {{
    Accidental,
    Formatter,
    Renderer,
    Stave,
    StaveConnector,
    StaveNote,
    Voice
  }} from "https://cdn.jsdelivr.net/npm/vexflow@4.2.3/build/esm/entry/vexflow.js";

  const host = document.getElementById("tubechord-score");
  const payloadNode = document.getElementById("tubechord-score-data");

  if (!host || !payloadNode) {{
    throw new Error("Missing VexFlow score container.");
  }}

  const payload = JSON.parse(payloadNode.textContent || "{{}}");
  const beats = Number(payload.beats) || 4;
  const beatValue = Number(payload.beat_value) || 4;
  const timeSignature = payload.time_signature || "4/4";

  const defaultTreble = [{{ keys: ["b/4"], duration: "wr", accidentals: [null] }}];
  const defaultBass = [{{ keys: ["d/3"], duration: "wr", accidentals: [null] }}];
  const measures = Array.isArray(payload.measures) && payload.measures.length > 0
    ? payload.measures
    : [{{ treble: defaultTreble, bass: defaultBass }}];

  const toStaveNotes = (entries, clef) => entries.map((entry) => {{
    const staveNote = new StaveNote({{
      clef,
      keys: Array.isArray(entry.keys) && entry.keys.length > 0 ? entry.keys : ["c/4"],
      duration: entry.duration || "q",
    }});

    if (Array.isArray(entry.accidentals)) {{
      entry.accidentals.forEach((symbol, noteIndex) => {{
        if (symbol) {{
          staveNote.addModifier(new Accidental(symbol), noteIndex);
        }}
      }});
    }}

    return staveNote;
  }});

  measures.forEach((measure, index) => {{
    const measureRoot = document.createElement("div");
    measureRoot.className = "tubechord-measure";
    host.appendChild(measureRoot);

    const renderer = new Renderer(measureRoot, Renderer.Backends.SVG);
    renderer.resize(760, 230);
    const context = renderer.getContext();

    const trebleStave = new Stave(20, 24, 700);
    const bassStave = new Stave(20, 130, 700);

    if (index === 0) {{
      trebleStave.addClef("treble").addTimeSignature(timeSignature);
      bassStave.addClef("bass").addTimeSignature(timeSignature);
    }} else {{
      trebleStave.addClef("treble");
      bassStave.addClef("bass");
    }}

    trebleStave.setContext(context).draw();
    bassStave.setContext(context).draw();

    const connectorLeft = new StaveConnector(trebleStave, bassStave);
    connectorLeft.setType(StaveConnector.type.SINGLE_LEFT);
    connectorLeft.setContext(context).draw();

    const connectorRight = new StaveConnector(trebleStave, bassStave);
    connectorRight.setType(StaveConnector.type.SINGLE_RIGHT);
    connectorRight.setContext(context).draw();

    const trebleEntries = Array.isArray(measure.treble) && measure.treble.length > 0
      ? measure.treble
      : defaultTreble;
    const bassEntries = Array.isArray(measure.bass) && measure.bass.length > 0
      ? measure.bass
      : defaultBass;

    const trebleVoice = new Voice({{ num_beats: beats, beat_value: beatValue }});
    const bassVoice = new Voice({{ num_beats: beats, beat_value: beatValue }});
    trebleVoice.setMode(Voice.Mode.SOFT);
    bassVoice.setMode(Voice.Mode.SOFT);

    trebleVoice.addTickables(toStaveNotes(trebleEntries, "treble"));
    bassVoice.addTickables(toStaveNotes(bassEntries, "bass"));

    new Formatter().joinVoices([trebleVoice]).joinVoices([bassVoice]).format(
      [trebleVoice, bassVoice],
      580,
    );

    trebleVoice.draw(context, trebleStave);
    bassVoice.draw(context, bassStave);
  }});
</script>
"""
