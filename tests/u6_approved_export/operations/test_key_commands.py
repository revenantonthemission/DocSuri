"""Operator key commands over the realm, as `docsuri_export_owner` (security design §4.5).

Each test keeps its own temporary key folder. The realm holds sealed tokens from other
tests under versions this folder never had; assertions name only this test's versions.
"""

import base64
import json
import secrets
from uuid import uuid4

import psycopg
import pytest
from backend import key_custody
from backend.modules.export import key_commands
from backend.modules.export.errors import ProtectionUnavailable
from backend.modules.export.token_keyring import (
    KEY_FILE,
    SETTINGS,
    KeyOperationRefused,
    TokenKeyring,
)
from backend.modules.export.token_vault import TokenVault

from tests.u6_approved_export import export_rows as rows

RUN = "u6-key-commands-test"
REPORT_FIELDS = {
    "command",
    "activeVersion",
    "generation",
    "retiredVersion",
    "resealed",
    "conflicts",
    "unopenable",
    "tokensUnderMissingVersions",
    "counts",
}


class Witness:
    def token_key_counts(self):
        return []


@pytest.fixture
def folder(tmp_path):
    root = tmp_path / "export-keys"
    root.mkdir(mode=0o700)
    return root


def local_ring(folder) -> TokenKeyring:
    """A keyring over an existing key file; its witness is never consulted then."""
    return TokenKeyring(folder, RUN, Witness())


def seal_into_realm(connect, folder) -> dict:
    """A first configure with a real sealed token, stored as the runtime role."""
    token = "synthetic-command-token-" + uuid4().hex
    with connect("export") as conn:
        connection, account, holder = rows.reserve(conn)
        binding = {"account_id": account, "connection_id": connection, "revision": 1}
        envelope, version = TokenVault(local_ring(folder)).seal(token, **binding)
        stored = conn.execute(
            "SELECT export.store_token_envelope(%s,%s,0,%s,%s,%s,'Synthetic Workspace',"
            "'synthetic-workspace','synthetic-bot',clock_timestamp()) AS revision",
            (account, connection, holder, envelope, version),
        ).fetchone()["revision"]
    assert stored == 1
    return {**binding, "token": token, "envelope": envelope, "version": version}


def opened(connect, sealed: dict) -> dict:
    with connect("export") as conn:
        return conn.execute(
            "SELECT * FROM export.open_token_envelope(%s,%s)",
            (sealed["account_id"], sealed["connection_id"]),
        ).fetchone()


def binding(sealed: dict) -> dict:
    return {key: sealed[key] for key in ("account_id", "connection_id", "revision")}


def assert_counts_only(report: dict, *sealed: dict) -> None:
    assert set(report) <= REPORT_FIELDS
    text = json.dumps(report)
    for item in sealed:
        for secret in (item["token"], str(item["connection_id"]), str(item["account_id"])):
            assert secret not in text
    assert all(type(n) is int for n in report["counts"].values())


def keyed_folder(operator, connect, folder) -> dict:
    """With a sealed token in the realm an empty folder is a loss: recover a key."""
    seed_realm(connect)
    report = key_commands.create_key_after_loss(folder, RUN, operator)
    assert report["tokensUnderMissingVersions"] >= 1
    return report


def seed_realm(connect) -> None:
    """At least one sealed token under a version no test folder holds."""
    with connect("export") as conn:
        rows.connected(conn)


def add_version_without_reseal(folder) -> str:
    with local_ring(folder).holding() as held:
        record = held.read()
        version = "u6-" + secrets.token_hex(16)
        record["keys"][version] = base64.b64encode(secrets.token_bytes(32)).decode()
        record["active"] = version
        record["generation"] += 1
        key_custody.write(SETTINGS, folder, record)
    return version


def test_commands_run_as_the_schema_owner_and_refuse_the_runtime_login(operator, connect, folder):
    seed_realm(connect)
    report = key_commands.key_counts(folder, RUN, operator)
    assert report["command"] == "key-counts" and report["counts"]
    assert operator.execute("SELECT current_user AS role").fetchone()["role"] == (
        "docsuri_export_owner"
    )
    runtime = connect("export")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        key_commands.key_counts(folder, RUN, runtime)


def test_create_key_after_loss_refuses_unless_the_state_is_loss(operator, connect, folder):
    created = keyed_folder(operator, connect, folder)
    assert created["generation"] == 1 and (folder / KEY_FILE).exists()
    with pytest.raises(KeyOperationRefused, match="not-a-loss"):
        key_commands.create_key_after_loss(folder, RUN, operator)
    (folder / KEY_FILE).chmod(0o644)  # broken custody is fixed, never replaced
    with pytest.raises(ProtectionUnavailable, match="key-custody-broken"):
        key_commands.create_key_after_loss(folder, RUN, operator)


def test_rotation_reseals_by_compare_and_set_and_reports_counts(
    operator, connect, folder, monkeypatch
):
    keyed_folder(operator, connect, folder)
    first, raced = seal_into_realm(connect, folder), seal_into_realm(connect, folder)
    old_version = first["version"]
    real_page = key_commands.OperatorStore.envelopes_for_reseal

    def racing_page(store, version, limit):
        page = real_page(store, version, limit)
        if version == old_version and not racing_page.done:
            racing_page.done = True  # a configure replaces this row while rotation runs
            with connect("export") as conn:
                assert rows.store(
                    conn, raced["account_id"], raced["connection_id"], 1, version=old_version
                ) == 2
        return page

    racing_page.done = False
    monkeypatch.setattr(key_commands.OperatorStore, "envelopes_for_reseal", racing_page)
    report = key_commands.rotate_key(folder, RUN, operator)
    assert_counts_only(report, first, raced)
    assert (report["resealed"], report["conflicts"], report["unopenable"]) == (1, 1, 0)
    assert report["counts"][old_version] == 1
    assert report["counts"][report["activeVersion"]] == 1
    resealed = opened(connect, first)
    assert (resealed["revision"], resealed["token_key_version"]) == (1, report["activeVersion"])
    assert TokenVault(local_ring(folder)).open(
        bytes(resealed["sealed_token"]), **binding(first)
    ) == first["token"]
    kept = opened(connect, raced)  # the concurrent replace was never overwritten
    assert kept["revision"] == 2 and kept["token_key_version"] == old_version


def test_rotation_with_three_versions_and_a_token_under_the_oldest_refuses(
    operator, connect, folder
):
    keyed_folder(operator, connect, folder)
    sealed = seal_into_realm(connect, folder)
    add_version_without_reseal(folder)
    add_version_without_reseal(folder)
    before = (folder / KEY_FILE).read_bytes()
    with pytest.raises(KeyOperationRefused) as refused:
        key_commands.rotate_key(folder, RUN, operator)
    assert refused.value.category == "oldest-version-in-use"
    assert refused.value.counts[sealed["version"]] == 1
    assert (folder / KEY_FILE).read_bytes() == before


def test_retirement_refuses_a_count_above_zero_and_the_active_version(
    operator, connect, folder
):
    keyed_folder(operator, connect, folder)
    sealed = seal_into_realm(connect, folder)
    active = add_version_without_reseal(folder)
    with pytest.raises(KeyOperationRefused) as refused:
        key_commands.retire_key(folder, RUN, operator, sealed["version"])
    assert refused.value.category == "version-in-use"
    assert refused.value.counts[sealed["version"]] == 1
    with pytest.raises(KeyOperationRefused, match="active-version"):
        key_commands.retire_key(folder, RUN, operator, active)
    with pytest.raises(KeyOperationRefused, match="version-invalid"):
        key_commands.retire_key(folder, RUN, operator, "u2-v1")
    rotation = key_commands.rotate_key(folder, RUN, operator)  # moves the token on
    assert rotation["resealed"] == 1
    report = key_commands.retire_key(folder, RUN, operator, sealed["version"])
    assert_counts_only(report, sealed)
    assert report["retiredVersion"] == sealed["version"]
    assert sealed["version"] not in local_ring(folder).load()["keys"]


def test_after_a_loss_rotation_skips_and_reports_tokens_under_the_missing_version(
    operator, connect, folder
):
    keyed_folder(operator, connect, folder)
    sealed = seal_into_realm(connect, folder)
    (folder / KEY_FILE).unlink()  # the marker stays: the table says loss
    created = key_commands.create_key_after_loss(folder, RUN, operator)
    assert_counts_only(created, sealed)
    assert created["counts"][sealed["version"]] == 1
    assert created["tokensUnderMissingVersions"] >= 1
    report = key_commands.rotate_key(folder, RUN, operator)
    assert_counts_only(report, sealed)
    assert report["counts"][sealed["version"]] == 1
    assert report["tokensUnderMissingVersions"] >= 1 and report["resealed"] == 0
    assert bytes(opened(connect, sealed)["sealed_token"]) == sealed["envelope"]


@pytest.mark.parametrize(
    "command",
    [
        lambda folder, conn: key_commands.key_counts(folder, RUN, conn),
        lambda folder, conn: key_commands.create_key_after_loss(folder, RUN, conn),
        lambda folder, conn: key_commands.rotate_key(folder, RUN, conn),
        lambda folder, conn: key_commands.retire_key(folder, RUN, conn, "u6-" + "a" * 32),
    ],
    ids=["key-counts", "create-key-after-loss", "rotate-key", "retire-key"],
)
def test_every_command_refuses_when_the_key_folder_check_fails(folder, command):
    class Untouched:
        """The folder check runs before anything touches the database."""

        def __getattr__(self, name):
            raise AssertionError(f"database touched: {name}")

    folder.chmod(0o750)
    try:
        with pytest.raises(ProtectionUnavailable, match="key-folder-unavailable"):
            command(folder, Untouched())
        assert list(folder.iterdir()) == []
    finally:
        folder.chmod(0o700)


def test_key_counts_output_holds_counts_only(operator, connect, folder):
    keyed_folder(operator, connect, folder)
    sealed = seal_into_realm(connect, folder)
    report = key_commands.key_counts(folder, RUN, operator)
    assert set(report) == {"command", "counts"}
    assert report["counts"][sealed["version"]] == 1
    assert_counts_only(report, sealed)
