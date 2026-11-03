#!/usr/bin/env python3
"""SS-026 §10.1, §10.4: the README's main example (the ```python block after the marker).

Shared by the unit test (runs it against a mock, type-checks it) and the stack test (runs it
against a test-mode server): `python -I scripts/readme_example.py README.md out.py`.
"""

from __future__ import annotations

import sys
from pathlib import Path

MARKER = "<!-- sdk-readme-example -->"


def extract(markdown: str) -> tuple[str, int]:
    """The example's code and the README line its first line is on."""
    lines = markdown.split("\n")
    markers = [i for i, line in enumerate(lines) if line.strip() == MARKER]
    if len(markers) != 1:
        raise ValueError(f"README: expected one {MARKER}, found {len(markers)}")
    i = markers[0] + 1
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    if i >= len(lines) or lines[i] != "```python":
        raise ValueError(f"README: {MARKER} must be followed by a ```python block")
    end = lines.index("```", i + 1)
    return "\n".join(lines[i + 1 : end]) + "\n", i + 2


if __name__ == "__main__":
    code, _ = extract(Path(sys.argv[1]).read_text("utf-8"))
    Path(sys.argv[2]).write_text(code, "utf-8")
