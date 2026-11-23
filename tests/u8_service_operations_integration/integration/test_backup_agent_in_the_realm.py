"""The backup agent in the composed realm (U8 plan Step 25 "In the realm"; BR6.6, BR10.2,
NFR1.5).

The realm driver runs the same agent (`docsuri_ops.backup_agent`) against the realm's
stand-in volume folder `/tmp/docsuri-u8-run/backup-volume/`, under the scheduler's
standing grant: `platform.database.backup` binds its receipt in the realm's
PlatformControl store, U7's bounded child hands the effect to the realm driver, and the
set lands on the stand-in volume. The two volume-level answers a folder cannot give
(enforced ownership and encryption) come from the realm's adapter, which says it is a
stand-in. The agent's status then reaches the service account only through
PlatformControl's bounded evidence reader, as `agent_status_reader` binds it.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.u8_host import agent_status_reader, build_platform_control
from docsuri_ops.backup_agent import cli
from docsuri_ops.backup_agent.config import load
from docsuri_ops.backup_agent.status import LOW_SPACE
from docsuri_ops.u8_platform.platform_profile import U8PlatformProfile
from tests.u8_service_operations_integration import platform_flows as pf

LOW_ONLY = {LOW_SPACE}


def agent_status(realm) -> dict:
    """The agent's own `status` word, as the scheduler's standing job runs it."""
    config = json.loads(
        (Path(realm.root) / "platform" / "effects" / "driver.json").read_bytes())
    context = cli.AgentContext(Path(config["agentFolder"]))
    out = io.BytesIO()
    status = cli.run(["status"], context, environ={"SUDO_UID": str(config["schedulerUid"])},
                     stdin=io.BytesIO(b"{}"), stdout=out, stderr=io.BytesIO())
    assert status == 0, out.getvalue()
    return json.loads(out.getvalue().splitlines()[-1])


def keys_made_and_used(realm) -> object:
    """U8 plan Step 90(c): every key still missing made through its owner's own path, and
    each used once, before the dump. U6's export keyring is made by the first `load()` of
    the composed export contribution's keyring and used for one seal through its vault;
    the control keyring's `u2-v1` key (derived from the verifier key) protects one factor
    through the entry's keyring, as `conftest.activate_factor` protects one. The verifier
    and cursor keys exist from `migrate` (L1-4). Returns U6's keyring."""
    import base64
    import secrets

    from backend.u8_host import compose

    composition = compose(realm)
    try:
        vault = composition.parts["approved-export"]["service"].vault
        keyring = vault._keys
        keyring.load()
        vault.seal("synthetic-export-token-" + uuid4().hex, account_id=uuid4(),
                   connection_id=uuid4(), revision=1)
        entry = composition.parts["account-controls"]["entry"]
        seed = base64.b32encode(secrets.token_bytes(20)).decode()
        entry.protect("mfa:" + str(uuid4()), {"seed": seed, "codes": []})
    finally:
        composition.close()
    return keyring


@pytest.fixture(scope="module")
def written(tmp_path_factory, realm):
    """The one set this module writes (Step 90(c)): there is no second dump."""
    keyring = keys_made_and_used(realm)
    journey = pf.journey(tmp_path_factory.mktemp("agent"), realm)
    agent = load(Path(journey.config["agentFolder"]))
    scheduler = journey.operator("scheduler")
    record, key = str(uuid4()), f"realm-backup-{pf.RUN}"
    receipt = scheduler.execute("platform.database.backup", "database-production",
                                {"database": "docsuri_u8", "recordId": record,
                                 "via": "standing"}, key=key)
    return SimpleNamespace(journey=journey, agent=agent, scheduler=scheduler, record=record,
                           key=key, receipt=receipt, keyring=keyring)


def test_the_realm_driver_runs_the_same_agent_against_the_standin_volume(realm, written):
    profile = U8PlatformProfile.realm(Path(realm.root))
    agent = written.agent
    assert agent.kind == "realm" and agent.mount == profile.run_root / "backup-volume"

    status = agent_status(realm)
    # The folder cannot answer for the volume: the realm's adapter does, as a stand-in.
    # It sits on this Mac's own disk, so low free space is the one finding it may report.
    assert status["standin"] is True and set(status["findings"]) <= LOW_ONLY, status
    assert status["deletionAllowed"] is True and status["catalogue"] == "intact"
    assert status["volumeIdentity"] == f"standin-{profile.run_id}"

    receipt = written.receipt
    assert receipt["outcome"] == "succeeded", receipt
    [effect, set_ref, *facts] = receipt["effectRefs"]
    assert effect.startswith("database-production/effect-")
    assert set_ref.startswith("backup-volume/archives/live-set-")
    # The agent's own receipt travels beside the reference, as `fact:` references.
    assert {fact.split("=", 1)[0] for fact in facts} >= {
        "fact:recordId", "fact:sha256", "fact:integrity", "fact:disposeAfter",
        "fact:stagingLocation", "fact:databaseBytes",
    }
    # The set is on the stand-in volume, in the agent's own folder there.
    assert (agent.u8_folder / set_ref.removeprefix("backup-volume/")).is_file()


# --- no key in a set or a ledger copy (U8 plan Step 90(c); BR4.8, NFR3.1) ----------------


def encodings(value: bytes) -> list[bytes]:
    """A needle as raw bytes, lowercase hex, and standard or URL-safe base64, each with
    and without padding."""
    import base64

    forms = [value, value.hex().encode()]
    for encode in (base64.b64encode, base64.urlsafe_b64encode):
        encoded = encode(value)
        forms += [encoded, encoded.rstrip(b"=")]
    return forms


def hits(needles: dict[str, bytes], text: bytes) -> list[str]:
    """The labels of the needles found in `text`, in any encoding. Only labels are ever
    returned, so a failure names no key."""
    return sorted({label for label, value in needles.items()
                   if any(form in text for form in encodings(value))})


def key_needles(realm, keyring) -> dict[str, bytes]:
    import hashlib
    import hmac

    from backend.local_profile import private_bytes, verifier_key_path
    from backend.modules.accounts.u8_verifier_key import _read_key
    from backend.u8_host import read_cursor_key

    found: dict[str, bytes] = {}
    record = keyring.load()
    assert keyring.root == Path(realm.root) / "export-keys"
    for version in record["keys"]:
        found[f"export-keys:{version}"] = keyring.key(version)
    # No assertion below names a key's bytes: a failure's explanation would print them.
    verifier = _read_key(verifier_key_path(realm))
    verifier_whole = verifier is not None and len(verifier) == 32
    assert verifier_whole
    # The realm's `control-keys/` holds no file: its key is the legacy `u2-v1` key.
    control = Path(realm.root) / "control-keys"
    control_files = sorted(path.name for path in control.iterdir()) if control.is_dir() else []
    assert control_files == []
    found["control-keys:u2-v1"] = hmac.new(verifier, b"encryption\0u2-controls-v1",
                                           hashlib.sha256).digest()
    found["verifier-key"] = verifier
    found["cursor-key"] = read_cursor_key(realm)
    cursor_whole = len(found["cursor-key"]) == 32
    assert cursor_whole
    root_cursor = Path(realm.root) / "search-cursor.key"
    if root_cursor.exists():
        found["root:search-cursor.key"] = private_bytes(root_cursor)
    return found


def test_no_key_material_reaches_a_backup_set_or_a_ledger_copy(realm, written):
    import secrets
    import subprocess

    from docsuri_ops.backup_agent.dumps import open_archive

    needles = key_needles(realm, written.keyring)
    for folder in ("export-keys", "control-keys", "verifier-key", "cursor-key"):
        assert [label for label in needles if label.startswith(folder)], folder
    # The scanner itself finds a needle planted in a sample text, in each encoding.
    sample = secrets.token_bytes(32)
    for form in encodings(sample):
        assert hits({"sample": sample}, b"text before " + form + b" text after") == ["sample"]
    assert hits({"sample": sample}, b"text without it") == []

    # The set: a custom-format dump, whose SQL text (`pg_restore -f -` through the agent's
    # own client programs for the realm) holds no needle.
    set_ref = written.receipt["effectRefs"][1]
    archive = written.agent.u8_folder / set_ref.removeprefix("backup-volume/")
    with open_archive(archive) as stream:
        first = stream.read(5)
    assert first == b"PGDMP"
    tools = cli.AgentContext(Path(written.journey.config["agentFolder"])).tools(written.agent)
    with open_archive(archive) as stream:
        completed = subprocess.run(tools.command("pg_restore", ["-f", "-"]), stdin=stream,
                                   capture_output=True, env=tools.environment(), timeout=120,
                                   check=False)
    assert completed.returncode == 0, completed.stderr[-2000:]
    sql_text = completed.stdout
    has_tables = b"CREATE TABLE" in sql_text
    assert has_tables
    # Each scan's labels are bound first, so a failure prints labels, never bytes.
    in_sql = hits(needles, sql_text)
    assert in_sql == []
    in_archive = hits(needles, archive.read_bytes())
    assert in_archive == []

    # One copy of the realm's ledger, taken by the scheduler's `platform.ledger.copy`
    # (L1-5), which the realm driver runs as the agent's `ledger-copy`.
    copied = written.scheduler.execute(
        "platform.ledger.copy", "ledger-copy", {"via": "standing", "environment": "rehearsal"},
        key=f"realm-ledger-copy-{uuid4().hex}")
    assert copied["outcome"] == "succeeded", copied
    [location] = [ref for ref in copied["effectRefs"] if ref.startswith("backup-volume/")]
    copy_file = written.agent.u8_folder / location.removeprefix("backup-volume/")
    payload = copy_file.read_bytes()
    copied_bytes = len(payload)
    assert copied_bytes > 0
    in_copy = hits(needles, payload)
    assert in_copy == []


# --- the receipt is bound before the agent's first byte (U8 plan Step 90(c); L1-2) ---------


def test_the_backup_receipt_is_bound_before_the_agents_first_byte(realm, written):
    import datetime as dt

    from docsuri_ops.backup_agent.catalogue import Catalogue
    from docsuri_ops.u8_platform.drivers import parse_facts
    from tests.u8_service_operations_integration.integration.test_restore_verification import (
        store_rows,
    )

    # Read causally, never by comparing timestamps across the two clocks: the store's row
    # exists, and the agent wrote its catalogue entries under the record id the operation
    # bound in its inputs.
    rows = store_rows(realm, written.journey, (
        "SELECT o.operation_name, r.effect_refs FROM platform_control.operation o JOIN "
        "platform_control.receipt r USING (operation_id) WHERE o.idempotency_key = %s"),
        (written.key,))
    assert [name for name, _ in rows] == ["platform.database.backup"]
    facts = parse_facts(written.receipt["effectRefs"])
    assert facts["recordId"] == written.record
    assert f"fact:recordId={written.record}" in rows[0][1]
    archive = written.receipt["effectRefs"][1].removeprefix("backup-volume/")
    staging = facts["stagingLocation"]
    catalogue = Catalogue.open(written.agent.u8_folder, clock=lambda: dt.datetime.now(dt.UTC))
    try:
        entries = catalogue.log.entries()
    finally:
        catalogue.close()

    def events(path: str) -> list:
        return [entry for entry in entries
                if entry.kind.startswith("file.") and entry.record.get("path") == path]

    for path, last in ((archive, "file.written"), (staging, "file.disposed")):
        found = events(path)
        assert found and found[0].kind == "file.writing", (path, [e.kind for e in found])
        assert found[0].record["recordId"] == written.record
        assert last in [entry.kind for entry in found[1:]], (path, [e.kind for e in found])
        assert all(entry.seq > found[0].seq for entry in found[1:])

    def moment(text: str) -> dt.datetime:
        return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))

    archive_events = events(archive)
    [done] = [entry for entry in archive_events if entry.kind == "file.written"]
    assert archive_events[0].record["disposeAfter"] == done.record["disposeAfter"]
    # The staging file's carries its begin time + 86,400 s: the writer read its clock just
    # before the archive's and staging's `file.writing` entries were appended, so the
    # entry's own time is at most moments after that begin time.
    begun = events(staging)[0]
    begin = moment(begun.record["disposeAfter"]) - dt.timedelta(seconds=86_400)
    assert dt.timedelta(0) <= moment(begun.at) - begin < dt.timedelta(seconds=5)
    assert begin <= moment(archive_events[0].at)


def test_the_agents_status_reaches_the_service_account_through_the_evidence_reader(
    tmp_path, realm,
):
    status = agent_status(realm)
    # The standing job records the status as PlatformControl evidence for the volume.
    store = pf.journey(tmp_path, realm).operator("scheduler").store
    store.record_evidence(target="backup-volume", input_hash="0" * 64,
                          environment=U8PlatformProfile.realm(Path(realm.root)).environment,
                          observations=status, max_age_seconds=3600)
    parts = build_platform_control(SimpleNamespace(profile=realm, arrangement=None))
    assert {"evidence", "receipt_reader", "evidence_reader", "inspect"} <= set(parts)
    composition = SimpleNamespace(parts={"platform-control": parts})
    read = agent_status_reader(composition)
    assert read is not None
    observed = read()
    assert observed == json.loads(json.dumps(status))
    assert observed["standin"] is True and set(observed["findings"]) <= LOW_ONLY
    assert parts["inspect"]()["outcome"] in ("available", "degraded")
    # A profile without a provisioned reader binds none, so the status reads unknown.
    assert agent_status_reader(SimpleNamespace(parts={"platform-control": {}})) is None
