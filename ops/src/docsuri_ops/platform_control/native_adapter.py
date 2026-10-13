"""The bounded native adapter: one real local effect per child process.

Invoked only by the operator's ``bounded-executor`` with a typed JSON request on
stdin. It never accepts a caller-supplied command, shell string or arbitrary
path: ``targetId`` and ``token`` are validated against a strict pattern and the
resolved path is proven to stay inside the owned target root. It writes one
typed JSON settlement record to stdout.

Read-only kinds (``file-probe``, ``credential-presence``) never create the
target directory; only a genuine write effect does.
"""

from __future__ import annotations

import errno
import json
import os
import re
import stat
import sys
import time
from pathlib import Path

MAX_REQUEST_BYTES = 65536
TARGET_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
TOKEN_PATTERN = re.compile(r"^[0-9a-f]{16}$")
EFFECT_KINDS = ("file-write", "file-probe", "credential-presence")
INJECTED_FAULTS = ("permission", "disk", "connectivity", "hang")
CREDENTIAL_NAME = "credential"


def _error(kind: str, message: str) -> dict:
    return {"kind": kind, "message": message}


def _result(
    status: str,
    *,
    refs: list[str] | None = None,
    error: dict | None = None,
    observations: dict | None = None,
) -> dict:
    record = {"status": status, "effectRefs": refs or [], "error": error}
    if observations is not None:
        record["observations"] = observations
    return record


def _resolve(root: Path, target_id: str, token: str) -> tuple[Path, Path]:
    """Return (target directory, effect path) without creating anything."""
    if not TARGET_PATTERN.fullmatch(target_id):
        raise ValueError("invalid target identity")
    if not TOKEN_PATTERN.fullmatch(token):
        raise ValueError("invalid effect token")
    base = root.resolve()
    directory = (base / target_id).resolve()
    # target_id carries no path separator, so the resolved directory must be the
    # direct child of the owned root; anything else is a traversal attempt.
    if directory != (base / target_id) or directory.parent != base:
        raise ValueError("target escapes the owned root")
    return directory, directory / f"effect-{token}.json"


def _classify_oserror(exc: OSError) -> str:
    if exc.errno in (errno.EACCES, errno.EPERM, errno.EROFS):
        return "permission"
    if exc.errno in (errno.ENOSPC, errno.EDQUOT, errno.EFBIG):
        return "disk"
    if exc.errno in (errno.ECONNREFUSED, errno.ECONNRESET, errno.EHOSTUNREACH, errno.ENETUNREACH):
        return "connectivity"
    return "internal"


def _injected(injected_fault: str | None) -> dict | None:
    table = {
        "permission": ("not-applied", _error("permission", "injected permission failure")),
        "disk": ("unknown", _error("disk", "injected disk exhaustion")),
        "connectivity": ("unknown", _error("connectivity", "injected connectivity loss")),
    }
    if injected_fault not in table:
        return None
    status, error = table[injected_fault]
    return _result(status, error=error)


def _write_effect(request: dict, directory: Path, path: Path, reference: str) -> dict:
    try:
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    except OSError as exc:
        return _result("not-applied", error=_error(_classify_oserror(exc), "target not writable"))
    payload = json.dumps(
        {
            "operationId": request.get("operationId"),
            "targetId": request["targetId"],
            "inputHash": request.get("inputHash"),
            "operation": request.get("operationName"),
        },
        sort_keys=True,
    ).encode()
    temporary = path.with_name(path.name + ".pending")
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(descriptor, payload)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.replace(temporary, path)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        kind_error = _classify_oserror(exc)
        status = "unknown" if kind_error == "disk" else "not-applied"
        return _result(status, error=_error(kind_error, "effect write failed"))
    return _result("applied", refs=[reference])


def _probe_effect(target_id: str, directory: Path, token: str) -> dict:
    """A genuinely read-only observation; never creates the target directory."""
    if not directory.is_dir():
        return _result("not-applied", error=_error("permission", "target directory absent"))
    try:
        entries = sum(1 for _ in os.scandir(directory))
    except OSError as exc:
        return _result("not-applied", error=_error(_classify_oserror(exc), "probe failed"))
    return _result(
        "applied", refs=[f"{target_id}/probe-{token}"], observations={"entries": entries}
    )


def _credential_effect(target_id: str, directory: Path, token: str) -> dict:
    """Real credential-presence semantics: exists, regular, non-empty, owner-only.

    Only presence and the permission mode are observed; the credential's content
    is never read and never leaves the target.
    """
    credential = directory / CREDENTIAL_NAME
    try:
        info = credential.stat()
    except OSError:
        return _result("not-applied", error=_error("permission", "credential absent"))
    if not stat.S_ISREG(info.st_mode) or info.st_size == 0:
        return _result(
            "not-applied", error=_error("internal", "credential is not a non-empty regular file")
        )
    mode = stat.S_IMODE(info.st_mode)
    if mode & 0o077:
        return _result(
            "not-applied",
            error=_error("permission", "credential permissions are not owner-only"),
        )
    return _result(
        "applied",
        refs=[f"{target_id}/credential-presence-{token}"],
        observations={"credentialPresent": True, "mode": oct(mode)},
    )


def apply_effect(request: dict, *, injected_fault: str | None = None) -> dict:
    """Perform exactly one bounded effect; return a typed settlement record."""
    if injected_fault not in (None, *INJECTED_FAULTS):
        raise ValueError("unknown injected fault")
    kind = request.get("effectKind")
    if kind not in EFFECT_KINDS:
        return _result("not-applied", error=_error("internal", "unsupported effect kind"))
    try:
        directory, path = _resolve(
            Path(request["targetRoot"]), request["targetId"], request["token"]
        )
    except (ValueError, OSError) as exc:
        mapped = injected_fault or ("permission" if isinstance(exc, OSError) else "internal")
        return _result("not-applied", error=_error(mapped, "target not reachable"))

    injected = _injected(injected_fault)
    if injected is not None:
        return injected
    if injected_fault == "hang":
        time.sleep(60)
        return _result("unknown", error=_error("internal", "injected hang"))

    target_id = request["targetId"]
    token = request["token"]
    reference = f"{target_id}/effect-{token}.json"
    if kind == "file-write":
        return _write_effect(request, directory, path, reference)
    if kind == "file-probe":
        return _probe_effect(target_id, directory, token)
    return _credential_effect(target_id, directory, token)


def main(argv: list[str] | None = None) -> int:
    raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
    if len(raw) > MAX_REQUEST_BYTES:
        sys.stderr.write("request too large\n")
        return 2
    try:
        request = json.loads(raw)
    except ValueError:
        sys.stderr.write("invalid request json\n")
        return 2
    injected = request.pop("injectedFault", None)
    try:
        result = apply_effect(request, injected_fault=injected)
    except (ValueError, KeyError, OSError) as exc:
        result = {"status": "not-applied", "effectRefs": [], "error": _error("internal", str(exc))}
    sys.stdout.write(json.dumps(result, sort_keys=True))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
