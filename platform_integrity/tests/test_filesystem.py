from contextlib import nullcontext

import pytest

from docsuri_platform_integrity.adapters.filesystem import GenerationStore, PublicationConflict
from docsuri_platform_integrity.adapters.journal import BootstrapJournal


def test_read_never_provisions_and_complete_generation_survives_rejected_activation(tmp_path):
    store = GenerationStore(tmp_path / "store")
    assert store.head() is None
    assert not store.root.exists()
    store.provision()
    one = store.seal({"python/a.py": b"a=1\n", "ts/a.ts": b"export const a=1;\n"})
    first = store.activate(one, expected=None, guard=nullcontext)
    pinned = store.pin()
    two = store.seal({"python/a.py": b"a=2\n", "ts/a.ts": b"export const a=2;\n"})
    with pytest.raises(PublicationConflict):
        store.activate(two, expected=None, guard=nullcontext)
    assert store.pin() == pinned
    store.activate(two, expected=first, guard=nullcontext)
    assert pinned[1]["python/a.py"] == b"a=1\n"
    assert store.pin()[1]["python/a.py"] == b"a=2\n"


@pytest.mark.parametrize("name", ["../escape", "/absolute", "a/../b", "manifest.json", "a\\b"])
def test_generation_path_is_closed(tmp_path, name):
    store = GenerationStore(tmp_path)
    store.provision()
    with pytest.raises(ValueError):
        store.seal({name: b"bad"})


def test_journal_chain_torn_and_truncated_detection(tmp_path):
    journal = BootstrapJournal(tmp_path / "journal")
    tail = journal.append({"assurance": "UNKNOWN", "effect": "step-1"}, expected_tail=None)
    second = journal.append({"assurance": "COMMITTED", "receipt": "native"}, expected_tail=tail)
    assert len(journal.inspect(expected_tail=second)) == 2
    with pytest.raises(ValueError):
        journal.inspect(expected_tail=tail)
    with journal.path.open("ab") as stream:
        stream.write(b'{"sequence":')
    with pytest.raises(ValueError, match="torn"):
        journal.inspect(expected_tail=second)
