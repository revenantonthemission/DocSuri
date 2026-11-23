"""PlatformControl's two drivers for every new platform effect (U8 plan Step 27; A6,
BR7.1, BR10.2).

The bounded child (U8's `adapter`, run by U7's `executor.run_effect`) hands each of A6's
effect kinds here. Everything above the driver is shared: the receipt is bound and the
preconditions checked before the child starts (`u8_protocols.Operator`), and the child
receives only the operation's identity. It finds its input beside its effect reference,
`<target>/input-<token>.json`, written by the operator, and refuses it unless its
canonical digest is the bound input hash, so it does exactly the input the receipt
binds. The arrangement's kind comes from `driver.json` at the effects root, which the
installer or the realm's tool writes:

- `arrangement` runs the fixed programs on this Mac (`drivers/arrangement.py`);
- `realm` acts on the composed realm (`drivers/realm.py`).

Each refuses the other's profile (BR7.1). After an applied effect the child writes the
effect record `<target>/effect-<token>.json`, the settlement's first effect reference,
so both drivers settle the same receipt for the same operation. `observe` answers, from
the target alone and without running anything again, whether an effect whose outcome is
unknown took place (reconciliation).
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

DRIVER_FILE = "driver.json"
MAX_INPUT = 64 * 1024
DRIVER_KINDS = ("arrangement", "realm")


class DriverRefused(Exception):
    """An effect refused before it ran, with a fixed reason key."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def input_hash(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


# The facts an effect hands back beside its references (U8 plan Step 29), each one
# `fact:<name>=<value>`, so the ledger records the backup agent's own receipt (BR4.3):
# what the agent wrote, its digest and size, its integrity and its earliest disposal
# time. Only these names are ever written, and a value is bounded and carries no space.
FACT_NAMES = (
    "recordId", "sha256", "size", "integrity", "disposeAfter", "stagingRemovedAt",
    "stagingLocation", "incarnation", "databaseBytes", "setRecordId", "setSha256",
    "setPath", "scratchDatabase",
    # A service control's job state before it ran (`true` or `false`), the fixed
    # program's own answer: the release command restarts only roles that were loaded.
    "wasLoaded",
    # A lone ledger copy's head (L1-5, U8 plan Step 64(c)).
    "headSequence", "headDigest",
    # The scratch restore's timed HNSW rebuild (U8 plan Steps 62(d), 64(i)).
    "hnswRebuildSeconds",
)
FACT_PREFIX = "fact:"
MAX_FACT = 200


def facts_of(result: dict, names: tuple[str, ...] = FACT_NAMES) -> list[str]:
    """`fact:` references for the named fields `result` holds."""
    refs = []
    for name in names:
        value = result.get(name)
        if value is None:
            continue
        text = str(value)
        if len(text) > MAX_FACT or any(character.isspace() for character in text):
            raise DriverRefused("effect-fact-outside-its-form")
        refs.append(f"{FACT_PREFIX}{name}={text}")
    return refs


def parse_facts(refs: list[str]) -> dict[str, str]:
    """The `fact:` references of a settled receipt, by name; other references are kept
    out. A name outside `FACT_NAMES` is refused rather than trusted."""
    facts: dict[str, str] = {}
    for ref in refs:
        if not isinstance(ref, str) or not ref.startswith(FACT_PREFIX):
            continue
        name, separator, value = ref[len(FACT_PREFIX):].partition("=")
        if not separator or name not in FACT_NAMES:
            raise ValueError("an effect fact outside its registered names")
        facts[name] = value
    return facts


def input_path(directory: Path, token: str) -> Path:
    return directory / f"input-{token}.json"


def _read_effects_file(base: Path, folder: Path, name: str, limit: int) -> bytes:
    """A file in an effects folder, read through the no-link walk from `base` (the
    effects root's parent, `control/effects`, which root owns in production): every
    folder below it is opened with `O_NOFOLLOW`, and the file with `O_NOFOLLOW |
    O_NONBLOCK`, read only when it is a regular file with one name, at most `limit` + 1
    bytes (your answer of 2026-11-10, "Fix both and sweep the rest"). The release
    command, run as root, reads these from your login's effects folder, so a FIFO there
    can no longer stall it and a link or a second name is never followed. A refusal is
    `effects-<key>`; a missing file or folder raises `FileNotFoundError` as before."""
    from docsuri_ops.arrangement import safe_fs

    try:
        with safe_fs.folder_at(base, folder) as descriptor:
            opened = safe_fs.open_existing(descriptor, name)
    except safe_fs.PathRefused as refused:
        raise DriverRefused(f"effects-{refused.reason}") from None
    try:
        return safe_fs.read_all(opened, limit)
    finally:
        os.close(opened)


def read_input(directory: Path, token: str, expected_hash: str) -> dict:
    """The operation's bound input, refused unless its digest is the bound one."""
    raw = _read_effects_file(directory.parent.parent, directory,
                             input_path(directory, token).name, MAX_INPUT)
    if len(raw) > MAX_INPUT:
        raise DriverRefused("input-too-large")
    value = json.loads(raw)
    if not isinstance(value, dict) or input_hash(value) != expected_hash:
        raise DriverRefused("input-hash-mismatch")
    return value


CALLERS = ("operator", "scheduler")
MAX_CALLER = 1024


def caller_path(directory: Path, token: str) -> Path:
    return directory / f"caller-{token}.json"


def write_caller(directory: Path, token: str, caller: str) -> None:
    """The realm's side only: who runs this effect (the operator in person or the standing
    scheduler), beside its input, so the realm's driver runs a standing request under the
    scheduler's identity (your decision of 2026-10-26, "Only in person"). Production
    needs none: each actor has its own effects folder and its own sudo grants."""
    if caller not in CALLERS:
        raise DriverRefused("caller-refused")
    if not _write_once(directory, caller_path(directory, token).name,
                       canonical({"caller": caller})):
        raise DriverRefused("caller-changed")


def _effects_folder(directory: Path):
    """`<effects root>/<target>` as a descriptor (your answer of 2026-11-10, "Fix both and
    sweep the rest"): the effects root is its actor's folder (in production your login's,
    which the release command, run as root, writes into), so it and the target folder are
    opened with `O_NOFOLLOW` from the effects root's own parent (`control/effects`,
    root-owned), the target folder made at 0700 when missing. A link at either is refused
    by the walk; its callers answer `effects-folder-is-a-link`."""
    from docsuri_ops.arrangement import safe_fs

    return safe_fs.folder_at(directory.parent.parent, directory, create=True, mode=0o700)


def _write_once(directory: Path, name: str, payload: bytes) -> bool:
    """A file written once relative to its folder's descriptor (`O_EXCL | O_NOFOLLOW`,
    0600); when the name is taken, whether the regular, one-name file there already holds
    exactly `payload` (read through the same descriptor, never through a link)."""
    from docsuri_ops.arrangement import safe_fs

    try:
        with _effects_folder(directory) as folder:
            try:
                safe_fs.create_file(folder, name, payload, mode=0o600)
            except FileExistsError:
                descriptor = safe_fs.open_existing(folder, name)
                try:
                    return safe_fs.read_all(descriptor, MAX_INPUT) == payload
                finally:
                    os.close(descriptor)
    except safe_fs.PathRefused as refused:
        raise DriverRefused(f"effects-{refused.reason}") from None
    return True


def read_caller(directory: Path, token: str) -> str:
    """The recorded caller, the operator when none was recorded (an effect a test runs
    directly); anything else is refused."""
    try:
        raw = _read_effects_file(directory.parent.parent, directory,
                                 caller_path(directory, token).name, MAX_CALLER)
    except FileNotFoundError:
        return "operator"
    if len(raw) > MAX_CALLER:
        raise DriverRefused("caller-refused")
    value = json.loads(raw)
    caller = value.get("caller") if isinstance(value, dict) else None
    if caller not in CALLERS:
        raise DriverRefused("caller-refused")
    return caller


def write_input(directory: Path, token: str, value: dict) -> Path:
    """The operator's side: the input beside the effect reference, 0600, never replaced;
    written relative to the target folder's descriptor (`_write_once`)."""
    path = input_path(directory, token)
    if not _write_once(directory, path.name, canonical(value)):
        raise DriverRefused("input-changed")
    return path


def load_config(root: Path) -> dict:
    """`driver.json` at the effects root, read through the no-link walk from the root's
    parent (`_read_effects_file`)."""
    raw = _read_effects_file(root.parent, root, DRIVER_FILE, MAX_INPUT)
    if len(raw) > MAX_INPUT:
        raise DriverRefused("driver-unconfigured")
    value = json.loads(raw)
    if not isinstance(value, dict) or value.get("kind") not in DRIVER_KINDS:
        raise DriverRefused("driver-unconfigured")
    return value


def driver_for(config: dict, *, production: bool | None = None):
    """The driver the configuration names; each refuses the other's profile."""
    if config["kind"] == "realm":
        from .realm import RealmDriver

        if production:
            raise DriverRefused("realm-driver-refuses-production")
        return RealmDriver(config)
    from .arrangement import ArrangementDriver

    if production is False:
        raise DriverRefused("arrangement-driver-refuses-synthetic")
    return ArrangementDriver(config)


def _effect_record(directory: Path, token: str, request: dict, refs: list[str]) -> str:
    """The effect record, replaced atomically through a pending file created new and
    renamed over it, both relative to the target folder's descriptor (your answer of
    2026-11-10, "Fix both and sweep the rest")."""
    from docsuri_ops.arrangement import safe_fs

    path = directory / f"effect-{token}.json"
    payload = canonical({
        "operationId": request.get("operationId"), "operation": request.get("operationName"),
        "targetId": request["targetId"], "inputHash": request["inputHash"], "refs": refs,
    })
    pending = path.name + ".pending"
    try:
        with _effects_folder(directory) as folder:
            safe_fs.remove(folder, pending)
            safe_fs.create_file(folder, pending, payload, mode=0o600)
            safe_fs.replace(folder, pending, path.name)
    except safe_fs.PathRefused as refused:
        raise DriverRefused(f"effects-{refused.reason}") from None
    return f"{request['targetId']}/effect-{token}.json"


def apply(request: dict, directory: Path) -> dict:
    """Run one of A6's effects; returns the child's typed settlement record."""
    root = Path(request["targetRoot"])
    try:
        config = load_config(root)
        inputs = read_input(directory, request["token"], request["inputHash"])
        driver = driver_for(config)
        context = {"operationId": request.get("operationId"), "targetId": request["targetId"],
                   "token": request["token"]}
        if config["kind"] == "realm":
            context["caller"] = read_caller(directory, request["token"])
        refs = driver.effect(request["effectKind"], inputs, context=context)
    except DriverRefused as refused:
        return {"status": "not-applied", "effectRefs": [],
                "error": {"kind": "internal", "message": refused.reason}}
    except (OSError, ValueError) as error:
        return {"status": "unknown", "effectRefs": [],
                "error": {"kind": "internal", "message": type(error).__name__}}
    # The record goes through the effects root as named, never as U7's check resolved it,
    # so the no-link walk starts from the effects root's own (root-owned) parent.
    record = _effect_record(root / request["targetId"], request["token"], request, list(refs))
    return {"status": "applied", "effectRefs": [record, *refs], "error": None}


def observe(root: Path, target: str, token: str, kind: str, expected_hash: str) -> bool:
    """Whether an unknown effect took place, read from its target; nothing runs again."""
    directory = root / target
    if (directory / f"effect-{token}.json").is_file():
        return True
    config = load_config(root)
    inputs = read_input(directory, token, expected_hash)
    return bool(driver_for(config).observe(kind, inputs))
