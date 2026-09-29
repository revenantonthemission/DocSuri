import contextlib
import json
import os
import sys
from types import SimpleNamespace

import pytest

from docsuri_platform_integrity.adapters.postgres_tls import PostgresTarget
from docsuri_platform_integrity.contracts.codec import digest
from docsuri_platform_integrity.contracts.models import SubjectSnapshot
from docsuri_platform_integrity.host import (
    HostConfiguration,
    SecretReference,
    SubjectPolicy,
    require_role,
    validate_configuration,
)

ROOT = "/Library/Application Support/DocSuri/rem-1-test"
D = digest(b"fixture")


def configuration(**changes):
    secret = SecretReference(keychain=ROOT + "/keys/reader.keychain-db",
                             service="docsuri.test", account="reader")
    return HostConfiguration(**({
        "profile": "test", "role": "reader", "uid": 600, "gid": 600, "clock_uid": 608,
        "clock_frame": ROOT + "/state/clock/current.json", "clock_config_digest": D,
        "database": PostgresTarget(database="rem1_test", user="r1_reader", port=15439),
        "database_tls": secret, "server_tls": secret,
        "policies": (SubjectPolicy(snapshot=SubjectSnapshot(subject="one", artifact=D,
                        incarnation="i1", policy=D), slots=("schema",)),),
    } | changes))


def test_complete_reader_configuration_has_explicit_credential_handles():
    assert validate_configuration(configuration()).role == "reader"


@pytest.mark.parametrize("changes", [
    {"clock_frame": "/Library/Application Support/DocSuri/rem-1/state/clock/current.json"},
    {"clock_frame": ROOT + "/../clock.json"},
    {"database_tls": None}, {"server_tls": None}, {"policies": ()},
])
def test_incomplete_or_cross_profile_configuration_is_rejected(changes):
    with pytest.raises(ValueError):
        validate_configuration(configuration(**changes))


def test_role_guard_rejects_caller_even_with_valid_config():
    if os.getuid() == 600:
        pytest.skip("test must not execute under deployed reader")
    with pytest.raises(PermissionError):
        require_role(configuration())


def clock_configuration(**changes):
    return HostConfiguration(**({
        "profile": "test", "role": "clock", "uid": 608, "gid": 608, "clock_uid": 608,
        "clock_frame": ROOT + "/state/clock/current.json", "clock_config_digest": D,
        "chronyc": ROOT + "/toolchains/chrony/bin/chronyc", "chronyc_digest": D,
        "chrony_socket": ROOT + "/state/chrony/chrony.sock",
    } | changes))


def test_clock_role_requires_every_observer_handle():
    assert validate_configuration(clock_configuration()).role == "clock"
    for changes in ({"chronyc": None}, {"chronyc_digest": None}, {"chrony_socket": None}):
        with pytest.raises(ValueError, match="clock observer configuration missing"):
            validate_configuration(clock_configuration(**changes))


def test_short_chrony_socket_is_exact_and_profile_bound():
    socket = "/var/db/docsuri/rem1-test/clock/chronyd.sock"
    assert validate_configuration(clock_configuration(chrony_socket=socket)).chrony_socket == socket
    for candidate in ("/var/db/docsuri/rem1/clock/chronyd.sock", socket + ".other",
                      "/tmp/chronyd.sock"):
        with pytest.raises(ValueError):
            validate_configuration(clock_configuration(chrony_socket=candidate))
    with pytest.raises(ValueError):
        validate_configuration(clock_configuration(chrony_socket=socket, clock_frame=socket))


def test_reader_profile_may_not_cross_the_deployment_port_boundary():
    production = "/Library/Application Support/DocSuri/rem-1"
    secret = SecretReference(keychain=production + "/reader/keys/reader.keychain-db",
                             service="docsuri.production", account="reader")
    snapshot = SubjectSnapshot(subject="one", artifact=D, incarnation="i1", policy=D)
    with pytest.raises(ValueError, match="port crosses deployment profile"):
        validate_configuration(HostConfiguration(
            profile="production", role="reader", uid=600, gid=600, clock_uid=608,
            clock_frame=production + "/clock/state/current.json", clock_config_digest=D,
            database=PostgresTarget(database="rem1", user="r1_reader", port=15439),
            database_tls=secret, server_tls=secret,
            policies=(SubjectPolicy(snapshot=snapshot, slots=("schema",)),)))
    assert validate_configuration(HostConfiguration(
        profile="production", role="reader", uid=600, gid=600, clock_uid=608,
        clock_frame=production + "/clock/state/current.json", clock_config_digest=D,
        database=PostgresTarget(database="rem1", user="r1_reader", port=5432),
        database_tls=secret, server_tls=secret,
        policies=(SubjectPolicy(snapshot=snapshot, slots=("schema",)),))).role == "reader"


def test_duplicate_reader_subject_policies_are_rejected():
    policies = configuration().policies
    with pytest.raises(ValueError, match="unique reader subject policies required"):
        validate_configuration(configuration(policies=policies * 2))


def test_role_guard_accepts_only_the_exact_identity_and_group_set(monkeypatch):
    from docsuri_platform_integrity import host

    uid, gid = os.getuid(), os.getgid()
    config = configuration(uid=uid, gid=gid)
    monkeypatch.setattr(host, "kernel_groups", lambda: (gid,))
    require_role(config)
    monkeypatch.setattr(host, "kernel_groups", lambda: (gid, 12))
    with pytest.raises(PermissionError, match="role mismatch"):
        require_role(config)


def test_reader_assembly_binds_credential_handles_without_reading_them():
    from docsuri_platform_integrity import host
    from docsuri_platform_integrity.adapters.credentials import KeychainTLS
    from docsuri_platform_integrity.application.evidence import EvidenceService

    service = host.build_reader(configuration())
    assert isinstance(service, EvidenceService)
    provider = host.secret_provider(configuration(), configuration().server_tls)
    assert isinstance(provider, KeychainTLS)
    with pytest.raises(ValueError, match="reader configuration required"):
        host.build_reader(clock_configuration())


def test_clock_collection_requires_a_role_owned_publisher_directory(monkeypatch, tmp_path):
    from docsuri_platform_integrity import host

    uid, gid = os.getuid(), os.getgid()
    frame = tmp_path / "clock" / "current.json"
    frame.parent.mkdir(mode=0o700)
    base = {"uid": uid, "gid": gid, "clock_uid": uid, "clock_frame": str(frame),
            "chronyc": str(tmp_path / "chronyc"), "chronyc_digest": D,
            "chrony_socket": str(tmp_path / "chrony.sock")}
    published = []
    monkeypatch.setattr(host, "publish_frame", lambda path, value: published.append(value))

    class Failing:
        def __init__(self, *args, **kwargs):
            pass

        def collect(self):
            raise OSError("chrony unavailable")

    monkeypatch.setattr(host, "ChronyCollector", Failing)
    with pytest.raises(OSError):
        host.collect_clock(clock_configuration(**base))
    assert published == [None]

    frame.parent.chmod(0o770)
    with pytest.raises(PermissionError, match="publisher directory"):
        host.collect_clock(clock_configuration(**{**base, "clock_uid": uid + 1}))


def test_clock_observation_publishes_only_a_verified_sample(monkeypatch, tmp_path):
    from docsuri_platform_integrity import host

    uid, gid = os.getuid(), os.getgid()
    frame = tmp_path / "clock" / "current.json"
    frame.parent.mkdir(mode=0o700)
    published = []
    monkeypatch.setattr(host, "publish_frame", lambda path, value: published.append(value))

    class Sampling:
        def __init__(self, executable, executable_digest, socket, config_digest):
            self.arguments = (executable, executable_digest, socket, config_digest)

        def collect(self):
            return "verified-frame"

    monkeypatch.setattr(host, "ChronyCollector", Sampling)
    host.collect_clock(clock_configuration(uid=uid, gid=gid, clock_uid=uid, clock_frame=str(frame),
                                           chronyc=str(tmp_path / "chronyc"), chronyc_digest=D,
                                           chrony_socket=str(tmp_path / "chrony.sock")))
    assert published == ["verified-frame"]


def test_entry_point_fails_closed_on_config_mismatch(tmp_path, monkeypatch, capsys):
    from docsuri_platform_integrity import host
    from docsuri_platform_integrity.contracts.codec import canonical

    config = configuration()
    path = tmp_path / "reader.json"
    path.write_bytes(canonical(config.model_dump(mode="json")))
    monkeypatch.setattr(host, "protected_chain", lambda value: None)
    monkeypatch.setattr(host, "protected_bytes", lambda value, **kwargs: path.read_bytes())
    monkeypatch.setattr(sys, "argv", ["host", "clock", "--config", str(path)])
    assert host.main() == 2
    assert json.loads(capsys.readouterr().out) == {"state": "BLOCKED", "role": "clock",
                                                   "reason": "native_runtime_unavailable"}


def test_clock_entry_point_observes_through_the_role_guard(tmp_path, monkeypatch, capsys):
    from docsuri_platform_integrity import host
    from docsuri_platform_integrity.contracts.codec import canonical

    uid, gid = os.getuid(), os.getgid()
    config = clock_configuration(uid=uid, gid=gid, clock_uid=uid)
    path = tmp_path / "clock.json"
    path.write_bytes(canonical(config.model_dump(mode="json")))
    observed = []
    monkeypatch.setattr(host, "protected_chain", lambda value: None)
    monkeypatch.setattr(host, "protected_bytes", lambda value, **kwargs: path.read_bytes())
    monkeypatch.setattr(host, "kernel_groups", lambda: (gid,))
    monkeypatch.setattr(host, "collect_clock", lambda value: observed.append(value))
    monkeypatch.setattr(sys, "argv", ["host", "clock", "--config", str(path)])
    assert host.main() == 0
    assert json.loads(capsys.readouterr().out) == {"state": "OBSERVED", "role": "clock"}
    assert observed == [config]


def test_reader_entry_point_serves_materialized_server_credentials(tmp_path, monkeypatch, capsys):
    from docsuri_platform_integrity import host
    from docsuri_platform_integrity.api import server as server_module
    from docsuri_platform_integrity.contracts.codec import canonical

    uid, gid = os.getuid(), os.getgid()
    config = configuration(uid=uid, gid=gid)
    path = tmp_path / "reader.json"
    path.write_bytes(canonical(config.model_dump(mode="json")))
    served = {}

    class FakeTLS:
        def materialize(self):
            return contextlib.nullcontext(SimpleNamespace(certificate="cert", private_key="key",
                                                           ca="ca"))

    monkeypatch.setattr(host, "protected_chain", lambda value: None)
    monkeypatch.setattr(host, "protected_bytes", lambda value, **kwargs: path.read_bytes())
    monkeypatch.setattr(host, "kernel_groups", lambda: (gid,))
    monkeypatch.setattr(host, "secret_provider", lambda config, reference: FakeTLS())
    built = []
    monkeypatch.setattr(host, "build_reader", built.append)
    monkeypatch.setattr(server_module, "build_server",
                        lambda app, **kwargs: served.update(app=app, kwargs=kwargs)
                        or SimpleNamespace(run=lambda: served.update(ran=True)))
    monkeypatch.setattr(sys, "argv", ["host", "reader", "--config", str(path)])
    assert host.main() == 0
    assert built == [config]
    from fastapi import FastAPI

    assert isinstance(served["app"], FastAPI)
    assert served["kwargs"] == {"certificate": "cert", "private_key": "key", "ca": "ca",
                                "port": 18101}
    assert served["ran"] is True
