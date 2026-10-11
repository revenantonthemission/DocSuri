"""Server-owned option policy and deliberate request-boundary faults."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from backend.modules.summarization.requests import (
    AssistanceCatalog,
    AssistanceRequests,
    AssistanceUnavailable,
    PROCESSING_POLICY,
)
from backend.transactions import Authority
from tests.u1_integrated_paper_journey.component.test_execution_payload import fixture

pytestmark = pytest.mark.u1_component


def catalog_fixture(*, ready=True):
    bound, source = fixture()
    definitions = [
        {
            "option": {
                "optionId": "selected-section",
                "operation": "summary",
                "sourceLanguageId": "en",
                "targetLanguageId": "en",
                "presentationLevelId": "selected-source",
                "labelKey": "assistance.selectedSummary",
            },
            "selectedSections": bound["payload"]["selectedSections"],
        }
    ]
    catalog = AssistanceCatalog(source, definitions, quality_ready=ready)
    request = dict(bound["payload"]["acceptedInput"])
    request.pop("glossary")
    request.update(
        optionId="selected-section",
        optionsRevision=catalog.revision,
        processingPolicy=PROCESSING_POLICY,
    )
    return catalog, request, source, definitions


def test_unready_catalog_exposes_no_runnable_options_or_admission():
    catalog, request, _, _ = catalog_fixture(ready=False)
    assert catalog.options()["options"] == []
    assert len(catalog.options()["limitations"]) == 2
    with pytest.raises(AssistanceUnavailable):
        catalog.bind(request)


def test_ready_catalog_binds_a_defensive_source_selection_and_revision():
    catalog, request, source, definitions = catalog_fixture()
    expected = deepcopy(definitions[0]["selectedSections"])
    definitions[0]["selectedSections"].clear()
    source["content"]["chunks"].clear()
    proposal = catalog.bind(request)
    assert proposal["selectedSections"] == expected
    assert proposal["request"] == request
    assert catalog.options()["options"][0]["optionId"] == request["optionId"]
    assert (
        AssistanceCatalog(catalog.source, catalog.definitions, quality_ready=False).revision
        != catalog.revision
    )


@pytest.mark.parametrize(
    "field",
    [
        "paper",
        "contentRevision",
        "contentHash",
        "optionsRevision",
        "processingPolicy",
        "optionId",
        "operation",
    ],
)
def test_changed_source_or_option_precondition_cannot_prepare(field):
    catalog, request, _, _ = catalog_fixture()
    if field == "paper":
        request[field] = dict(request[field], eligibilityRevision="changed")
    elif field == "processingPolicy":
        request[field] = {"policyId": "cloud", "revision": "1"}
    else:
        request[field] = "changed"
    with pytest.raises(ValueError):
        catalog.bind(request)


def test_original_replay_uses_current_owner_check_before_any_catalog_read():
    _, request, _, _ = catalog_fixture()
    original = {"intent": {"frozen": True}}
    repository = SimpleNamespace(replay_request=Mock(return_value=original), prepare_request=Mock())
    admission = SimpleNamespace(assistance=repository, accept=Mock(return_value={"id": "same"}))
    corpus, factory = Mock(), Mock()
    service = AssistanceRequests(admission, corpus, factory)
    authority, operation = Authority(uuid4(), uuid4()), uuid4()
    assert service.submit(authority, operation, request) == {"id": "same"}
    repository.replay_request.assert_called_once_with(authority, operation, request)
    admission.accept.assert_called_once_with(authority, operation, original["intent"])
    corpus.read.assert_not_called()
    factory.assert_not_called()
    repository.prepare_request.assert_not_called()


def test_current_authority_denial_and_unknown_preparation_do_not_admit():
    catalog, request, source, _ = catalog_fixture()
    repository = SimpleNamespace(
        replay_request=Mock(side_effect=PermissionError), prepare_request=Mock()
    )
    admission = SimpleNamespace(assistance=repository, accept=Mock())
    service = AssistanceRequests(admission, Mock(read=Mock(return_value=source)), lambda _: catalog)
    with pytest.raises(PermissionError):
        service.submit(Authority(uuid4(), uuid4()), uuid4(), request)
    repository.replay_request.side_effect = None
    repository.replay_request.return_value = None
    repository.prepare_request.side_effect = RuntimeError("injected unknown preparation reply")
    with pytest.raises(RuntimeError):
        service.submit(Authority(uuid4(), uuid4()), uuid4(), request)
    admission.accept.assert_not_called()


def test_fresh_submission_uses_owner_prepared_snapshot_not_browser_glossary():
    catalog, request, source, _ = catalog_fixture()
    prepared = {"intent": {"ownerFrozen": True}}
    repository = SimpleNamespace(
        replay_request=Mock(return_value=None), prepare_request=Mock(return_value=prepared)
    )
    admission = SimpleNamespace(assistance=repository, accept=Mock(return_value={"id": "accepted"}))
    service = AssistanceRequests(admission, Mock(read=Mock(return_value=source)), lambda _: catalog)
    authority, operation = Authority(uuid4(), uuid4()), uuid4()
    assert service.submit(authority, operation, request) == {"id": "accepted"}
    assert "acceptedInput" not in repository.prepare_request.call_args.args[2]
    admission.accept.assert_called_once_with(authority, operation, prepared["intent"])
    with pytest.raises(ValueError):
        service.submit(authority, operation, dict(request, glossary={"forged": True}))
