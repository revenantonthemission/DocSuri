"""The contribution gates of `assemble_u3` (R-06 row 10), with stub profiles refused or
admitted before any connection is made: an admitted assembly stops at a stand-in for
`OwnerTransactions`, so nothing reaches a database."""

from types import SimpleNamespace

import pytest
from backend import transactions as transactions_module
from backend.local_browser import (
    CORPUS_ORIGIN,
    EXPORT_ORIGIN,
    RESEARCH_ORIGIN,
    TOPICS_ORIGIN,
)
from backend.u3_host import assemble_u3
from backend.u4_host import assemble_u4
from backend.u5_host import assemble_u5

U3 = ("docsuri_u3", "corpus-maintenance", CORPUS_ORIGIN)
U4 = ("docsuri_u4", "research-workspace", RESEARCH_ORIGIN)
U5 = ("docsuri_u5", "topics-digests", TOPICS_ORIGIN)
U6 = ("docsuri_u6", "approved-export", EXPORT_ORIGIN)
EXPORT_REALM = "export contribution requires the exact owned U6 realm"
EXPORT_PARTS = "the U6 realm hosts the inherited research and topics contributions"
TOPICS_REALM = "topics contribution requires the exact owned U5 realm"
TOPICS_PARTS = "the U5 realm hosts the inherited research contribution"
RESEARCH_REALM = "research contribution requires the exact owned U4 realm"
CORPUS_REALM = "U3 assembly requires the owned corpus-maintenance realm"


class Admitted(Exception):
    """Raised where the assembly would open its first connection."""


def factory(*_args, **_kwargs):
    raise AssertionError("no contribution is built before the gates")


def profile(triple):
    database, realm, origin = triple
    return SimpleNamespace(database_name=database, realm=realm, origin=origin)


@pytest.fixture(autouse=True)
def no_connection(monkeypatch):
    def refuse(*_args, **_kwargs):
        raise Admitted()

    monkeypatch.setattr(transactions_module, "OwnerTransactions", refuse)


def gate(triple, **factories) -> str:
    """'admitted', or the refusal's message."""
    try:
        assemble_u3(profile(triple), **factories)
    except Admitted:
        return "admitted"
    except ValueError as error:
        return str(error)
    raise AssertionError("the assembly neither stopped nor refused")


ALL = {"research_factory": factory, "topics_factory": factory, "export_factory": factory}


@pytest.mark.parametrize("triple", [U3, U4, U5, ("docsuri_u6", "approved-export", TOPICS_ORIGIN)])
def test_an_export_factory_is_refused_outside_the_u6_realm(triple):
    assert gate(triple, **ALL) == EXPORT_REALM


@pytest.mark.parametrize(
    "factories",
    [
        {"export_factory": factory},
        {"export_factory": factory, "research_factory": factory},
        {"export_factory": factory, "topics_factory": factory},
    ],
)
def test_an_export_factory_needs_both_research_and_topics(factories):
    assert gate(U6, **factories) == EXPORT_PARTS


def test_the_u6_realm_admits_export_with_research_and_topics():
    assert gate(U6, **ALL) == "admitted"


def test_the_topics_gate_admits_the_u6_triple_and_refuses_other_realms():
    both = {"research_factory": factory, "topics_factory": factory}
    assert gate(U6, **both) == "admitted"
    assert gate(U5, **both) == "admitted"
    for triple in (U3, U4, ("docsuri_u5", "topics-digests", EXPORT_ORIGIN)):
        assert gate(triple, **both) == TOPICS_REALM
    assert gate(U5, topics_factory=factory) == TOPICS_PARTS
    assert gate(U6, topics_factory=factory) == TOPICS_PARTS


def test_the_u3_and_u4_gates_refuse_exactly_as_before():
    assert gate(U4, research_factory=factory) == "admitted"
    assert gate(U3) == "admitted"
    for triple in (U3, U5, U6):
        assert gate(triple, research_factory=factory) == RESEARCH_REALM
    for triple in (U4, U5, U6, ("docsuri_u3", "corpus-maintenance", RESEARCH_ORIGIN)):
        assert gate(triple) == CORPUS_REALM


def test_u4_and_u5_pass_the_export_factory_through():
    with pytest.raises(Admitted):
        assemble_u5(profile(U6), export_factory=factory)
    with pytest.raises(Admitted):
        assemble_u5(profile(U5))
    with pytest.raises(ValueError, match=EXPORT_REALM):
        assemble_u5(profile(U5), export_factory=factory)
    with pytest.raises(ValueError, match=EXPORT_PARTS):
        assemble_u4(profile(U6), export_factory=factory)
    with pytest.raises(Admitted):
        assemble_u4(profile(U4))
