"""Explicit, restartable U6 browser fixture provisioning in its owned realm.

Two synthetic accounts (memberA exports, memberB checks isolation), two synthetic
papers, a ready novelty result for memberA produced through U4's own service and
synthetic execution (never by writing research tables), and `fake-notion.json`, the
fake Notion's run-bound scenario:

- shared pages, including an untitled one and two same-titled ones told apart by their
  parent, plus a shared page the connection cannot read;
- for each browser spec that cancels or settles (`journeys.spec.ts`, `keyboard.spec.ts`
  and the dialogs `accessibility.spec.ts` opens) its own cancel destination and settle
  destination, so no spec depends on another's leftovers. A cancel destination answers
  its first two page requests normally (the preview's destination read and the approve
  call's binding read) and every later one with 503, so the lane's pre-write check
  cannot complete and the export waits as accepted until the journey cancels it. A
  settle destination answers its create with 504; from then on its children answer
  503, so every scan records listing-unavailable and settlement is offered once the
  delegated clock passes the settling wait.

The synthetic token only the fake accepts lives in `browser-fixtures.json` (0600). No
real user data, external content or provider call is involved, and secret fixture
bytes never print. `advance-clock` moves the delegated export clock one hour forward.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import secrets
import sys
from contextlib import nullcontext
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "ops/src"))

from psycopg.types.json import Jsonb

from backend.local_profile import private_bytes
from backend.transactions import Authority, OwnerTransactions
from scripts import verify_docsuri_u6 as runner

FIXTURE_VERSION = "u6-browser-v1"
SCENARIO_FILE = "fake-notion.json"
CLOCK_FILE = "export-fixture-clock.json"
CLOCK_STEP = dt.timedelta(hours=1)
CLOCK_AHEAD = dt.timedelta(days=2)
NOVELTY_STEPS = 20
TOKEN = re.compile(r"u6-synthetic-[0-9a-f]{40}")
PAPERS = (
    {
        "paperId": "u6-paper-alpha",
        "versionId": "u6-paper-alpha/v1",
        "title": "Synthetic export study alpha",
        "text": "Synthetic fixture alpha: an approved export writes one page per explicit approval. This text is a test fixture, not a published study.",
    },
    {
        "paperId": "u6-paper-beta",
        "versionId": "u6-paper-beta/v1",
        "title": "Synthetic export study beta",
        "text": "Synthetic fixture beta: an unclear export is checked before the owner settles it. This example is a test fixture.",
    },
)
SPECS = {"journeys": "여정", "keyboard": "키보드", "accessibility": "접근성"}
WORKSPACE_NAME = "DocSuri 합성 워크스페이스"
PRACTICE_PAGE = "DocSuri 내보내기 연습장"
SCENARIO_NAMES = {
    "practicePage": PRACTICE_PAGE,
    "untitledPage": None,
    "sameTitle": "연구 노트",
    "unreadablePage": "읽을 수 없는 페이지",
    "specs": {
        spec: {"cancel": f"취소 확인 · {label}", "settle": f"직접 확인 · {label}"}
        for spec, label in SPECS.items()
    },
}
NOVELTY_TOPIC = "합성 내보내기 확인 주제"


def stable_id(run_id: str, purpose: str) -> UUID:
    return uuid5(NAMESPACE_URL, run_id + ":u6-browser:" + purpose)


def page_id(run_id: str, purpose: str) -> str:
    return stable_id(run_id, "page:" + purpose).hex


def _account_valid(profile, key: str, record) -> bool:
    return (
        isinstance(record, dict)
        and set(record) == {"email", "password", "accountId"}
        and record["accountId"] == str(stable_id(profile.run_id, key))
        and record["email"] == f"{key.lower()}@u6.fixture.example.com"
        and isinstance(record["password"], str)
        and 24 <= len(record["password"]) <= 100
    )


def _novelty_valid(value) -> bool:
    keys = {"jobId", "contextId", "artifactId", "revision", "contentHash"}
    return value is None or (
        isinstance(value, dict)
        and set(value) == keys
        and all(isinstance(value[key], str) and value[key] for key in keys)
    )


def _check_record(profile, value) -> dict:
    if (
        not isinstance(value, dict)
        or value.get("runId") != profile.run_id
        or value.get("fixtureVersion") != FIXTURE_VERSION
        or value.get("state") not in {"prepared", "ready"}
        or set(value.get("accounts", {})) != {"memberA", "memberB"}
        or value.get("papers") != list(PAPERS)
        or value.get("scenario") != SCENARIO_NAMES
        or not isinstance(value.get("notionToken"), str)
        or TOKEN.fullmatch(value["notionToken"]) is None
        or not _novelty_valid(value.get("novelty"))
    ):
        raise runner.Refused("browser fixture identity differs; preserve for reconciliation")
    if not all(_account_valid(profile, key, value["accounts"][key]) for key in value["accounts"]):
        raise runner.Refused("browser fixture account binding differs")
    if value["state"] == "ready" and value.get("novelty") is None:
        raise runner.Refused("acknowledged fixture novelty binding is missing")
    return value


def fixture_record(profile) -> dict:
    target = profile.root / "browser-fixtures.json"
    if target.exists() or target.is_symlink():
        return _check_record(profile, json.loads(private_bytes(target)))
    value = {
        "runId": profile.run_id,
        "fixtureVersion": FIXTURE_VERSION,
        "state": "prepared",
        "accounts": {
            key: {
                "email": f"{key.lower()}@u6.fixture.example.com",
                "password": "U6!" + secrets.token_urlsafe(24),
                "accountId": str(stable_id(profile.run_id, key)),
            }
            for key in ("memberA", "memberB")
        },
        "papers": list(PAPERS),
        "scenario": SCENARIO_NAMES,
        "notionToken": "u6-synthetic-" + secrets.token_hex(20),
        "novelty": None,
    }
    # Persist credentials before their first database write; a retry cannot invent a
    # different password or token after an interrupted acknowledgement.
    runner.private_json(target, value)
    return value


def seed_accounts(conn, fixtures: dict, hashes: dict, run_id: str) -> None:
    identifiers = [UUID(account["accountId"]) for account in fixtures["accounts"].values()]
    conn.execute("SELECT pg_advisory_xact_lock(hashtext('u6-browser-fixture-accounts'))")
    existing = conn.execute(
        "SELECT id,email FROM accounts.account WHERE id=ANY(%s)", (identifiers,)
    ).fetchall()
    count = conn.execute("SELECT count(*) AS count FROM accounts.account").fetchone()["count"]
    if count + len(identifiers) - len(existing) > 20:
        raise runner.Refused("finite account fixture allocation exhausted")
    expected = {UUID(item["accountId"]): item["email"] for item in fixtures["accounts"].values()}
    if any(expected[row["id"]] != row["email"] for row in existing):
        raise runner.Refused("existing fixture account identity differs")
    for key, account in fixtures["accounts"].items():
        conn.execute(
            "INSERT INTO accounts.account(id,email,password_hash,verified,active,authority_revision,display_name) "
            "VALUES(%s,%s,%s,true,true,%s,%s) ON CONFLICT(id) DO NOTHING",
            (
                UUID(account["accountId"]),
                account["email"],
                hashes[key],
                stable_id(run_id, key + ":authority"),
                key,
            ),
        )
        conn.execute(
            "INSERT INTO accounts.consent(account_id,purpose,granted) VALUES(%s,'local-research',true) "
            "ON CONFLICT(account_id,purpose) DO NOTHING",
            (UUID(account["accountId"]),),
        )


def seed_fixture_session(conn, account_id: UUID, run_id: str) -> UUID:
    """A short-lived session the fixture's own U4 calls run under; never a login."""
    session = stable_id(run_id, "memberA:fixture-session")
    revision = conn.execute(
        "SELECT authority_revision FROM accounts.account WHERE id=%s", (account_id,)
    ).fetchone()["authority_revision"]
    conn.execute(
        "INSERT INTO accounts.session(id,account_id,token_hash,csrf_hash,authority_revision,expires_at) "
        "VALUES(%s,%s,%s,%s,%s,clock_timestamp()+interval '30 minutes') ON CONFLICT(id) DO UPDATE "
        "SET revoked=false,authority_revision=excluded.authority_revision,expires_at=excluded.expires_at",
        (session, account_id, secrets.token_hex(32), secrets.token_hex(32), revision),
    )
    return session


def seed_corpus(conn, fixtures: dict) -> None:
    """Two eligible synthetic public papers, inserted once and never rewritten."""
    for paper in PAPERS:
        metadata = {"fixtureVersion": FIXTURE_VERSION, "runId": fixtures["runId"], "synthetic": True}
        conn.execute(
            "INSERT INTO corpus.paper(id,title,authors,metadata,published_on,withdrawn) "
            "VALUES(%s,%s,%s,%s,CURRENT_DATE,false) ON CONFLICT(id) DO NOTHING",
            (paper["paperId"], paper["title"], Jsonb(["Synthetic fixture author"]), Jsonb(metadata)),
        )
        document = {
            "title": paper["title"],
            "sections": [
                {"heading": "Synthetic abstract", "anchor": "abstract", "text": paper["text"]}
            ],
            "provenance": {"fixtureVersion": FIXTURE_VERSION, "synthetic": True},
        }
        conn.execute(
            "INSERT INTO corpus.version(id,paper_id,source_url,source_hash,version_label,"
            "private_path,eligible,purpose,provenance,content) "
            "VALUES(%s,%s,%s,%s,'v1','synthetic',true,'local-research',%s,%s) "
            "ON CONFLICT(id) DO NOTHING",
            (
                paper["versionId"],
                paper["paperId"],
                f"https://u6-fixture.invalid/{paper['paperId']}",
                "0" * 64,
                Jsonb(metadata),
                Jsonb(document),
            ),
        )
        known = conn.execute(
            "SELECT eligible FROM corpus.version WHERE id=%s", (paper["versionId"],)
        ).fetchone()
        if not known or not known["eligible"]:
            raise runner.Refused("existing synthetic source binding differs")


def research_ports(transactions):
    """U4's own service and synthetic execution, as `research_contribution` builds them."""
    from backend.modules.corpus.repository import CorpusRepository
    from backend.modules.research.execution import ResearchExecution
    from backend.modules.research.service import ResearchService

    corpus = CorpusRepository(transactions, None)
    execution = ResearchExecution(transactions, corpus)
    execution.enabled = True
    return ResearchService(transactions, corpus, execution=execution), execution


def _ready(service, authority: Authority, novelty: dict | None) -> bool:
    if novelty is None:
        return False
    reference = {key: novelty[key] for key in ("artifactId", "revision", "contentHash")}
    try:
        service.readNoveltyArtifactForExport(authority, reference)
    except Exception:  # noqa: BLE001 - any refusal means a new result is needed
        return False
    return True


def ready_novelty(transactions, authority: Authority, known: dict | None) -> dict:
    """A ready novelty result through U4's service: accept, then run the execution."""
    service, execution = research_ports(transactions)
    if _ready(service, authority, known):
        return known
    execution.usage.ensure_entitlement(authority)
    policy = service.policy.reference()
    context = service.create_context(authority, {"purpose": "novelty", "policy": policy})
    value = {
        "scope": {
            "contextId": context["contextId"],
            "publicPapers": [],
            "attachmentIds": [],
            "webReferences": [],
            "scopePolicy": policy,
        },
        "text": NOVELTY_TOPIC,
        "policy": policy,
        "inputMode": "topic",
    }
    job = service.accept(authority, str(uuid4()), value, "novelty-analysis")
    reference = {
        "jobId": job["jobId"],
        "contextId": context["contextId"],
        "kind": "novelty-analysis",
    }
    for _ in range(NOVELTY_STEPS):
        snapshot = service.read_job(authority, reference)
        if snapshot["state"] in ("succeeded", "failed", "cancelled"):
            break
        execution.step()
    snapshot = service.read_job(authority, reference)
    if snapshot["state"] != "succeeded" or snapshot["result"] is None:
        raise runner.Refused("synthetic novelty execution did not produce a ready result")
    result = snapshot["result"]
    return {
        "jobId": reference["jobId"],
        "contextId": reference["contextId"],
        "artifactId": result["resultId"],
        "revision": result["revision"],
        "contentHash": result["contentHash"],
    }


def _page(run_id: str, purpose: str, title, *, parent=None, readable=True, **extra) -> dict:
    page = {
        "id": page_id(run_id, purpose),
        "title": title,
        "parentId": page_id(run_id, parent) if parent else None,
        "readable": readable,
        "createdBy": stable_id(run_id, "page-author").hex,
        "blocks": [],
    }
    page.update(extra)
    return page


def scenario(run_id: str, token: str) -> dict:
    """The fake Notion's run-bound scenario, deterministic for one run."""
    pages = [
        _page(run_id, "personal", "개인 공간"),
        _page(run_id, "team", "팀 공간"),
        _page(run_id, "practice", PRACTICE_PAGE),
        _page(run_id, "untitled", None),
        _page(run_id, "notes-personal", SCENARIO_NAMES["sameTitle"], parent="personal"),
        _page(run_id, "notes-team", SCENARIO_NAMES["sameTitle"], parent="team"),
        _page(run_id, "unreadable", SCENARIO_NAMES["unreadablePage"], readable=False),
    ]
    for spec, names in SCENARIO_NAMES["specs"].items():
        pages.append(_page(run_id, f"cancel-{spec}", names["cancel"], normalPageReads=2))
        pages.append(
            _page(
                run_id,
                f"settle-{spec}",
                names["settle"],
                busyChildrenAfterCreate=True,
                createAnswers=[{"status": 504}],
            )
        )
    return {
        "runId": run_id,
        "tokens": {
            token: {
                "botId": stable_id(run_id, "bot").hex,
                "workspaceId": str(stable_id(run_id, "workspace")),
                "workspaceName": WORKSPACE_NAME,
            }
        },
        "pages": pages,
        "search": {"mode": "complete", "pageSize": 100},
    }


def _seed_database(profile, fixtures: dict) -> dict:
    transactions = OwnerTransactions(profile, process="maintenance")
    try:
        from backend.modules.accounts.services.guarded_entry import GuardedEntryService

        entry = GuardedEntryService(transactions)
        hashes = {
            key: entry._hash_password(account["password"])
            for key, account in fixtures["accounts"].items()
        }
        transactions.run(
            "accounts", lambda conn: seed_accounts(conn, fixtures, hashes, profile.run_id)
        )
        transactions.run("corpus", lambda conn: seed_corpus(conn, fixtures))

        def seed_preferences(conn):
            for account in fixtures["accounts"].values():
                conn.execute(
                    "INSERT INTO personalization.settings(account_id,revision,defaults) "
                    "VALUES(%s,%s,%s) ON CONFLICT(account_id) DO NOTHING",
                    (UUID(account["accountId"]), uuid4(), Jsonb({"timeZone": "UTC"})),
                )

        transactions.run("personalization", seed_preferences)
        member = UUID(fixtures["accounts"]["memberA"]["accountId"])
        session = transactions.run(
            "accounts", lambda conn: seed_fixture_session(conn, member, profile.run_id)
        )
        return ready_novelty(transactions, Authority(member, session), fixtures.get("novelty"))
    finally:
        transactions.close()


def setup(path: Path) -> dict:
    profile, value = runner.manifest(path)
    runner.require_no_real_export()
    runner.require_resources(value)
    runner.require_stopped()
    fixtures = fixture_record(profile)
    novelty = _seed_database(profile, fixtures)
    runner.private_json(profile.root / SCENARIO_FILE, scenario(profile.run_id, fixtures["notionToken"]))
    if fixtures["state"] != "ready" or fixtures.get("novelty") != novelty:
        fixtures = {**fixtures, "state": "ready", "novelty": novelty}
        runner.private_json(profile.root / "browser-fixtures.json", fixtures)
    return {
        "state": "fixtures-ready",
        "accounts": 2,
        "papers": 2,
        "noveltyResults": 1,
        "scenarioPages": len(scenario(profile.run_id, fixtures["notionToken"])["pages"]),
        "synthetic": True,
    }


def next_instant(profile, now: dt.datetime) -> dt.datetime:
    """One hour past the later of the current delegated instant and the real time; a
    frozen clock therefore always moves forward past every settling wait it holds."""
    current = now
    target = profile.root / CLOCK_FILE
    if target.exists() or target.is_symlink():
        recorded = json.loads(private_bytes(target))
        if recorded.get("runId") != profile.run_id:
            raise runner.Refused("export fixture clock belongs to another run")
        current = max(now, dt.datetime.fromisoformat(recorded["instant"]))
    instant = current + CLOCK_STEP
    if instant > now + CLOCK_AHEAD - CLOCK_STEP:
        raise runner.Refused("export fixture clock allocation exhausted")
    return instant


def advance_clock(path: Path, *, delegated: bool) -> dict:
    profile, value = runner.manifest(path)
    if delegated:
        runner.authorize_clock_child(value)
    runner.require_no_real_export()
    runner.require_resources(value)
    # A separate synthetic export clock: sessions, expiry, quota, migration receipts
    # and database timestamps never move.
    instant = next_instant(profile, dt.datetime.now(dt.UTC))
    runner.private_json(
        profile.root / CLOCK_FILE, {"runId": profile.run_id, "instant": instant.isoformat()}
    )
    return {"state": "clock-advanced", "synthetic": True, "instant": instant.isoformat()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment-file", type=Path, required=True)
    parser.add_argument("--action", choices=["setup", "advance-clock"], required=True)
    args = parser.parse_args(argv)
    # Only the authenticated browser child may move its synthetic clock while the
    # parent holds phase ownership; setup still requires exclusive custody.
    delegated = args.action == "advance-clock" and bool(os.environ.get(runner.CLOCK_CAPABILITY))
    with nullcontext() if delegated else runner.exclusive():
        if args.action == "setup":
            result = setup(args.environment_file)
        else:
            result = advance_clock(args.environment_file, delegated=delegated)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (runner.Refused, ValueError, OSError) as error:
        print(json.dumps({"state": "refused", "category": type(error).__name__}))
        raise SystemExit(1) from None
