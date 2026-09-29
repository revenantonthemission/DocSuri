"""Generation boundary: durability receipts, verified import, pinned collection, recovery.

Every scenario the plan names for Step 7 is exercised here: interrupted seal/head/receipt,
torn tail, stale head, late writable descriptors, reader/backup pins and recovery.
"""

import os
import stat
from contextlib import nullcontext
from pathlib import Path

import pytest

from docsuri_platform_integrity.adapters.filesystem import (
    GenerationBoundary,
    PublicationConflict,
)
from docsuri_platform_integrity.adapters.journal import BootstrapJournal
from docsuri_platform_integrity.domain.generation import collectible, receipt_matches

ONE = {"python/a.py": b"a=1\n"}
TWO = {"python/a.py": b"a=2\n", "ts/a.ts": b"export const a=2;\n"}


def boundary(tmp_path, pins=None):
    store = GenerationBoundary(tmp_path / "store", pins)
    store.provision()
    return store


def publish(store, files):
    generation = store.seal(files)
    head = store.activate(generation, expected=store.head(), guard=nullcontext)
    store.write_receipt(generation, head["revision"])
    return generation, head


# -- durability receipt ---------------------------------------------------


def test_seal_without_a_receipt_is_not_durable(tmp_path):
    store = boundary(tmp_path)
    generation = store.seal(ONE)
    assert not store.has_receipt(generation)
    assert not store.durable(generation)


def test_receipt_appears_only_after_activation(tmp_path):
    store = boundary(tmp_path)
    generation = store.seal(ONE)
    assert not store.durable(generation)
    head = store.activate(generation, expected=None, guard=nullcontext)
    assert not store.durable(generation), "no receipt may be implied by activation"
    store.write_receipt(generation, head["revision"])
    assert store.durable(generation)
    assert store.receipt(generation).generation == "sha256:" + generation


def test_interrupted_receipt_is_never_counted_as_durable(tmp_path):
    store = boundary(tmp_path)
    generation, head = publish(store, ONE)
    path = store.root / "receipts" / f"{generation}.json"
    raw = path.read_bytes()
    path.unlink()
    assert not store.durable(generation)
    # A torn receipt file is refused rather than repaired.
    path.write_bytes(raw[: len(raw) // 2])
    path.chmod(0o400)
    assert not store.durable(generation)
    with pytest.raises(ValueError):
        store.receipt(generation)


def test_tampered_receipt_body_is_rejected(tmp_path):
    store = boundary(tmp_path)
    generation, head = publish(store, ONE)
    path = store.root / "receipts" / f"{generation}.json"
    body = store.receipt(generation).model_dump(mode="json")
    body["bytes"] = str(int(body["bytes"]) + 1)
    path.chmod(0o600)
    path.write_bytes(__import__("json").dumps(body).encode())
    with pytest.raises(ValueError, match="self-consistent"):
        store.receipt(generation)
    assert not store.durable(generation)


def test_receipt_agreement_requires_every_field():
    receipt = dict(
        generation="sha256:" + "a" * 64,
        manifest="sha256:" + "b" * 64,
        files="3",
        bytes="99",
        head_revision="2",
        receipt="sha256:" + "c" * 64,
    )
    from docsuri_platform_integrity.domain.generation import DurabilityReceipt

    value = DurabilityReceipt(**receipt)
    good = dict(generation=receipt["generation"], manifest=receipt["manifest"],
                files=3, total_bytes=99, head_revision=2)
    assert receipt_matches(value, **good)
    for field, bad in (("files", 4), ("total_bytes", 100), ("head_revision", 3)):
        assert not receipt_matches(value, **{**good, field: bad})
    assert not receipt_matches(value, **{**good, "files": True})
    assert not receipt_matches(value, **{**good, "files": -1})


# -- expected-head atomic replacement -------------------------------------


def test_stale_head_never_replaces_a_newer_one(tmp_path):
    store = boundary(tmp_path)
    one, head_one = publish(store, ONE)
    two, _ = publish(store, TWO)
    with pytest.raises(PublicationConflict):
        store.activate(one, expected=head_one, guard=nullcontext)
    assert store.pin()[0]["generation"] == two


def test_activation_requires_current_authority(tmp_path):
    store = boundary(tmp_path)
    generation = store.seal(ONE)
    with pytest.raises(PermissionError):
        store.activate(generation, expected=None, guard=None)
    assert store.head() is None


def test_manifest_change_after_activation_is_detected(tmp_path):
    store = boundary(tmp_path)
    generation = store.seal(ONE)
    store.activate(generation, expected=None, guard=nullcontext)
    target = store.root / "generations" / generation / "python" / "a.py"
    target.chmod(0o600)
    target.write_bytes(b"a=999\n")
    with pytest.raises(ValueError):
        store._read_generation(generation)
    assert not store.durable(generation)


# -- late writable descriptors --------------------------------------------


def test_a_late_writer_cannot_alter_a_sealed_generation(tmp_path):
    """The directory is sealed to 0500 and files to 0400 before the head can name them."""
    store = boundary(tmp_path)
    generation, _ = publish(store, ONE)
    root = store.root / "generations" / generation
    assert stat.S_IMODE(root.stat().st_mode) == 0o500
    assert stat.S_IMODE((root / "python" / "a.py").stat().st_mode) == 0o400
    # A descriptor obtained before sealing, or any attempt to obtain one after, must fail.
    with pytest.raises(PermissionError):
        os.open(root / "python" / "a.py", os.O_WRONLY)
    with pytest.raises(PermissionError):
        (root / "python" / "later.py").write_bytes(b"late\n")
    assert store.pin()[1]["python/a.py"] == b"a=1\n"


def test_unreadable_or_absent_generation_never_resolves(tmp_path):
    store = boundary(tmp_path)
    generation, _ = publish(store, ONE)
    root = store.root / "generations" / generation
    os.chmod(root, 0o700)
    os.chmod(root / "python", 0o700)
    (root / "python" / "a.py").unlink()
    with pytest.raises(ValueError, match="file set mismatch"):
        store.pin()
    assert not store.durable(generation), "a receipt cannot outlive its generation"


# -- pins and collection --------------------------------------------------


def test_head_and_pinned_generations_survive_collection(tmp_path):
    store = boundary(tmp_path)
    one, _ = publish(store, ONE)
    two, _ = publish(store, TWO)
    assert store.collect() == (one,)
    assert not (store.root / "generations" / one).exists()
    assert store.pin()[0]["generation"] == two


def test_a_pinned_generation_is_never_collected(tmp_path):
    store = boundary(tmp_path)
    one, _ = publish(store, ONE)
    publish(store, TWO)
    with store.pins.hold(one):
        assert store.collect() == ()
        assert (store.root / "generations" / one).exists()
    assert store.collect() == (one,)


def test_shared_pins_are_reference_counted(tmp_path):
    store = boundary(tmp_path)
    one, _ = publish(store, ONE)
    store.pins.pin(one)
    store.pins.pin(one)
    store.pins.release(one)
    assert store.pins.held() == frozenset({one})
    store.pins.release(one)
    assert store.pins.held() == frozenset()
    with pytest.raises(ValueError):
        store.pins.release(one)


def test_backup_pin_holds_a_generation_while_a_copy_runs(tmp_path):
    store = boundary(tmp_path)
    one, _ = publish(store, ONE)
    publish(store, TWO)
    with store.pins.hold(one):
        # A backup reading the pinned generation still verifies it in full.
        assert store._read_generation(one) == ONE
        assert store.collect() == ()
    assert store.pin()[0]["generation"] == store.head()["generation"]


def test_unreceipted_generation_is_retained_as_interrupted_seal_evidence(tmp_path):
    store = boundary(tmp_path)
    one, _ = publish(store, ONE)
    publish(store, TWO)  # head moves on, so `one` becomes collectible
    orphan = store.seal({"python/a.py": b"a=3\n"})  # sealed, never activated, never receipted
    assert store.collect() == (one,)
    assert (store.root / "generations" / orphan).exists(), "interrupted seal evidence must survive"


def test_collectible_is_pure_and_refuses_to_collect_head_or_pins():
    receipts = frozenset({"a", "b", "c"})
    assert collectible("a", head="b", pins=frozenset(), receipts=receipts)
    assert not collectible("b", head="b", pins=frozenset(), receipts=receipts)
    assert not collectible("c", head="b", pins=frozenset({"c"}), receipts=receipts)
    assert not collectible("d", head="b", pins=frozenset(), receipts=receipts)


def test_collection_does_not_touch_a_symlinked_generation(tmp_path):
    store = boundary(tmp_path)
    one, _ = publish(store, ONE)
    publish(store, TWO)
    os.chmod(store.root / "generations" / one, 0o700)
    (store.root / "generations" / one).rename(
        store.root / "generations" / ("z" * 64)
    )
    (store.root / "generations" / one).symlink_to("/tmp")
    assert store.collect() == ()
    assert (store.root / "generations" / one).is_symlink()


def test_trash_is_outside_the_published_namespace(tmp_path):
    store = boundary(tmp_path)
    one, _ = publish(store, ONE)
    publish(store, TWO)
    store.collect()
    trash = store.root / "trash"
    assert trash.is_dir() and not any(trash.iterdir())
    assert {p.name for p in (store.root / "generations").iterdir()} == {
        store.head()["generation"]
    }


# -- verified import ------------------------------------------------------


def test_import_verifies_metadata_without_publishing(tmp_path):
    store = boundary(tmp_path)
    source = tmp_path / "foreign"
    source.mkdir()
    for name, data in TWO.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    from docsuri_platform_integrity.contracts.codec import canonical, digest

    manifest = canonical({n: digest(d) for n, d in sorted(TWO.items())})
    (source / "manifest.json").write_bytes(manifest)

    imported = store.import_metadata(source)
    assert imported.verifiable == "ELIGIBLE"
    assert int(imported.files) == 2
    assert store.head() is None, "import must not publish or activate anything"
    assert not any((store.root / "generations").iterdir())


def test_import_of_a_wrong_manifest_is_a_hard_failure(tmp_path):
    store = boundary(tmp_path)
    source = tmp_path / "foreign"
    source.mkdir()
    (source / "a.py").write_bytes(b"a=1\n")
    from docsuri_platform_integrity.contracts.codec import canonical, digest

    (source / "manifest.json").write_bytes(
        canonical({"a.py": digest(b"a=1\n")})
    )
    with pytest.raises(ValueError, match="expected"):
        store.import_metadata(source, expected_manifest="sha256:" + "0" * 64)


def test_import_rejects_tampered_content_and_extra_files(tmp_path):
    from docsuri_platform_integrity.contracts.codec import canonical, digest

    store = boundary(tmp_path)
    source = tmp_path / "foreign"
    source.mkdir()
    (source / "a.py").write_bytes(b"a=1\n")
    (source / "manifest.json").write_bytes(canonical({"a.py": digest(b"a=1\n")}))
    (source / "extra.py").write_bytes(b"surprise\n")
    with pytest.raises(ValueError, match="file set mismatch"):
        store.import_metadata(source)

    (source / "extra.py").unlink()
    (source / "a.py").write_bytes(b"a=2\n")
    with pytest.raises(ValueError, match="integrity mismatch"):
        store.import_metadata(source)


def test_import_refuses_a_symlinked_source_or_member(tmp_path):
    from docsuri_platform_integrity.contracts.codec import canonical, digest

    store = boundary(tmp_path)
    real = tmp_path / "real"
    real.mkdir()
    (real / "a.py").write_bytes(b"a=1\n")
    (real / "manifest.json").write_bytes(canonical({"a.py": digest(b"a=1\n")}))
    link = tmp_path / "link"
    link.symlink_to(real)
    with pytest.raises(ValueError, match="symlink"):
        store.import_metadata(link)

    (real / "member.py").symlink_to(real / "a.py")
    with pytest.raises(ValueError, match="symlink"):
        store.import_metadata(real)


# -- journal tail and recovery -------------------------------------------


def test_torn_tail_after_recovery_is_refused(tmp_path):
    journal = BootstrapJournal(tmp_path / "journal")
    tail = journal.append({"assurance": "COMMITTED", "receipt": "r1"}, expected_tail=None)
    with journal.path.open("ab") as stream:
        stream.write(b'{"sequence":"1","previous":null}')
    with pytest.raises(ValueError, match="torn"):
        journal.inspect(expected_tail=tail)
    # Recovery: the torn record is dropped by an explicit truncation to a known-good tail.
    lines = journal.path.read_bytes().split(b"\n")
    journal.path.write_bytes(lines[0] + b"\n")
    recovered = journal.inspect(expected_tail=tail)
    assert len(recovered) == 1 and recovered[0]["record"]["receipt"] == "r1"


def test_journal_floor_mismatch_blocks_a_new_append(tmp_path):
    journal = BootstrapJournal(tmp_path / "journal")
    tail = journal.append({"assurance": "UNKNOWN", "effect": "e1"}, expected_tail=None)
    with pytest.raises(ValueError):
        journal.append({"assurance": "COMMITTED"}, expected_tail=None)
    journal.append({"assurance": "COMMITTED"}, expected_tail=tail)


def test_recovery_after_an_uninitialised_publication(tmp_path):
    store = boundary(tmp_path)
    assert store.head() is None
    with pytest.raises(FileNotFoundError):
        store.pin()
    generation, head = publish(store, ONE)
    recovered = store.pin()
    assert recovered[0] == head
    assert recovered[1] == ONE


def test_staged_directory_is_never_published(tmp_path):
    store = boundary(tmp_path)
    with pytest.raises(ValueError):
        store.seal({"../escape": b"bad"})
    assert not any((store.root / "generations").iterdir())
    assert store.head() is None


def test_a_failed_seal_leaves_no_named_generation(tmp_path):
    store = boundary(tmp_path)
    with pytest.raises(ValueError):
        store.seal({"ok/a.py": b"a=1\n", "../escape": b"bad"})
    assert [p.name for p in (store.root / "generations").iterdir()] == []


def test_boundary_exposes_the_publication_namespace_only(tmp_path):
    store = boundary(tmp_path)
    generation, _ = publish(store, ONE)
    assert Path(store.root).is_absolute()
    assert sorted(p.name for p in store.root.iterdir()) == [
        "generations", "head.json", "publication.lock", "receipts",
    ]
    assert (store.root / "generations" / generation).is_dir()
