"""Export service, destinations: writable, last destination, partial and gated listings
(BR1.5, BR8.2, A1, S2)."""

from uuid import UUID, uuid4

from backend.modules.export.fake_notion import Answer
from backend.u6_policy import real_activation_export
from docsuri_shared.workspace import wire

from tests.u6_approved_export import service_flows as sf


def listing(rig) -> dict:
    view = rig.service.list_destinations(rig.authority, {})
    wire.ExportDestinations.model_validate(view)
    return view


def entries(view) -> dict:
    return {entry["destinationId"]: entry for entry in view["destinations"]}


def set_connection(connect, connection_id: str, **facts) -> None:
    columns = ",".join(f"{name}=%s" for name in facts)
    with connect("export") as conn:
        conn.execute(
            f"UPDATE export.connection SET {columns} WHERE id=%s",
            (*facts.values(), UUID(connection_id)),
        )


def test_writable_is_false_for_an_unreadable_page_and_for_a_refused_capability(
    transactions, connect, authority, tmp_path
):
    rig = sf.build(transactions, connect, authority, tmp_path)
    connection = rig.configure()
    readable, hidden = rig.page("읽을 수 있음"), rig.page("읽을 수 없음", readable=False)
    untitled = rig.page(None)
    set_connection(connect, connection["connectionId"], last_destination_id=hidden)

    found = entries(listing(rig))

    assert found[readable]["writable"] is True
    assert found[readable]["creationCapability"] == "unknown"
    assert (found[hidden]["readable"], found[hidden]["writable"]) == (False, False)
    assert found[untitled]["title"] == "제목 없음"
    assert {entry["parentPageId"] for entry in found.values()} == set(found)
    set_connection(connect, connection["connectionId"], creation_capability="refused")
    refused = entries(listing(rig))
    assert {entry["writable"] for entry in refused.values()} == {False}
    assert {entry["creationCapability"] for entry in refused.values()} == {"refused"}


def test_after_a_succeeded_export_the_listing_names_its_destination_as_readable(
    transactions, connect, authority, tmp_path
):
    rig = sf.build(transactions, connect, authority, tmp_path)
    rig.configure()
    page = rig.page()
    rig.succeed(rig.press(page)["effect"])

    view = listing(rig)

    assert view["lastDestinationId"] == page and view["listingComplete"] is True
    assert entries(view)[page]["readable"] is True
    assert entries(view)[page]["creationCapability"] == "confirmed"
    assert view["connectionRevision"] == "1"


def test_a_last_destination_that_is_not_listed_or_not_readable_is_dropped(
    transactions, connect, authority, tmp_path
):
    rig = sf.build(transactions, connect, authority, tmp_path)
    connection = rig.configure()
    page = rig.page()
    absent = uuid4().hex
    set_connection(connect, connection["connectionId"], last_destination_id=absent)

    view = listing(rig)

    assert view["lastDestinationId"] == absent and absent not in entries(view)
    set_connection(connect, connection["connectionId"], last_destination_id=page)
    rig.fake.queue("pages.retrieve", Answer.error(503), target=page)
    view = listing(rig)
    assert entries(view)[page]["readable"] is False and entries(view)[page]["writable"] is False


def test_a_partial_search_keeps_the_listing_incomplete(transactions, connect, authority, tmp_path):
    rig = sf.build(transactions, connect, authority, tmp_path)
    rig.configure()
    for index in range(3):
        rig.page(f"페이지 {index}")
    rig.fake.set_search("partial", page_size=1)

    view = listing(rig)

    assert view["listingComplete"] is False and len(view["destinations"]) == 1
    rig.fake.set_search("unavailable")
    assert listing(rig)["destinations"] == [] and listing(rig)["listingComplete"] is False


def test_a_gate_refusal_answers_an_unavailable_listing_at_once(
    transactions, connect, authority, tmp_path
):
    rig = sf.build(transactions, connect, authority, tmp_path)
    connection = UUID(rig.configure()["connectionId"])
    rig.page()
    asked, gated = len(rig.fake.requests), len(rig.gate.asked)
    assert rig.gate.try_acquire(connection)
    try:
        view = listing(rig)
    finally:
        rig.gate.release(connection)

    assert view["destinations"] == [] and view["listingComplete"] is False
    assert len(rig.fake.requests) == asked
    assert rig.gate.asked[gated:] == [connection, connection]
    assert listing(rig)["listingComplete"] is True


def test_the_real_composition_allows_only_its_activation_destination(
    transactions, connect, authority, tmp_path
):
    activation = uuid4().hex
    policy = real_activation_export(
        activation_destination_id=activation, free_terms_reference="free-terms-2026-10"
    )
    rig = sf.build(transactions, connect, authority, tmp_path, policy=policy)
    connection = rig.configure()
    rig.page("활성 대상", page_id=activation)
    other = rig.page("다른 페이지")

    found = entries(listing(rig))

    assert connection["destinationScopeIds"] == [activation]
    assert "synthetic-only" not in connection["limitations"]
    assert found[activation]["writable"] is True
    assert found[other]["writable"] is False
    assert rig.fake.writes == []
