# AI Contributing Guide (Single Source of Truth)

This is the canonical instruction set for AI coding assistants in this repository.

Entrypoint files such as `AGENTS.md`, `CLAUDE.md`, and `.github/copilot-instructions.md`
should only reference this document to avoid duplicate maintenance.

## Project Summary

- TubeChord extracts chords from YouTube audio and writes beginner-friendly piano MIDI.
- `tubechord sheet` renders MIDI to:
  - `html` (verovio SVG output)
  - `md-vexflow` (Markdown + embedded VexFlow)

## Environment and Tooling

- Python: `3.10+`
- Package manager: `poetry`
- Setup:
  - `poetry install --with dev`

## Required Quality Gate (Must Pass Before Finalizing)

1. `make check`
2. `poetry run pytest -m 'not integration'`

If either fails, fix before proposing completion.

## Code Change Rules

- Keep changes minimal and scoped to the task.
- Do not modify unrelated files.
- Keep CLI UX and output messaging consistent with existing patterns.
- Preserve backward compatibility unless explicitly asked to change behavior.
- Prefer explicit typing; this repository uses strict mypy.
- Do not re-enable global missing-import ignores.
- For untyped third-party packages, add local stubs under `typings/`.

## Formatting and Linting

- Ruff is the source of truth for lint and format.
- If formatting fails, run:
  - `poetry run ruff format .`
  - `poetry run ruff check .`
- Re-run the full quality gate afterwards.

## Common File Map

- CLI orchestration: `tubechord/cli.py`
- Audio/chord analysis: `tubechord/audio_processor.py`, `tubechord/chord_analyzer.py`
- MIDI export: `tubechord/midi_exporter.py`
- Sheet pipeline: `tubechord/sheet_exporter.py`, `tubechord/sheet_renderers.py`
- Sheet models: `tubechord/sheet_models.py`
- Tests: `tests/`
- Typing stubs: `typings/`

## Safety Notes

- Avoid destructive operations unless explicitly requested.
- If blocked by missing dependencies/tools, report the exact command and blocker.
