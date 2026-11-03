#!/usr/bin/env python3
"""SS-026 §10.2: builds the sdist and wheel twice (fixed SOURCE_DATE_EPOCH), requires identical
bytes, the exact file lists and metadata, then installs the wheel into a fresh venv and imports it.
Usage: `uv run python scripts/check_dist.py` (writes only under .tmp/dist-check/, removed after a
pass)."""

from __future__ import annotations

import email.parser
import hashlib
import os
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / ".tmp" / "dist-check"
EPOCH = "1793750400"  # fixed: reproducibility only, not a release date
# hatchling always adds the VCS ignore file to an sdist.
SDIST_TOP = {
    ".gitignore",
    "src",
    "README.md",
    "CHANGELOG.md",
    "LICENSE",
    "NOTICE",
    "pyproject.toml",
    "PKG-INFO",
}
REQUIRES = ["httpx<1,>=0.27", "typing-extensions>=4.7; python_version < '3.11'"]


def fail(message: str) -> None:
    print(f"check_dist: {message}", file=sys.stderr)
    sys.exit(1)


def build(out: Path) -> list[Path]:
    env = {**os.environ, "SOURCE_DATE_EPOCH": EPOCH}
    subprocess.run(["uv", "build", "--quiet", "--out-dir", str(out)], cwd=ROOT, check=True, env=env)
    return sorted(out.iterdir())


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    shutil.rmtree(WORK, ignore_errors=True)
    first, second = build(WORK / "a"), build(WORK / "b")
    if [p.name for p in first] != [p.name for p in second]:
        fail("two builds produced different file names")
    if [sha(p) for p in first] != [sha(p) for p in second]:
        fail("two builds differ (not reproducible)")
    wheel = next(p for p in first if p.suffix == ".whl")
    sdist = next(p for p in first if p.name.endswith(".tar.gz"))
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        metadata = next(n for n in names if n.endswith(".dist-info/METADATA"))
        meta = email.parser.Parser().parsestr(archive.read(metadata).decode("utf-8"))
    outside = [n for n in names if not (n.startswith("storeshot/") or ".dist-info/" in n)]
    if outside or "storeshot/py.typed" not in names or any(n.endswith(".pyc") for n in names):
        fail(f"wheel file list: {outside or names}")
    if not {"storeshot/_generated/schemas.py", "storeshot/_generated/operations.py"} <= set(names):
        fail("the wheel lacks the generated models")
    expected = {
        "Name": "storeshot",
        "Requires-Python": ">=3.10",
        "License-Expression": "Apache-2.0",
    }
    for key, value in expected.items():
        if meta[key] != value:
            fail(f"METADATA {key} = {meta[key]!r}, expected {value!r}")
    if sorted(meta.get_all("License-File") or []) != ["LICENSE", "NOTICE"]:
        fail(f"License-File: {meta.get_all('License-File')}")
    requires = sorted(r.replace('"', "'") for r in meta.get_all("Requires-Dist") or [])
    if requires != sorted(REQUIRES):
        fail(f"Requires-Dist: {requires}")
    with tarfile.open(sdist) as archive:
        top = {Path(m).parts[1] for m in archive.getnames() if len(Path(m).parts) > 1}
    if top != SDIST_TOP:
        fail(f"sdist contents: {sorted(top)}")
    venv = WORK / "venv"
    subprocess.run(["uv", "venv", "--quiet", str(venv)], check=True)
    python = venv / "bin" / "python"
    subprocess.run(
        ["uv", "pip", "install", "--quiet", "--python", str(python), str(wheel)], check=True
    )
    smoke = (
        "import storeshot; from storeshot import Storeshot, verify_webhook_signature; "
        "import storeshot.types; print(storeshot.__version__, storeshot.CONTRACT_VERSION)"
    )
    subprocess.run([str(python), "-I", "-c", smoke], check=True)
    shutil.rmtree(WORK)
    print(f"check_dist: {wheel.name} and {sdist.name} reproducible, file lists and metadata ok")


if __name__ == "__main__":
    main()
