"""The composed realm's fixtures (U8 plan Step 43; unit-test instructions § Test data).

Version `u8-fixtures-v1`. Everything here is generated per run and bound to it; nothing is
real data, every address is in `example.com`, every secret is made for the run.

- **The synthetic v1 dataset** (`v1_dataset`): the records v1's stores hold, loaded into the
  synthetic v1's own stores (`scripts/u8_synthetic_v1.py`): its PostgreSQL through v1's own
  tables, as v1's migrations created them, with passwords hashed by v1's own hasher; its
  search index; its object store. It holds at least one record for every misfit kind and
  reason of the functional spec's table (`backend/modules/operations/migration/misfits.py`),
  and accounts in each v1 state: active, pending, locked, deactivated, pending deletion,
  ORCID-only without email, and two emails differing only in case. It also holds identity
  links, settings, saved papers with version suffixes, papers beyond v2's limits, and every
  not-in-scope kind that has a v1 table. Its document models sit under v1's own
  `doc-model/` prefix; paper `2101.00006` is named only by its search index (L1-57), with
  a figure and member B's saved paper; and its bucket also holds two figures, one
  evidence upload and the orphan model `doc-model/2109.99999/v1.json` (U8 plan Step
  68(e)-(f)).
- **The v2 fixtures** (`prepare_v2`): memberA, memberB and an administrator with a completed
  second factor, written through the accounts owner's own login as the earlier units'
  fixtures and the conftest write theirs (v2's two consent decisions settled, a usage
  entitlement, the administrator's factor enrolled as U2's enrolment leaves it), and a
  ready novelty result for memberA produced through U4's own service and synthetic
  execution, never by writing ResearchWorkspace's tables. The browser reads them from the
  run-bound `fixtures/browser.json` (0600), which holds the run's synthetic passwords and
  the administrator's factor seed and nothing else secret.
- **The production-size corpus** is `scripts/u8_corpus.py`.

Every file this module writes is mode 0600 inside the run's own `fixtures/` folder.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "u8-fixtures-v1"
# The synthetic v1's password is made once per realm by `setup` (`v1-password.json`,
# U8 plan Step 96(d), L1-36) and read by `v1_dataset`.
V1_PASSWORD_FILE = "v1-password.json"
NOW = dt.datetime(2026, 9, 1, 12, 0, tzinfo=dt.UTC)
NAMESPACE = uuid.UUID("6f1c8b0e-4f43-5c6a-9a43-8d2f0c1b7e55")
INDEX = "docsuri-corpus-v1"
BUCKET = "docsuri-synthetic"
# v1's own document model prefix (`S3DocModelStore`'s default), written here as a literal
# and never imported from the migration tool, so a wrong constant fails the tests.
DOCMODEL_PREFIX = "doc-model/"
# Small bodies for the bucket's extra objects (U8 plan Step 68(e)-(f)).
WEBP_BODY = (b"RIFF\x1a\x00\x00\x00WEBPVP8L\x0d\x00\x00\x00"
             b"\x2f\x00\x00\x00\x10\x07\x10\x11\x11\x88\x88\xfe\x07\x00")
PDF_BODY = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
# v1's accounts, by the reason each one exists for (BR8.5, BR8.13, BR8.14; the misfit
# table of functional-spec.md): `name: (status, password kind, role, email kind)`.
ACCOUNTS = {
    "member-a": ("ACTIVE", "argon2", "USER", "plain"),
    "member-b": ("ACTIVE", "argon2", "USER", "plain"),
    "administrator": ("ACTIVE", "argon2", "ADMIN", "plain"),
    "orcid": ("ACTIVE", "argon2", "USER", "plain"),
    "provider": ("ACTIVE", "provider-only", "USER", "plain"),
    "orcid-only": ("ACTIVE", "provider-only", "USER", "none"),
    "pending": ("PENDING", "argon2", "USER", "plain"),
    "locked": ("LOCKED", "argon2", "USER", "plain"),
    "deactivated": ("DEACTIVATED", "argon2", "USER", "plain"),
    "deleting": ("ACTIVE", "argon2", "USER", "plain"),
    "case-a": ("ACTIVE", "argon2", "USER", "case-a"),
    "case-b": ("ACTIVE", "argon2", "USER", "case-b"),
    "legacy": ("ACTIVE", "legacy", "USER", "plain"),
}
# v1's identity links: (provider, subject suffix, owner, status, ORCID name).
LINKS = (
    ("ORCID", "0000-0002-0000-0001", "orcid", "LINKED", "Ada Synthetic"),
    ("GOOGLE", "google-provider-1", "provider", "LINKED", None),
    ("GOOGLE", "google-provider-2", "provider", "LINKED", None),
    ("GOOGLE", "google-member-a-pending", "member-a", "PENDING_CONFIRMATION", None),
    ("GOOGLE", "google-pending-account", "pending", "LINKED", None),
    ("ORCID", "0000-0002-0000-0002", "orcid-only", "LINKED", "Only Orcid"),
)
# v1's papers: paper id → (versions, kind of document model).
PAPERS = {
    "2101.00001": ((1, 2), "good"),
    "2101.00002": ((1,), "too-large"),
    "2101.00003": ((1,), "no-metadata"),
    "2101.00004": ((1,), "unconvertible"),
    "2101.00005": ((1,), "good"),
    # A paper only v1's search index names: no `paper_version_state` row (L1-57).
    "2101.00006": ((1,), "index-only"),
}
# Saved papers: (source suffix, owner, arXiv id with or without a version suffix).
SAVED = (
    ("saved-1", "member-a", "2101.00001v1"),
    ("saved-2", "member-a", "2101.00001v2"),
    ("saved-3", "member-a", "2101.00003"),
    ("saved-4", "member-a", "2101.00005v1"),
    ("saved-5", "member-b", "2101.00001"),
    ("saved-6", "pending", "2101.00001"),
    ("saved-7", "orcid", "2101.00001v2"),
    ("saved-8", "member-b", "2101.00006"),
)


def account_id(name: str) -> str:
    """v1's account identifier: a deterministic UUID string, as v1 assigns UUIDs."""
    return str(uuid.uuid5(NAMESPACE, f"v1-account:{name}"))


def email(name: str) -> str | None:
    kind = ACCOUNTS[name][3]
    if kind == "none":
        return None
    if kind == "case-a":
        return "Case.Owner@example.com"
    if kind == "case-b":
        return "case.owner@example.com"
    return f"{name}@example.com"


def document(paper: str, version: int, blocks: int = 3) -> dict:
    """A v1 document model in the shape v1's parser stores it."""
    return {
        "meta": {"paperId": paper, "version": version, "title": f"Synthetic paper {paper}",
                 "provenance": {"sourceTier": "native_html", "parserVersion": "docmodel-parser@8",
                                "schemaVersion": "1.1.0",
                                "generatedAt": "2026-09-01T12:00:00Z"}},
        "fullText": " ".join(f"Paragraph {index} of {paper}." for index in range(blocks)),
        "sections": [{"id": "s1", "title": "Introduction", "blocks": [
            {"id": f"s1.p{index}", "type": "paragraph",
             "text": f"Paragraph {index} of {paper} version {version}."}
            for index in range(blocks)]}],
    }


@dataclass(frozen=True)
class V1Dataset:
    """The synthetic v1's records, ready to load. `accounts` maps a fixture name to v1's
    account id; `password` is the one password every hashed account has, the realm's own
    (`v1_password`)."""

    accounts: dict[str, str]
    password: str

    def digest(self) -> str:
        value = {"version": VERSION, "accounts": self.accounts, "papers": PAPERS,
                 "saved": SAVED, "links": LINKS, "docmodelPrefix": DOCMODEL_PREFIX,
                 "bucketExtras": sorted(self.bucket_extras())}
        return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()

    def bucket_extras(self) -> dict[str, bytes]:
        """The bucket's objects beside the document models (Step 68(e)-(f)): the figures
        the `paper_asset` rows name, one evidence upload at the key v1's
        `object_key_for_upload` gives it, and an orphan model no paper names."""
        member_a = self.accounts["member-a"]
        return {
            "assets/2101.00001/v1/fig1.webp": WEBP_BODY,
            "assets/2101.00006/v1/fig1.webp": WEBP_BODY,
            f"uploads/evidence/{member_a}/attachment-1/attachment-1/paper.pdf": PDF_BODY,
            f"{DOCMODEL_PREFIX}2109.99999/v1.json": json.dumps(
                document("2109.99999", 1)).encode(),
        }

    def index_documents(self) -> list[dict]:
        """v1's search-index documents: one chunk per paper version with metadata."""
        documents = []
        for paper, (versions, kind) in PAPERS.items():
            for version in versions:
                if kind == "no-metadata":
                    continue
                documents.append({
                    "chunkId": f"{paper}:{version}:0", "paperId": paper, "version": version,
                    "title": f"Synthetic paper {paper}", "authors": ["A. Synthetic"],
                    "arxivId": paper, "vector": [0.1] * 4 if paper == "2101.00001" else None,
                    "arxivUrl": f"https://arxiv.org/abs/{paper}v{version}",
                })
        return documents

    def objects(self) -> dict[str, bytes]:
        """v1's object store: each version's document model under its prefix."""
        objects = {}
        for paper, (versions, kind) in PAPERS.items():
            for version in versions:
                key = f"{DOCMODEL_PREFIX}{paper}/v{version}.json"
                if kind == "too-large":
                    value = document(paper, version, blocks=2001)
                elif kind == "unconvertible":
                    value = {"meta": {"paperId": paper}, "sections": "not a tree"}
                else:
                    value = document(paper, version)
                objects[key] = json.dumps(value).encode()
        return objects


def v1_password(root: Path) -> str:
    """The realm's synthetic v1 password from `<root>/v1-password.json`, which `setup`
    writes once per realm; a missing record or another run's is refused."""
    from backend.local_profile import private_bytes

    path = root / V1_PASSWORD_FILE
    if not path.exists():
        raise ValueError("the realm holds no synthetic v1 password; run setup first")
    value = json.loads(private_bytes(path))
    environment = json.loads(private_bytes(root / "environment.json"))
    password = value.get("password")
    if value.get("runId") != environment.get("runId") or not isinstance(password, str):
        raise ValueError("the synthetic v1 password belongs to another run")
    return password


def v1_dataset(root: Path) -> V1Dataset:
    return V1Dataset(accounts={name: account_id(name) for name in ACCOUNTS},
                     password=v1_password(root))


# --- loading into v1's PostgreSQL ----------------------------------------------------------


def _naive(moment: dt.datetime) -> dt.datetime:
    return moment.replace(tzinfo=None)


def load_v1_database(conn, dataset: V1Dataset) -> dict:
    """Write the dataset into v1's own tables, once. Passwords use v1's own hasher. A
    database that already holds the dataset is left as it is; one that holds anything
    else is refused."""
    from backend.modules.accounts.password import get_password_hasher

    marker = dataset.accounts["member-a"]
    existing = conn.execute("SELECT count(*) FROM accounts").fetchone()[0]
    if existing:
        if conn.execute("SELECT 1 FROM accounts WHERE id=%s", (marker,)).fetchone() is None:
            raise ValueError("v1's database holds records that are not the synthetic dataset")
        return {"state": "present", "accounts": existing}
    hashed = get_password_hasher().hash(dataset.password)
    with conn.transaction():
        _accounts(conn, dataset, hashed)
        _links(conn, dataset)
        _preferences(conn, dataset)
        _papers(conn)
        _saved(conn, dataset)
        _not_in_scope(conn, dataset)
    return {"state": "loaded", "accounts": len(dataset.accounts)}


def _accounts(conn, dataset: V1Dataset, hashed: str) -> None:
    for name, (status, password, role, _) in ACCOUNTS.items():
        value = {"provider-only": "!", "legacy": "pbkdf2$v1$legacy"}.get(password, hashed)
        conn.execute(
            "INSERT INTO accounts(id,email,password_hash,status,role,created_at) "
            "VALUES(%s,%s,%s,%s,%s,%s)",
            (dataset.accounts[name], email(name), value, status, role, _naive(NOW)))
    conn.execute("INSERT INTO account_deletions(account_id,purge_after) VALUES(%s,%s)",
                 (dataset.accounts["deleting"], _naive(NOW + dt.timedelta(days=30))))


def _links(conn, dataset: V1Dataset) -> None:
    for provider, subject, owner, status, name in LINKS:
        conn.execute(
            "INSERT INTO social_identities(provider,provider_subject,account_id,email_at_link,"
            "linked_at,status,orcid_name) VALUES(%s,%s,%s,NULL,%s,%s,%s)",
            (provider, subject, dataset.accounts[owner], _naive(NOW), status, name))


def _preferences(conn, dataset: V1Dataset) -> None:
    ids = dataset.accounts
    conn.execute("INSERT INTO personalization_settings(owner_id,enabled) VALUES(%s,true),"
                 "(%s,false)", (ids["member-a"], ids["pending"]))
    conn.execute(
        "INSERT INTO user_interest_profiles(owner_id,category_weights,summary_defaults,"
        "updated_at) VALUES(%s,%s,%s,%s)",
        (ids["member-a"], json.dumps({"cs.CL": 0.7}), json.dumps({"length": "short"}), NOW))
    conn.execute("INSERT INTO onboarding_status(owner_id,state) VALUES(%s,'completed')",
                 (ids["orcid"],))


def _papers(conn) -> None:
    for paper, (versions, kind) in PAPERS.items():
        if kind == "index-only":
            continue  # only v1's search index names it (L1-57)
        for version in versions:
            conn.execute(
                "INSERT INTO paper_version_state(paper_id,version,doc_model_ref,status) "
                "VALUES(%s,%s,%s,'ACTIVE')",
                (paper, version, f"s3://{BUCKET}/{DOCMODEL_PREFIX}{paper}/v{version}.json"))
    for paper in ("2101.00001", "2101.00006"):
        conn.execute(
            "INSERT INTO paper_asset(paper_id,version,asset_id,type,caption,ordinal,"
            "source_mode,object_ref) VALUES(%s,1,'fig1','figure','A figure',1,'structured',%s)",
            (paper, f"s3://{BUCKET}/assets/{paper}/v1/fig1.webp"))


def _saved(conn, dataset: V1Dataset) -> None:
    for minute, (source, owner, arxiv) in enumerate(SAVED, start=1):
        conn.execute(
            "INSERT INTO library_items(id,owner_id,arxiv_id,meta,added_at) "
            "VALUES(%s,%s,%s,'{}',%s)",
            (str(uuid.uuid5(NAMESPACE, f"v1-saved:{source}")), dataset.accounts[owner], arxiv,
             NOW + dt.timedelta(minutes=minute)))


def _not_in_scope(conn, dataset: V1Dataset) -> None:
    """One record of every not-in-scope kind with a v1 table (BR8.1)."""
    owner = dataset.accounts["member-a"]

    def ident(kind: str) -> str:
        return str(uuid.uuid5(NAMESPACE, f"v1-{kind}:{owner}"))

    statements = (
        ("INSERT INTO followed_topics(id,owner_id,topic,created_at) VALUES(%s,%s,'nlp',%s)",
         (ident("topic"), owner, NOW)),
        ("INSERT INTO digest_settings(owner_id,opted_in,updated_at) VALUES(%s,true,%s)",
         (owner, NOW)),
        ("INSERT INTO user_glossary(user_id,term_from,term_to) VALUES(%s,'a','b')", (owner,)),
        (("INSERT INTO saved_searches(id,owner_id,query,normalized_query,created_at) "
          "VALUES(%s,%s,'q','q',%s)"), (ident("search"), owner, NOW)),
        (("INSERT INTO search_history(id,owner_id,query,executed_at,result_count,dedupe_key) "
          "VALUES(%s,%s,'q',%s,1,'k')"), (ident("history"), owner, NOW)),
        (("INSERT INTO user_behavior_events(id,owner_id,event_type,subject,source,dedupe_key,"
          "occurred_at) VALUES(%s,%s,'view','{}','web','k',%s)"), (ident("event"), owner, NOW)),
        (("INSERT INTO plan_assignments(id,user_id,tier,starts_at,expires_at,granted_by,"
          "created_at) VALUES(%s,%s,'plus',%s,%s,%s,%s)"),
         (ident("plan"), owner, NOW, NOW + dt.timedelta(days=30), dataset.accounts[
             "administrator"], NOW)),
        (("INSERT INTO research_jobs(job_id,owner_id,title,state,created_at,updated_at) "
          "VALUES(%s,%s,'Synthetic research','COMPLETED',%s,%s)"),
         (ident("research"), owner, NOW, NOW)),
        (("INSERT INTO novelty_jobs(job_id,owner_id,input_type,topic,state,created_at,"
          "updated_at) VALUES(%s,%s,'topic','Synthetic topic','COMPLETED',%s,%s)"),
         (ident("novelty"), owner, NOW, NOW)),
        (("INSERT INTO content_jobs(job_id,owner_id,task_type,input,state,created_at,"
          "updated_at) VALUES(%s,%s,'summary','{}','COMPLETED',%s,%s)"),
         (ident("summary"), owner, NOW, NOW)),
    )
    for statement, params in statements:
        conn.execute(statement, params)


# --- the v2 fixtures ---------------------------------------------------------------------------

# memberA runs the cross-unit journeys, memberB checks isolation, memberC is erased by
# the recovery journey, memberD by the lifecycle journey (an erasure consumes its account),
# and memberE holds J04's current-authority checks and J05: the verification run puts the
# recovery journey first (the person's decision of 2026-10-23, "Smaller database"), so J04
# cannot use memberC, and memberD's usage period holds J08's jobs only. unverifiedA and
# unverifiedB stay unverified, one for each verify-email leg of the security journey's
# fresh-browser links (U8 plan Step 96(c), L1-1); they hold no usage.
V2_ACCOUNTS = ("memberA", "memberB", "memberC", "memberD", "memberE", "administrator",
               "unverifiedA", "unverifiedB")
UNVERIFIED_ACCOUNTS = ("unverifiedA", "unverifiedB")
NOVELTY_TOPIC = "합성 참신성 분석 주제"
NOVELTY_STEPS = 20
MAX_ACCOUNTS = 20


def stable_id(run_id: str, purpose: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, run_id + ":u8-fixtures:" + purpose)


def browser_record(root: Path, run_id: str) -> dict:
    """The run's fixture record: created once, before any database write, so a retry
    never invents another password or seed."""
    import secrets

    path = root / "fixtures" / "browser.json"

    def account(key: str) -> dict:
        return {"email": f"{key.lower()}@u8.fixture.example.com",
                "password": "U8!" + secrets.token_urlsafe(24),
                "accountId": str(stable_id(run_id, key))}

    if path.exists():
        value = json.loads(path.read_text())
        if value.get("runId") != run_id or value.get("version") != VERSION:
            raise ValueError("browser fixtures belong to another run")
        missing = [key for key in V2_ACCOUNTS if key not in value["accounts"]]
        if missing:  # an account the fixtures came to name later; the others stay as they are
            value = {**value, "accounts": {**value["accounts"],
                                           **{key: account(key) for key in missing}}}
            write_private(path, value)
        return value
    value = {"version": VERSION, "runId": run_id, "state": "prepared",
             "accounts": {key: account(key) for key in V2_ACCOUNTS}, "novelty": None}
    write_private(path, value)
    return value


def account_plan(record: dict) -> dict[str, dict[str, bool]]:
    """Each fixture account's verified flag and whether it gets usage: the two unverified
    accounts are unverified and get none (`ImportedUsage.grant_imported` refuses an
    unverified account as `account-not-active`), every other account is verified and gets
    usage. Pure: it reads only the record's keys."""
    return {key: {"verified": key not in UNVERIFIED_ACCOUNTS,
                  "usage": key not in UNVERIFIED_ACCOUNTS}
            for key in record["accounts"]}


def seed_accounts(conn, record: dict, hashes: dict, run_id: str) -> None:
    ids = [uuid.UUID(item["accountId"]) for item in record["accounts"].values()]
    plan = account_plan(record)
    conn.execute("SELECT pg_advisory_xact_lock(hashtext('u8-browser-fixture-accounts'))")
    existing = {row["id"]: row["email"] for row in conn.execute(
        "SELECT id,email FROM accounts.account WHERE id=ANY(%s)", (ids,)).fetchall()}
    count = conn.execute("SELECT count(*) AS n FROM accounts.account").fetchone()["n"]
    if count + len(ids) - len(existing) > MAX_ACCOUNTS:
        raise ValueError("the realm's synthetic account allocation is exhausted")
    for key, account in record["accounts"].items():
        identity = uuid.UUID(account["accountId"])
        if identity in existing and existing[identity] != account["email"]:
            raise ValueError("an existing fixture account differs")
        verified = plan[key]["verified"]
        # Every fixtures run resets the two unverified accounts, so a realm whose
        # security phase verified them holds them unverified again; the others keep
        # what a run made.
        conflict = "DO NOTHING" if verified else "DO UPDATE SET verified=false"
        conn.execute(
            "INSERT INTO accounts.account(id,email,password_hash,verified,active,"
            "authority_revision,display_name,role) VALUES(%s,%s,%s,%s,true,%s,%s,%s) "
            "ON CONFLICT(id) " + conflict,
            (identity, account["email"], hashes[key], verified,
             stable_id(run_id, key + ":authority"), key,
             "administrator" if key == "administrator" else "member"))
        conn.execute(
            "INSERT INTO accounts.consent(account_id,purpose,granted) VALUES"
            "(%s,'local-research',true),(%s,'personalization',false) "
            "ON CONFLICT(account_id,purpose) DO NOTHING", (identity, identity))


GOOGLE_LINKED = "memberB"


def google_subject(run_id: str) -> str:
    return f"u8-google-{stable_id(run_id, 'google-subject').hex[:24]}"


def seed_google_link(conn, record: dict, run_id: str) -> None:
    """memberB's Google identity link, so the security journey's cross-site arrival
    signs a linked account in (U2 admits a provider sign-in only through a link)."""
    from psycopg.types.json import Jsonb

    account = uuid.UUID(record["accounts"][GOOGLE_LINKED]["accountId"])
    conn.execute(
        "INSERT INTO accounts.identity_link(id,account_id,provider,subject,provenance) "
        "VALUES(%s,%s,'google',%s,%s) ON CONFLICT(id) DO NOTHING",
        (stable_id(run_id, "google-link"), account, google_subject(run_id),
         Jsonb({"source": "realm-fixture"})))


def seed_settings(conn, record: dict) -> None:
    from psycopg.types.json import Jsonb

    for account in record["accounts"].values():
        conn.execute(
            "INSERT INTO personalization.settings(account_id,revision,defaults) "
            "VALUES(%s,%s,%s) ON CONFLICT(account_id) DO NOTHING",
            (uuid.UUID(account["accountId"]), uuid.uuid4(), Jsonb({"timeZone": "Asia/Seoul"})))


def seed_usage(transactions, record: dict) -> None:
    """Each fixture account's usage, granted through UsageEntitlements' `ImportedUsage`
    under the composed realm's `U8_SYNTHETIC_POLICY` (the plan's Step 43, the person's
    decision of 2026-10-23): the same grant an imported account receives; a held grant is
    kept."""
    from backend.modules.accounts.u8_control_policy import U8_SYNTHETIC_POLICY
    from backend.modules.plans.u8_usage import ImportedUsage

    usage = ImportedUsage(transactions, U8_SYNTHETIC_POLICY)
    plan = account_plan(record)
    for key, account in record["accounts"].items():
        if not plan[key]["usage"]:
            continue
        result = usage.grant_imported(uuid.UUID(account["accountId"]), source="realm_fixture")
        if result["disposition"] not in ("imported", "unchanged"):
            raise ValueError(f"a fixture account's usage grant was {result.get('reasonKey')}")


def enrol_factor(transactions, entry, account_id: uuid.UUID) -> str:
    """The administrator's completed second factor, as U2's enrolment leaves it (the
    seed protected under the entry's keyring); an active one is kept. Returns the seed."""
    import base64
    import secrets

    def existing(conn):
        return conn.execute(
            "SELECT id,ciphertext FROM accounts.mfa_enrollment WHERE account_id=%s AND "
            "state='active'", (account_id,)).fetchone()

    found = transactions.run("accounts", existing)
    if found is not None:
        return entry.reveal("mfa:" + str(found["id"]), found["ciphertext"])["seed"]
    identifier, seed = uuid.uuid4(), base64.b32encode(secrets.token_bytes(20)).decode()
    protected = entry.protect("mfa:" + str(identifier), {"seed": seed, "codes": []})

    def write(conn):
        conn.execute(
            "INSERT INTO accounts.mfa_enrollment(id,account_id,key_version,ciphertext,"
            "delivery_hash,delivery_expires_at,delivered_at,state) VALUES(%s,%s,%s,%s,%s,"
            "clock_timestamp(),clock_timestamp(),'active')",
            (identifier, account_id, entry.protection_version(protected), protected,
             secrets.token_hex(32)))

    transactions.run("accounts", write)
    return seed


def unverified_read_back(transactions, record: dict) -> None:
    """The two unverified accounts read back unverified and holding no entitlement,
    through the accounts and usage owners' own logins; the fixtures phase fails
    otherwise."""
    ids = [uuid.UUID(record["accounts"][key]["accountId"]) for key in UNVERIFIED_ACCOUNTS]
    verified = transactions.run("accounts", lambda conn: conn.execute(
        "SELECT id,verified FROM accounts.account WHERE id=ANY(%s)", (ids,)).fetchall())
    if len(verified) != len(ids) or any(row["verified"] for row in verified):
        raise ValueError("an unverified fixture account is verified or missing")
    entitled = transactions.run("usage", lambda conn: conn.execute(
        "SELECT count(*) AS n FROM usage.entitlement WHERE account_id=ANY(%s)",
        (ids,)).fetchone()["n"])
    if entitled:
        raise ValueError("an unverified fixture account holds an entitlement")


def fixture_session(transactions, account_id: uuid.UUID, run_id: str, key: str = "memberA"):
    """A short-lived session U4's own calls run under for the fixture; never a sign-in.
    Each account's fixture session has its own id (memberA keeps the one built first)."""
    import secrets

    from backend.transactions import Authority

    session = stable_id(run_id, f"{key}:fixture-session")

    def write(conn):
        revision = conn.execute("SELECT authority_revision FROM accounts.account WHERE id=%s",
                                (account_id,)).fetchone()["authority_revision"]
        conn.execute(
            "INSERT INTO accounts.session(id,account_id,token_hash,csrf_hash,"
            "authority_revision,expires_at,purpose) VALUES(%s,%s,%s,%s,%s,"
            "clock_timestamp()+interval '30 minutes','full_session') ON CONFLICT(id) DO UPDATE "
            "SET revoked=false,authority_revision=excluded.authority_revision,"
            "expires_at=excluded.expires_at",
            (session, account_id, secrets.token_hex(32), secrets.token_hex(32), revision))

    transactions.run("accounts", write)
    return Authority(account_id, session)


def ready_novelty(transactions, authority, known: dict | None) -> dict:
    """A ready novelty result through U4's service and synthetic execution, its
    reservation through U2's usage controls under the composed realm's policy
    (`use_complete_usage`): the fixture account's grant pays for it."""
    from backend.modules.corpus.repository import CorpusRepository
    from backend.modules.plans.u8_usage import use_complete_usage
    from backend.modules.research.execution import ResearchExecution
    from backend.modules.research.service import ResearchService

    corpus = CorpusRepository(transactions, None)
    execution = use_complete_usage(ResearchExecution(transactions, corpus), transactions)
    execution.enabled = True
    service = ResearchService(transactions, corpus, execution=execution)
    if known is not None:
        try:
            service.readNoveltyArtifactForExport(authority, {
                key: known[key] for key in ("artifactId", "revision", "contentHash")})
            return known
        except Exception:  # noqa: BLE001 - any refusal means a new result is needed
            known = None
    policy = service.policy.reference()
    context = service.create_context(authority, {"purpose": "novelty", "policy": policy})
    job = service.accept(authority, str(uuid.uuid4()), {
        "scope": {"contextId": context["contextId"], "publicPapers": [], "attachmentIds": [],
                  "webReferences": [], "scopePolicy": policy},
        "text": NOVELTY_TOPIC, "policy": policy, "inputMode": "topic"}, "novelty-analysis")
    reference = {"jobId": job["jobId"], "contextId": context["contextId"],
                 "kind": "novelty-analysis"}
    for _ in range(NOVELTY_STEPS):
        if service.read_job(authority, reference)["state"] in ("succeeded", "failed",
                                                               "cancelled"):
            break
        execution.step()
    snapshot = service.read_job(authority, reference)
    if snapshot["state"] != "succeeded" or snapshot["result"] is None:
        raise ValueError("the synthetic novelty execution produced no ready result")
    result = snapshot["result"]
    return {"jobId": reference["jobId"], "contextId": reference["contextId"],
            "artifactId": result["resultId"], "revision": result["revision"],
            "contentHash": result["contentHash"]}


NOTION_WORKSPACE = "DocSuri 합성 워크스페이스"
NOTION_PRACTICE = "DocSuri 내보내기 연습장"
NOTION_STUCK = "응답 지연 확인 페이지"
NOTION_SETTLE = "직접 확인 페이지"


def notion_scenario(run_id: str, token: str) -> dict:
    """The fake Notion's run-bound scenario (U6's `FakeNotion`, which the composed realm
    loads from `fake-notion.json`): a practice page that accepts exports, and a page whose
    reads stop answering after the export's binding read, so an export to it stays
    accepted until its owner cancels it (the navigation journey's late export)."""

    def page(purpose: str, title: str, **extra) -> dict:
        return {"id": stable_id(run_id, "page:" + purpose).hex, "title": title,
                "parentId": None, "readable": True,
                "createdBy": stable_id(run_id, "page-author").hex, "blocks": [], **extra}

    stuck = page("stuck", NOTION_STUCK, normalPageReads=2)
    return {
        "runId": run_id,
        "tokens": {token: {"botId": stable_id(run_id, "bot").hex,
                           "workspaceId": str(stable_id(run_id, "workspace")),
                           "workspaceName": NOTION_WORKSPACE}},
        # The settle page answers its create with 504 and its children with 503 from
        # then on: the export's outcome is unclear until its owner settles it (U6's).
        "pages": [page("practice", NOTION_PRACTICE), stuck,
                  page("settle", NOTION_SETTLE, busyChildrenAfterCreate=True,
                       createAnswers=[{"status": 504}])],
        "search": {"mode": "complete", "pageSize": 100},
        # Each role has its own fake (`u8_host.role_page_reads`): the host's answers the
        # stuck page's preview and approval reads (its two normal reads), the workers'
        # answers none, so the worker's pre-write read meets 503 and the export stays
        # accepted until its owner cancels it (J12's late export).
        "u8RolePageReads": {"workers": {stuck["id"]: 0}},
    }


def prepare_v2(profile) -> dict:
    """The v2 fixtures in the realm; restartable, never rewriting what a run made."""
    from backend.modules.accounts.password import get_password_hasher
    from backend.modules.accounts.u8_control_policy import U8_SYNTHETIC_POLICY
    from backend.modules.accounts.u8_entry import CompleteControlEntryService
    from backend.transactions import OwnerTransactions

    record = browser_record(profile.root, profile.run_id)
    transactions = OwnerTransactions(profile, process="maintenance")
    try:
        hasher = get_password_hasher()
        hashes = {key: hasher.hash(item["password"]) for key, item in record["accounts"].items()}
        transactions.run("accounts", lambda conn: seed_accounts(conn, record, hashes,
                                                                profile.run_id))
        transactions.run("accounts", lambda conn: seed_google_link(conn, record,
                                                                    profile.run_id))
        transactions.run("personalization", lambda conn: seed_settings(conn, record))
        seed_usage(transactions, record)
        unverified_read_back(transactions, record)
        entry = CompleteControlEntryService(transactions, U8_SYNTHETIC_POLICY)
        administrator = uuid.UUID(record["accounts"]["administrator"]["accountId"])
        seed = enrol_factor(transactions, entry, administrator)
        member = uuid.UUID(record["accounts"]["memberA"]["accountId"])
        novelty = ready_novelty(transactions, fixture_session(transactions, member,
                                                              profile.run_id),
                                record.get("novelty"))
        # memberE's own ready result, so J05 spends none of memberE's places on it.
        member_e = uuid.UUID(record["accounts"]["memberE"]["accountId"])
        novelty_e = ready_novelty(transactions, fixture_session(transactions, member_e,
                                                                profile.run_id, "memberE"),
                                  record.get("noveltyMemberE"))
        from backend.artifacts import PrivateArtifacts
        from backend.modules.corpus.limits import for_profile
        from u8_fixture_assets import paper_asset

        files = PrivateArtifacts.for_profile(profile, "corpus-files",
                                             maximum_bytes=for_profile(profile).max_source_bytes)
        # The isolation journeys' own paper: J03's and J13's reads of its asset (L3-5).
        asset = paper_asset(transactions, files, record.get("paperAsset"))
        from u8_fixture_assistance import assistance_job

        # memberA's ready assistance job, for the isolation journey's owner pass (L4-13).
        assistance = assistance_job(transactions, files, fixture_session(
            transactions, member, profile.run_id), record.get("assistanceJob"))
    finally:
        transactions.close()
    import secrets

    token = record.get("notionToken") or "u8-synthetic-" + secrets.token_hex(20)
    record = {**record, "state": "ready", "novelty": novelty, "noveltyMemberE": novelty_e,
              "notionToken": token, "paperAsset": asset, "assistanceJob": assistance,
              "notion": {"workspace": NOTION_WORKSPACE, "practice": NOTION_PRACTICE,
                         "stuck": NOTION_STUCK, "settle": NOTION_SETTLE},
              "accounts": {**record["accounts"], "administrator": {
                  **record["accounts"]["administrator"], "totpSeed": seed}}}
    write_private(profile.root / "fixtures" / "browser.json", record)
    # The composed realm reads the fake Notion's scenario at its start (`u6_host.
    # synthetic_notion`); the token is the run's own, accepted only by the fake.
    write_private(profile.root / "fake-notion.json", notion_scenario(profile.run_id, token))
    # The identity stand-in's scenario (`u8_identity_standin.load_scenario`), which the
    # served realm loads at its start: Google signs in as memberB's linked identity, ORCID
    # answers the person's refusal (the security journey).
    write_private(profile.root / "identity-scenario.json", {
        "google": {"subject": google_subject(profile.run_id),
                   "email": record["accounts"][GOOGLE_LINKED]["email"]},
        "orcid": "access_denied",
    })
    return {"accounts": len(record["accounts"]), "noveltyResults": 2, "paperAssets": 2,
            "unverified": list(UNVERIFIED_ACCOUNTS), "factor": "active",
            "notionPages": len(notion_scenario(profile.run_id, token)["pages"])}


# --- private files ---------------------------------------------------------------------------


def write_private(path: Path, value: object) -> None:
    """One 0600 JSON file, written whole, never through a link."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    pending = path.with_name(path.name + ".pending")
    descriptor = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump(value, stream, sort_keys=True, default=str)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(pending, path)


def dataset_record(dataset: V1Dataset, run_id: str) -> dict:
    """The dataset's run-bound description the journeys read (never a secret beyond the
    run's own synthetic password)."""
    return {"version": VERSION, "runId": run_id, "digest": dataset.digest(),
            "accounts": {name: {"v1AccountId": ident, "email": email(name),
                                "state": ACCOUNTS[name][0]}
                         for name, ident in dataset.accounts.items()},
            "password": dataset.password, "papers": sorted(PAPERS),
            "index": INDEX, "bucket": BUCKET}


# --- the fixtures phase's program --------------------------------------------------------------

PREPARE_SECONDS = 280


# The corpus modes (the person's decision of 2026-10-23, "Smaller database"): `load` is
# the whole phase; `skip` stops before the corpus, so the journeys that need no corpus run
# on a small database; `only` resumes the corpus alone, never reseeding the v2 fixtures
# after journeys have consumed accounts (the verification run's later corpus runs).
CORPUS_MODES = ("load", "skip", "only")


def prepare(environment: Path, corpus_mode: str = "load") -> dict:
    """The `fixtures` phase: the v2 fixtures, the synthetic v1 dataset's record (which
    `v1-up` loads into the synthetic v1's own stores) and the production-size corpus,
    within the phase's bound; an unfinished corpus is reported with its counts and
    resumed by the next run, never shrunk."""
    import time

    import u8_corpus
    from backend.local_profile import LocalProfile

    if corpus_mode not in CORPUS_MODES:
        raise ValueError("unknown corpus mode")
    started = time.monotonic()
    profile = LocalProfile.load(environment)
    if getattr(profile, "is_production", False) or (profile.realm, profile.database_name) != (
            "service-operations", "docsuri_u8"):
        raise ValueError("the fixtures serve the composed realm only")
    result: dict = {"corpusMode": corpus_mode}
    if corpus_mode == "only":
        if not (profile.root / "fixtures" / "browser.json").exists():
            raise ValueError("the corpus alone needs the v2 fixtures first")
    else:
        dataset = v1_dataset(profile.root)
        result |= {"v2": prepare_v2(profile), "v1Dataset": dataset.digest()}
        write_private(profile.root / "fixtures" / "v1-dataset.json",
                      dataset_record(dataset, profile.run_id))
    if corpus_mode == "skip":
        return {**result, "state": "corpus-skipped", "corpus": None,
                "seconds": round(time.monotonic() - started, 1)}
    corpus = u8_corpus.prepare(profile, seconds=PREPARE_SECONDS - (time.monotonic() - started))
    write_private(profile.root / "fixtures" / "corpus.json", corpus)
    # Deviation by the person's decision of 2026-10-23 ("Load over two runs"): a corpus
    # the bound did not finish is a plain, counted state, picked up by the next run;
    # `performance` and `verification-run` refuse it.
    state = "fixtures-ready" if corpus["complete"] else "corpus-incomplete"
    return {**result, "state": state, "corpus": corpus,
            "seconds": round(time.monotonic() - started, 1)}


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    # The source roots the realm's pytest configuration uses (`pythonpath`).
    for entry in (ROOT, ROOT / "ingestion/src", ROOT / "ops/src", ROOT / "scripts"):
        if str(entry) not in sys.path:
            sys.path.insert(0, str(entry))
    parser = argparse.ArgumentParser(prog="u8_fixtures.py")
    parser.add_argument("word", choices=("prepare",))
    parser.add_argument("--environment-file", required=True, type=Path)
    parser.add_argument("--corpus", choices=CORPUS_MODES, default="load")
    args = parser.parse_args(argv)
    try:
        result = prepare(args.environment_file.resolve(), args.corpus)
    except (ValueError, OSError) as error:
        print(json.dumps({"state": "refused", "reason": str(error)[:300]}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
