"""Where the SDK finds its inputs (SS-026 §9).

In the public mirror they are files of this package, at the paths in INPUTS. In the Storeshot
monorepo each has one source of truth outside the package, mapped by mirror/inputs.json (monorepo
only, never exported); the mirror export copies them with the same map, so no copy ever exists in
the monorepo. Stdlib only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
MAP_FILE = PACKAGE_ROOT / "mirror" / "inputs.json"

INPUTS = {
    "contract": "contract/openapi.json",
    "webhook_vectors": "tests/fixtures/webhook-signature-vectors.json",
    "webhook_snippet": "tests/fixtures/verify_webhook.py",
}


def input_path(name: str) -> Path:
    """Absolute path of an input (`contract`, `webhook_vectors`, `webhook_snippet`)."""
    rel = INPUTS[name]
    if not MAP_FILE.is_file():
        return PACKAGE_ROOT / rel
    mapping: dict[str, Any] = json.loads(MAP_FILE.read_text("utf-8"))
    source: str | None = mapping["inputs"].get(rel)
    if source is None:
        raise KeyError(f"mirror/inputs.json has no source for {rel}")
    root: str = mapping["monorepoRoot"]
    return (PACKAGE_ROOT / root / source).resolve()
