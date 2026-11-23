"""Model evidence and the model runtime (U8 plan Step 22; A7, BR6.11, BR7.1, BR7.7, P2, P3).

The shared runtime is never called: this Mac's live v1 site uses 127.0.0.1:11434. Every
request goes through a stand-in transport handed to the real client
(`SharedModelRuntime`), which records it; the test-wide guard refuses the client's own
network transport. The stand-in answers `/api/tags` with chosen digests, `/api/embed`
with deterministic vectors and `/api/chat` with a source-bound answer.
"""

from __future__ import annotations

import json
import secrets
import time

import httpx
import pytest

from backend.local_host import assistance_readiness
from backend.modules.discovery.local_embedding import EmbeddingTimeout, LocalEmbeddings
from backend.modules.summarization import model_runtime
from backend.modules.summarization.model_runtime import (
    EMBEDDING_MODEL,
    GENERATION_MODEL,
    ModelEvidenceMismatch,
    ProductionAssistanceExecutor,
    SharedModelRuntime,
)
from backend.modules.summarization.worker import ExecutionRefused
from docsuri_ops.local_models import MODEL_PINS

REFUSED = "tests never build a network transport"
STANDIN = "http://127.0.0.1:18115"  # the realm's own address for a stand-in, never bound


class Runtime:
    """The stand-in runtime: chosen digests, deterministic answers, every request kept."""

    def __init__(self, digests: dict | None = None, *, embed_fails: Exception | None = None):
        self.digests = dict(MODEL_PINS if digests is None else digests)
        self.embed_fails = embed_fails
        self.requests: list[httpx.Request] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if path == "/api/tags":
            return httpx.Response(200, json={"models": [
                {"name": name, "digest": digest} for name, digest in self.digests.items()]})
        body = json.loads(request.content)
        if path == "/api/embed":
            if self.embed_fails is not None:
                raise self.embed_fails
            vectors = [[1.0] + [0.0] * 1023 for _ in body["input"]]
            return httpx.Response(200, json={"model": body["model"], "embeddings": vectors})
        if path == "/api/chat":
            anchors = body["format"]["properties"]["citations"]["items"]["enum"] if (
                "format" in body) else ["a1"]
            content = json.dumps({"text": f"요약입니다 [{anchors[0]}]", "citations": anchors[:1]})
            return httpx.Response(200, json={
                "model": body["model"], "message": {"role": "assistant", "content": content},
                "done": True, "done_reason": "stop", "prompt_eval_count": 40,
                "eval_count": 20})
        return httpx.Response(404)

    def factory(self):
        return httpx.MockTransport(self.handle)

    def calls(self, path: str) -> list[dict]:
        return [json.loads(r.content) for r in self.requests if r.url.path == path]


def runtime(standin: Runtime, **options) -> SharedModelRuntime:
    return SharedModelRuntime(base_url=STANDIN, transport_factory=standin.factory, **options)


def embeddings(standin: Runtime) -> LocalEmbeddings:
    return LocalEmbeddings(runtime(standin), keep_alive=-1, query_seconds=2.0, batch=16)


SECTIONS = [{"sectionId": "s1", "heading": "Introduction", "anchor": "a1",
             "text": "Attention lets a model weigh every input token."}]


def bound(operation: str = "summary") -> dict:
    return {"input": {"operation": operation}, "sections": SECTIONS}


# 1. A model whose digest differs from its pin, or that has no pin, is never used ----------


@pytest.mark.parametrize("digests", [
    {**MODEL_PINS, EMBEDDING_MODEL: "0" * 64},  # the runtime's digest differs
    {GENERATION_MODEL: MODEL_PINS[GENERATION_MODEL]},  # the runtime does not hold it
])
def test_a_model_whose_digest_differs_from_its_pin_is_never_used(digests):
    standin = Runtime(digests)
    with pytest.raises(ModelEvidenceMismatch) as refused:
        embeddings(standin).embed_query("attention")
    assert refused.value.reason == "model-evidence-mismatch"
    assert standin.calls("/api/embed") == []  # checked before any model request


def test_a_model_the_release_does_not_pin_is_never_used():
    standin = Runtime({**MODEL_PINS, "llama3:8b": "1" * 64})
    unpinned = runtime(standin)
    with pytest.raises(ModelEvidenceMismatch):
        unpinned.verify("llama3:8b")
    with pytest.raises(Exception):  # noqa: B017 - refused before the request is built
        unpinned.infer(model="llama3:8b", body={"model": "llama3:8b"}, timeout=1)
    assert standin.requests == []  # refused by the pins alone, before any request


def test_the_executor_refuses_a_mismatched_generation_model():
    standin = Runtime({**MODEL_PINS, GENERATION_MODEL: "2" * 64})
    executor = ProductionAssistanceExecutor(runtime(standin), ready=lambda: True)
    with pytest.raises(ExecutionRefused) as refused:
        executor.run(bound(), time.monotonic() + 60)
    assert refused.value.reason == "dependency-unavailable"
    assert standin.calls("/api/chat") == [] and executor.stopped()


# 2. Assistance stays pending until the readiness marker is recorded ------------------------


def test_assistance_stays_pending_until_its_readiness_marker_is_recorded(realm):
    from backend.modules.operations.producers import AssistanceProducer

    standin = Runtime()
    assert assistance_readiness(realm) is False  # the composed realm records none
    executor = ProductionAssistanceExecutor(runtime(standin),
                                            ready=lambda: assistance_readiness(realm))
    with pytest.raises(ExecutionRefused) as refused:
        executor.run(bound(), time.monotonic() + 60)
    assert refused.value.reason == "dependency-unavailable"
    assert standin.requests == []  # not even the digest check
    import datetime as dt

    observed = AssistanceProducer("assistance.summary", realm).observe(dt.datetime.now(dt.UTC))
    assert observed.reason == "assistance-readiness-pending"


def test_once_ready_the_executor_runs_the_pinned_model_with_source_bound_output():
    standin = Runtime()
    executor = ProductionAssistanceExecutor(runtime(standin), ready=lambda: True)
    prepared = executor.run(bound(), time.monotonic() + 60)
    document = json.loads(prepared.content)
    assert document["citations"] == ["a1"] and document["sections"][0]["anchor"] == "a1"
    assert prepared.provenance["modelDigest"] == MODEL_PINS[GENERATION_MODEL]
    assert prepared.provenance["provider"] == "local-model-runtime"
    [chat] = standin.calls("/api/chat")
    assert chat["model"] == GENERATION_MODEL


# 3. An embedding past 2 s answers search by words only, with its limitation ----------------


def test_an_embedding_past_its_bound_is_a_timeout_and_the_request_carried_the_bound():
    standin = Runtime(embed_fails=httpx.ReadTimeout("no answer"))
    with pytest.raises(EmbeddingTimeout) as refused:
        embeddings(standin).embed_query("attention")
    assert refused.value.reason == "semantic-search-unavailable"
    [request] = [r for r in standin.requests if r.url.path == "/api/embed"]
    assert 0 < request.extensions["timeout"]["read"] <= 2.0


def test_search_past_the_embedding_bound_answers_by_words_with_its_limitation(transactions):
    from backend.modules.discovery.guarded_repository import GuardedDiscoveryRepository
    from backend.modules.discovery.u8_search import CompleteSearch
    from backend.modules.library.u3_history import U3HistoryConsumer
    from backend.u3_policy import QUERY_VOCABULARY, SEARCH_POLICY

    standin = Runtime(embed_fails=httpx.ReadTimeout("no answer"))
    search = CompleteSearch(
        transactions, GuardedDiscoveryRepository(transactions), U3HistoryConsumer(transactions),
        cursor_key=secrets.token_bytes(32), embedder=embeddings(standin))
    answer = search.search(None, {"query": {
        "query": "attention", "modeId": "semantic", "orderId": "relevance", "filters": [],
        "vocabularyRevision": QUERY_VOCABULARY, "policyRef": SEARCH_POLICY}})
    assert (answer["outcome"], answer["effectiveModeId"]) == ("degraded", "lexical")
    assert "semantic-search-unavailable" in answer["limitations"]


@pytest.mark.parametrize("digests", [
    {**MODEL_PINS, EMBEDDING_MODEL: "0" * 64},  # the runtime's digest differs
    {GENERATION_MODEL: MODEL_PINS[GENERATION_MODEL]},  # the runtime does not hold it
])
def test_search_answers_by_words_when_the_search_models_digest_differs_from_its_pin(
        transactions, digests):
    """NFR3.11 (security-design § 8): a search model whose digest differs from its pin is
    never asked; a semantic search answers by words with its limitation."""
    from backend.modules.discovery.guarded_repository import GuardedDiscoveryRepository
    from backend.modules.discovery.u8_search import CompleteSearch
    from backend.modules.library.u3_history import U3HistoryConsumer
    from backend.u3_policy import QUERY_VOCABULARY, SEARCH_POLICY

    standin = Runtime(digests)
    search = CompleteSearch(
        transactions, GuardedDiscoveryRepository(transactions), U3HistoryConsumer(transactions),
        cursor_key=secrets.token_bytes(32), embedder=embeddings(standin))
    answer = search.search(None, {"query": {
        "query": "attention", "modeId": "semantic", "orderId": "relevance", "filters": [],
        "vocabularyRevision": QUERY_VOCABULARY, "policyRef": SEARCH_POLICY}})
    assert (answer["outcome"], answer["effectiveModeId"]) == ("degraded", "lexical")
    assert "semantic-search-unavailable" in answer["limitations"]
    assert standin.calls("/api/embed") == []  # refused before any model request


# 3b. Search's circuit breaker over provider.models (L3-7) ------------------------------------


def models_reader(state: str, calls: list | None = None):
    """A fixed `capability_states` reader, bound to its state when made; `calls`, when
    given, counts each read."""

    def read() -> dict[str, dict]:
        if calls is not None:
            calls.append(state)
        return {"provider.models": {"state": state, "reason": None}}

    return read


def breaker_search(transactions, embedder):
    from backend.modules.discovery.guarded_repository import GuardedDiscoveryRepository
    from backend.modules.discovery.u8_search import CompleteSearch
    from backend.modules.library.u3_history import U3HistoryConsumer

    return CompleteSearch(
        transactions, GuardedDiscoveryRepository(transactions), U3HistoryConsumer(transactions),
        cursor_key=secrets.token_bytes(32), embedder=embedder)


def search_for(search, mode: str = "semantic") -> dict:
    from backend.u3_policy import QUERY_VOCABULARY, SEARCH_POLICY

    return search.search(None, {"query": {
        "query": "attention", "modeId": mode, "orderId": "relevance", "filters": [],
        "vocabularyRevision": QUERY_VOCABULARY, "policyRef": SEARCH_POLICY}})


def test_search_makes_no_model_call_while_provider_models_is_observed_unavailable(transactions):
    """Reliability-design § 10 (lines 133-137, 145), L3-7: while provider.models is
    observed unavailable a semantic search answers by words and sends nothing to the
    runtime; every other state fails open; each call reads afresh; a lexical query never
    reads the observation."""
    from backend.u8_outward import search_breaker

    for state in ("available", "degraded", "unknown", "stale", "unavailable"):
        standin = Runtime()
        answer = search_for(breaker_search(transactions, search_breaker(
            embeddings(standin), models_reader(state))))
        if state == "unavailable":
            assert (answer["outcome"], answer["effectiveModeId"]) == ("degraded", "lexical")
            assert "semantic-search-unavailable" in answer["limitations"]
            assert standin.requests == []
        else:
            assert (answer["outcome"], answer["effectiveModeId"]) == (
                "complete", "semantic"), state
            assert "semantic-search-unavailable" not in answer["limitations"], state
            assert len(standin.calls("/api/embed")) == 1, state

    standin, states = Runtime(), ["unavailable", "available"]
    search = breaker_search(transactions, search_breaker(
        embeddings(standin), lambda: {"provider.models": {"state": states.pop(0)}}))
    first = search_for(search)
    assert (first["outcome"], standin.requests) == ("degraded", [])
    second = search_for(search)
    assert second["outcome"] == "complete" and len(standin.calls("/api/embed")) == 1

    standin, calls = Runtime(), []
    lexical = search_for(breaker_search(transactions, search_breaker(
        embeddings(standin), models_reader("unavailable", calls))), mode="lexical")
    assert lexical["effectiveModeId"] == "lexical"
    assert (calls, standin.requests) == ([], [])

    embedder = embeddings(Runtime())
    assert search_breaker(embedder, None) is embedder


def breaker_profile_root(tmp_path, name: str):
    """A stub production profile root, as the import test below builds it."""
    import os

    root = tmp_path / name
    (root / "corpus-files").mkdir(parents=True, mode=0o700)
    (root / "cursor-key").mkdir(mode=0o700)
    descriptor = os.open(root / "cursor-key" / "search-cursor.key",
                         os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(secrets.token_bytes(32))
    return root


def test_production_wires_searchs_breaker_over_the_corpus_embedder(
        tmp_path, transactions, monkeypatch):
    """L3-7, BR7.1: every production profile wires search's breaker over the corpus's
    bare embedder, once, whatever ServiceOperations is; a synthetic profile does not."""
    from types import SimpleNamespace

    from backend import u8_host
    from backend.modules.export import notion_session
    from backend.u8_outward import ObservedSearchEmbeddings, production_corpus

    monkeypatch.setattr(notion_session, "_INSTALLED_GATE", {})
    standin = Runtime()
    profile = SimpleNamespace(is_production=True,
                              root=breaker_profile_root(tmp_path, "profile"),
                              realm="production")
    parts = production_corpus(SimpleNamespace(profile=profile, transactions=transactions),
                              runtime=runtime(standin))
    down = models_reader("unavailable")
    u8_host.wire_adapters({"paper-corpus": parts}, profile)
    assert parts["search"].embedder is parts["embedder"]
    u8_host.wire_adapters({"paper-corpus": parts}, profile, capability_states=down)
    assert isinstance(parts["search"].embedder, ObservedSearchEmbeddings)
    assert parts["search"].embedder.embedder is parts["embedder"]
    assert isinstance(parts["embedder"], LocalEmbeddings)
    u8_host.wire_adapters({"paper-corpus": parts}, profile, capability_states=down)
    assert parts["search"].embedder.embedder is parts["embedder"]  # one layer
    answer = search_for(parts["search"])
    assert (answer["outcome"], answer["effectiveModeId"]) == ("degraded", "lexical")
    assert standin.requests == []

    synthetic = SimpleNamespace(is_production=False, realm="synthetic")
    other = production_corpus(SimpleNamespace(
        profile=SimpleNamespace(is_production=True,
                                root=breaker_profile_root(tmp_path, "synthetic"),
                                realm="production"),
        transactions=transactions), runtime=runtime(Runtime()))
    u8_host.wire_adapters({"paper-corpus": other}, synthetic, capability_states=down)
    assert other["search"].embedder is other["embedder"]


# 4. Every embedding call passes keep_alive: -1, every research-model call 300 seconds -----


def test_each_model_call_passes_its_own_keep_alive_and_the_research_model_is_never_pinned():
    standin = Runtime()
    shared = runtime(standin)
    LocalEmbeddings(shared, keep_alive=-1, batch=16).embed_batches(
        [f"chunk {i}" for i in range(20)])
    shared.pin_resident(EMBEDDING_MODEL)
    ProductionAssistanceExecutor(shared, ready=lambda: True).run(bound(), time.monotonic() + 60)
    shared.infer(model=GENERATION_MODEL, body={"model": GENERATION_MODEL, "messages": [],
                                               "keep_alive": 0}, timeout=5)
    embeds, chats = standin.calls("/api/embed"), standin.calls("/api/chat")
    # Two import batches and the re-pin keep the search model loaded; the executor's chat
    # and one direct chat let the research model unload after 300 idle seconds.
    assert len(embeds) == 3 and {item["keep_alive"] for item in embeds} == {-1}
    assert len(chats) == 2 and {item["keep_alive"] for item in chats} == {300}
    assert model_runtime.KEEP_ALIVE == {EMBEDDING_MODEL: -1, GENERATION_MODEL: 300}
    # Imports go 16 chunks a request.
    assert [len(item["input"]) for item in embeds[:2]] == [16, 4]
    before = len(standin.requests)
    with pytest.raises(ValueError, match="search model"):
        shared.pin_resident(GENERATION_MODEL)
    assert len(standin.requests) == before


def test_a_slow_tags_answer_still_ends_a_querys_embedding_by_its_2_second_bound():
    standin = Runtime()
    embeddings(standin).embed_query("attention")
    tags = [r for r in standin.requests if r.url.path == "/api/tags"]
    # One evidence check per request, inside the query's own 2 s.
    assert len(tags) == 1 and 0 < tags[0].extensions["timeout"]["read"] <= 2.0
    slow = Runtime()
    original = slow.handle

    def handle(request):
        if request.url.path == "/api/tags":
            slow.requests.append(request)
            raise httpx.ReadTimeout("the tags answer came after the bound")
        return original(request)

    slow.handle = handle
    with pytest.raises(EmbeddingTimeout):
        embeddings(slow).embed_query("attention")
    [tag] = slow.requests
    assert 0 < tag.extensions["timeout"]["read"] <= 2.0 and slow.calls("/api/embed") == []


def test_work_starts_its_deadline_only_after_it_takes_the_lane():
    import threading

    from backend.modules.summarization.model_runtime import LaneBusy

    now = [1000.0]
    shared = runtime(Runtime(), clock=lambda: now[0])
    taken, release, deadlines = threading.Event(), threading.Event(), []

    def hold():
        with shared.work(30, wait=0):
            taken.set()
            release.wait(5)
            now[0] += 7.0  # the holder ran for 7 s

    holder = threading.Thread(target=hold)
    holder.start()
    assert taken.wait(5)
    with pytest.raises(LaneBusy):
        with shared.work(10, wait=0):
            pass

    def wait_for_it():
        with shared.work(10) as deadline:
            deadlines.append(deadline)

    waiter = threading.Thread(target=wait_for_it)
    waiter.start()
    release.set()
    holder.join(5)
    waiter.join(5)
    assert deadlines == [1017.0]  # 7 s waiting for the lane did not shorten its 10 s
    # A work item nested in the one this thread holds keeps the outer deadline.
    with shared.work(20) as outer, shared.work(90) as inner:
        assert inner == outer == 1027.0
    with pytest.raises(ValueError):
        with shared.work(91):
            pass


def test_the_lanes_holder_hands_its_work_item_to_exactly_one_other_thread():
    import threading

    from backend.modules.summarization.model_runtime import LaneBusy

    now = [500.0]
    standin = Runtime()
    shared = runtime(standin, clock=lambda: now[0])
    with pytest.raises(ValueError, match="holder"):
        with shared.hand_over():
            pass
    seen: dict = {}

    def executor():
        # The worker's own thread: it takes the handed work item, its nested work and
        # requests too, without a second lane.
        with shared.work(90) as deadline, shared.work(30) as nested:
            seen["deadline"], seen["nested"] = deadline, nested
            shared.infer(model=EMBEDDING_MODEL, body={"model": EMBEDDING_MODEL,
                                                      "input": ["x"]}, timeout=5)

    def intruder():
        try:
            with shared.work(5, wait=0):
                seen["intruder"] = "entered"
        except LaneBusy:
            seen["intruder"] = "busy"

    with shared.work(60) as held, shared.hand_over() as handed:
        assert handed == held == 560.0
        with pytest.raises(ValueError, match="already"):
            with shared.hand_over():
                pass
        first = threading.Thread(target=executor)
        first.start()
        first.join(5)
        second = threading.Thread(target=intruder)
        second.start()
        second.join(5)
    assert seen == {"deadline": 560.0, "nested": 530.0, "intruder": "busy"}
    assert len(standin.calls("/api/embed")) == 1
    # Once handed back, the lane is free again for anyone.
    intruder()
    assert seen["intruder"] == "entered"


@pytest.mark.parametrize("marker", [
    {},
    {"models": {**MODEL_PINS, GENERATION_MODEL: "0" * 64}, "purposes": {"research": "a" * 64}},
    {"purposes": {"oracle": "a" * 64}},
    {"purposes": {"research": "a" * 63}},
    {"recordedAt": "2999-01-01T00:00:00+00:00"},
    {"recordedAt": "2026-10-24T00:00:00"},
    {"purposes": {}},
    {"evidenceSha256": "a" * 64},
])
def test_the_readiness_marker_refuses_every_other_shape(tmp_path, marker):
    import datetime as dt

    from backend.u8_outward import model_readiness

    value = {"models": MODEL_PINS, "purposes": {"research": "a" * 64},
             "recordedAt": dt.datetime.now(dt.UTC).isoformat(), **marker}
    if marker == {}:
        value = {}
    profile = marker_profile(tmp_path, value)
    assert model_readiness(profile, "research") is False


def test_the_readiness_marker_accepts_the_purposes_it_lists(tmp_path):
    import datetime as dt

    from backend.u8_outward import model_readiness, readiness_recorded

    profile = marker_profile(tmp_path, {
        "models": MODEL_PINS, "purposes": {"assistance": "b" * 64},
        "recordedAt": dt.datetime.now(dt.UTC).isoformat()})
    assert model_readiness(profile, "assistance") is True
    assert model_readiness(profile, "research") is False  # its own review is not recorded
    assert readiness_recorded(profile)() is True
    with pytest.raises(ValueError):
        model_readiness(profile, "search")
    missing = SimpleProfile(tmp_path / "absent")
    assert model_readiness(missing, "assistance") is False


class SimpleProfile:
    def __init__(self, root):
        self.root = root


def marker_profile(tmp_path, value: dict):
    import os

    root = tmp_path / "profile"
    (root / "evidence").mkdir(parents=True, mode=0o700)
    path = root / "evidence" / "model-readiness.json"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump(value, stream)
    return SimpleProfile(root)


def test_the_assistance_executor_reports_its_availability_cached_for_30_seconds():
    now = [0.0]
    standin = Runtime()
    ready = [False]
    executor = ProductionAssistanceExecutor(runtime(standin), ready=lambda: ready[0],
                                            clock=lambda: now[0])
    assert executor.available() is False and standin.requests == []
    ready[0], now[0] = True, 31.0
    assert executor.available() is True and len(standin.requests) == 1
    now[0] = 50.0
    assert executor.available() is True and len(standin.requests) == 1
    standin.digests[GENERATION_MODEL] = "3" * 64
    now[0] = 62.0
    assert executor.available() is False


def test_the_runtime_is_plain_http_on_loopback_and_holds_one_job_at_a_time():
    for address in ("https://127.0.0.1:11434", "http://localhost:11434",
                    "http://10.0.0.2:11434", "http://127.0.0.1:11434/api"):
        with pytest.raises(ValueError):
            SharedModelRuntime(base_url=address)
    standin = Runtime()
    shared = runtime(standin)
    import threading

    with shared.work(seconds=5):
        blocked: list = []
        other = threading.Thread(target=lambda: blocked.append(
            pytest.raises(TimeoutError, shared.infer, model=EMBEDDING_MODEL,
                          body={"model": EMBEDDING_MODEL, "input": ["x"]}, timeout=0.2)))
        other.start()
        other.join(5)
    assert blocked and standin.calls("/api/embed") == []


# 5. No model call is made in a synthetic profile ---------------------------------------------


def test_no_model_call_is_made_in_a_synthetic_profile(realm):
    from backend.modules.discovery.u8_search import StandinEmbeddings
    from backend.modules.summarization.u3_provider import SyntheticAssistanceExecutor
    from backend.u3_policy import QUERY_VOCABULARY, SEARCH_POLICY
    from backend.u8_host import compose

    with pytest.raises(RuntimeError, match=REFUSED):
        model_runtime.network_transport()  # the guard holds for the whole run
    composition = compose(realm)
    try:
        corpus = composition.parts["paper-corpus"]
        assert isinstance(corpus["dispatch"].executor, SyntheticAssistanceExecutor)
        assert isinstance(corpus["search"].embedder, StandinEmbeddings)
        answer = corpus["search"].search(None, {"query": {
            "query": "attention", "modeId": "semantic", "orderId": "relevance",
            "filters": [], "vocabularyRevision": QUERY_VOCABULARY,
            "policyRef": SEARCH_POLICY}})
        assert answer["effectiveModeId"] == "semantic"
        assert "semantic-search-unavailable" not in answer["limitations"]
    finally:
        composition.close()


# 6. Imports embed in separate requests of 16 chunks (Step 55(d)) ------------------------------


def test_imports_embed_in_separate_requests_of_sixteen_chunks(tmp_path, transactions):
    """A stub production profile under a temporary root (the start checks' allowed
    double), built as `test_corpus_limits.py`'s composition test builds it, with this
    file's stand-in runtime passed as `runtime=`."""
    import os
    import secrets
    from types import SimpleNamespace

    from backend.u8_outward import production_corpus

    root = tmp_path / "profile"
    (root / "corpus-files").mkdir(parents=True, mode=0o700)
    # The search cursor key in its own folder, as the composition reads it (U8 plan Step
    # 73(f), L1-4).
    (root / "cursor-key").mkdir(mode=0o700)
    descriptor = os.open(root / "cursor-key" / "search-cursor.key",
                         os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(secrets.token_bytes(32))
    profile = SimpleNamespace(is_production=True, root=root, realm="production")
    standin = Runtime()
    parts = production_corpus(SimpleNamespace(profile=profile, transactions=transactions),
                              runtime=runtime(standin))
    embedder = parts["embedder"]
    assert (embedder.batch, embedder.keep_alive) == (16, -1)
    vectors = embedder.embed_batches([f"chunk {index}" for index in range(40)])
    assert len(vectors) == 40
    embeds = standin.calls("/api/embed")
    assert [len(item["input"]) for item in embeds] == [16, 16, 8]
    assert [item["keep_alive"] for item in embeds] == [-1, -1, -1]


# 7. The runtime's own circuit breaker over provider.models (U8 plan Step 162(a); L4-11) -------


class ResidentRuntime(Runtime):
    """The stand-in runtime, answering `/api/ps` too."""

    def handle(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/ps":
            self.requests.append(request)
            return httpx.Response(200, json={"models": [
                {"name": EMBEDDING_MODEL, "size": 1_200_000_000}]})
        return super().handle(request)


def fixed_state(state: str, calls: list | None = None):
    """A fixed reader of provider.models' state, bound to its state when made; `calls`,
    when given, counts each read."""

    def read() -> str:
        if calls is not None:
            calls.append(state)
        return state

    return read


def unreadable_state():
    raise RuntimeError("the observations cannot be read")


# Every operation of the runtime that sends a request.
RUNTIME_OPERATIONS = {
    "tags": lambda shared: shared.tags(),
    "verify": lambda shared: shared.verify(EMBEDDING_MODEL),
    "infer-embedding": lambda shared: shared.infer(
        model=EMBEDDING_MODEL, body={"model": EMBEDDING_MODEL, "input": ["x"]}, timeout=5),
    "infer-generation": lambda shared: shared.infer(
        model=GENERATION_MODEL, body={"model": GENERATION_MODEL, "messages": []}, timeout=5),
    "resident": lambda shared: shared.resident(),
    "pin_resident": lambda shared: shared.pin_resident(),
}


def event_lines(caplog, event: str) -> list[dict]:
    from backend.log_events import EVENTS_LOGGER

    lines = [json.loads(record.getMessage()) for record in caplog.records
             if record.name == EVENTS_LOGGER]
    return [line for line in lines if line["event"] == event]


def test_no_runtime_operation_sends_a_request_while_provider_models_is_observed_unavailable(
        caplog):
    """Reliability-design § 10 (lines 133-137), L4-11: the breaker sits in the one runtime
    client. While provider.models reads `unavailable`, each operation that sends a
    request raises the held refusal before any client is built; every other state, and a
    read that raises, sends the request; each operation reads the state once."""
    import logging

    from backend.log_events import EVENTS_LOGGER
    from backend.modules.summarization.model_runtime import ProviderHeld, RuntimeUnreachable

    for name, operation in RUNTIME_OPERATIONS.items():
        standin, calls = ResidentRuntime(), []
        shared = runtime(standin, observed=fixed_state("unavailable", calls))
        assert shared.held() is True
        calls.clear()
        with pytest.raises(ProviderHeld) as refused:
            operation(shared)
        assert isinstance(refused.value, RuntimeUnreachable), name
        assert refused.value.reason == "provider-held", name
        assert standin.requests == [], name  # nothing reached the transport
        assert calls == ["unavailable"], name  # one read for the whole operation
        for state in ("available", "degraded", "unknown", "stale"):
            standin, calls = ResidentRuntime(), []
            shared = runtime(standin, observed=fixed_state(state, calls))
            operation(shared)
            assert standin.requests, (name, state)  # the request was sent
            assert calls == [state], (name, state)
        standin = ResidentRuntime()
        shared = runtime(standin, observed=unreadable_state)
        with caplog.at_level(logging.ERROR, logger=EVENTS_LOGGER):
            caplog.clear()
            operation(shared)
            assert standin.requests, name
            [line] = event_lines(caplog, "breaker.state-unreadable")
        assert (line["reason"], line["errorType"]) == ("provider.models", "RuntimeError"), name
    # Without a reader the runtime behaves as built.
    bare = runtime(ResidentRuntime())
    assert bare.observed is None and bare.held() is False


def test_production_installs_the_models_breaker_on_the_shared_runtime(
        tmp_path, transactions, monkeypatch):
    """L4-11, BR7.1: every production profile sets the shared runtime's reader to
    provider.models' derived state; with no derived states, and in a synthetic profile,
    none is set; a second wiring installs nothing new. This shows which object is wired,
    not what it does."""
    from types import SimpleNamespace

    from backend import u8_host
    from backend.modules.export import notion_session
    from backend.u8_outward import ObservedState, production_corpus

    monkeypatch.setattr(notion_session, "_INSTALLED_GATE", {})
    profile = SimpleNamespace(is_production=True,
                              root=breaker_profile_root(tmp_path, "profile"),
                              realm="production")
    parts = production_corpus(SimpleNamespace(profile=profile, transactions=transactions),
                              runtime=runtime(Runtime()))
    shared = parts["runtime"]
    assert parts["embedder"].runtime is shared and parts["dispatch"].executor.runtime is shared
    down = models_reader("unavailable")
    u8_host.wire_adapters({"paper-corpus": parts}, profile)
    assert shared.observed is None  # no derived states: nothing is installed
    u8_host.wire_adapters({"paper-corpus": parts}, profile, capability_states=down)
    first = shared.observed
    assert first == ObservedState("provider.models", down) and shared.held() is True
    u8_host.wire_adapters({"paper-corpus": parts}, profile, capability_states=down)
    assert shared.observed is first  # a second wiring changes nothing

    synthetic = SimpleNamespace(is_production=False, realm="synthetic")
    other = production_corpus(SimpleNamespace(
        profile=SimpleNamespace(is_production=True,
                                root=breaker_profile_root(tmp_path, "synthetic"),
                                realm="production"),
        transactions=transactions), runtime=runtime(Runtime()))
    u8_host.wire_adapters({"paper-corpus": other}, synthetic, capability_states=down)
    assert other["runtime"].observed is None


def test_while_provider_models_is_observed_unavailable_the_assistance_executor_is_not_available(  # noqa: E501
        realm):
    """L4-11: the executor's availability asks the breaker first and afresh, outside its
    kept answer, so the lane claims nothing; a run is refused before any request. The
    breaker is opened by a stored observation in a production stand-in's own database,
    derived as the composition derives it (`readiness.observed_state`) at the real clock,
    which is the clock the observation is stamped with."""
    import datetime as dt

    from backend.modules.operations.observation_store import ObservationStore
    from backend.modules.operations.observations import Observations
    from backend.modules.operations.readiness import observed_state
    from backend.u8_policy import PRODUCTION_OPERATIONS
    from backend.u8_registry import CAPABILITY_BY_ID
    from tests.u8_service_operations_integration.host_flows import production_stand_in

    capability = "provider.models"
    producer = CAPABILITY_BY_ID[capability].producer
    with production_stand_in(realm) as standin:
        store = ObservationStore(standin.transactions)

        def stored_state() -> str:
            row = store.latest([capability]).get(capability)
            return observed_state(capability, row, dt.datetime.now(dt.UTC),
                                  PRODUCTION_OPERATIONS).state

        def observe(outcome: str, reason: str | None = None) -> None:
            observations = Observations(store)
            row = observations.make(capability, producer, outcome, reason=reason,
                                    observed_at=dt.datetime.now(dt.UTC))
            assert observations.record(producer, [row])["written"] == 1

        now = [0.0]
        standin_runtime = Runtime()
        executor = ProductionAssistanceExecutor(
            runtime(standin_runtime, observed=stored_state), ready=lambda: True,
            clock=lambda: now[0])
        assert stored_state() == "unknown"
        assert executor.available() is True and len(standin_runtime.requests) == 1
        observe("unavailable", "runtime-unreachable")
        now[0] = 5.0  # inside the kept answer's 30 s
        assert stored_state() == "unavailable" and executor.available() is False
        assert len(standin_runtime.requests) == 1  # no request, over a kept True answer
        with pytest.raises(ExecutionRefused) as refused:
            executor.run(bound(), time.monotonic() + 60)
        assert refused.value.reason == "dependency-unavailable"
        assert len(standin_runtime.requests) == 1 and executor.stopped()
        now[0] = 40.0  # past the kept answer too: still nothing is asked
        assert executor.available() is False and len(standin_runtime.requests) == 1
        observe("available")  # the probe passed: calls resume
        assert executor.available() is True and len(standin_runtime.requests) == 2
        prepared = executor.run(bound(), time.monotonic() + 60)
        assert prepared.provenance["modelDigest"] == MODEL_PINS[GENERATION_MODEL]


class FixedGate:
    """A fixed provider gate, an allowed double: every provider `active` in rehearsal."""

    mode = "rehearsal"

    def state(self, provider: str) -> str:
        return "active"


def account_mail_as_production_wires_it(tmp_path, capability_states):
    """Production's Resend account mail, built by `wire_adapters` itself on a stub
    production profile with a fixed gate."""
    import os
    from types import SimpleNamespace
    from uuid import uuid4

    from backend import u8_host

    root = tmp_path / "mail-profile"
    root.mkdir(mode=0o700)
    descriptor = os.open(root / "private-environment.json",
                         os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump({"resendApiKey": "re_" + uuid4().hex[:24],  # generated per run (L1-36)
                   "accountMailSender": "DocSuri <no-reply@x.example>"}, stream)
    profile = SimpleNamespace(is_production=True, root=root,
                              origin="https://docsuri.rvnnt.dev")
    entry = SimpleNamespace(account_mail=None, mail=None)
    parts = {"account-controls": {"entry": entry},
             "service-operations": {"activation": FixedGate(), "allowance": object()}}
    u8_host.wire_adapters(parts, profile, capability_states=capability_states)
    return entry


def test_a_state_read_that_raises_reads_unknown_for_every_breaker(
        tmp_path, transactions, monkeypatch, caplog):
    """L4-11, review 08's R-17: a state read that raises reads `unknown` at every breaker,
    which holds nothing, and logs one event for each read. Search then answers by meaning
    instead of failing the query, and account mail, wired as production wires it, is not
    held and does not raise."""
    import logging

    from backend.log_events import EVENTS_LOGGER
    from backend.modules.accounts.integrations.account_mail import ResendAccountMail
    from backend.modules.export import notion_session
    from backend.u8_outward import (
        ObservedProviderGate,
        ObservedState,
        digest_gate,
        notion_gate,
        read_state,
        search_breaker,
        sign_in_gate,
        state_reader,
    )

    monkeypatch.setattr(notion_session, "_INSTALLED_GATE", {})
    reads: list[str] = []

    def broken() -> dict:
        reads.append("read")
        raise RuntimeError("the observations cannot be read")

    activation = FixedGate()
    with caplog.at_level(logging.ERROR, logger=EVENTS_LOGGER):
        assert read_state("provider.models", broken) == "unknown"
        # Search: the query is embedded and answers by meaning.
        standin = Runtime()
        answer = search_for(breaker_search(transactions, search_breaker(
            embeddings(standin), broken)))
        assert (answer["outcome"], answer["effectiveModeId"]) == ("complete", "semantic")
        assert len(standin.calls("/api/embed")) == 1
        # Notion's, the sign-in and the digest gates pass the activation's answer through.
        assert notion_gate(activation, broken).state("notion") == "active"
        sign_in = sign_in_gate(activation, broken)
        assert isinstance(sign_in, ObservedProviderGate)
        assert [sign_in.state("google"), sign_in.state("orcid")] == ["active", "active"]
        digests = digest_gate(activation)
        digests.bind(state_reader(broken))
        assert digests.state("resend") == "active"
        # The runtime's reader, as the composition installs it.
        shared = runtime(Runtime(), observed=ObservedState("provider.models", broken))
        assert shared.held() is False
        # Account mail, wired as production wires it.
        entry = account_mail_as_production_wires_it(tmp_path, broken)
        assert isinstance(entry.account_mail, ResendAccountMail)
        assert entry.account_mail.held_for_all() is False
        # The tools' reader (the import program and `research-review`): a profile whose
        # store cannot be opened reads `unknown`, with the same event.
        from types import SimpleNamespace

        from backend.modules.operations.readiness import stored_state_reader
        from backend.u8_policy import PRODUCTION_OPERATIONS

        unopened = SimpleNamespace(root=tmp_path / "no-such-profile")
        read, close = stored_state_reader(
            unopened, "provider.models", lambda: None, PRODUCTION_OPERATIONS,
            process="maintenance")
        assert read() == "unknown"
        close()
        events = event_lines(caplog, "breaker.state-unreadable")
    # One event for each read: the helper, search, Notion, Google, ORCID, the digest
    # gate, the runtime, account mail and the tools' reader.
    assert len(reads) == 8 and len(events) == 9
    assert [line["reason"] for line in events] == [
        "provider.models", "provider.models", "provider.notion", "provider.google",
        "provider.orcid", "provider.resend", "provider.models", "provider.resend",
        "provider.models"]
    assert events[-1]["errorType"] != "RuntimeError"  # the store's own error, by type
    events = events[:-1]
    assert {line["errorType"] for line in events} == {"RuntimeError"}
