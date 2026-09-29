"""Pin one verified generated tree per process (F13); never follow a mutable head per import."""

import hashlib
import json
from pathlib import Path


def pinned_path() -> str:
    root = Path(__file__).resolve().parent
    head = json.loads((root / "_binding_head.json").read_bytes())
    generation, files = head["generation"], head["files"]
    manifest = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    if hashlib.sha256(manifest).hexdigest() != generation:
        raise ImportError("binding manifest integrity mismatch")
    directory = root / "_binding_generations" / generation
    if directory.is_symlink():
        raise ImportError("binding generation symlink")
    if not isinstance(files, dict) or not files or len(files) > 10000:
        raise ImportError("invalid binding file manifest")
    actual = {path.relative_to(directory).as_posix() for path in directory.rglob("*.py")}
    if actual != set(files):
        raise ImportError("binding file set mismatch")
    for name, expected in files.items():
        path = directory / name
        if path.is_symlink() or not path.resolve().is_relative_to(directory.resolve()):
            raise ImportError("binding path escape")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ImportError("binding file integrity mismatch")
    return str(directory)
