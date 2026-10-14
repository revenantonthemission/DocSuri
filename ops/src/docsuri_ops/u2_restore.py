"""Bounded old-backup rehearsal in a fixed, permanently quarantined U2 database.

The original database remains the authority for the current checkpoint. This
same-host synthetic exercise does not establish host-loss recovery or activate
the restored application. Required owner evidence is never replaced by a newer
whole-database copy.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import selectors
import shutil
import signal
import socket
import stat
import subprocess
import time
from dataclasses import replace
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
from backend.local_profile import LocalProfile, private_bytes
from backend.transactions import DeadlineConnection, OwnerTransactions
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .u2_restore_context import (
    RESTORE_DATABASE,
    RestoreContext,
    canonical_json_bytes,
    compute_checkpoint_digest,
    context_from_json,
    context_to_json,
    fragment_digest,
    read_json_record,
    sha256_json,
    verify_checkpoint_digest,
)

MIB = 1024**2
BACKUP_LIMIT = 256 * MIB
RESTORE_LIMIT = 512 * MIB
EVIDENCE_LIMIT = 256 * MIB
REQUIRED = frozenset(
    (
        "AccountAccess",
        "Library",
        "Personalization",
        "DiscoveryCitations",
        "PaperAssistance",
        "UsageEntitlements",
    )
)
ROLES = frozenset(
    (
        "accounts",
        "corpus",
        "library",
        "personalization",
        "discovery",
        "assistance",
        "usage",
        "operations",
    )
)
KEY_VERSION = "u2-restore-journal-v1"
IMAGE = "postgres@sha256:a3b7f434b2dc57ce85a67e171163eb8ab1a1ebcb39d27484661f26b1dfbe30d6"


class RestoreRefused(RuntimeError):
    """Quarantine remains in force; no recoverability or activation is implied."""


def _owned_file(path: Path, maximum: int) -> int:
    info = path.lstat()
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o600
        or info.st_nlink != 1
        or not 0 < info.st_size <= maximum
    ):
        raise RestoreRefused("bounded private restore material custody differs")
    return info.st_size


def _owned_directory(path: Path) -> None:
    info = path.lstat()
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        raise RestoreRefused("private restore directory custody differs")


def _sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_new(path: Path, value: dict) -> None:
    _owned_directory(path.parent)
    payload = canonical_json_bytes(value)
    if len(payload) > 2 * MIB:
        raise RestoreRefused("checkpoint exceeds bounded evidence allocation")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    _sync_directory(path.parent)


def _file_digest(path: Path, maximum: int) -> tuple[str, int]:
    expected = _owned_file(path, maximum)
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    digest, count = hashlib.sha256(), 0
    with os.fdopen(descriptor, "rb") as stream:
        opened = os.fstat(stream.fileno())
        if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
            raise RestoreRefused("restore archive changed during open")
        while chunk := stream.read(65536):
            count += len(chunk)
            if count > maximum:
                raise RestoreRefused("restore archive grew past its allocation")
            digest.update(chunk)
    if count != expected:
        raise RestoreRefused("restore archive changed during read")
    return digest.hexdigest(), count


class RestoreTransactions:
    """Owner-role effects only in the fixed quarantine, never a public profile."""

    def __init__(self, coordinator, context):
        self.coordinator, self.context = coordinator, context
        self.profile = coordinator.profile

    def run(self, owner, callback):
        if owner not in ROLES:
            raise RestoreRefused("unknown restore owner")
        self.coordinator.current_checkpoint(self.context)
        deadline = min(self.coordinator.deadline, time.monotonic() + 5)
        with self.coordinator._connect(RESTORE_DATABASE) as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
            self.coordinator._guard_target(conn, self.context)
            conn.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(f"docsuri_{owner}")))
            bounded = DeadlineConnection(conn, deadline, statement_ms=3000)
            result = callback(bounded)
            bounded.remaining()
            conn.commit()
            return result


class IsolatedRestore:
    """Caller holds the run's exclusive fixture lock and stops all writers.

    The constructor performs read-only identity checks. All DB commands target
    either the original named U2 realm, its fixed quarantine, or postgres for
    database creation. No method drops or overwrites the original U2 realm.
    """

    def __init__(
        self,
        manifest: Path,
        *,
        source_digest: str,
        policy_digest: str,
        manifest_digest: str,
        seconds: float = 300,
    ):
        if not 10 <= seconds <= 300:
            raise RestoreRefused("finite restore deadline required")
        self.cleanup_deadline = time.monotonic() + seconds
        self.deadline = self.cleanup_deadline - 7
        self.profile = LocalProfile.load(manifest)
        if self.profile.realm != "account-controls" or self.profile.database_name != "docsuri_u2":
            raise RestoreRefused("explicit current U2 profile required")
        self.root = self.profile.root
        self.run = self.profile.run_id
        value = read_json_record(private_bytes(manifest))
        if (
            value.get("container") != self.run
            or value.get("volume") != self.run + "-pgdata"
            or value.get("databaseImage") != IMAGE
        ):
            raise RestoreRefused("U2 container identity differs")
        self.source_digest, self.policy_digest, self.manifest_digest = (
            source_digest,
            policy_digest,
            manifest_digest,
        )
        self.directory = self.root / "restore-evidence"
        if not self.directory.exists():
            self.directory.mkdir(mode=0o700)
        _owned_directory(self.directory)
        self._remaining()
        self._verify_container()

    def _remaining(self, maximum: float = 10, *, cleanup: bool = False) -> float:
        remaining = (self.cleanup_deadline if cleanup else self.deadline) - time.monotonic()
        if remaining <= 0 or (not cleanup and time.time() >= self.profile.expires_at):
            raise RestoreRefused("restore deadline or synthetic retention expired")
        return min(maximum, remaining)

    def _docker(self, arguments: list[str], *, maximum: int = MIB, cleanup: bool = False) -> bytes:
        result = subprocess.run(
            ["docker", *arguments],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=self._remaining(3 if cleanup else 10, cleanup=cleanup),
            check=False,
        )
        if result.returncode or len(result.stdout) > maximum or len(result.stderr) > MIB:
            raise RestoreRefused("owned restore control command failed")
        return result.stdout

    def _verify_container(self):
        record = json.loads(self._docker(["inspect", self.run]))[0]
        if (
            record["Config"]["Labels"].get("dev.docsuri.u2.run") != self.run
            or record["State"]["Status"] != "running"
            or record["HostConfig"]["Memory"] != 1024**3
            or record["Config"]["Image"] != IMAGE
        ):
            raise RestoreRefused("owned bounded database container unavailable")
        volume = json.loads(self._docker(["volume", "inspect", self.run + "-pgdata"]))[0]
        if volume["Labels"].get("dev.docsuri.u2.run") != self.run:
            raise RestoreRefused("database volume ownership differs")

    def _connect(self, database: str = "docsuri_u2", *, cleanup: bool = False):
        if database not in ("docsuri_u2", RESTORE_DATABASE, "postgres"):
            raise RestoreRefused("database outside explicit restore vocabulary")
        self._remaining(cleanup=cleanup)
        secret = read_json_record(private_bytes(self.root / "migration-credentials.json"))
        return psycopg.connect(
            host="127.0.0.1",
            port=15449,
            dbname=database,
            user="postgres",
            password=secret["databaseAdminPassword"],
            connect_timeout=3,
            row_factory=dict_row,
            application_name="docsuri-u2-restore-coordinator",
            options=(
                "-c statement_timeout=3000 -c lock_timeout=2000 "
                "-c idle_in_transaction_session_timeout=5000"
            ),
        )

    def ensure_stopped(self):
        self._remaining()
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", 18049)) == 0:
                raise RestoreRefused("stop the U2 application before restore work")
        with self._connect() as conn:
            active = conn.execute(
                "SELECT count(*) AS n FROM pg_stat_activity WHERE datname='docsuri_u2' "
                "AND pid<>pg_backend_pid() AND usename LIKE 'docsuri_%'"
            ).fetchone()["n"]
            if active:
                raise RestoreRefused(
                    "owner connections remain; stop writers before checkpoint capture"
                )

    def _schema_digest(self) -> str:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT run_id,schema_hashes FROM public.docsuri_local_identity WHERE singleton"
            ).fetchone()
            if not row or row["run_id"] != self.run:
                raise RestoreRefused("source database identity differs")
            return sha256_json(row["schema_hashes"])

    def provision_keys(self) -> None:
        """One explicit initial provisioning; missing half-pairs never self-heal."""
        primary = self.root / "restore-journal-key.json"
        recovery_dir = self.root / "restore-key-recovery"
        if not recovery_dir.exists():
            recovery_dir.mkdir(mode=0o700)
        _owned_directory(recovery_dir)
        recovery = recovery_dir / "restore-journal-key.json"
        if primary.exists() or primary.is_symlink() or recovery.exists() or recovery.is_symlink():
            self._key()
            return
        value = {"runId": self.run, "version": KEY_VERSION, "key": os.urandom(32).hex()}
        _write_new(primary, value)
        _write_new(recovery, value)
        self._key()

    def _key(self) -> bytes:
        primary = self.root / "restore-journal-key.json"
        recovery_dir = self.root / "restore-key-recovery"
        _owned_directory(recovery_dir)
        recovery = recovery_dir / "restore-journal-key.json"
        for path in (primary, recovery):
            _owned_file(path, 1024)
        one, two = private_bytes(primary, maximum=1024), private_bytes(recovery, maximum=1024)
        if not hmac.compare_digest(one, two):
            raise RestoreRefused("journal key recovery copy differs")
        value = read_json_record(one)
        if (
            set(value) != {"runId", "version", "key"}
            or value["runId"] != self.run
            or value["version"] != KEY_VERSION
            or not re.fullmatch(r"[0-9a-f]{64}", value["key"])
        ):
            raise RestoreRefused("journal key identity differs")
        return bytes.fromhex(value["key"])

    def _authenticated(self, value: dict) -> dict:
        payload = canonical_json_bytes(value)
        tag = hmac.new(
            self._key(), b"docsuri-u2-restore-v1\n" + payload, hashlib.sha256
        ).hexdigest()
        return {"payload": value, "keyVersion": KEY_VERSION, "authentication": tag}

    def _read_authenticated(self, path: Path) -> dict:
        _owned_file(path, 2 * MIB)
        value = read_json_record(private_bytes(path, maximum=2 * MIB), maximum=2 * MIB)
        if set(value) != {"payload", "keyVersion", "authentication"}:
            raise RestoreRefused("journal authentication envelope differs")
        expected = self._authenticated(value["payload"])
        if (
            value["keyVersion"] != KEY_VERSION
            or not isinstance(value["authentication"], str)
            or not hmac.compare_digest(value["authentication"], expected["authentication"])
        ):
            raise RestoreRefused("journal authentication failed")
        return value["payload"]

    def _account_keys(self):
        """Read existing key custody; never rotate or repair it implicitly."""
        from backend.modules.accounts.control_keys import ControlKeyring

        verifier = private_bytes(self.root / "account-verifier.key", maximum=32)
        if len(verifier) != 32:
            raise RestoreRefused("account verifier custody unavailable")
        legacy = hmac.new(verifier, b"encryption\0u2-controls-v1", hashlib.sha256).digest()
        return verifier, ControlKeyring(self.root, self.run, legacy)

    def _capture_account_keys(self) -> dict:
        from backend.modules.accounts.control_key_recovery import capture

        _, ring = self._account_keys()
        return capture(ring)

    def _verify_account_keys(self, reference: dict) -> None:
        if (
            not isinstance(reference, dict)
            or set(reference) != {"runId", "generation", "digest"}
            or reference["runId"] != self.run
            or type(reference["generation"]) is not int
            or not 1 <= reference["generation"] <= 3
            or not isinstance(reference["digest"], str)
            or not re.fullmatch("[0-9a-f]{64}", reference["digest"])
        ):
            raise RestoreRefused("complete backup key-custody identity required")
        directory = self.root / "account-key-recovery"
        _owned_directory(directory)
        bundle = directory / (reference["digest"] + ".json")
        digest, _ = _file_digest(bundle, 8192)
        if digest != reference["digest"]:
            raise RestoreRefused("backup key-custody snapshot changed")
        value = read_json_record(private_bytes(bundle, maximum=8192), maximum=8192)
        if (
            value.get("version") != 1
            or value.get("runId") != self.run
            or value.get("generation") != reference["generation"]
        ):
            raise RestoreRefused("backup key-custody metadata differs")
        verifier, ring = self._account_keys()
        current = ring.read()
        snapshot = value["keyring"]
        # Require the initialization marker even if both live keyring files were
        # lost: absence cannot silently fall back to virtual legacy generation 1.
        if (
            private_bytes(self.root / "account-control-keyring.initialized", maximum=128)
            != self.run.encode()
        ):
            raise RestoreRefused("account key initialization custody differs")
        if (
            snapshot["runId"] != self.run
            or snapshot["generation"] != reference["generation"]
            or current["generation"] < reference["generation"]
            or not hmac.compare_digest(verifier, base64.b64decode(value["verifier"], validate=True))
            or not snapshot["keys"]
            or len(snapshot["keys"]) > 3
        ):
            raise RestoreRefused("current account keys cannot satisfy the older backup")
        for version, encoded in snapshot["keys"].items():
            if not hmac.compare_digest(ring.key(version), base64.b64decode(encoded, validate=True)):
                raise RestoreRefused("retained backup encryption key differs")

    def _verify_checkpoint_keys(self, record: dict, context: RestoreContext) -> None:
        backup_id = UUID(record["backupId"])
        metadata = self._read_authenticated(self.directory / f"backup-{backup_id}.json")
        if metadata.get("sha256") != context.backup_digest or metadata.get("runId") != self.run:
            raise RestoreRefused("checkpoint key custody addresses another backup")
        self._verify_account_keys(metadata.get("accountKeyCustody"))

    def _resources(self):
        backup_bytes = evidence_bytes = 0
        for path in self.directory.iterdir():
            # Refuse unowned material rather than following a link out of the run.
            info = path.lstat()
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_nlink != 1
            ):
                raise RestoreRefused("restore evidence custody differs")
            if path.suffix == ".dump":
                backup_bytes += info.st_size
            else:
                evidence_bytes += info.st_size
        total = backup_bytes + evidence_bytes
        if backup_bytes > BACKUP_LIMIT or evidence_bytes > EVIDENCE_LIMIT:
            raise RestoreRefused("restore evidence and backup allocation exceeded")
        with self._connect() as conn:
            live = conn.execute("SELECT pg_database_size('docsuri_u2') AS bytes").fetchone()[
                "bytes"
            ]
            wal = conn.execute(
                "SELECT coalesce(sum(size),0) AS bytes FROM pg_ls_waldir()"
            ).fetchone()["bytes"]
            restore = conn.execute(
                "SELECT pg_database_size(oid) AS bytes FROM pg_database WHERE datname=%s",
                (RESTORE_DATABASE,),
            ).fetchone()
        if live + wal > 512 * MIB or (restore and restore["bytes"] > RESTORE_LIMIT):
            raise RestoreRefused("live or restored database exceeded finite allocation")
        if 2496 * MIB + live + wal + (restore["bytes"] if restore else 0) + total > 4096 * MIB:
            raise RestoreRefused("recovery reserve no longer fits the 4 GiB allocation")
        if shutil.disk_usage(self.root).free < 2496 * MIB:
            raise RestoreRefused("physical recovery free-space reserve unavailable")
        return {
            "liveBytes": live,
            "walBytes": int(wal),
            "restoreBytes": restore["bytes"] if restore else 0,
            "backupBytes": backup_bytes,
            "ownedEvidenceBytes": evidence_bytes,
            "reserveBytes": 2496 * MIB,
        }

    def _stream(self, arguments: list[str], archive: Path, *, restore: bool):
        """Stream to/from the host; container /tmp is never an archive staging area."""
        operation = "docsuri-u2-restore-" + uuid4().hex
        pgname = operation
        marker = f"/tmp/{operation}.pid"
        command = [
            "docker",
            "exec",
            "-i",
            "-e",
            f"PGAPPNAME={pgname}",
            self.run,
            "sh",
            "-c",
            'umask 077; set -C; printf "%s\\n" "$$" > "$1"; shift; exec "$@"',
            "owned-restore",
            marker,
            *arguments,
        ]
        if restore:
            _owned_file(archive, BACKUP_LIMIT)
            descriptor = os.open(archive, os.O_RDONLY | os.O_NOFOLLOW)
        else:
            descriptor = os.open(
                archive, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
            )
        process, count, stderr_count = None, 0, 0
        previous_signals = {
            value: signal.getsignal(value) for value in (signal.SIGTERM, signal.SIGINT)
        }

        def interrupted(signum, frame):
            raise RestoreRefused("archive operation interrupted; quarantine retained")

        for value in previous_signals:
            signal.signal(value, interrupted)
        try:
            with (
                os.fdopen(descriptor, "rb" if restore else "wb") as stream,
                selectors.DefaultSelector() as selector,
            ):
                process = subprocess.Popen(
                    command,
                    stdin=stream if restore else subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    start_new_session=True,
                )
                for channel in (process.stdout, process.stderr):
                    os.set_blocking(channel.fileno(), False)
                    selector.register(channel, selectors.EVENT_READ)
                sample_at = 0.0
                while selector.get_map():
                    self._remaining()
                    for key, _ in selector.select(timeout=0.05):
                        chunk = os.read(key.fileobj.fileno(), 65536)
                        if not chunk:
                            selector.unregister(key.fileobj)
                        elif key.fileobj is process.stderr:
                            stderr_count += len(chunk)
                            if stderr_count > MIB:
                                raise RestoreRefused("restore diagnostics exceeded bound")
                        else:
                            count += len(chunk)
                            if count > (MIB if restore else BACKUP_LIMIT):
                                raise RestoreRefused("archive stream exceeded finite allocation")
                            if not restore:
                                stream.write(chunk)
                    if time.monotonic() >= sample_at:
                        self._resources()
                        sample_at = time.monotonic() + 0.5
                if process.wait(timeout=self._remaining()) != 0:
                    raise RestoreRefused("archive command failed; quarantine retained")
                if not restore:
                    stream.flush()
                    os.fsync(stream.fileno())
                    if not count:
                        raise RestoreRefused("empty backup is not recoverable evidence")
            _sync_directory(self.directory)
        finally:
            for value, previous in previous_signals.items():
                signal.signal(value, previous)
            if process is not None:
                # Terminate the owned database backend and remote client as well
                # as the local docker process; killing docker alone is insufficient.
                try:
                    if process.poll() is None:
                        with self._connect("postgres", cleanup=True) as conn:
                            conn.execute(
                                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                                "WHERE application_name=%s",
                                (pgname,),
                            )
                        # Match the private operation environment before a signal:
                        # a stale marker must never kill a reused process ID.
                        self._docker(
                            [
                                "exec",
                                self.run,
                                "sh",
                                "-c",
                                'if test -f "$1"; then read -r pid < "$1"; '
                                'case "$pid" in *[!0-9]*|"") exit 1;; esac; '
                                'if test -r "/proc/$pid/environ" && '
                                'tr "\\000" "\\n" < "/proc/$pid/environ" | '
                                'grep -Fxq "PGAPPNAME=$2"; '
                                'then kill -KILL "$pid" 2>/dev/null || true; fi; rm -- "$1"; fi',
                                "owned-restore",
                                marker,
                                pgname,
                            ],
                            cleanup=True,
                        )
                    else:
                        self._docker(["exec", self.run, "rm", "-f", "--", marker], cleanup=True)
                finally:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait(timeout=self._remaining(3, cleanup=True))
                    for channel in (process.stdout, process.stderr):
                        channel.close()

    def backup(self) -> dict:
        self.ensure_stopped()
        self._resources()
        self._key()
        account_keys = self._capture_account_keys()
        self._verify_account_keys(account_keys)
        identifier = uuid4()
        archive = self.directory / f"backup-{identifier}.dump"
        schema = self._schema_digest()
        self._stream(["pg_dump", "-U", "postgres", "-Fc", "docsuri_u2"], archive, restore=False)
        digest, size = _file_digest(archive, BACKUP_LIMIT)
        value = {
            "runId": self.run,
            "backupId": str(identifier),
            "sha256": digest,
            "bytes": size,
            "schemaDigest": schema,
            "sourceDigest": self.source_digest,
            "policyDigest": self.policy_digest,
            "manifestDigest": self.manifest_digest,
            "accountKeyCustody": account_keys,
        }
        _write_new(self.directory / f"backup-{identifier}.json", self._authenticated(value))
        return value

    def _backup(self, identifier: UUID) -> tuple[dict, Path]:
        if not isinstance(identifier, UUID):
            raise RestoreRefused("typed backup identity required")
        value = self._read_authenticated(self.directory / f"backup-{identifier}.json")
        self._verify_account_keys(value.get("accountKeyCustody"))
        archive = self.directory / f"backup-{identifier}.dump"
        digest, size = _file_digest(archive, BACKUP_LIMIT)
        if (
            value.get("runId") != self.run
            or value.get("backupId") != str(identifier)
            or value.get("sha256") != digest
            or value.get("bytes") != size
            or value.get("schemaDigest") != self._schema_digest()
            or value.get("sourceDigest") != self.source_digest
            or value.get("policyDigest") != self.policy_digest
            or value.get("manifestDigest") != self.manifest_digest
        ):
            raise RestoreRefused("backup identity or compatibility differs")
        return value, archive

    @staticmethod
    def _exports(transactions, context):
        from backend.control_restore import (
            AccountsRestore,
            AssistanceRestore,
            DiscoveryRestore,
            UsageRestore,
        )
        from backend.modules.library import restore as library
        from backend.modules.personalization import restore as personalization

        accounts = AccountsRestore.export_restrictions(transactions, context)
        return [
            accounts,
            DiscoveryRestore.export_restrictions(transactions, context, accounts_fragment=accounts),
            library.export_restrictions(transactions, context, accounts_fragment=accounts),
            personalization.export_restrictions(transactions, context, accounts_fragment=accounts),
            AssistanceRestore.export_restrictions(
                transactions, context, accounts_fragment=accounts
            ),
            UsageRestore.export_restrictions(transactions, context),
        ]

    def capture_checkpoint(self, backup_id: UUID) -> RestoreContext:
        self.ensure_stopped()
        backup, _ = self._backup(backup_id)
        with self._connect() as conn:
            previous = conn.execute(
                "SELECT operations.read_restore_checkpoint() AS value"
            ).fetchone()["value"]
        context = RestoreContext(
            self.run,
            uuid4(),
            previous["sequence"] + 1 if previous else 1,
            previous["checkpointDigest"] if previous else None,
            "0" * 64,
            backup["sha256"],
            self.source_digest,
            self._schema_digest(),
            self.policy_digest,
            self.manifest_digest,
        )
        transactions = OwnerTransactions(self.profile, process="maintenance")
        try:
            fragments = self._exports(transactions, context)
        finally:
            transactions.close()
        context = replace(
            context,
            checkpoint_digest=compute_checkpoint_digest(
                context, fragments, required_owners=REQUIRED
            ),
        )
        value = {
            "context": context_to_json(context),
            "backupId": str(backup_id),
            "fragments": fragments,
        }
        _write_new(
            self.directory / f"checkpoint-{context.checkpoint_id}.json", self._authenticated(value)
        )
        with self._connect() as conn:
            current = conn.execute(
                "SELECT operations.advance_restore_checkpoint(%s) AS value",
                (Jsonb(context_to_json(context)),),
            ).fetchone()["value"]
            if current != context_to_json(context):
                raise RestoreRefused("live checkpoint acknowledgement differs")
        return context

    def current_checkpoint(
        self, expected: RestoreContext | None = None
    ) -> tuple[RestoreContext, dict]:
        self._remaining()
        with self._connect() as conn:
            current = conn.execute(
                "SELECT operations.read_restore_checkpoint() AS value"
            ).fetchone()["value"]
        if current is None:
            raise RestoreRefused("current restriction anchor is missing")
        context = context_from_json(current)
        if expected is not None and context != expected:
            raise RestoreRefused("checkpoint is stale or replaced")
        if (
            context.run_id != self.run
            or context.schema_digest != self._schema_digest()
            or context.source_digest != self.source_digest
            or context.policy_digest != self.policy_digest
            or context.manifest_digest != self.manifest_digest
        ):
            raise RestoreRefused("current checkpoint metadata differs")
        record = self._read_authenticated(
            self.directory / f"checkpoint-{context.checkpoint_id}.json"
        )
        if record["context"] != current:
            raise RestoreRefused("journal and live anchor differ")
        verify_checkpoint_digest(context, record["fragments"], required_owners=REQUIRED)
        self._verify_checkpoint_keys(record, context)
        return context, record

    def restore(self, context: RestoreContext) -> dict:
        self.ensure_stopped()
        _, record = self.current_checkpoint(context)
        backup, archive = self._backup(UUID(record["backupId"]))
        if backup["sha256"] != context.backup_digest:
            raise RestoreRefused("checkpoint addresses another backup")
        with self._connect("postgres") as conn:
            conn.autocommit = True
            if conn.execute(
                "SELECT 1 FROM pg_database WHERE datname=%s", (RESTORE_DATABASE,)
            ).fetchone():
                raise RestoreRefused(
                    "restore database already exists; explicit owned cleanup required"
                )
            conn.execute(
                sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(
                    sql.Identifier(RESTORE_DATABASE)
                )
            )
            conn.execute(
                sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(
                    sql.Identifier(RESTORE_DATABASE)
                )
            )
        with self._connect(RESTORE_DATABASE) as conn:
            conn.execute(
                "CREATE TABLE public.docsuri_restore_guard("
                "singleton boolean PRIMARY KEY CHECK(singleton),run_id text NOT NULL,"
                "backup_digest text NOT NULL,quarantined boolean NOT NULL CHECK(quarantined),"
                "starting_context jsonb NOT NULL)"
            )
            conn.execute(
                "INSERT INTO public.docsuri_restore_guard VALUES(true,%s,%s,true,%s)",
                (self.run, context.backup_digest, Jsonb(context_to_json(context))),
            )
            conn.execute("REVOKE ALL ON public.docsuri_restore_guard FROM PUBLIC")
            for owner in (
                "accounts",
                "discovery",
                "library",
                "personalization",
                "assistance",
                "usage",
            ):
                conn.execute(
                    sql.SQL("GRANT SELECT ON public.docsuri_restore_guard TO {}").format(
                        sql.Identifier(f"docsuri_{owner}_owner")
                    )
                )
        self._stream(
            [
                "pg_restore",
                "-U",
                "postgres",
                "--exit-on-error",
                "--single-transaction",
                "-d",
                RESTORE_DATABASE,
            ],
            archive,
            restore=True,
        )
        with self._connect(RESTORE_DATABASE) as conn:
            # pg_restore replays the source public-schema ACL. Schema owners
            # need only these identity reads to execute the guarded definer
            # hooks; runtime CONNECT remains denied throughout.
            for owner in (
                "accounts",
                "discovery",
                "library",
                "personalization",
                "assistance",
                "usage",
            ):
                role = sql.Identifier(f"docsuri_{owner}_owner")
                conn.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(role))
                conn.execute(
                    sql.SQL("GRANT SELECT ON public.docsuri_local_identity TO {}").format(role)
                )
            self._guard_target(conn, context)
        return {
            "state": "restored-quarantined",
            "backupDigest": context.backup_digest,
            **self._resources(),
        }

    def _guard_target(self, conn, context):
        if conn.execute("SELECT current_database() AS name").fetchone()["name"] != RESTORE_DATABASE:
            raise RestoreRefused("refusing restore effect on the original database")
        guard = conn.execute(
            "SELECT * FROM public.docsuri_restore_guard WHERE singleton FOR SHARE"
        ).fetchone()
        identity = conn.execute(
            "SELECT run_id,schema_hashes FROM public.docsuri_local_identity WHERE singleton"
        ).fetchone()
        if (
            not guard
            or guard["run_id"] != self.run
            or guard["backup_digest"] != context.backup_digest
            or guard["quarantined"] is not True
            or identity["run_id"] != self.run
            or sha256_json(identity["schema_hashes"]) != context.schema_digest
        ):
            raise RestoreRefused("restore quarantine identity differs")
        baseline = context_from_json(guard["starting_context"])
        if (
            baseline.run_id != context.run_id
            or baseline.backup_digest != context.backup_digest
            or baseline.schema_digest != context.schema_digest
            or baseline.sequence > context.sequence
            or (baseline.sequence == context.sequence and baseline != context)
        ):
            raise RestoreRefused("restore starting checkpoint differs")
        for owner in ROLES:
            if conn.execute(
                "SELECT has_database_privilege(%s,%s,'CONNECT') AS allowed",
                (f"docsuri_{owner}", RESTORE_DATABASE),
            ).fetchone()["allowed"]:
                raise RestoreRefused("runtime role can connect to quarantined database")

    def reconcile(self, context: RestoreContext) -> dict:
        self.ensure_stopped()
        _, record = self.current_checkpoint(context)
        source = OwnerTransactions(self.profile, process="maintenance")
        try:
            current_fragments = self._exports(source, context)
        finally:
            source.close()
        if (
            compute_checkpoint_digest(context, current_fragments, required_owners=REQUIRED)
            != context.checkpoint_digest
        ):
            raise RestoreRefused("source restrictions changed after checkpoint capture")
        from backend.control_restore import (
            AccountsRestore,
            AssistanceRestore,
            DiscoveryRestore,
            UsageRestore,
        )
        from backend.modules.library import restore as library
        from backend.modules.personalization import restore as personalization

        hooks = {
            "AccountAccess": AccountsRestore,
            "DiscoveryCitations": DiscoveryRestore,
            "Library": library,
            "Personalization": personalization,
            "PaperAssistance": AssistanceRestore,
            "UsageEntitlements": UsageRestore,
        }
        transactions = RestoreTransactions(self, context)
        fragments = {fragment["owner"]: fragment for fragment in record["fragments"]}
        evidence = []
        for owner, hook in hooks.items():
            result = hook.reconcile_restore(transactions, fragments[owner], context)
            if (
                result.get("owner") != owner
                or result.get("disposition") != "reconciled"
                or result.get("checkpointId") != str(context.checkpoint_id)
                or result.get("sequence") != context.sequence
                or result.get("fragmentDigest") != fragment_digest(context, fragments[owner])
            ):
                raise RestoreRefused("owner returned incompatible reconciliation evidence")
            UUID(result["evidenceRef"])
            evidence.append(result)
        return {
            "state": "reconciled-quarantined",
            "checkpointId": str(context.checkpoint_id),
            "checkpointDigest": context.checkpoint_digest,
            "owners": evidence,
            "activated": False,
            **self._resources(),
        }

    def discard_quarantine(self, context: RestoreContext) -> None:
        """Explicit cleanup of this proven owned copy; original DB is never named."""
        with self._connect(RESTORE_DATABASE) as conn:
            self._guard_target(conn, context)
        with self._connect("postgres") as conn:
            conn.autocommit = True
            conn.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(RESTORE_DATABASE))
            )
