"""Probe a capability on this host and, only if it holds, sign a receipt for it.

This is the issuer counterpart to ``preflight.py``. It never installs, enables or restarts
anything: it runs a readonly probe from :mod:`docsuri_platform_integrity.deployment.capability`
and refuses to sign when the probe does not hold. A receipt it cannot prove is not written at
all, so a missing file always means "not proven" rather than "proof lost".

The configuration document carries *references* only — keychain paths, service and account
names, a database target, a frame path, a restore receipt path. Credentials, connections and
key material are never read from it.

``native_commit_guard`` is issued from a live :class:`PostgresOperatorAuthority` bound to an
operator approval, a digest-pinned frozen plan, an authenticated protected clock and an idle
autocommit target connection. Those are real collaborators, so they are built in a session
that owns the connection's lifetime rather than read from the reference document. The role the
authority demands is *derived* from the operator target, never taken from the document.
"""

import argparse
import json
import os
import stat
import sys
import time
import traceback
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, replace
from pathlib import Path

from docsuri_platform_integrity.adapters.credentials import KeychainTLS, TLSReference
from docsuri_platform_integrity.adapters.keychain_provisioning import NativeKeychain
from docsuri_platform_integrity.adapters.nts import ProtectedClock
from docsuri_platform_integrity.adapters.operator_authority import PostgresOperatorAuthority
from docsuri_platform_integrity.adapters.postgres_tls import PostgresTarget, PostgresTLS
from docsuri_platform_integrity.application.receipts import issue_protected, requested_capabilities
from docsuri_platform_integrity.contracts.codec import decode
from docsuri_platform_integrity.contracts.models import ApprovalBinding, TargetFence
from docsuri_platform_integrity.deployment.capability import Outcome, ProbeSet
from docsuri_platform_integrity.deployment.operator_plan import read_frozen_plan
from docsuri_platform_integrity.deployment.receipt import (
    Capability,
    host_identity,
)
from docsuri_platform_integrity.deployment.receipt_policy import ReceiptOperation, load_policy

GUARD_SECTION = "nativeCommitGuard"
MAX_GUARD_DEADLINE_SECONDS = 300


def read_probe_config(path: Path):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > 262_144:
            raise ValueError("probe reference bounds")
        config = decode(stream.read(262_145), max_bytes=262_144)
    if not isinstance(config, dict):
        raise ValueError("probe references must be an object")
    return config


def _section(config: dict, name: str) -> dict:
    """Fetch an object section, or None. A wrong type is a configuration error, not a default."""
    value = config.get(name)
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError(f"probe configuration section {name} must be an object")
    return value


def _handle(item, *, keys, extra=()):
    """Validate one keychain handle: an absolute path plus two bounded, printable names."""
    if not isinstance(item, dict) or set(item) != set(keys) | set(extra):
        raise ValueError("invalid purpose keychain handle")
    if not all(isinstance(item[key], str) and item[key] for key in keys):
        raise ValueError("purpose keychain handle fields must be strings")
    path = Path(item["keychain"])
    if not path.is_absolute() or ".." in path.parts or "\x00" in str(path):
        raise ValueError("purpose keychain path must be absolute without traversal")
    return item


def build_probe_set(config: dict, *, release: str, host: str) -> ProbeSet:
    """Turn a reference document into a ProbeSet with real, readonly collaborators.

    Every section is optional. A missing section leaves its capability ``not_configured``,
    which is how an operator tells "never installed" apart from "installed and broken".
    """
    keychain = config.get("keychainRoles")
    if keychain is not None and (not isinstance(keychain, list) or not all(
        isinstance(item, dict) for item in keychain
    )):
        raise ValueError("keychainRoles must be a list of handles")
    database = _section(config, "database")
    database_tls = _section(config, "databaseTls")
    clock = _section(config, "clock")
    credentials = None
    target = None
    if database is not None and database_tls is not None:
        _handle(database_tls, keys=("keychain", "service", "account"),
                extra=("runtimeRoot",))
        root = database_tls.get("runtimeRoot")
        if not isinstance(root, str) or not Path(root).is_absolute():
            raise ValueError("databaseTls runtimeRoot must be an absolute path")
        target = PostgresTarget(**database)
        credentials = KeychainTLS(
            TLSReference(Path(database_tls["keychain"]), database_tls["service"],
                         database_tls["account"]),
            Path(root),
        )
    elif database is not None or database_tls is not None:
        raise ValueError("database and databaseTls must be configured together")
    if clock is not None and not isinstance(clock.get("kwargs", {}), dict):
        raise ValueError("clock kwargs must be an object")
    # A wrong-typed guard section is a configuration error like any other section, not a
    # default. build_probe_set runs inside the guarded block, so it fails closed there.
    _section(config, GUARD_SECTION)
    restore = config.get("restoreReceipt")
    if restore is not None and (not isinstance(restore, str) or not Path(restore).is_absolute()):
        raise ValueError("restoreReceipt must be an absolute path")
    return ProbeSet(
        release=release,
        host=host,
        keychain_references=tuple(
            TLSReference(Path(item["keychain"]), item["service"], item["account"])
            for item in (_handle(entry, keys=("keychain", "service", "account"))
                         for entry in (keychain or ()))
        ),
        database=target,
        credentials=credentials,
        clock_frame=Path(clock["frame"]) if clock else None,
        clock_uid=clock.get("writerUid") if clock else None,
        clock_config_digest=clock.get("configDigest") if clock else None,
        clock_kwargs=clock.get("kwargs", {}) if clock else {},
        restore_receipt=Path(restore) if restore else None,
    )


@dataclass(frozen=True)
class GuardSession:
    """A live operator authority and its connection, or the reason there is none.

    ``reason`` is set instead of raising so a declared-but-unusable section is reported as one
    unproven capability while the other four probes still run and report.
    """

    authority: object = None
    connection: object = None
    identity: str | None = None
    definition_digest: str | None = None
    reason: str | None = None


def build_guard_authority(section: dict, *, release: str, clock_frame, clock_uid,
                          clock_config_digest, clock_kwargs):
    """Build a real authority from a digest-pinned plan and an operator approval.

    The role the authority enforces is taken from the operator target's own user, so a
    document cannot declare its way into a different role.
    """
    expected = {"plan", "planDigest", "operatorDatabase", "operatorTls", "approval", "fence",
                "deadlineSeconds"}
    if not expected <= set(section) <= expected | {"identity"}:
        raise ValueError(f"{GUARD_SECTION} must contain exactly {sorted(expected)}")
    seconds = section["deadlineSeconds"]
    if type(seconds) is not int or not 1 <= seconds <= MAX_GUARD_DEADLINE_SECONDS:
        raise ValueError("guard deadlineSeconds must be an integer within bounds")
    plan = read_frozen_plan(Path(section["plan"]), section["planDigest"], release=release)
    if not isinstance(section["approval"], dict) or not isinstance(section["fence"], dict):
        raise ValueError("guard approval and fence must be objects")
    if not isinstance(section["operatorDatabase"], dict):
        raise ValueError("operatorDatabase must be an object")
    _handle(section["operatorTls"], keys=("keychain", "service", "account"),
            extra=("runtimeRoot",))
    runtime_root = section["operatorTls"].get("runtimeRoot")
    if not isinstance(runtime_root, str) or not Path(runtime_root).is_absolute():
        raise ValueError("operatorTls runtimeRoot must be an absolute path")
    target = PostgresTarget(**section["operatorDatabase"])
    binding = ApprovalBinding.model_validate(section["approval"])
    fence = TargetFence.model_validate(section["fence"])
    # The plan is pinned by digest, so the approval must name that same plan.
    if binding.plan != section["planDigest"]:
        raise ValueError("approval does not name the pinned frozen plan")
    identity = section.get("identity")
    if identity is None:
        # The proof follows the approval: the operator already declared which purpose this
        # authority is for, so pick the identity that purpose governs rather than guessing.
        preferred = "registry:adopt" if binding.purpose == "adopt" else "registry:apply"
        if preferred not in plan.identities:
            raise ValueError("the approval's purpose has no conventional identity in the plan; "
                             "set identity explicitly")
        identity = preferred
    if identity not in plan.identities:
        raise ValueError("requested identity is not in the frozen plan")
    definition_digest = plan.identities[identity]
    # The adapter derives purpose from the identity; catch the mismatch before the database.
    if binding.purpose != ("adopt" if identity == "registry:adopt" else "apply"):
        raise ValueError("approval purpose does not match the planned identity")
    if binding.target != fence.target:
        raise ValueError("approval and fence name different targets")
    if clock_frame is None or clock_uid is None or clock_config_digest is None:
        raise ValueError("the authenticated clock is required to prove the guard")
    clock = ProtectedClock(clock_frame, writer_uid=clock_uid, config_digest=clock_config_digest,
                           **clock_kwargs)
    authority = PostgresOperatorAuthority(
        binding, fence, actor_role=target.user, definitions=dict(plan.identities),
        clock=clock, deadline=time.monotonic() + seconds,
    )
    credentials = KeychainTLS(
        TLSReference(Path(section["operatorTls"]["keychain"]),
                     section["operatorTls"]["service"], section["operatorTls"]["account"]),
        Path(runtime_root),
    )
    return GuardSession(authority=authority, connection=PostgresTLS(target, credentials),
                        identity=identity, definition_digest=definition_digest)


@contextmanager
def guard_session(config: dict, *, release: str, probe_set: ProbeSet):
    """Open the live operator connection for the duration of the probe run.

    The connection is readonly: the guard only reads authority state and takes share locks, so
    the probe has no reason to hold a writable session.
    """
    section = _section(config, GUARD_SECTION)
    if section is None:
        yield GuardSession(reason="not_configured")
        return
    try:
        session = build_guard_authority(
            section, release=release, clock_frame=probe_set.clock_frame,
            clock_uid=probe_set.clock_uid, clock_config_digest=probe_set.clock_config_digest,
            clock_kwargs=probe_set.clock_kwargs)
    except Exception:
        yield GuardSession(reason="guard_configuration_unusable")
        return
    # ExitStack, not a bare `with`: an exception raised by the probe body must propagate
    # normally rather than be caught here and turned into a second yield.
    with ExitStack() as stack:
        try:
            connection = stack.enter_context(session.connection.connect())
        except Exception:
            yield GuardSession(reason="operator_connection_unusable")
            return
        yield replace(session, connection=connection)


def run_probes(config, *, release, host, window=None):
    probes = build_probe_set(config, release=release, host=host)
    with guard_session(config, release=release, probe_set=probes) as session:
        active = probes if session.authority is None else replace(
            probes, authority=session.authority, guard_connection=session.connection,
            guard_identity=session.identity, guard_definition_digest=session.definition_digest)
        outcomes = active.run(window=window)
        if session.reason not in (None, "not_configured"):
            outcomes[Capability.NATIVE_COMMIT_GUARD] = Outcome(
                capability=Capability.NATIVE_COMMIT_GUARD, proven=False, reason=session.reason)
    return outcomes


@contextmanager
def unlocked_keychain(snapshot, password):
    """Hold the purpose Keychain unlocked for exactly one issuance, then lock it again.

    The password arrives on stdin so it never appears in argv, the environment or a file,
    and it is dropped as soon as the call returns.
    """
    if password is None:
        yield
        return
    manager = NativeKeychain()
    path = Path(snapshot.policy.signer.keychain)
    manager.unlock(path, password, owner=snapshot.policy.signer.uid)
    try:
        yield
    finally:
        password = None
        manager.lock(path, owner=snapshot.policy.signer.uid)


def read_password(enabled: bool):
    """A single line from stdin, or None. Never echoed, never logged."""
    if not enabled:
        return None
    line = sys.stdin.readline()
    if not line.endswith("\n") or not 12 <= len(line.rstrip("\n").encode()) <= 1024:
        raise ValueError("keychain password must be one 12..1024 byte line on stdin")
    return line.rstrip("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path,
                        help="reference-only diagnostics; requires --probe-only")
    parser.add_argument("--profile", choices=("test", "production"),
                        help="load the independent root-owned release receipt policy")
    parser.add_argument("--release", required=True)
    # Retain parsing only to give old callers an explicit refusal, never a PEM fallback.
    parser.add_argument("--key", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--key-id", help=argparse.SUPPRESS)
    parser.add_argument("--out", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--days", type=int, default=1, help="receipt validity in days (<=7)")
    parser.add_argument("--capability", action="append", choices=[c.value for c in Capability],
                        help="capability to issue; repeatable, default is every issuable one")
    parser.add_argument("--probe-only", action="store_true",
                        help="run the readonly probes, sign nothing, never read a key")
    parser.add_argument("--keychain-password-stdin", action="store_true",
                        help="read the purpose Keychain password from stdin for this run only")
    parser.add_argument("--debug", action="store_true",
                        help="include a traceback when refusing to sign")
    args = parser.parse_args()

    if not args.probe_only and (args.key or args.key_id or args.out or args.config):
        print(json.dumps({"state": "BLOCKED", "reason": "protected_signing_required"}))
        return 2
    stage = "policy" if args.profile else "probe_configuration"
    try:
        if args.profile:
            if args.config is not None:
                raise ValueError("protected policy cannot be replaced by caller references")
            snapshot = load_policy(args.profile, args.release)
            config, host = snapshot.policy.probe_config(), snapshot.policy.host
            requested = requested_capabilities(
                snapshot.policy, [Capability(name) for name in args.capability]
                if args.capability else None)
        elif args.probe_only and args.config:
            snapshot = None
            config, host = read_probe_config(args.config), host_identity()
            requested = tuple(Capability(name) for name in args.capability) \
                if args.capability else tuple(Capability)
        else:
            raise ValueError("protected profile is required for issuance")
        if args.probe_only:
            operation = ReceiptOperation(snapshot) if snapshot is not None else None
            stage = "probe"
            outcomes = run_probes(config, release=args.release, host=host,
                                  window=operation.initial if operation else None)
            if operation:
                operation.check()
            report = {cap.value: {"proven": result.proven, "reason": result.reason}
                      for cap, result in outcomes.items()}
            print(json.dumps({"state": "PROBED", "host": host, "release": args.release,
                              "capabilities": report}, indent=2))
            return 0 if all(outcomes[cap].proven for cap in requested) else 2
        if not 0 < args.days <= 7:
            raise ValueError("invalid receipt window")
        stage = "sign_and_publish"
        with unlocked_keychain(snapshot, read_password(args.keychain_password_stdin)):
            issued = issue_protected(
                snapshot, lambda window: run_probes(config, release=args.release, host=host,
                                                    window=window),
                requested=requested, seconds=args.days * 86400,
            )
        print(json.dumps({"state": "ISSUED", "host": host, "release": args.release,
                          "capabilities": [cap.value for cap in issued]}))
        return 0
    except Exception as error:
        reason = "protected_receipt_unavailable" if args.profile or not args.probe_only \
            else "probe_configuration_unusable"
        report = {"state": "BLOCKED", "reason": reason,
                  "stage": stage, "errorType": type(error).__name__}
        # The operator cannot act on an opaque refusal: a PermissionError here is the difference
        # between "this role may not read the clock frame" and "the keychain is still locked", and
        # those need different fixes. The filename is reported because it is the actionable part;
        # nothing about the key, the password or the signed material is exposed.
        detail = str(error)
        if isinstance(error, OSError) and error.filename:
            detail = f"{detail} ({error.filename})"
        report["detail"] = detail
        if args.debug:
            report["traceback"] = traceback.format_exc()
        print(json.dumps(report))
        return 2


if __name__ == "__main__":
    sys.exit(main())
