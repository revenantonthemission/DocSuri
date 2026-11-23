"""Moving the model runtime without leaving v1 without its models (U8 plan Step 37;
Workflow 20 step 5, BR6.11 (2), R-109, R-110, R-111, R-112).

- `clone_models` clones, as root, every file of each model the release pins
  (ModelEvidence, `local_models.MODEL_PINS`) from your home folder's copy into the models
  folder with APFS clones (`cp -c`: shared blocks, no extra space, and a later change to
  either copy never reaches the other), and gives the clones to the models account.
- `verify_models` checks the clones before use: each model's manifest must hash to the
  release's pin, which is also the hash of the manifest the registry serves for that tag,
  and every file the manifest lists must match its digest. A failure deletes the clones
  and changes nothing else (`ModelsRefused`).
- `runtime_reports_pins` reads the model runtime's `/api/tags` at the usual address and
  confirms it reports every pinned digest.

Your home folder keeps its copy: the repository's local model runner clones from it.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
from collections.abc import Callable
from pathlib import Path

from docsuri_ops.local_models import MODEL_PINS

from . import safe_fs

REGISTRY = Path("manifests/registry.ollama.ai/library")
BLOB = re.compile(r"sha256:([0-9a-f]{64})")


class ModelsRefused(RuntimeError):
    """A model clone failed its verification; the message is a fixed key."""


def _digest_of(descriptor: int) -> str:
    accumulator = hashlib.sha256()
    while block := os.read(descriptor, 1 << 20):
        accumulator.update(block)
    return accumulator.hexdigest()


MAX_MODEL_MANIFEST = 1024 * 1024
# Who must own a file in the models folder, asked of its open descriptor (the models
# account's uid, through the tools' `descriptor_owner`); None checks no owner.
OwnedBy = Callable[[int], bool]


def _open_model_file(base: Path, path: Path, owned_by: OwnedBy | None) -> int:
    """A file in the models folder opened through the no-link walk from `base`, and kept
    only when it is a regular file with one name owned as `owned_by` asks: every clone
    reaches the folder with exactly one name, the models account's (your answer of
    2026-11-10, "Fix both and sweep the rest"). Anything else is refused
    (`model-file-differs`) with nothing read."""
    try:
        with safe_fs.folder_at(base, path.parent) as folder:
            descriptor = safe_fs.open_existing(folder, path.name)
    except safe_fs.PathRefused:
        raise ModelsRefused("model-file-differs") from None
    try:
        if owned_by is not None and not owned_by(descriptor):
            raise ModelsRefused("model-file-differs")
    except BaseException:  # the descriptor is closed on every way out, as `open_existing`'s
        os.close(descriptor)
        raise
    return descriptor


def _listed(data: object, model: str, manifest: Path) -> list[tuple[Path, str]]:
    listed = [(manifest, MODEL_PINS[model])]
    if not isinstance(data, dict) or not isinstance(data.get("layers"), list):
        raise ModelsRefused("model-blob-identity")
    for item in [data.get("config"), *data["layers"]]:
        if not isinstance(item, dict):
            raise ModelsRefused("model-blob-identity")
        match = BLOB.fullmatch(str(item.get("digest", "")))
        if match is None:
            raise ModelsRefused("model-blob-identity")
        listed.append((Path("blobs") / f"sha256-{match.group(1)}", match.group(1)))
    return listed


def members(root: Path, model: str, *, base: Path | None = None,
            owned_by: OwnedBy | None = None) -> list[tuple[Path, str]]:
    """The model's manifest and every blob it lists, each with its expected digest. With
    `base`, the manifest is read through the no-link walk from it (the models folder,
    which the models account could change), only as a regular file with one name owned
    as `owned_by` asks; without, by path (your home folder's copy, whose every clone is
    checked against its digest before it reaches the models folder). A manifest that does
    not decode, or is outside its shape, is refused (`model-blob-identity`)."""
    name, tag = model.split(":")
    manifest = REGISTRY / name / tag
    if base is None:
        raw = (root / manifest).read_bytes()
    else:
        descriptor = _open_model_file(base, root / manifest, owned_by)
        try:
            raw = safe_fs.read_all(descriptor, MAX_MODEL_MANIFEST)
        finally:
            os.close(descriptor)
        if len(raw) > MAX_MODEL_MANIFEST:
            raise ModelsRefused("model-file-differs")
    try:
        data = json.loads(raw)
    except (ValueError, RecursionError):  # a deeply nested manifest stops the decoder
        raise ModelsRefused("model-blob-identity") from None
    return _listed(data, model, manifest)


def _regular(path: Path) -> bool:
    info = path.lstat()
    return stat.S_ISREG(info.st_mode)


def _file_digest(base: Path, path: Path, owned_by: OwnedBy | None = None) -> str:
    """A file's digest read through the no-link walk from `base`: a link, a second name,
    another owner than `owned_by` asks, or another thing than a regular file, is refused
    (`model-file-differs`), never read."""
    descriptor = _open_model_file(base, path, owned_by)
    try:
        return _digest_of(descriptor)
    finally:
        os.close(descriptor)


def verify_models(root: Path, *, base: Path | None = None,
                  owned_by: OwnedBy | None = None) -> list[str]:
    """Each pinned model's manifest and files, by digest; returns the models verified.
    The models folder is the models account's, so every file is read through the no-link
    walk from `base` (the root-owned folder holding it, its parent by default), and only
    as a regular file with one name owned as `owned_by` asks (the models account)."""
    base = root.parent if base is None else base
    verified = []
    for model in sorted(MODEL_PINS):
        for relative, expected in members(root, model, base=base, owned_by=owned_by):
            if _file_digest(base, root / relative, owned_by) != expected:
                raise ModelsRefused("model-file-differs")
        verified.append(model)
    return verified


def clone_models(tools, source: Path, target: Path, *, uid: int, gid: int,
                 base: Path | None = None) -> list[str]:
    """Clone every pinned model's files from `source` (your home folder's
    `.ollama/models`) into `target`, give them to the models account and verify them.
    Any failure deletes what was cloned.

    The models folder is the models account's (your answer of 2026-11-10, "Fix both and
    sweep the rest"), so nothing is cloned, given or removed there by path: each file is
    cloned into a root-only staging folder in `base` (the root-owned prefix, the target's
    parent by default, on the same volume), checked there against its expected digest (so
    whatever your home folder's copy held at that moment, only the pinned bytes go on),
    given to the models account through its own descriptor, and then linked into its
    folder, reached by the no-link walk, under a name that must be free (`os.link`
    relative to both folders' descriptors never replaces one), and the staging name
    removed."""
    base = target.parent if base is None else base
    created: list[Path] = []
    staging = Path(tempfile.mkdtemp(prefix=".docsuri-models-", dir=base))
    try:
        with safe_fs.folder_at(staging.parent, staging) as staged:
            for model in sorted(MODEL_PINS):
                if (source / REGISTRY / Path(*model.split(":"))).is_symlink():
                    raise ModelsRefused("model-manifest-is-a-link")
                for relative, expected in members(source, model):
                    origin = source / relative
                    if not _regular(origin):
                        raise ModelsRefused("model-file-not-regular")
                    name = f"clone-{len(created)}"
                    with safe_fs.folder_at(base, (target / relative).parent,
                                           create=True) as folder:
                        if safe_fs.lexists(folder, relative.name):
                            continue
                        tools.clone(origin, staging / name)
                        _settle(tools, staged, name, folder, relative.name, expected,
                                uid=uid, gid=gid)
                    created.append(relative)
        return verify_models(target, base=base,
                             owned_by=lambda descriptor: tools.descriptor_owner(descriptor) == uid)
    except BaseException:
        for relative in created:
            with contextlib.suppress(OSError):
                with safe_fs.folder_at(base, (target / relative).parent) as folder:
                    safe_fs.remove(folder, relative.name)
        raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def _settle(tools, staged: int, name: str, folder: int, final: str, expected: str, *,
            uid: int, gid: int) -> None:
    """One staged clone: refused unless it is a regular file holding the expected digest,
    given to the models account through its own descriptor, linked into its folder under
    a free name and its staging name removed."""
    descriptor = safe_fs.open_existing(staged, name)
    try:
        if _digest_of(descriptor) != expected:
            raise ModelsRefused("model-file-differs")
        tools.fchown(descriptor, uid, gid)
    finally:
        os.close(descriptor)
    try:
        os.link(name, final, src_dir_fd=staged, dst_dir_fd=folder)
    except FileExistsError:
        raise ModelsRefused("model-file-in-the-way") from None
    os.unlink(name, dir_fd=staged)


def runtime_reports_pins(tags: Callable[[], dict]) -> bool:
    """`/api/tags` at 127.0.0.1:11434 reports each pinned model at its pinned digest."""
    try:
        reported = {item.get("name"): item.get("digest") for item in tags().get("models", [])}
    except (OSError, ValueError, AttributeError):
        return False
    return all(reported.get(model) == digest for model, digest in MODEL_PINS.items())
