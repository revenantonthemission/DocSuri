import os
import socket
import sys

import pytest
from fastapi.testclient import TestClient

from docsuri_platform_integrity.adapters.authority import (
    CurrentReadAuthority,
    ReadGrant,
    check_binding,
)
from docsuri_platform_integrity.adapters.clock import (
    ClockSample,
    ClockUnavailable,
    unavailable_clock,
)
from docsuri_platform_integrity.adapters.keychain import peer_identity
from docsuri_platform_integrity.api.app import create_app
from docsuri_platform_integrity.application.evidence import EvidenceService, ImmutableByteCache
from docsuri_platform_integrity.contracts.codec import digest
from docsuri_platform_integrity.contracts.models import ApprovalBinding, TargetRef, ValidityWindow


class Reader:
    calls = 0

    def healthy(self):
        return True

    def snapshot(self, subject):
        self.calls += 1
        return (), ()


def test_clock_boundaries_and_resume_invalidation():
    sample = ClockSample(100_000_000, 0, 100, 1.0, "boot", "resume", True)
    assert sample.window(continuous_ns=0, boot_id="boot", resume_id="resume") == (
        99_999_900,
        100_000_100,
    )
    with pytest.raises(ClockUnavailable):
        sample.window(continuous_ns=30_000_000_000, boot_id="boot", resume_id="resume")
    with pytest.raises(ClockUnavailable):
        sample.window(continuous_ns=1, boot_id="boot", resume_id="new-resume")


def test_current_read_grant_is_not_cached():
    grants = {"cert": ReadGrant("cert", frozenset({"one"}), 200)}
    authority = CurrentReadAuthority(grants.get, lambda: (100, 100))
    assert authority.permits("cert", "one")
    assert not authority.permits("cert", "two")
    grants.clear()
    assert not authority.permits("cert", "one")


@pytest.mark.parametrize("window", [(-1, -1), (101, 100), (True, True), (100.0, 101.0)])
def test_read_grant_rejects_invalid_clock_window(window):
    authority = CurrentReadAuthority(lambda _: ReadGrant("cert", frozenset({"one"}), 200),
                                     lambda: window)
    assert not authority.permits("cert", "one")


@pytest.mark.parametrize("revoked", [None, 0])
def test_mutation_binding_requires_explicit_not_revoked(revoked):
    d = digest(b"fixture")
    target = TargetRef(target_id="db", namespace="public", incarnation="test")
    binding = ApprovalBinding(approval_id="grant", actor="operator", purpose="apply",
                              target=target, plan=d, artifact=d, policy=d,
                              validity=ValidityWindow(valid_from="0", valid_until="200"),
                              authority_revision="1")
    with pytest.raises(PermissionError):
        check_binding(binding, target=target, plan=d, artifact=d, policy=d, revision="1",
                      lower=100, upper=100, revoked=revoked, purpose="apply")


def test_readonly_api_does_not_trust_headers_or_fake_health():
    reader = Reader()
    authority = CurrentReadAuthority(lambda _: None, unavailable_clock)
    app = create_app(EvidenceService(reader, authority, unavailable_clock, {}))
    # The daemon serves loopback only; probe it the way the TLS transport reaches it.
    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        assert client.get("/healthz").json() == {"alive": True}
        assert client.get("/readyz").status_code == 503
        assert (
            client.get(
                "/internal/v1/evidence/private", headers={"X-Client-Cert": "cert"}
            ).status_code
            == 401
        )
        assert reader.calls == 0
        assert client.post("/internal/v1/evidence/private", content="x").status_code == 400


def test_readonly_api_rejects_non_loopback_peers():
    reader = Reader()
    authority = CurrentReadAuthority(lambda _: None, unavailable_clock)
    app = create_app(EvidenceService(reader, authority, unavailable_clock, {}))
    with TestClient(app, client=("203.0.113.7", 50000)) as client:
        # Indistinguishable from an unknown route, so existence is not confirmed off-host.
        assert client.get("/healthz").status_code == 404
        assert client.get("/internal/v1/evidence/private").status_code == 404
        assert client.get("/internal/v1/evidence/private").json() == {"reason": "not_found"}
        assert reader.calls == 0


def test_immutable_cache_has_a_byte_budget():
    cache = ImmutableByteCache(limit=1024)
    for i in range(100):
        cache.put(digest(str(i).encode()), b"x" * 100)
        assert cache.size <= 1024
    with pytest.raises(ValueError):
        cache.put("current-grant", b"yes")


@pytest.mark.skipif(sys.platform != "darwin", reason="native macOS capability")
def test_native_peer_is_kernel_identity():
    left, right = socket.socketpair()
    try:
        assert peer_identity(left) == (os.getuid(), os.getgid())
    finally:
        left.close()
        right.close()


def test_database_read_authority_rejects_unbound_identity_before_any_query():
    """Malformed fingerprints and subjects must never reach the control connection."""
    from contextlib import contextmanager

    from docsuri_platform_integrity.adapters.read_authority import PostgresReadAuthority

    @contextmanager
    def unreachable():
        raise AssertionError("control connection must not be opened")

    authority = PostgresReadAuthority(unreachable, lambda: (0, 0))
    for fingerprint, subject in ((None, "subject"), ("A" * 64, "subject"), ("a" * 63, "subject"),
                                 ("a" * 64, None), ("a" * 64, "bad subject"),
                                 ("a" * 64, "x" * 201), (123, "subject")):
        assert authority.permits(fingerprint, subject) is False


def test_database_read_authority_fails_closed_on_query_and_clock_errors():
    from docsuri_platform_integrity.adapters.read_authority import PostgresReadAuthority

    class Row:
        def __init__(self, values):
            self.values = values

        def __getitem__(self, index):
            return self.values[index]

    class Connection:
        def __init__(self, row=None, error=None):
            self.row, self.error = row, error

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, query, params):
            assert "reader_grants" in query and params[1] == "subject"
            if self.error:
                raise self.error
            return self

        def fetchone(self):
            return self.row

    fingerprint = "a" * 64
    assert PostgresReadAuthority(lambda: Connection(Row((10, 20, False))),
                                lambda: (15, 15)).permits(fingerprint, "subject") is True
    def denies(row, clock):
        return PostgresReadAuthority(lambda: Connection(row), clock).permits(
            fingerprint, "subject") is False

    assert denies(Row((10, 20, True)), lambda: (15, 15)) is True        # revoked
    assert denies(Row((10, 20, False)), lambda: (25, 25)) is True       # outside window
    assert denies(Row((10, 20, False)), lambda: ("15", 15)) is True     # non-integer clock
    assert denies(None, lambda: (15, 15)) is True                       # absent grant
    assert PostgresReadAuthority(lambda: Connection(error=OSError("control unavailable")),
                                lambda: (15, 15)).permits(fingerprint, "subject") is False
