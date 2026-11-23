"""Shared arrangements for the recovery tests (U8 plan Step 30).

- `open_ledger`: the ledger component in a private folder under the test's own
  temporary folder, never the realm's live ledger.
- `set_record`, `approval_record`, `receipt`: ledger records as the machine reads them,
  for the component tests, each receipt-bearing one with its binding facts.
- `JourneyDatabase`: a production stand-in of the test's own in the realm's instance
  (`docsuri_u8r<hex>`), with two owners' schemas, tables, a vector index and rows, so a
  production restore recreates and restores it without touching `docsuri_u8`.
- `journey_agent`: the backup agent's own folder and stand-in volume for that database,
  configured as the realm configures its agent.
- `decide`: your decision through PlatformControl's decision operation and the ledger
  component's append, as Workflow 18 records it.
- `FaultyOperator`: the realm's operator, with U7's injected permission failure for the
  named steps, so a failure path runs through the real receipts.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql

from backend.local_profile import private_bytes
from backend.modules.operations.ledger import Ledger, utc_text
from docsuri_ops.arrangement.paths import DatabaseNames
from docsuri_ops.backup_agent.config import AgentConfig, Login, write
from docsuri_ops.backup_agent.disposal import prepare_volume

GIB = 1024**3
OWNERS = ("accounts", "library")


def open_ledger(tmp_path: Path, clock) -> Ledger:
    folder = tmp_path / "operations-ledger"
    folder.mkdir(mode=0o700)
    return Ledger.open(folder, clock=clock)


def receipt(operation: str = "platform.database.backup", target: str = "database-production",
            outcome: str = "succeeded", *, now: dt.datetime) -> dict:
    return {"receiptId": str(uuid4()), "operationId": str(uuid4()), "operation": operation,
            "targetId": target, "inputHash": secrets.token_hex(32), "outcome": outcome,
            "confirmedAt": utc_text(now)}


def set_record(ledger: Ledger, *, environment: str = "live", integrity: str = "passed",
               now: dt.datetime, database: str = "docsuri_u8", size_bytes: int = 1024,
               **fields) -> dict:
    """A backup set of `size_bytes` (U8 plan Step 71(g)); `fields` adds or replaces any
    other field (`recoveryRequestId`, `trigger`, or a later version's fields), U8 plan
    Step 59(c)."""
    facts = receipt(now=now)
    revision = sum(1 for item in ledger.records("backup-set")
                   if item["environment"] == environment) + 1
    backup = str(uuid4())
    record = {
        "backupId": backup, "environment": environment, "revision": revision,
        "trigger": "scheduled", "takenAt": utc_text(now), "checksum": secrets.token_hex(32),
        "sizeBytes": size_bytes, "sourceDatabaseBytes": 4096,
        "location": f"archives/live-set-20261022T120000-{backup}.archive",
        "databaseIncarnation": f"{database}:16384",
        "stagingLocation": f"staging/live-set-20261022T120000-{backup}",
        "retainUntil": utc_text(now + dt.timedelta(days=14)), "integrity": integrity,
        "operatorReceiptRef": facts["receiptId"], **fields,
    }
    ledger.append("backup-set", record, expect_revision=0, receipts=(facts,))
    return record


def approval_record(ledger: Ledger, step: str, subject: str, *, now: dt.datetime,
                    decision: str = "approved") -> dict:
    facts = receipt("platform.decision.record", "decisions", now=now)
    record = {"approvalId": str(uuid4()), "step": step, "subjectRef": subject,
              "subjectDigest": secrets.token_hex(32), "decision": decision,
              "recordedAt": utc_text(now), "operatorReceiptRef": facts["receiptId"]}
    ledger.append("maintainer-approval", record, expect_revision=0, receipts=(facts,))
    return record


def cutover_record(ledger: Ledger, state: str, **fields) -> dict:
    record = {"cutoverId": str(uuid4()), "releaseTag": "v2.0.0", "state": state,
              "soakPeriodSeconds": 604800, "soakClean": False, "switchTimeBoundSeconds": 14400,
              "rollbackWindowSeconds": 1209600, "effectReceipts": [], "approvals": [], **fields}
    ledger.append("cutover-record", record, expect_revision=0)
    return record


def advance_cutover(ledger: Ledger, record: dict, state: str, **fields) -> dict:
    updated = {**record, "state": state, **fields}
    ledger.append("cutover-record", updated,
                  expect_revision=ledger.revision("cutover-record", record["cutoverId"]))
    return updated


def decide(operator, ledger: Ledger, clock, step: str, subject_ref: str,
           decision: str = "approved", subject: dict | None = None) -> str:
    """Your decision, recorded through `platform.decision.record` and appended."""
    from docsuri_ops.u8_platform.decisions import Decisions

    def append(document: dict) -> dict:
        facts = tuple({**item, "confirmedAt": utc_text(clock())}
                      for item in document["receipts"])
        ledger.append(document["kind"], document["record"],
                      expect_revision=document["expectRevision"], receipts=facts)
        return {"ok": True}

    decisions = Decisions(operator, append, clock=clock)
    shown_subject = subject or {"subject": subject_ref, "step": step}
    shown = decisions.show(step, subject_ref, shown_subject)
    return decisions.record(shown, decision, current=lambda: shown_subject)["approvalId"]


# --- the realm's logins -------------------------------------------------------------------


def credentials(realm, file: str) -> dict:
    return json.loads(private_bytes(Path(realm.root) / file))


def admin(realm, database: str = "postgres"):
    password = credentials(realm, "migration-credentials.json")["databaseAdminPassword"]
    return psycopg.connect(host="127.0.0.1", port=realm.database_port, dbname=database,
                           user="postgres", password=password, require_auth="scram-sha-256",
                           connect_timeout=5, autocommit=True)


def login(realm, role: str, database: str):
    password = credentials(realm, "standin-credentials.json")["roles"][role]
    user = {"restore": "docsuri_restore", "scheduler": "docsuri_scheduler",
            "backupAgent": "docsuri_backup_agent"}[role]
    return psycopg.connect(host="127.0.0.1", port=realm.database_port, dbname=database,
                           user=user, password=password, require_auth="scram-sha-256",
                           connect_timeout=5, autocommit=True)


def database_exists(realm, name: str) -> bool:
    with admin(realm) as conn:
        return conn.execute("SELECT 1 FROM pg_database WHERE datname=%s",
                            (name,)).fetchone() is not None


def drop_database(realm, name: str) -> None:
    with admin(realm) as conn:
        conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
            sql.Identifier(name)))


# --- a production stand-in of the test's own ---------------------------------------------


@dataclass
class JourneyDatabase:
    realm: object
    name: str = field(default_factory=lambda: f"docsuri_u8r{secrets.token_hex(3)[:5]}")

    @property
    def names(self) -> DatabaseNames:
        return DatabaseNames(self.name)

    def create(self) -> JourneyDatabase:
        """Two owners' schemas, each owner's table with rows and a vector index, and the
        grants a production database holds: no PUBLIC connection, the logins' CONNECT."""
        drop_database(self.realm, self.name)
        with admin(self.realm) as conn:
            ident = sql.Identifier(self.name)
            conn.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template1").format(ident))
            conn.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(ident))
            for role in ("docsuri_restore", "docsuri_backup_agent", "docsuri_accounts",
                         "docsuri_library"):
                conn.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                    ident, sql.Identifier(role)))
        with admin(self.realm, self.name) as conn:
            conn.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
            for owner in OWNERS:
                role = sql.Identifier(f"docsuri_{owner}_owner")
                conn.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(role))
                conn.execute(sql.SQL("CREATE SCHEMA {} AUTHORIZATION {}").format(
                    sql.Identifier(owner), role))
            conn.execute("SET ROLE docsuri_accounts_owner")
            conn.execute(
                "CREATE TABLE accounts.account(id uuid PRIMARY KEY,email text NOT NULL,"
                "active boolean NOT NULL DEFAULT true,lifecycle_state text NOT NULL DEFAULT "
                "'active',embedding vector(3) NOT NULL)")
            conn.execute("CREATE INDEX account_embedding ON accounts.account USING hnsw "
                         "(embedding vector_cosine_ops)")
            conn.execute("CREATE TABLE accounts.session(id uuid PRIMARY KEY,account_id uuid "
                         "NOT NULL REFERENCES accounts.account(id))")
            conn.execute("GRANT SELECT ON accounts.account TO docsuri_accounts")
            conn.execute("RESET ROLE")
            conn.execute("SET ROLE docsuri_library_owner")
            conn.execute("CREATE TABLE library.saved_paper(account_id uuid NOT NULL,"
                         "paper_id text NOT NULL,PRIMARY KEY(account_id,paper_id))")
            conn.execute("RESET ROLE")
        return self

    def add_owner(self, account: str | None = None) -> str:
        identity = account or str(uuid4())
        with admin(self.realm, self.name) as conn:
            conn.execute("INSERT INTO accounts.account(id,email,embedding) VALUES(%s,%s,%s)",
                         (identity, f"{identity}@fixture.invalid", "[0.1,0.2,0.3]"))
            conn.execute("INSERT INTO accounts.session(id,account_id) VALUES(%s,%s)",
                         (str(uuid4()), identity))
            conn.execute("INSERT INTO library.saved_paper(account_id,paper_id) VALUES(%s,%s)",
                         (identity, "arxiv:2101.00001"))
        return identity

    def snapshot(self) -> dict:
        """Every owner object with its owner, and every row, for comparison."""
        with admin(self.realm, self.name) as conn:
            owners = conn.execute(
                "SELECT n.nspname||'.'||c.relname, pg_get_userbyid(c.relowner) FROM pg_class c "
                "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname = ANY(%s) "
                "ORDER BY 1", (list(OWNERS),)).fetchall()
            rows = {
                "accounts": conn.execute("SELECT id::text,email,active,lifecycle_state FROM "
                                         "accounts.account ORDER BY id").fetchall()
                if self.has_tables(conn) else [],
                "library": conn.execute("SELECT account_id::text,paper_id FROM "
                                        "library.saved_paper ORDER BY 1,2").fetchall()
                if self.has_tables(conn) else [],
            }
        return {"owners": owners, "rows": rows}

    @staticmethod
    def has_tables(conn) -> bool:
        return conn.execute("SELECT to_regclass('accounts.account')").fetchone()[0] is not None

    def tables(self) -> list[str]:
        with admin(self.realm, self.name) as conn:
            return [row[0] for row in conn.execute(
                "SELECT n.nspname||'.'||c.relname FROM pg_class c JOIN pg_namespace n "
                "ON n.oid=c.relnamespace WHERE c.relkind='r' AND n.nspname = ANY(%s)",
                (list(OWNERS),)).fetchall()]

    def drop(self) -> None:
        drop_database(self.realm, self.name)


def journey_agent(tmp_path: Path, realm, database: JourneyDatabase, clock) -> Path:
    """The agent's own folder and stand-in volume for the journey's database."""
    driver = json.loads(private_bytes(Path(realm.root) / "platform" / "effects" / "driver.json"))
    environment = json.loads(private_bytes(Path(realm.root) / "environment.json"))
    volume, folder = tmp_path / "volume", tmp_path / "agent"
    for path in (volume, folder):
        path.mkdir(mode=0o700)
    prepare_volume(volume, clock=clock)
    descriptor = os.open(folder / "v2-login", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write(credentials(realm, "standin-credentials.json")["roles"]["backupAgent"])
    write(folder, AgentConfig(
        kind="realm", mount=volume, volume_identity=f"standin-journey-{secrets.token_hex(4)}",
        database_prefix=database.name,
        v2_login=Login("127.0.0.1", realm.database_port, "docsuri_backup_agent", "v2-login"),
        scheduler_uid=driver["schedulerUid"], operator_uid=driver["operatorUid"],
        service_uid=environment.get("serviceUid", 710), container=environment["container"],
        space_floor_bytes=1024**2,
    ))
    return folder


class FaultyOperator:
    """The realm's operator with U7's injected permission failure for the named effects:
    `fail` maps (operation, a key fragment) to how many times it fails."""

    def __init__(self, operator, fail: dict[tuple[str, str], int] | None = None):
        self.operator, self.fail = operator, dict(fail or {})
        self.calls: list[tuple[str, str]] = []

    def __getattr__(self, name):
        return getattr(self.operator, name)

    def execute(self, operation, target, inputs, *, key, injected_fault=None, **options):
        self.calls.append((operation, key))
        for (name, fragment), count in self.fail.items():
            if name == operation and fragment in key and count > 0:
                self.fail[(name, fragment)] = count - 1
                return self.operator.execute(operation, target, inputs, key=key,
                                             injected_fault="permission", **options)
        return self.operator.execute(operation, target, inputs, key=key,
                                     injected_fault=injected_fault, **options)


class InPersonCopy:
    """Production's in-person ledger copy (`production_wiring.production_procedures`, role
    `operator`), put on the realm's procedures: the ledger's own copy, then its bytes into
    the agent's `ledger-copy`, here through the realm driver's agent instead of
    `sudo -k -u _docsuri_r1t_backup`. Its first `failures` copies are refused as the agent
    refuses one (review finding, Critical, R15); `vias` records how each was asked for."""

    def __init__(self, procedures, ledger, tmp_path: Path, *, failures: int = 0):
        from types import SimpleNamespace

        from docsuri_ops import production_wiring as wiring
        from docsuri_ops.arrangement.paths import ArrangementPaths
        from docsuri_ops.u8_platform.drivers import DriverRefused

        realm_driver = procedures.platform.agent.__self__
        self.failures, self.vias = failures, []

        def ledger_copy(stream: bytes, *, via: str) -> dict:
            self.vias.append(via)
            if self.failures > 0:
                self.failures -= 1
                raise DriverRefused("volume-check-failed")
            return realm_driver.ledger_copy(stream)

        driver = SimpleNamespace(ledger_copy=ledger_copy, agent_word=realm_driver.agent_word)
        operator = SimpleNamespace(facts=lambda: SimpleNamespace(current_rehearsal=None))
        built = wiring.production_procedures(
            ledger, operator, role="operator", driver=driver,
            paths=ArrangementPaths.under(tmp_path / "in-person" / "Library" / "DocSuri"),
            release=lambda login: bytearray(secrets.token_hex(32).encode()))
        procedures.platform.ledger_copy = built.procedures.platform.ledger_copy
