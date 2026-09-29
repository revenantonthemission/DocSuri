"""The issuer signs only what a readonly probe proved, and writes nothing when it cannot."""

import importlib.util
import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from docsuri_platform_integrity.deployment.receipt import host_identity

SCRIPT = Path(__file__).resolve().parents[1] / "platform-integrity" / "issue_receipt.py"
RELEASE = "r1-2026.09"
KEY_ID = "release-key-1"
# A restore that finished a moment ago, bound to this host and release.
DIGEST = "sha256:" + "a" * 64


def load_issuer():
    spec = importlib.util.spec_from_file_location("rem1_issue_receipt", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def signing_key(path: Path, *, mode=0o600, uid=None):
    key = Ed25519PrivateKey.generate()
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption())
    path.write_bytes(pem)
    os.chmod(path, mode)
    if uid is not None:
        os.chown(path, uid, -1)
    return key


def restore_receipt(path: Path, *, release=RELEASE, host=None):
    from docsuri_platform_integrity.contracts.codec import canonical

    moment = int(time.time() * 1_000_000)
    path.write_bytes(canonical({
        "host": host or host_identity(), "release": release,
        "source": {"target_id": "pg", "namespace": "r1", "incarnation": "1"},
        "restored": {"target_id": "pg", "namespace": "r1", "incarnation": "2"},
        "encrypted": True, "verified": True, "completed_utc_us": str(moment),
    }))
    return path


def run(*args, cwd=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, timeout=120,
        check=False, cwd=cwd)


def test_probe_only_never_reads_a_key_and_never_writes(tmp_path):
    config = tmp_path / "config.json"
    restore_receipt(tmp_path / "restore.json")
    config.write_text(json.dumps({"restoreReceipt": str(tmp_path / "restore.json")}))
    out = tmp_path / "receipts"
    result = run("--config", str(config), "--release", RELEASE, "--probe-only",
                 "--out", str(out), "--key", str(tmp_path / "absent.pem"),
                 "--key-id", KEY_ID)
    payload = json.loads(result.stdout)
    assert payload["state"] == "PROBED"
    # Reference-only diagnostics have no authenticated clock, so a restore may not be
    # claimed from them; the probe says so instead of falling back to wall time.
    assert payload["capabilities"]["restore_receipt"] == {
        "proven": False, "reason": "trusted_clock_required"}
    assert payload["capabilities"]["tls_roles"]["reason"] == "not_configured"
    assert not out.exists()


def test_issuance_requires_the_protected_profile(tmp_path):
    """The critical property: a partial run must not look like acceptance."""
    config = tmp_path / "config.json"
    config.write_text(json.dumps({}))
    signing_key(tmp_path / "key.pem")
    out = tmp_path / "receipts"
    result = run("--config", str(config), "--release", RELEASE, "--key", str(tmp_path / "key.pem"),
                 "--key-id", KEY_ID, "--out", str(out))
    payload = json.loads(result.stdout)
    assert result.returncode == 2
    assert payload == {"state": "BLOCKED", "reason": "protected_signing_required"}
    assert not out.exists(), "no receipt may be written when the run is refused"


def test_a_caller_configuration_cannot_replace_the_protected_policy(tmp_path):
    config = tmp_path / "config.json"
    restore_receipt(tmp_path / "restore.json")
    config.write_text(json.dumps({"restoreReceipt": str(tmp_path / "restore.json")}))
    result = run("--config", str(config), "--profile", "test", "--release", RELEASE)
    payload = json.loads(result.stdout)
    assert result.returncode == 2
    assert payload["reason"] == "protected_signing_required"
    assert not (tmp_path / "receipts").exists()


def test_issuance_without_a_profile_is_refused(tmp_path):
    config = tmp_path / "config.json"
    restore_receipt(tmp_path / "restore.json")
    config.write_text(json.dumps({"restoreReceipt": str(tmp_path / "restore.json")}))
    result = run("--config", str(config), "--release", RELEASE, "--out", str(tmp_path / "out"))
    assert result.returncode == 2
    assert json.loads(result.stdout)["reason"] == "protected_signing_required"


@pytest.mark.parametrize("argument", ["key", "key-id", "out"])
def test_legacy_signing_arguments_are_always_refused(tmp_path, argument):
    """A file-based signing path must not exist, whatever the caller supplies."""
    values = {"key": str(signing_key(tmp_path / "key.pem")),
              "key-id": KEY_ID, "out": str(tmp_path / "out")}
    result = run("--release", RELEASE, f"--{argument}", values[argument],
                 "--profile", "test")
    payload = json.loads(result.stdout)
    assert result.returncode == 2
    assert payload["reason"] == "protected_signing_required"
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("mode", [0o644, 0o640, 0o604, 0o777, 0o600])
def test_no_key_file_mode_can_reach_a_signature(tmp_path, mode):
    """Whatever a key file looks like, the protected path never reads it."""
    key = signing_key(tmp_path / "key.pem", mode=mode)
    result = run("--release", RELEASE, "--key", str(tmp_path / "key.pem"),
                 "--key-id", KEY_ID, "--out", str(tmp_path / "out"), "--profile", "test")
    assert result.returncode == 2
    assert json.loads(result.stdout)["reason"] == "protected_signing_required"
    assert key is not None
    assert not (tmp_path / "out").exists()


def test_a_symlinked_signing_key_is_refused(tmp_path):
    real = signing_key(tmp_path / "real.pem")
    link = tmp_path / "key.pem"
    link.symlink_to(tmp_path / "real.pem")
    result = run("--release", RELEASE, "--key", str(link), "--key-id", KEY_ID,
                 "--out", str(tmp_path / "out"))
    assert result.returncode == 2
    assert json.loads(result.stdout)["reason"] == "protected_signing_required"
    assert real is not None


def test_native_commit_guard_is_unproven_when_its_section_is_absent(tmp_path):
    config = tmp_path / "config.json"
    restore_receipt(tmp_path / "restore.json")
    config.write_text(json.dumps({"restoreReceipt": str(tmp_path / "restore.json")}))
    result = run("--config", str(config), "--release", RELEASE, "--probe-only",
                 "--capability", "native_commit_guard")
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["capabilities"]["native_commit_guard"] == {
        "proven": False, "reason": "not_configured"}


def test_a_receipt_for_another_release_is_not_proven(tmp_path):
    config = tmp_path / "config.json"
    restore_receipt(tmp_path / "restore.json", release="r1-2026.10")
    config.write_text(json.dumps({"restoreReceipt": str(tmp_path / "restore.json")}))
    result = run("--config", str(config), "--release", RELEASE, "--probe-only",
                 "--capability", "restore_receipt")
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["capabilities"]["restore_receipt"] == {
        "proven": False, "reason": "trusted_clock_required"}


def test_a_non_object_configuration_is_refused(tmp_path):
    config = tmp_path / "config.json"
    config.write_text(json.dumps(["nope"]))
    result = run("--config", str(config), "--release", RELEASE, "--probe-only")
    assert result.returncode == 2
    assert json.loads(result.stdout)["reason"] == "probe_configuration_unusable"


def test_a_non_canonical_configuration_is_refused(tmp_path):
    config = tmp_path / "config.json"
    config.write_text('{"restoreReceipt": "' + str(tmp_path / "restore.json") + '", }')
    result = run("--config", str(config), "--release", RELEASE, "--probe-only")
    assert result.returncode == 2
    assert json.loads(result.stdout)["reason"] == "probe_configuration_unusable"


def test_probe_only_writes_nothing_anywhere(tmp_path):
    """Diagnostics are readonly: no receipt, no temporary, no key material echoed."""
    config = tmp_path / "config.json"
    restore_receipt(tmp_path / "restore.json")
    config.write_text(json.dumps({"restoreReceipt": str(tmp_path / "restore.json")}))
    signing_key(tmp_path / "key.pem")
    out = tmp_path / "receipts"
    result = run("--config", str(config), "--release", RELEASE, "--probe-only",
                 "--key", str(tmp_path / "key.pem"), "--key-id", KEY_ID, "--out", str(out))
    assert result.returncode == 2
    assert json.loads(result.stdout)["state"] == "PROBED"
    assert not out.exists()
    assert "PRIVATE KEY" not in result.stdout and "PRIVATE KEY" not in result.stderr


def test_build_probe_set_rejects_a_malformed_section(tmp_path):
    """A wrong-typed section is a configuration error, never a silent default."""
    issuer = load_issuer()
    for document in ({"database": "not-an-object"}, {"keychainRoles": "nope"},
                     {"clock": 5}, {"keychainRoles": [{"keychain": "relative/path",
                                                        "service": "s", "account": "a"}]},
                     {"database": {"database": "rem1", "user": "r1_reader", "port": 5432}},
                     {"restoreReceipt": "relative/restore.json"}):
        with pytest.raises(ValueError):
            issuer.build_probe_set(document, release=RELEASE, host="H")


def test_build_probe_set_leaves_absent_sections_unconfigured():
    issuer = load_issuer()
    outcomes = issuer.build_probe_set({}, release=RELEASE, host="H").run()
    assert {o.reason for o in outcomes.values()} == {"not_configured"}


def test_the_probe_config_carries_no_secret_material(tmp_path):
    """Guard against a credential ever being pasted into the reference document."""
    config = tmp_path / "config.json"
    restore_receipt(tmp_path / "restore.json")
    config.write_text(json.dumps({
        "restoreReceipt": str(tmp_path / "restore.json"),
        "keychainRoles": [{"keychain": "/k", "service": "s", "account": "a"}],
        "database": {"database": "rem1", "user": "r1_reader", "port": 5432},
        "databaseTls": {"keychain": "/k", "service": "s", "account": "a",
                        "runtimeRoot": "/r"},
    }))
    issuer = load_issuer()
    probes = issuer.build_probe_set(
        json.loads(config.read_text()), release=RELEASE, host="H")
    assert probes.credentials is not None
    # The Keychain reference is a handle; the bundle is only ever read through the Keychain.
    assert probes.credentials.reference.service == "s"
    assert not hasattr(probes, "password")
    assert DIGEST  # sanity


# --- native commit guard: a live authority built from a digest-pinned plan -------------------

APPLY = "registry:apply"
STEP = "sha256:" + "b" * 64
PLAN = "sha256:" + "c" * 64


def frozen_plan(tmp_path, *, release=RELEASE, identities=None, mode=0o400):
    from docsuri_platform_integrity.contracts.codec import canonical, digest

    data = canonical({"release": release,
                      "identities": identities or {APPLY: STEP, "registry:adopt": PLAN}})
    path = tmp_path / "operator-plan.json"
    if path.exists():
        os.chmod(path, 0o600)
    path.write_bytes(data)
    os.chmod(path, mode)
    return path, digest(data)


def guard_section(tmp_path, *, plan_digest=None, purpose="apply", actor="operator",
                  target=None, user="r1_operator", identity=None, **overrides):
    if plan_digest is None:
        plan_path, plan_digest = frozen_plan(tmp_path)
    else:
        plan_path = tmp_path / "operator-plan.json"
    section = {
        "plan": str(plan_path), "planDigest": plan_digest,
        "operatorDatabase": {"database": "rem1", "user": user, "port": 15439},
        "operatorTls": {"keychain": "/abs/rem1-operator.keychain", "service": "docsuri",
                        "account": "operator", "runtimeRoot": "/var/empty"},
        # The approval and fence are validated directly against the models, so their fields
        # use the models' own snake_case names.
        "approval": {"approval_id": "approval-1", "actor": actor, "purpose": purpose,
                     "target": target or {"target_id": "pg", "namespace": "public",
                                          "incarnation": "i1"},
                     "plan": plan_digest, "artifact": PLAN, "policy": PLAN,
                     "validity": {"valid_from": "0", "valid_until": "1800000000"},
                     "authority_revision": "1"},
        "fence": {"target": target or {"target_id": "pg", "namespace": "public",
                                       "incarnation": "i1"},
                  "epoch": "1", "holder": "attempt-1",
                  "validity": {"valid_from": "0", "valid_until": "1800000000"}},
        "deadlineSeconds": 30,
    }
    if identity is not None:
        section["identity"] = identity
    section.update(overrides)
    return section


def test_guard_authority_is_built_from_a_pinned_plan_and_derived_role(tmp_path):
    issuer = load_issuer()
    plan_path, plan_digest = frozen_plan(tmp_path)
    section = guard_section(tmp_path, plan_digest=plan_digest)
    # A clock is mandatory: the adapter allows no wall-clock or database-time fallback.
    session = issuer.build_guard_authority(
        section, release=RELEASE, clock_frame=object(), clock_uid=0,
        clock_config_digest=STEP, clock_kwargs={})
    assert session.definition_digest == STEP
    # The identity follows the approval's declared purpose, not sort order.
    assert session.identity == APPLY
    # The role comes from the operator target, not from anything the document can say.
    assert session.authority.actor_role == "r1_operator"
    assert session.authority.definitions == {APPLY: STEP, "registry:adopt": PLAN}
    assert session.authority.binding.plan == plan_digest
    assert plan_path.exists()


def test_guard_role_is_taken_from_the_operator_target_not_the_document(tmp_path):
    issuer = load_issuer()
    section = guard_section(tmp_path, user="r1_operator")
    section["actorRole"] = "r1_reader"
    with pytest.raises(ValueError, match="exactly"):
        issuer.build_guard_authority(section, release=RELEASE, clock_frame=object(),
                                     clock_uid=0, clock_config_digest=STEP, clock_kwargs={})


def test_guard_approval_must_name_the_pinned_plan(tmp_path):
    issuer = load_issuer()
    section = guard_section(tmp_path)
    section["approval"]["plan"] = "sha256:" + "d" * 64
    with pytest.raises(ValueError, match="does not name the pinned"):
        issuer.build_guard_authority(section, release=RELEASE, clock_frame=object(),
                                     clock_uid=0, clock_config_digest=STEP, clock_kwargs={})


def test_guard_plan_substitution_is_refused_before_use(tmp_path):
    issuer = load_issuer()
    plan_path, plan_digest = frozen_plan(tmp_path)
    section = guard_section(tmp_path, plan_digest=plan_digest)
    # Rewrite the pinned file with a different plan: the digest no longer matches.
    frozen_plan(tmp_path, identities={APPLY: PLAN})
    with pytest.raises(PermissionError, match="digest does not match"):
        issuer.build_guard_authority(section, release=RELEASE, clock_frame=object(),
                                     clock_uid=0, clock_config_digest=STEP, clock_kwargs={})


def test_guard_purpose_must_match_the_planned_identity(tmp_path):
    issuer = load_issuer()
    # registry:adopt is the only identity whose purpose is "adopt".
    section = guard_section(tmp_path, identity="registry:adopt", purpose="apply")
    with pytest.raises(ValueError, match="purpose does not match"):
        issuer.build_guard_authority(section, release=RELEASE, clock_frame=object(),
                                     clock_uid=0, clock_config_digest=STEP, clock_kwargs={})
    section = guard_section(tmp_path, identity="registry:adopt", purpose="adopt")
    assert issuer.build_guard_authority(
        section, release=RELEASE, clock_frame=object(), clock_uid=0,
        clock_config_digest=STEP, clock_kwargs={}).definition_digest == PLAN


def test_guard_identity_must_exist_in_the_plan(tmp_path):
    issuer = load_issuer()
    section = guard_section(tmp_path, identity="registry:absent")
    with pytest.raises(ValueError, match="not in the frozen plan"):
        issuer.build_guard_authority(section, release=RELEASE, clock_frame=object(),
                                     clock_uid=0, clock_config_digest=STEP, clock_kwargs={})


def test_guard_requires_the_authenticated_clock(tmp_path):
    issuer = load_issuer()
    section = guard_section(tmp_path)
    with pytest.raises(ValueError, match="authenticated clock is required"):
        issuer.build_guard_authority(section, release=RELEASE, clock_frame=None, clock_uid=None,
                                     clock_config_digest=None, clock_kwargs={})


def test_guard_deadline_is_bounded(tmp_path):
    issuer = load_issuer()
    for seconds in (0, -1, 301, True, "30"):
        section = guard_section(tmp_path, deadlineSeconds=seconds)
        with pytest.raises(ValueError, match="deadlineSeconds"):
            issuer.build_guard_authority(section, release=RELEASE, clock_frame=object(),
                                         clock_uid=0, clock_config_digest=STEP,
                                         clock_kwargs={})


def test_guard_approval_and_fence_must_name_the_same_target(tmp_path):
    issuer = load_issuer()
    section = guard_section(tmp_path)
    section["fence"]["target"] = {"target_id": "other", "namespace": "public",
                                  "incarnation": "i1"}
    with pytest.raises(ValueError, match="different targets"):
        issuer.build_guard_authority(section, release=RELEASE, clock_frame=object(),
                                     clock_uid=0, clock_config_digest=STEP, clock_kwargs={})


def test_declared_but_unusable_guard_reports_its_reason_and_others_still_run(tmp_path):
    """One broken section must not hide the status of the other four capabilities."""
    config = tmp_path / "config.json"
    restore_receipt(tmp_path / "restore.json")
    section = guard_section(tmp_path, deadlineSeconds=9999)
    config.write_text(json.dumps({"restoreReceipt": str(tmp_path / "restore.json"),
                                  "nativeCommitGuard": section}))
    result = run("--config", str(config), "--release", RELEASE, "--probe-only")
    payload = json.loads(result.stdout)
    assert payload["capabilities"]["native_commit_guard"] == {
        "proven": False, "reason": "guard_configuration_unusable"}
    # The restore probe still ran and still reported its own truth.
    assert payload["capabilities"]["restore_receipt"] == {
        "proven": False, "reason": "trusted_clock_required"}
    assert result.returncode == 2


def test_guard_section_without_a_clock_section_is_unusable(tmp_path):
    config = tmp_path / "config.json"
    restore_receipt(tmp_path / "restore.json")
    config.write_text(json.dumps({"restoreReceipt": str(tmp_path / "restore.json"),
                                  "nativeCommitGuard": guard_section(tmp_path)}))
    result = run("--config", str(config), "--release", RELEASE, "--probe-only")
    payload = json.loads(result.stdout)
    assert payload["capabilities"]["native_commit_guard"]["reason"] == \
        "guard_configuration_unusable"


def test_wrong_typed_guard_section_fails_closed_rather_than_crashing(tmp_path):
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"nativeCommitGuard": ["not", "an", "object"]}))
    result = run("--config", str(config), "--release", RELEASE, "--probe-only")
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert {key: payload[key] for key in ("state", "reason")} == {
        "state": "BLOCKED", "reason": "probe_configuration_unusable"}
    assert payload["stage"] == "probe"
    assert payload["errorType"] == "ValueError"


def test_a_keychain_password_must_be_one_bounded_line():
    """The password is read once from stdin, never from argv or the environment."""
    issuer = load_issuer()
    assert issuer.read_password(False) is None
    monkey = pytest.MonkeyPatch()
    try:
        monkey.setattr(sys, "stdin", io.StringIO("correct horse battery\n"))
        assert issuer.read_password(True) == "correct horse battery"
        for bad in ("short\n", "no newline", "\n", "x" * 1025 + "\n"):
            monkey.setattr(sys, "stdin", io.StringIO(bad))
            with pytest.raises(ValueError, match="12..1024 byte line"):
                issuer.read_password(True)
    finally:
        monkey.undo()


def test_issuance_unlocks_the_purpose_keychain_for_one_call_and_locks_it_again():
    """Provisioning leaves the Keychain locked; issuance holds it open only while signing."""
    issuer = load_issuer()
    events = []

    class FakeKeychain:
        def unlock(self, path, password, *, owner=None):
            events.append(("unlock", str(path), password, owner))

        def lock(self, path, *, owner=None):
            events.append(("lock", str(path), owner))

    class Policy:
        signer = type("Signer", (), {"keychain": "/realm/sign/r1.keychain-db", "uid": 612})

    snapshot = type("Snapshot", (), {"policy": Policy})
    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setattr(issuer, "NativeKeychain", FakeKeychain)
        with pytest.raises(RuntimeError, match="boom"):
            with issuer.unlocked_keychain(snapshot, "s3cret"):
                events.append("signing")
                raise RuntimeError("boom")
        assert events == [
            ("unlock", "/realm/sign/r1.keychain-db", "s3cret", 612),
            "signing",
            ("lock", "/realm/sign/r1.keychain-db", 612),
        ]
        events.clear()
        with issuer.unlocked_keychain(snapshot, None):
            events.append("signing")
        # No password means the caller already holds it open; the issuer must not touch it.
        assert events == ["signing"]
    finally:
        monkeypatch.undo()


# -- a refusal must be actionable -----------------------------------------


def test_a_refusal_reports_the_failing_path_and_error(tmp_path):
    """An operator cannot fix an opaque refusal.

    A PermissionError while signing is the difference between "this role may not read the clock
    frame" and "the keychain is still locked", and those need different fixes. The report must
    therefore carry the error text and, for an OSError, the path that could not be used.
    """
    config = tmp_path / "config.json"
    config.write_text('{"restoreReceipt": "' + str(tmp_path / "restore.json") + '", }')
    result = run("--config", str(config), "--release", RELEASE, "--probe-only")
    assert result.returncode == 2
    report = json.loads(result.stdout)
    assert report["state"] == "BLOCKED"
    assert "detail" in report, "refusal must explain itself"
    assert report["detail"]
    # A traceback is opt-in: useful while diagnosing, noise in an accepted report.
    assert "traceback" not in report


def test_debug_adds_a_traceback_for_diagnosis(tmp_path):
    config = tmp_path / "config.json"
    config.write_text('{"restoreReceipt": "' + str(tmp_path / "restore.json") + '", }')
    result = run("--config", str(config), "--release", RELEASE, "--probe-only", "--debug")
    report = json.loads(result.stdout)
    assert report["state"] == "BLOCKED"
    assert "Traceback" in report["traceback"]


def test_a_refusal_does_not_leak_key_or_password_material(tmp_path):
    """The detail field must never become an accidental secret channel."""
    config = tmp_path / "config.json"
    secret = "hunter2-not-a-real-password"
    config.write_text(json.dumps({"restoreReceipt": str(tmp_path / "restore.json"),
                                  "note": secret}))
    result = run("--config", str(config), "--release", RELEASE, "--probe-only", "--debug")
    report = json.loads(result.stdout)
    assert secret not in json.dumps(report)
