#!/usr/bin/env python
"""Generate the pydantic v2 models in ``docsuri_shared/_generated`` from the
language-neutral JSON Schema SSOT (``shared/{vector-spec,dtos,events}/*.schema.json``).

§5-B decision: the JSON Schema files are the single source of truth; the Python
types are GENERATED, never hand-edited. This script is the only thing that writes
``_generated/``. Run it after changing a schema; run it with ``--check`` in CI to
fail the build if the committed models have drifted from the schemas.

Usage::

    uv run python tools/generate.py            # regenerate _generated/ in place
    uv run python tools/generate.py --check     # fail (exit 1) if _generated/ is stale

Only ``*.schema.json`` is fed to the generator. ``vector-spec/vector-spec.yaml`` is
embedding *config*, not a per-record shape, so it is hand-mapped to constants in
``docsuri_shared/vector_spec.py`` (guarded by ``tests/test_vector_spec.py``), never
codegen'd.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote

from docsuri_schema import load_catalog

PKG_ROOT = Path(__file__).resolve().parents[1]  # shared/python/
SHARED_ROOT = PKG_ROOT.parent  # shared/
SCHEMA_DIRS = ("vector-spec", "dtos", "events")
GENERATED_DIR = PKG_ROOT / "src" / "docsuri_shared" / "_generated"
GENERATIONS = GENERATED_DIR.parent / "_binding_generations"
HEAD = GENERATED_DIR.parent / "_binding_head.json"

# NOTE: datamodel-codegen inserts --custom-file-header verbatim, so every line MUST
# already be a comment (leading '#'), otherwise the generated modules are invalid Python.
FILE_HEADER = (
    "# DO NOT EDIT. Generated from the JSON Schema SSOT in shared/ by tools/generate.py.\n"
    "# Change the schema and regenerate (§5-B); never hand-edit."
)


def _stage_schemas(dest: Path) -> int:
    """Validate the complete declared catalog before staging local, schema-aware references."""
    catalog = load_catalog(SHARED_ROOT)
    roots = catalog.consumer_roots("python")
    if set(roots) != set(catalog.documents):
        raise ValueError("Python binding profile requires complete catalog coverage")
    for identity in roots:
        path = dest / catalog.paths[identity]
        path.parent.mkdir(parents=True, exist_ok=True)

        def encode(location, current=path):
            target = dest / catalog.paths[location.document]
            relative = "" if target == current else os.path.relpath(target, current.parent)
            fragment = "#" + quote(location.pointer, safe="/~$") if location.pointer else ""
            return relative + fragment

        path.write_text(
            json.dumps(catalog.rewrite(identity, encode), ensure_ascii=False), encoding="utf-8"
        )
    return len(roots)


def _run_codegen(input_dir: Path, output_dir: Path) -> None:
    """Run datamodel-codegen into ``output_dir`` (must be a fresh, empty dir)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "datamodel-codegen",
        "--input",
        str(input_dir),
        "--input-file-type",
        "jsonschema",
        "--output",
        str(output_dir),
        "--output-model-type",
        "pydantic_v2.BaseModel",
        "--target-python-version",
        "3.11",
        "--use-standard-collections",
        "--use-union-operator",
        "--use-schema-description",
        "--field-constraints",
        "--disable-timestamp",  # deterministic output → clean --check diff
        "--custom-file-header",
        FILE_HEADER,
        "--formatters",
        "black",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except FileNotFoundError as exc:
        raise SystemExit(
            "datamodel-codegen not found on PATH — run via `uv run python tools/generate.py` "
            "(it is a dev dependency in pyproject.toml)."
        ) from exc
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        raise SystemExit(f"datamodel-codegen failed (rc={proc.returncode})")


def _build(output_dir: Path) -> int:
    """Stage schemas and codegen into ``output_dir`` (fresh). Returns schema count."""
    with tempfile.TemporaryDirectory() as tmp:
        staged = Path(tmp) / "schemas"
        n = _stage_schemas(staged)
        _run_codegen(staged, output_dir)
    return n


def generate(*, announce: bool = True) -> None:
    """Publish an immutable generation using one atomic head. Import pins one directory.

    Existing legacy modules remain as historical source; the compatibility loader never falls
    back to them after managed publication. Generation/verification failure changes no head.
    """
    with tempfile.TemporaryDirectory() as tmp:
        fresh = Path(tmp) / "_generated"
        n = _build(fresh)
        files = {
            p.as_posix(): hashlib.sha256((fresh / p).read_bytes()).hexdigest()
            for p in sorted(_py_files(fresh))
        }
        manifest = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
        generation = hashlib.sha256(manifest).hexdigest()
        GENERATIONS.mkdir(parents=True, exist_ok=True)
        with (PKG_ROOT / ".codegen.lock").open("a+b") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            destination = GENERATIONS / generation
            if destination.exists():
                if _content_diff(destination, fresh):
                    raise ValueError("immutable binding generation conflict")
            else:
                # Stage on the target filesystem; rename only after every file is durable.
                staged = Path(tempfile.mkdtemp(prefix="candidate-", dir=GENERATIONS))
                for path in sorted(_py_files(fresh)):
                    target = staged / path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with target.open("xb") as stream:
                        stream.write((fresh / path).read_bytes())
                        stream.flush()
                        os.fsync(stream.fileno())
                os.rename(staged, destination)
            staged_head = HEAD.with_suffix(".tmp")
            with staged_head.open("wb") as stream:
                stream.write(
                    json.dumps({"generation": generation, "files": files}, sort_keys=True).encode()
                )
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(staged_head, HEAD)
            directory_fd = os.open(HEAD.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    if announce:
        print(f"generated models from {n} schema files -> {GENERATED_DIR}")


def _py_files(root: Path) -> set[Path]:
    """Relative paths of the generated .py files (ignores __pycache__/.pyc noise)."""
    return {p.relative_to(root) for p in root.rglob("*.py")}


def _content_diff(committed: Path, fresh: Path) -> list[str]:
    """Content-based diff of two generated trees (NOT stat/shallow — robust to mtime
    coincidence and coarse-mtime filesystems). Compares bytes of every .py file."""
    a, b = _py_files(committed), _py_files(fresh)
    diffs: list[str] = []
    diffs += [f"  only in committed: {p}" for p in sorted(a - b)]
    diffs += [f"  only in freshly-generated: {p}" for p in sorted(b - a)]
    diffs += [
        f"  differs: {p}"
        for p in sorted(a & b)
        if (committed / p).read_bytes() != (fresh / p).read_bytes()
    ]
    return diffs


def check() -> int:
    if not GENERATED_DIR.exists():
        sys.stderr.write("drift: _generated/ does not exist — run tools/generate.py\n")
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        fresh = Path(tmp) / "_generated"
        _build(fresh)
        committed = GENERATED_DIR
        if HEAD.exists():
            head = json.loads(HEAD.read_text())
            generation = head.get("generation", "")
            if len(generation) != 64 or any(c not in "0123456789abcdef" for c in generation):
                raise ValueError("invalid binding head")
            committed = GENERATIONS / generation
        diffs = _content_diff(committed, fresh)
    if diffs:
        sys.stderr.write(
            "drift: committed _generated/ is stale vs the schemas.\n"
            "Run `uv run python tools/generate.py` and commit the result.\n"
            + "\n".join(diffs)
            + "\n"
        )
        return 1
    print("ok: _generated/ matches the schemas")
    return 0


if __name__ == "__main__":
    if "--check" in sys.argv[1:]:
        raise SystemExit(check())
    generate()
