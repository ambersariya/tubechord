"""SheetExporter: Converts a MIDI file to a self-contained HTML file with embedded SVG notation."""


class SheetExporter:
    """
    Converts a MIDI file to a self-contained HTML file with embedded SVG music notation.

    Pipeline
    --------
    1. Parse the MIDI file with music21 → Score object
    2. Remove empty Parts (e.g. Grade 1 left-hand track has no notes)
    3. Export the Score to MusicXML bytes in memory
    4. Load MusicXML into a verovio Toolkit and render every page to SVG
    5. Assemble all SVGs into a single HTML document with screen + print CSS

    The output HTML is completely self-contained: all SVG is inline, verovio
    embeds the Leipzig SMuFL font as path data, and there are no external assets.

    Dependencies
    ------------
    Requires ``music21`` and ``verovio`` to be installed. Both are imported
    lazily inside the private methods so that importing this module does not
    add startup cost to the ``extract`` subcommand.
    """

    # Verovio A4 layout constants (verovio abstract units; ~1 unit ≈ 0.1 mm)
    _PAGE_HEIGHT: int = 2970   # A4 portrait height
    _PAGE_WIDTH: int = 2100    # A4 portrait width
    _SCALE: int = 40           # 40% — fits grand staff comfortably on A4
    _PAGE_MARGIN: int = 100    # uniform margin on all four sides

    def __init__(self, title: str = "") -> None:
        """
        Args:
            title: Human-readable title shown in the HTML ``<h1>`` and ``<title>``.
                   Pass an empty string (default) to omit the heading.
        """
        self.title = title

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _midi_to_musicxml_bytes(self, midi_path: str) -> bytes:
        """
        Parse a MIDI file with music21 and return its MusicXML representation.

        Empty Parts (tracks that contain no notes) are removed before export
        so that Grade 1 files — which have an empty left-hand track — do not
        produce a spurious blank bass-clef staff in the score.

        Args:
            midi_path: Path to a ``.mid`` file.

        Returns:
            UTF-8 encoded MusicXML document as bytes.
        """
        from music21 import converter  # type: ignore[import-untyped]
        from music21.musicxml.m21ToXml import GeneralObjectExporter  # type: ignore[import-untyped]

        score = converter.parse(midi_path, format="midi")

        # Remove parts that contain no note or chord objects.
        for part in list(score.parts):
            if not part.flatten().notes:
                score.remove(part)

        exporter = GeneralObjectExporter(score)
        return exporter.parse()  # type: ignore[no-any-return]

    def _render_svgs(self, musicxml_bytes: bytes) -> list[str]:
        """
        Render a MusicXML document to a list of SVG strings via verovio.

        verovio converts MusicXML to its internal MEI representation, performs
        layout, and renders each page as a standalone SVG string.

        Args:
            musicxml_bytes: UTF-8 encoded MusicXML document.

        Returns:
            One SVG string per page, in page order.

        Raises:
            ValueError: If verovio cannot load the MusicXML data.
        """
        import verovio  # type: ignore[import-untyped]

        tk = verovio.toolkit()
        tk.setOptions({
            "pageHeight": self._PAGE_HEIGHT,
            "pageWidth": self._PAGE_WIDTH,
            "scale": self._SCALE,
            "pageMarginTop": self._PAGE_MARGIN,
            "pageMarginBottom": self._PAGE_MARGIN,
            "pageMarginLeft": self._PAGE_MARGIN,
            "pageMarginRight": self._PAGE_MARGIN,
            "adjustPageHeight": True,
            "font": "Leipzig",
        })

        loaded: bool = tk.loadData(musicxml_bytes.decode("utf-8"))
        if not loaded:
            raise ValueError("verovio could not load the MusicXML data.")

        page_count: int = tk.getPageCount()
        return [
            tk.renderToSVG(pageNo=page_no, xmlDeclaration=False)
            for page_no in range(1, page_count + 1)
        ]

    def _escape_html(self, text: str) -> str:
        """Escape the three characters that are unsafe in HTML text content."""
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def _build_html(self, svgs: list[str]) -> str:
        """
        Wrap a list of SVG strings in a self-contained HTML document.

        Each SVG is placed in its own ``.page`` div. The stylesheet includes
        both screen styles (white cards on a grey background) and print styles
        (``page-break-after: always`` per page, no drop shadows).

        Args:
            svgs: Ordered list of SVG strings, one per musical page.

        Returns:
            Complete HTML document as a string.
        """
        title_safe = self._escape_html(self.title)
        heading = f"  <h1>{title_safe}</h1>\n" if self.title else ""
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

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def export(self, midi_path: str, output_path: str) -> None:
        """
        Convert a MIDI file to a self-contained HTML file with SVG notation.

        Args:
            midi_path:   Path to the source ``.mid`` file.
            output_path: Destination ``.html`` file path.

        Raises:
            ValueError: If verovio cannot load the generated MusicXML.
            OSError: If the output file cannot be written.
        """
        musicxml_bytes = self._midi_to_musicxml_bytes(midi_path)
        svgs = self._render_svgs(musicxml_bytes)
        html = self._build_html(svgs)

        with open(output_path, "w", encoding="utf-8") as fh:
            fh.write(html)
