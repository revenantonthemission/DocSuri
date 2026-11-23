"""memberA's ready paper-assistance job for the isolation journeys (U8 plan Step 167; L4-13).

The isolation journey asks every owner list and read as its owner first. One of memberA's
records cannot be made through the browser inside the phase's bound: a paper-assistance
job with a result. The realm's fixtures make it here, as `u8_fixtures.ready_novelty` makes
the research one: through PaperAssistance's own catalog, admission, repository and
dispatch, under memberA's fixture session, paid by the fixture account's grant, and
executed by the realm's labelled synthetic executor.

The job's paper is the fixture's own: one eligible `local-research` version whose content
carries two chunks, written through the corpus owner's login. It has no projection, so
search never finds it.

`assistance_job` is restartable: given the record of an earlier run whose result its
owner still reads, it returns that record; otherwise it makes a new paper and a new job.
"""

from __future__ import annotations

SOURCE_URL = "https://fixture.example.com/assistance-paper"
SECTIONS = (
    ("intro", "Introduction", "This synthetic paper states one bound for the isolation journey."),
    ("result", "Result", "The bound holds for every owner, and no other owner reads it."),
)
# One pending job needs one pass; the others cover a job the realm's worker holds first.
DISPATCH_PASSES = 8


def _content(paper_id: str) -> dict:
    import hashlib

    return {"document": {"title": paper_id}, "chunks": [
        {"anchor": anchor, "section": section, "text": text, "kind": "paragraph",
         "textHash": hashlib.sha256(text.encode()).hexdigest()}
        for anchor, section, text in SECTIONS]}


def _write_paper(transactions) -> str:
    """The fixture's paper and its one eligible version; returns the version's id."""
    import secrets
    import uuid

    from psycopg.types.json import Jsonb

    paper_id = "u8-assist-" + secrets.token_hex(6)
    version_id = f"{paper_id}-v1"

    def write(conn) -> None:
        conn.execute("INSERT INTO corpus.paper(id,title,authors,metadata) "
                     "VALUES(%s,'Synthetic assistance paper','[]','{}')", (paper_id,))
        conn.execute(
            "INSERT INTO corpus.version(id,paper_id,source_url,source_hash,version_label,"
            "private_path,eligible,purpose,eligibility_revision,provenance,content) VALUES"
            "(%s,%s,%s,%s,'v1','fixture',true,'local-research',%s,'{}',%s)",
            (version_id, paper_id, SOURCE_URL, secrets.token_hex(32), uuid.uuid4(),
             Jsonb(_content(paper_id))))

    transactions.run("corpus", write)
    return version_id


def _still_read(repository, authority, known: dict | None) -> bool:
    """Whether `known` names a job whose result its owner still reads."""
    from uuid import UUID

    if not known or not isinstance(known.get("jobId"), str):
        return False
    try:
        reference = repository.result_reference(authority, UUID(known["jobId"]))
    except (ValueError, PermissionError):
        return False
    return reference is not None and reference["resultId"] == known.get("resultId")


def _request(catalog, source: dict, glossary_revision: str) -> dict:
    """The first offered option of the paper's own catalog, bound as the page binds it."""
    options = catalog.options()
    option = options["options"][0]
    return {"paper": catalog.paper, "contentRevision": catalog.content_revision,
            "contentHash": source["source_hash"], "operation": option["operation"],
            "optionId": option["optionId"], "optionsRevision": catalog.revision,
            "glossaryRevision": str(glossary_revision), "processingPolicy": options["policy"]}


def assistance_job(transactions, files, authority, known: dict | None) -> dict:
    """A ready assistance job for `authority`'s account, with its result:
    `{"jobId", "paper", "resultId", "revision", "contentHash"}`. Returns `known` when its
    owner still reads its result."""
    import uuid

    from backend.modules.corpus.repository import CorpusRepository
    from backend.modules.plans.u8_usage import use_complete_usage
    from backend.modules.summarization.guarded_repository import GuardedAssistanceRepository
    from backend.modules.summarization.requests import AssistanceRequests
    from backend.modules.summarization.u3_catalog import catalog_for
    from backend.modules.summarization.u3_provider import SyntheticAssistanceExecutor
    from backend.u8_job_lines import CompleteAssistanceDispatch

    repository = GuardedAssistanceRepository(transactions, files)
    if _still_read(repository, authority, known):
        return known
    corpus = CorpusRepository(transactions, files=None)
    dispatch = use_complete_usage(
        CompleteAssistanceDispatch(transactions, files, SyntheticAssistanceExecutor()),
        transactions)
    source = corpus.read(_write_paper(transactions))
    catalog = catalog_for(source, provider_ready=True)
    if catalog is None:
        raise ValueError("the fixture's assistance paper offers no option")
    requests = AssistanceRequests(
        dispatch.admission, corpus, lambda value: catalog_for(value, provider_ready=True))
    glossary = repository.current_glossary(authority)["revision"]
    accepted = requests.submit(authority, uuid.uuid4(), _request(catalog, source, glossary))
    reference = repository.result_reference(authority, accepted["id"])
    for _ in range(DISPATCH_PASSES):
        if reference is not None:
            break
        dispatch.run_once(limit=1)
        reference = repository.result_reference(authority, accepted["id"])
    if reference is None:
        raise ValueError("the synthetic assistance execution produced no ready result")
    return {"jobId": str(accepted["id"]), "paper": catalog.paper,
            "resultId": reference["resultId"], "revision": reference["revision"],
            "contentHash": reference["contentHash"]}
