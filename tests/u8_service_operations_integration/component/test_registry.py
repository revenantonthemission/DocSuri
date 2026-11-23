"""The complete application's registration manifest (U8 plan Step 12; BR1.1, BR2.1,
BR3.11, BR5.3, BR6.11)."""

from __future__ import annotations

import dataclasses

import pytest

from backend import u8_host, u8_registry
from backend.u8_registry import (
    CAPABILITIES,
    CONTRIBUTIONS,
    LIFECYCLE_MANIFEST,
    LIFECYCLE_PAIR_BOUND,
    MANIFEST,
    MANIFEST_REVISION,
    MODEL_EVIDENCE,
    NAVIGATION,
    Manifest,
    ManifestRefused,
    chain_files_of,
    dependency_order,
    release_digests,
    schema_digest_of,
)
from docsuri_ops.local_models import MODEL_PINS

# BR3.11, stated here from the rule itself.
BR3_11_REQUIRED = {
    "account.entry", "account.controls", "library.saved-work", "personalization.settings",
    "usage.wallet", "corpus.content", "discovery.search", "research", "novelty",
    "topics.digest", "export", "operations.ledger", "storage.capacity", "background.work",
}
BR2_1 = {
    "AccountAccess": {"live_records", "derived_artifacts"},
    "Library": {"live_records"},
    "Personalization": {"live_records", "derived_artifacts", "pending_work"},
    "UsageEntitlements": {"live_records"},
    "PaperAssistance": {"live_records", "derived_artifacts", "pending_work"},
    "DiscoveryCitations": {"live_records"},
    "ResearchWorkspace": {"live_records", "derived_artifacts", "pending_work"},
    "TopicsDigests": {"live_records", "pending_work"},
    "ApprovedExport": {"live_records", "pending_work", "external_copies"},
    "ServiceOperations": {"backups", "restore_enforcement"},
}
BR5_3_PRIMARY = [
    "검색", "내 서재", "연구", "참신성 분석", "작업",
    "주제 구독", "내보내기", "설정", "사용량", "계정",
]


def rebuilt(**changes) -> Manifest:
    fields = {
        "contributions": CONTRIBUTIONS, "capabilities": CAPABILITIES,
        "navigation": NAVIGATION, "lifecycle": LIFECYCLE_MANIFEST,
        "model_evidence": MODEL_EVIDENCE, **changes,
    }
    return Manifest(**fields).sealed()


def test_the_built_manifest_verifies_and_its_revision_is_the_digest_of_its_entries():
    assert MANIFEST.verify() is MANIFEST
    assert MANIFEST_REVISION == MANIFEST.computed_revision() == rebuilt().revision
    assert [entry.contribution_id for entry in CONTRIBUTIONS] == list(u8_registry.CONTRIBUTION_IDS)
    assert len(CONTRIBUTIONS) == 8


@pytest.mark.parametrize(
    "manifest",
    [
        pytest.param(rebuilt(contributions=CONTRIBUTIONS[:-1]), id="lacks-a-contribution"),
        pytest.param(rebuilt(contributions=CONTRIBUTIONS + CONTRIBUTIONS[:1]), id="repeats-one"),
        pytest.param(dataclasses.replace(MANIFEST, revision="0" * 64), id="differs-from-digest"),
        pytest.param(
            rebuilt(contributions=(
                *CONTRIBUTIONS[:6],
                dataclasses.replace(CONTRIBUTIONS[6], routes=("/api/v2/c10/",)),
                CONTRIBUTIONS[7],
            )),
            id="platform-control-mounts-a-route",
        ),
        pytest.param(rebuilt(capabilities=CAPABILITIES[:-1]), id="capability-without-owner"),
        pytest.param(rebuilt(lifecycle=LIFECYCLE_MANIFEST * 2), id="lifecycle-repeats"),
    ],
)
def test_a_manifest_that_is_not_the_complete_verified_input_is_refused(manifest):
    with pytest.raises(ManifestRefused):
        manifest.verify()


def test_no_partial_application_is_produced_from_a_refused_manifest(realm, monkeypatch):
    def never(*args, **kwargs):
        raise AssertionError("a refused manifest reached the database")

    monkeypatch.setattr(u8_host, "connect_database", never)
    monkeypatch.setattr(u8_host, "open_ledger", never)
    with pytest.raises(ManifestRefused):
        u8_host.compose(realm, manifest=rebuilt(contributions=CONTRIBUTIONS[1:]))


def test_a_requirement_cycle_is_refused():
    first, second = CONTRIBUTIONS[0], CONTRIBUTIONS[1]
    cyclic = (
        dataclasses.replace(first, requires=("account-controls",)), second, *CONTRIBUTIONS[2:]
    )
    with pytest.raises(ManifestRefused, match="cycle"):
        rebuilt(contributions=cyclic).verify()
    order = [entry.contribution_id for entry in dependency_order(MANIFEST)]
    for entry in CONTRIBUTIONS:
        position = order.index(entry.contribution_id)
        assert all(order.index(need) < position for need in entry.requires)


def test_the_required_flags_equal_br3_11s_list():
    assert {cap.capability_id for cap in CAPABILITIES if cap.required} == BR3_11_REQUIRED
    assert u8_registry.REQUIRED == BR3_11_REQUIRED
    # Providers, paper assistance, platform evidence and the cutover check are never
    # required; public.static is the host's own.
    for capability in CAPABILITIES:
        if capability.capability_id.startswith(("provider.", "platform.", "assistance.")):
            assert not capability.required
    assert not u8_registry.CAPABILITY_BY_ID["operations.cutover"].required
    assert u8_registry.CAPABILITY_BY_ID["public.static"].producer == "host"


def test_each_capability_belongs_to_exactly_one_contribution():
    provided = [cap for entry in CONTRIBUTIONS for cap in entry.provides]
    assert sorted(provided) == sorted(cap.capability_id for cap in CAPABILITIES)
    assert len(provided) == len(set(provided)) == 25


def test_the_lifecycle_manifest_has_21_pairs_within_the_32_pair_bound():
    assert len(LIFECYCLE_MANIFEST) == 21 <= LIFECYCLE_PAIR_BOUND == 32
    assert len(set(LIFECYCLE_MANIFEST)) == 21
    grouped: dict[str, set] = {}
    for participant, scope in LIFECYCLE_MANIFEST:
        grouped.setdefault(participant, set()).add(scope)
    assert grouped == BR2_1
    assert u8_registry.LIFECYCLE_REVISION == "u8-owners-v1"
    named = {name for entry in CONTRIBUTIONS for name in entry.lifecycle_participants}
    assert named == set(BR2_1)


def test_the_model_pins_are_the_same_values_as_model_pins():
    assert {model: pin for model, _, pin in MODEL_EVIDENCE} == MODEL_PINS
    assert dict((model, purpose) for model, purpose, _ in MODEL_EVIDENCE) == {
        "bge-m3:latest": "embedding", "qwen3:8b": "assistance",
    }


def test_the_navigation_set_has_br5_3s_order_and_placements():
    primary = [entry for entry in NAVIGATION if entry.placement == "primary"]
    ordinary = [entry.label for entry in primary if entry.access != "administrator"]
    assert ordinary == BR5_3_PRIMARY
    operations = [entry for entry in NAVIGATION if entry.route_id == "operations"]
    assert len(operations) == 1 and operations[0].access == "administrator"
    assert operations[0].label == "운영" and operations[0].placement == "primary"
    paper = next(entry for entry in NAVIGATION if entry.route_id == "paper")
    assert (paper.label, paper.placement) == ("논문", "contextual")
    footer = {entry.route_id: entry for entry in NAVIGATION if entry.placement == "footer"}
    assert set(footer) == {"privacy", "terms"}
    assert {entry.capability_id for entry in footer.values()} == {"public.static"}
    assert [footer["privacy"].label, footer["terms"].label] == ["개인정보 처리방침", "이용약관"]
    # 작업 is backed by research, not by assistance.summary as the earlier host has it.
    assert next(entry for entry in NAVIGATION if entry.route_id == "jobs").capability_id == (
        "research"
    )
    assert len({entry.path for entry in NAVIGATION}) == len(NAVIGATION)


def test_each_schema_digest_is_the_digest_of_its_files_in_the_composed_chain():
    files = {}
    for entry in CONTRIBUTIONS:
        own = chain_files_of(entry.contribution_id)
        assert own, entry.contribution_id
        assert entry.schema_digest == schema_digest_of(
            own, release_digests(entry.contribution_id)
        )
        files[entry.contribution_id] = set(own)
    # Every chain file belongs to exactly one contribution.
    chain = set(u8_registry.u8_migrations.chain_files())
    assert set().union(*(files[name] for name in files if name != "platform-control")) == chain
    assert sum(len(files[name]) for name in files if name != "platform-control") == len(chain)


def test_platform_controls_contribution_lists_the_store_amendment():
    """The person's decision of 2026-10-25, "After the move, same build": the store
    amendment is part of PlatformControl's schema digest, named as the literal path
    `platform_profile.STORE_AMENDMENT` holds."""
    from docsuri_ops.u8_platform.platform_profile import STORE_AMENDMENT

    assert STORE_AMENDMENT in u8_registry.PLATFORM_FILES
    assert chain_files_of("platform-control") == u8_registry.PLATFORM_FILES
    assert u8_registry.PLATFORM_FILES[-1] == STORE_AMENDMENT
    entry = MANIFEST.contribution("platform-control")
    assert entry.schema_digest == schema_digest_of(u8_registry.PLATFORM_FILES,
                                                   release_digests("platform-control"))


def test_a_change_to_the_amendment_alone_changes_platform_controls_schema_digest(tmp_path):
    root = u8_registry.ROOT
    for file in u8_registry.PLATFORM_FILES:
        target = tmp_path / file
        target.parent.mkdir(parents=True, exist_ok=True)
        suffix = b"\n-- a later amendment\n" if file.endswith("u8_store.sql") else b""
        target.write_bytes((root / file).read_bytes() + suffix)
    files = u8_registry.PLATFORM_FILES
    before = schema_digest_of(files, release_digests("platform-control", root))
    after = schema_digest_of(files, release_digests("platform-control", tmp_path))
    assert before == MANIFEST.contribution("platform-control").schema_digest
    assert after != before
    # A release with that amendment no longer matches the built manifest: registration
    # reports PlatformControl incompatible rather than running a store it did not build.
    activations = u8_host.register(
        MANIFEST, u8_host.BuildContext(profile=None, transactions=None, clock=None), {},
        builders={"platform-control": u8_host.BUILDERS["platform-control"]},
        release_root=tmp_path)
    assert activations["platform-control"].reason == "incompatible"


def test_without_u8s_platform_package_the_registry_still_loads_and_reports_it_missing():
    """`PLATFORM_FILES` imports nothing from U8's PlatformControl package: with that package
    blocked, the registry imports and registration reports PlatformControl `missing`."""
    import os
    import subprocess
    import sys

    program = "\n".join((
        "import sys",
        "sys.modules['docsuri_ops.u8_platform'] = None",
        "from backend import u8_host, u8_registry",
        "assert 'ops/src/docsuri_ops/u8_platform/u8_store.sql' in u8_registry.PLATFORM_FILES",
        "ctx = u8_host.BuildContext(profile=None, transactions=None, clock=None)",
        "activations = u8_host.register(u8_registry.MANIFEST, ctx, {}, builders={",
        "    'platform-control': u8_host.BUILDERS['platform-control']})",
        "print(activations['platform-control'].reason)",
        "print(sorted(name for name, module in sys.modules.items()",
        "             if name.startswith('docsuri_ops.u8_platform') and module is not None))",
    ))
    root = u8_registry.ROOT
    path = os.pathsep.join(str(root / part) for part in ("", "ingestion/src", "ops/src"))
    finished = subprocess.run([sys.executable, "-c", program], cwd=root, capture_output=True,
                              text=True, timeout=60, env={**os.environ, "PYTHONPATH": path})
    assert finished.returncode == 0, finished.stderr
    assert finished.stdout.splitlines() == ["missing", "[]"]


def test_the_timing_follows_each_capabilitys_class():
    from backend.u8_policy import PRODUCTION_OPERATIONS as policy

    by_id = u8_registry.CAPABILITY_BY_ID
    assert u8_registry.timing(by_id["research"], policy) == (60, 180, 600)
    assert u8_registry.timing(by_id["provider.models"], policy) == (300, 900, 600)
    assert u8_registry.timing(by_id["platform.isolation"], policy) == (300, 900, 900)
    assert u8_registry.timing(by_id["operations.cutover"], policy) == (300, 900, 900)
    assert u8_registry.timing(by_id["public.static"], policy) == (0, 0, 0)
    # NFR9.2 (1)-(2): platform.status and the outward providers renew every 5 minutes
    # and are stale after 15.
    for capability in ("platform.status", "provider.google", "provider.orcid",
                       "provider.resend", "provider.notion"):
        assert u8_registry.timing(by_id[capability], policy) == (300, 900, 600), capability
