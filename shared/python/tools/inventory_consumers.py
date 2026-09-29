"""AST inventory of actual Python consumers, without importing application code."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SHARED = ROOT / "shared/python/src/docsuri_shared"
SOURCE_ROOTS = ("backend", "ingestion", "ops", "platform_integrity/src", "shared/python/src")
EXCLUDED = {
    ".venv", "__pycache__", ".pytest_cache", "_generated", "_binding_generations",
    "tests", "test", "dist", "build",
}


def source_files(root):
    for directory in SOURCE_ROOTS:
        for path in sorted((root / directory).rglob("*.py")):
            if not EXCLUDED.intersection(path.relative_to(root).parts):
                if path.is_symlink():
                    raise ValueError("consumer source symlink")
                yield path


def generated_origin(module, symbol, seen=None, *, shared=SHARED):
    seen = set() if seen is None else seen
    key = module, symbol
    if key in seen:
        return ()
    seen.add(key)
    if module.startswith("docsuri_shared._generated."):
        return (f"{module}:{symbol}",)
    if not module.startswith("docsuri_shared"):
        return ()
    parts = module.split(".")[1:]
    path = shared.joinpath(*parts).with_suffix(".py") if parts else shared / "__init__.py"
    if not path.is_file():
        return ()
    tree = ast.parse(path.read_text())
    origins = set()
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom):
            continue
        imported = node.module or ""
        if node.level:
            parent = module.split(".") if path.name == "__init__.py" else module.split(".")[:-1]
            prefix = parent[:len(parent) - node.level + 1]
            imported = ".".join(prefix + ([imported] if imported else []))
        for alias in node.names:
            if symbol == "*" or (alias.asname or alias.name) == symbol:
                child = shared / (alias.name + ".py")
                if imported == "docsuri_shared" and child.is_file():
                    origins.update(generated_origin(
                        imported + "." + alias.name, "*", seen, shared=shared,
                    ))
                else:
                    origins.update(generated_origin(imported, alias.name, seen, shared=shared))
    return tuple(sorted(origins))


def inventory(root=ROOT):
    records = []
    local_models, source_digests = [], []
    shared = root / "shared/python/src/docsuri_shared"
    for path in source_files(root):
        source = path.read_bytes()
        tree = ast.parse(source)
        before = len(records) + len(local_models)
        shadowed = {
            node.name for node in tree.body
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        }
        for node in tree.body:
            targets = node.targets if isinstance(node, ast.Assign) else (
                [node.target] if isinstance(node, ast.AnnAssign) else []
            )
            shadowed.update(part.id for target in targets for part in ast.walk(target)
                            if isinstance(part, ast.Name))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                bases = [ast.unparse(base) for base in node.bases]
                if any(base.rsplit(".", 1)[-1] in {"BaseModel", "TypedDict", "RootModel"}
                       for base in bases):
                    local_models.append({"file": path.relative_to(root).as_posix(),
                                         "symbol": node.name, "bases": bases})
            if isinstance(node, ast.ImportFrom) and (
                node.module or ""
            ).startswith("docsuri_shared"):
                for alias in node.names:
                    local = alias.asname or alias.name
                    records.append({
                        "file": path.relative_to(root).as_posix(), "module": node.module,
                        "symbol": alias.name, "local": local,
                        "generated": list(generated_origin(node.module, alias.name, shared=shared)),
                        "shadowed": local in shadowed,
                    })
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("docsuri_shared"):
                        records.append({
                            "file": path.relative_to(root).as_posix(), "module": alias.name,
                            "symbol": "*", "local": alias.asname or alias.name,
                            "generated": list(generated_origin(alias.name, "*", shared=shared)),
                            "shadowed": (alias.asname or alias.name.split(".")[0]) in shadowed,
                        })
        if before != len(records) + len(local_models):
            source_digests.append({"file": path.relative_to(root).as_posix(),
                                   "sha256": hashlib.sha256(source).hexdigest()})
    return {
        "version": 1, "imports": sorted(records, key=lambda item: json.dumps(item, sort_keys=True)),
        "localModels": sorted(local_models, key=lambda item: (item["file"], item["symbol"])),
        "sourceDigests": sorted(source_digests, key=lambda item: item["file"]),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = inventory()
    if any(record["generated"] and record["shadowed"] for record in result["imports"]):
        raise SystemExit("generated wire import is shadowed by a local declaration")
    output = ROOT / "shared/python-consumers.json"
    content = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.write:
        output.write_text(content)
    elif not output.is_file() or output.read_text() != content:
        raise SystemExit("actual Python consumer inventory drift")
    print("ok: actual Python shared-contract consumers")


if __name__ == "__main__":
    main()
