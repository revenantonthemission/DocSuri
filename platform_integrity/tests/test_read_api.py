"""R1C read surface: authentication, readiness depth, compatibility, and response bounds."""

import pytest
from fastapi.testclient import TestClient

from docsuri_platform_integrity.adapters.authority import CurrentReadAuthority, ReadGrant
from docsuri_platform_integrity.adapters.breaker import DependencyUnavailable
from docsuri_platform_integrity.api.app import MAX_RESPONSE_ITEMS, create_app
from docsuri_platform_integrity.application.evidence import EvidenceService
from docsuri_platform_integrity.contracts.codec import canonical, digest
from docsuri_platform_integrity.contracts.models import (
    CompatibilityManifest,
    GateVerdict,
    SubjectSnapshot,
)
from docsuri_platform_integrity.domain.compatibility import (
    CompatibilityPolicy,
    RuntimeObservation,
)

FINGERPRINT = "a" * 64
OTHER_FINGERPRINT = "b" * 64
SUBJECT = "repo/one"
D = digest(b"fixture")
LOOPBACK = ("127.0.0.1", 50000)


def window():
    return (100, 100)


def snapshot(subject=SUBJECT):
    return SubjectSnapshot(
        subject=subject,
        artifact=D,
        incarnation="incarnation-one",
        policy=D,
    )


class Reader:
    def __init__(self, heads=(), evidence=(), healthy=True):
        self._heads = tuple(heads)
        self._evidence = tuple(evidence)
        self._healthy = healthy
        self.calls = 0

    def healthy(self):
        return self._healthy

    def snapshot(self, subject):
        self.calls += 1
        return self._heads, self._evidence


def service(*, grants=None, reader=None, compatibility=None, policies=None):
    lookup = (grants or {}).get
    return EvidenceService(
        reader if reader is not None else Reader(),
        CurrentReadAuthority(lookup, window),
        window,
        policies if policies is not None else {SUBJECT: (snapshot(), ())},
        compatibility=compatibility,
    )


def client_for(svc, fingerprint=FINGERPRINT):
    app = create_app(svc)
    return TestClient(app, client=LOOPBACK)


def authed(fingerprint=FINGERPRINT):
    return {"X-Client-Cert": fingerprint}


def transport_client(svc, fingerprint=FINGERPRINT):
    """A client that presents the identity the TLS transport would have injected."""
    app = create_app(svc)

    @app.middleware("http")
    async def _identity(request, call_next):
        request.scope["client_certificate_fingerprint"] = fingerprint
        return await call_next(request)

    return TestClient(app, client=LOOPBACK)


def test_unauthenticated_internal_read_is_401_and_touches_nothing():
    reader = Reader()
    svc = service(reader=reader)
    with client_for(svc) as client:
        response = client.get(f"/internal/v1/evidence/{SUBJECT}")
        assert response.status_code == 401
        assert response.json() == {"reason": "unauthenticated"}
        assert reader.calls == 0


def test_only_the_transport_injected_identity_is_accepted():
    """A caller cannot assert its own identity with a header of any name."""
    svc = service(grants={FINGERPRINT: ReadGrant(FINGERPRINT, frozenset({SUBJECT}), 200)})
    with client_for(svc) as client:
        for header in ("X-Client-Cert", "X-SSL-Client-Cert", "X-Forwarded-Client-Cert"):
            response = client.get(f"/internal/v1/evidence/{SUBJECT}", headers={header: FINGERPRINT})
            assert response.status_code == 401
        assert client.get(
            f"/internal/v1/evidence/{SUBJECT}", params={"fingerprint": FINGERPRINT}
        ).status_code == 401


def test_malformed_injected_identity_is_refused():
    svc = service(grants={FINGERPRINT: ReadGrant(FINGERPRINT, frozenset({SUBJECT}), 200)})
    for bad in ("", "A" * 64, "a" * 63, "a" * 65, "g" * 64, 1, None, ["a" * 64]):
        with transport_client(svc, fingerprint=bad) as client:
            assert client.get(f"/internal/v1/evidence/{SUBJECT}").status_code == 401


def test_granted_caller_reads_and_denied_caller_is_indistinguishable_from_absent():
    grants = {FINGERPRINT: ReadGrant(FINGERPRINT, frozenset({SUBJECT}), 200)}
    svc = service(grants=grants)
    with transport_client(svc) as client:
        allowed = client.get(f"/internal/v1/evidence/{SUBJECT}")
        assert allowed.status_code == 200
        assert allowed.json()["verdict"]
        denied = client.get("/internal/v1/evidence/repo/absent")
        assert denied.status_code == 404
        assert denied.json() == {"reason": "not_found"}
    with transport_client(svc, fingerprint=OTHER_FINGERPRINT) as client:
        ungranted = client.get(f"/internal/v1/evidence/{SUBJECT}")
        assert ungranted.status_code == 404
        assert ungranted.json() == {"reason": "not_found"}


def test_health_stays_reachable_without_a_certificate_and_reveals_no_subject():
    svc = service(reader=Reader())
    with client_for(svc) as client:
        assert client.get("/healthz").json() == {"alive": True}
        assert client.get("/readyz").json()["subjectEligible"] is False


def test_readiness_reports_shallow_deep_and_subject_separately():
    svc = service(grants={FINGERPRINT: ReadGrant(FINGERPRINT, frozenset({SUBJECT}), 200)})
    with transport_client(svc) as client:
        ready = client.get("/readyz")
        assert ready.status_code == 200
        # No subject asked for, so there is nothing to be ineligible for.
        assert ready.json() == {
            "shallow": True,
            "deep": True,
            "subjectEligible": False,
            "reasons": [],
        }
        permitted = client.get("/readyz", params={"subject": SUBJECT})
        assert permitted.json()["subjectEligible"] is True
        other = client.get("/readyz", params={"subject": "repo/absent"})
        assert other.status_code == 200
        assert other.json()["subjectEligible"] is False


def test_readiness_is_not_ready_without_a_working_clock_or_policies():
    with client_for(service(policies={})) as client:
        state = client.get("/readyz")
        assert state.status_code == 503
        assert state.json()["shallow"] is True
        assert state.json()["deep"] is False
        assert "no_policies" in state.json()["reasons"]


def test_readiness_is_not_ready_when_the_observation_cannot_be_taken():
    class Broken(Reader):
        def snapshot(self, subject):
            raise OSError("reader unavailable")

    svc = service(reader=Broken())
    with transport_client(svc) as client:
        state = client.get("/readyz")
        assert state.status_code == 503
        assert state.json()["deep"] is False
        assert "deep_observation_unavailable" in state.json()["reasons"]


def manifest():
    return CompatibilityManifest(
        artifact=D,
        registry=D,
        generation=D,
        operations=("read",),
        required_capabilities=("read",),
    )


def policy():
    return CompatibilityPolicy(
        manifest_digests=frozenset({digest(b"manifest")}),
        writer_epoch="epoch",
        schema_versions=(("evidence", "1"),),
        role_artifacts=(("r1c", D),),
        config_digest=D,
    )


def observation(**overrides):
    values = dict(
        artifact=D,
        registry=D,
        generation=D,
        operations=frozenset({"read"}),
        capabilities=frozenset({"read"}),
        writer_epoch="epoch",
        schema_versions=(("evidence", "1"),),
        role_artifacts=(("r1c", D),),
        config_digest=D,
    )
    values.update(overrides)
    return RuntimeObservation(**values)


UNSET = object()


def compatibility_source(*, observed=UNSET, manifest_value=UNSET, policy_value=UNSET):
    def source(release):
        return (
            manifest() if manifest_value is UNSET else manifest_value,
            policy() if policy_value is UNSET else policy_value,
            observation() if observed is UNSET else observed,
        )

    return source


def policy_for(manifest_value=UNSET):
    """A policy that trusts exactly this manifest, the way the owner pins a release."""
    trusted = manifest() if manifest_value is UNSET else manifest_value
    base = policy()
    return CompatibilityPolicy(
        manifest_digests=frozenset({digest(canonical(trusted.model_dump(mode="json")))}),
        writer_epoch=base.writer_epoch,
        schema_versions=base.schema_versions,
        role_artifacts=base.role_artifacts,
        config_digest=base.config_digest,
    )


def test_compatibility_reports_exact_release_agreement():
    svc = service(
        grants={FINGERPRINT: ReadGrant(FINGERPRINT, frozenset({"release-1"}), 200)},
        compatibility=compatibility_source(policy_value=policy_for()),
    )
    with transport_client(svc) as client:
        result = client.get("/internal/v1/compatibility/release-1")
        assert result.status_code == 200
        assert result.json() == {
            "release": "release-1", "verdict": "ELIGIBLE", "reasons": [],
        }


@pytest.mark.parametrize(
    "overrides,expected,reason",
    [
        ({"writer_epoch": "other"}, GateVerdict.BLOCKED, "unsupported_writer_epoch"),
        (
            {"schema_versions": (("evidence", "2"),)},
            GateVerdict.BLOCKED,
            "unsupported_schema_versions",
        ),
        ({"operations": frozenset()}, GateVerdict.BLOCKED, "unsupported_operations"),
        ({"capabilities": frozenset()}, GateVerdict.BLOCKED, "missing_capabilities"),
        ({"config_digest": digest(b"other")}, GateVerdict.STALE, "runtime_binding_changed"),
    ],
)
def test_compatibility_distinguishes_blocked_stale_and_missing(overrides, expected, reason):
    svc = service(
        grants={FINGERPRINT: ReadGrant(FINGERPRINT, frozenset({"release-1"}), 200)},
        compatibility=compatibility_source(
            observed=observation(**overrides), policy_value=policy_for()
        ),
    )
    with transport_client(svc) as client:
        result = client.get("/internal/v1/compatibility/release-1")
        assert result.status_code == 200
        assert result.json()["verdict"] == expected
        assert reason in result.json()["reasons"]


def test_an_unpinned_manifest_is_blocked_before_any_runtime_comparison():
    svc = service(
        grants={FINGERPRINT: ReadGrant(FINGERPRINT, frozenset({"release-1"}), 200)},
        compatibility=compatibility_source(),
    )
    with transport_client(svc) as client:
        result = client.get("/internal/v1/compatibility/release-1")
        assert result.json() == {
            "release": "release-1",
            "verdict": GateVerdict.BLOCKED,
            "reasons": ["unsupported_manifest"],
        }


def test_compatibility_without_an_observation_is_incomplete_not_eligible():
    svc = service(
        grants={FINGERPRINT: ReadGrant(FINGERPRINT, frozenset({"release-1"}), 200)},
        compatibility=compatibility_source(observed=None, policy_value=policy_for()),
    )
    with transport_client(svc) as client:
        result = client.get("/internal/v1/compatibility/release-1")
        assert result.json()["verdict"] == GateVerdict.INCOMPLETE


def test_compatibility_never_grants_a_release_to_an_unpermitted_caller():
    svc = service(compatibility=compatibility_source())
    with transport_client(svc) as client:
        assert client.get("/internal/v1/compatibility/release-1").status_code == 404
    unprovisioned = service()
    with transport_client(unprovisioned) as client:
        # No compatibility source provisioned: unavailable, never a permissive default.
        assert client.get("/internal/v1/compatibility/release-1").status_code == 503


def test_response_item_cap_cannot_be_sidestepped():
    from docsuri_platform_integrity.contracts.models import GateEvaluation

    over_cap = GateEvaluation(
        verdict=GateVerdict.ELIGIBLE,
        reasons=(),
        evidence_ids=tuple(f"e{i}" for i in range(MAX_RESPONSE_ITEMS + 1)),
    )

    class Flood(EvidenceService):
        def read(self, fingerprint, subject):
            return over_cap

    svc = Flood(Reader(), CurrentReadAuthority(lambda _: None, window), window, {})
    with transport_client(svc) as client:
        response = client.get(f"/internal/v1/evidence/{SUBJECT}")
        assert response.status_code == 503
        assert response.json() == {"reason": "response_limit"}


def test_breaker_trips_after_three_failures_and_does_not_serve_stale_reads():
    class Flaky(Reader):
        def __init__(self):
            super().__init__()
            self.fail = True

        def snapshot(self, subject):
            self.calls += 1
            if self.fail:
                raise OSError("dependency down")
            return (), ()

    reader = Flaky()
    svc = service(
        reader=reader, grants={FINGERPRINT: ReadGrant(FINGERPRINT, frozenset({SUBJECT}), 200)}
    )
    with transport_client(svc) as client:
        for _ in range(3):
            assert client.get(f"/internal/v1/evidence/{SUBJECT}").status_code == 503
        reader.fail = False
        opened = client.get(f"/internal/v1/evidence/{SUBJECT}")
        assert opened.status_code == 503
        assert opened.json() == {"reason": "evidence_unavailable"}
        assert reader.calls == 3, "an open breaker must not call the dependency"


def test_evidence_reads_never_mutate_the_dependency():
    reader = Reader()
    grants = {FINGERPRINT: ReadGrant(FINGERPRINT, frozenset({SUBJECT}), 200)}
    svc = service(reader=reader, grants=grants)
    with transport_client(svc) as client:
        assert client.get(f"/internal/v1/evidence/{SUBJECT}").status_code == 200
        assert client.get("/internal/v1/compatibility/release-1").status_code in (404, 503)
        assert client.get("/readyz").status_code == 200
        assert set(grants) == {FINGERPRINT}


def test_oversized_and_malformed_content_length_are_refused():
    svc = service()
    with client_for(svc) as client:
        big = client.get(
            f"/internal/v1/evidence/{SUBJECT}", headers={"content-length": str(10**9)}
        )
        assert big.status_code == 413
        assert client.get(
            f"/internal/v1/evidence/{SUBJECT}", headers={"content-length": "abc"}
        ).status_code == 413
        assert client.get(
            f"/internal/v1/evidence/{SUBJECT}", headers={"transfer-encoding": "chunked"}
        ).status_code == 400


def test_dependency_unavailable_is_not_leaked_as_an_internal_error():
    class Broken(EvidenceService):
        def compatibility(self, fingerprint, release):
            raise DependencyUnavailable("internal detail")

    svc = Broken(Reader(), CurrentReadAuthority(lambda _: None, window), window, {})
    with transport_client(svc) as client:
        response = client.get("/internal/v1/compatibility/release-1")
        assert response.status_code == 503
        assert response.json() == {"reason": "compatibility_unavailable"}
        assert "internal detail" not in response.text


def test_oversized_subject_is_a_not_found_not_a_500():
    svc = service()
    with transport_client(svc) as client:
        assert client.get("/internal/v1/evidence/" + "s" * 400).status_code == 404
