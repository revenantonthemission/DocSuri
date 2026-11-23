"""A synthetic v1 for the migration tests (U8 plan Step 32).

`SyntheticV1` is a v1 database of the test's own in the realm's instance: v1's own
migrations (`backend/migrations/registry.py`, in its order) create v1's tables, and the
synthetic records are written into them, one or more for every misfit reason of the
functional spec's table. Its search index documents and its document-model objects are
the stand-ins for v1's OpenSearch and MinIO, which the snapshot reads through the
readers the migration tool is given. Nothing here is v1's real data: every record is
generated, every address is in `example.com`.

The accounts, by the reason each one exists for (BR8.5, BR8.13, BR8.14):

| account | v1 state | expected |
|---|---|---|
| `active` | ACTIVE, Argon2id hash | imported, display name from the email |
| `orcid` | ACTIVE, ORCID link with a name | imported, display name from ORCID |
| `provider` | ACTIVE, `!` (provider-only), Google link | imported, no password |
| `orcid-only` | ACTIVE, no email | `no-email` |
| `pending` | PENDING | `unverified-in-v1` |
| `locked` | LOCKED | imported reset-required (mapped `locked-in-v1`) |
| `deactivated` | DEACTIVATED | `closed-in-v1` |
| `deleting` | ACTIVE with a pending deletion | `closed-in-v1` |
| `case-a`, `case-b` | emails differing only in case | `email-case-conflict` |
| `legacy` | ACTIVE, a non-Argon2id hash | imported reset-required |

The papers' document models sit under v1's own `doc-model/` prefix. Paper `2101.00006` is
named only by v1's search index, with no `paper_version_state` row (L1-57): it has a figure
and orcid's saved paper `saved-6`. `listing()` answers the bucket's listing as the copy
records it, `{"key", "size", "etag"}` per object, over the models, the two figures, one
evidence upload and the orphan model `doc-model/2109.99999/v1.json` (U8 plan Step
68(e)-(f)).
"""

from __future__ import annotations

import contextlib
import datetime as dt
import json
import secrets
from dataclasses import dataclass, field
from pathlib import Path

from psycopg import sql
from psycopg.rows import dict_row

from tests.u8_service_operations_integration import recovery_flows as rf

ROOT = Path(__file__).resolve().parents[2]
# Generated at import, once per process (L1-36): `SyntheticV1.create` hashes it in the
# process that later signs in with it.
V1_PASSWORD = "Synthetic-V1-" + secrets.token_hex(8) + "-1!"
NOW = dt.datetime(2026, 9, 1, 12, 0, tzinfo=dt.UTC)
ACCOUNTS = ("active", "orcid", "provider", "orcid-only", "pending", "locked", "deactivated",
            "deleting", "case-a", "case-b", "legacy")
PAPERS = {
    # v1 paper id: (versions, kind of document)
    "2101.00001": ((1, 2), "good"),
    "2101.00002": ((1,), "too-large"),
    "2101.00003": ((1,), "no-metadata"),
    "2101.00004": ((1,), "unconvertible"),
    "2101.00006": ((1,), "index-only"),
}
# Small bodies for the bucket's extra objects.
WEBP_BODY = (b"RIFF\x1a\x00\x00\x00WEBPVP8L\x0d\x00\x00\x00"
             b"\x2f\x00\x00\x00\x10\x07\x10\x11\x11\x88\x88\xfe\x07\x00")
PDF_BODY = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


PROJECTION_INSERT = "INSERT INTO corpus.projection"


@contextlib.contextmanager
def refusing(version: str, how, *, when=lambda: True):
    """The time refusal's injections (U8 plan Step 69(h), listed by Step 98(h)), on
    `DeadlineConnection.execute`, just before the `INSERT INTO corpus.projection` of one
    version (`arxiv:2101.00006@v1`), while `when()` holds:

    - `"sleep"`: a call-through spy that first runs `SELECT pg_sleep(3.5)` through the same
      bounded connection, so the database's own 3 s statement bound cancels it
      (`QueryCanceled`);
    - `"deadline"`: a spy that moves the bounded connection's deadline into the past, so the
      real `remaining()` raises `DeadlineReached`;
    - an exception: raise-only, raised there.
    """
    import time

    from backend.transactions import DeadlineConnection

    original = DeadlineConnection.execute

    def execute(self, query, params=None, **kwargs):
        if (isinstance(query, str) and query.startswith(PROJECTION_INSERT) and params
                and params[0] == version and when()):
            if how == "sleep":
                original(self, "SELECT pg_sleep(3.5)")
            elif how == "deadline":
                self.deadline = time.monotonic() - 1.0
            else:
                raise how
        return original(self, query, params, **kwargs)

    DeadlineConnection.execute = execute
    try:
        yield
    finally:
        DeadlineConnection.execute = original


def realm_environment() -> dict:
    """A synthetic v1 environment naming only the realm's own stores (U8 plan Step 43);
    its secret contains a real port's digits, which is not an address. Its secrets are
    generated per call (L1-36)."""
    return {
        "ENV": "production",
        "DATABASE_URL": (f"postgresql+psycopg://docsuri:{secrets.token_hex(8)}"
                         "@127.0.0.1:15510/docsuri"),
        "REDIS_HOST": "127.0.0.1", "REDIS_PORT": "16389",
        "DOCSURI_OPENSEARCH_ENDPOINT": "http://127.0.0.1:19209",
        "AWS_ENDPOINT_URL_S3": "http://127.0.0.1:19009",
        "AWS_ACCESS_KEY_ID": "u8v1abc",
        "AWS_SECRET_ACCESS_KEY": secrets.token_hex(4) + "-6379-5432",
        "CORS_ORIGINS": "https://127.0.0.1:18110", "SES_MOCK": "true",
    }


def write_environment(run: Path, value: object, *, mode: int = 0o600) -> Path:
    """`<run>/v1/environment.json` as `u8_synthetic_v1.wire_driver` writes it."""
    import os

    folder = run / "v1"
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = folder / "environment.json"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump(value, stream)
    os.chmod(path, mode)
    return path


def v1_migrations() -> list[Path]:
    from backend.migrations.registry import DOMAINS

    return [ROOT / folder / name for _, folder, files in DOMAINS for name in files]


def document(paper: str, version: int, blocks: int = 3) -> dict:
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


@dataclass
class SyntheticV1:
    realm: object
    name: str = field(default_factory=lambda: f"v1_synthetic_{secrets.token_hex(4)}")
    ids: dict = field(default_factory=dict)

    def connect(self):
        conn = rf.admin(self.realm, self.name)
        conn.row_factory = dict_row
        return conn

    def create(self) -> SyntheticV1:
        from backend.modules.accounts.password import get_password_hasher

        rf.drop_database(self.realm, self.name)
        with rf.admin(self.realm) as conn:
            conn.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template1").format(
                sql.Identifier(self.name)))
        with rf.admin(self.realm, self.name) as conn:
            for path in v1_migrations():
                conn.execute(path.read_text(), prepare=False)
            self.ids = {name: f"v1-{name}-{secrets.token_hex(4)}" for name in ACCOUNTS}
            hashed = get_password_hasher().hash(V1_PASSWORD)
            self._accounts(conn, hashed)
            self._links(conn)
            self._preferences(conn)
            self._papers(conn)
            self._saved(conn)
            self._not_in_scope(conn)
        return self

    def email(self, name: str) -> str:
        return {"case-a": "Case.Owner@example.com", "case-b": "case.owner@example.com"}.get(
            name, f"{self.ids[name]}@example.com")

    def _accounts(self, conn, hashed: str) -> None:
        states = {"pending": "PENDING", "locked": "LOCKED", "deactivated": "DEACTIVATED"}
        for name in ACCOUNTS:
            # v1's stored marker for a provider-only account, or a legacy hash v2 cannot
            # verify, generated per run (L1-36); otherwise the hash of `V1_PASSWORD`.
            stored = {"provider": "!", "orcid-only": "!",
                      "legacy": "pbkdf2$v1$" + secrets.token_hex(8)}.get(name, hashed)
            conn.execute(
                "INSERT INTO accounts(id,email,password_hash,status,role,created_at) "
                "VALUES(%s,%s,%s,%s,%s,%s)",
                (self.ids[name], None if name == "orcid-only" else self.email(name), stored,
                 states.get(name, "ACTIVE"), "ADMIN" if name == "legacy" else "USER",
                 NOW.replace(tzinfo=None)))
        conn.execute("INSERT INTO account_deletions(account_id,purge_after) VALUES(%s,%s)",
                     (self.ids["deleting"], (NOW + dt.timedelta(days=30)).replace(tzinfo=None)))

    def _links(self, conn) -> None:
        rows = [
            ("ORCID", "0000-0002-0000-0001", "orcid", "LINKED", "Ada Synthetic"),
            ("GOOGLE", "google-provider-1", "provider", "LINKED", None),
            ("GOOGLE", "google-provider-2", "provider", "LINKED", None),
            ("GOOGLE", "google-active-pending", "active", "PENDING_CONFIRMATION", None),
            ("GOOGLE", "google-pending-account", "pending", "LINKED", None),
            ("ORCID", "0000-0002-0000-0002", "orcid-only", "LINKED", "Only Orcid"),
        ]
        for provider, subject, owner, status, name in rows:
            conn.execute(
                "INSERT INTO social_identities(provider,provider_subject,account_id,email_at_link,"
                "linked_at,status,orcid_name) VALUES(%s,%s,%s,NULL,%s,%s,%s)",
                (provider, subject, self.ids[owner], NOW.replace(tzinfo=None), status, name))

    def _preferences(self, conn) -> None:
        conn.execute("INSERT INTO personalization_settings(owner_id,enabled) VALUES(%s,true),"
                     "(%s,false)", (self.ids["active"], self.ids["pending"]))
        conn.execute(
            "INSERT INTO user_interest_profiles(owner_id,category_weights,summary_defaults,"
            "updated_at) VALUES(%s,%s,%s,%s)",
            (self.ids["active"], json.dumps({"cs.CL": 0.7}), json.dumps({"length": "short"}),
             NOW))
        conn.execute("INSERT INTO onboarding_status(owner_id,state) VALUES(%s,'completed')",
                     (self.ids["orcid"],))

    def _papers(self, conn) -> None:
        for paper, (versions, kind) in PAPERS.items():
            if kind == "index-only":
                continue
            for version in versions:
                conn.execute(
                    "INSERT INTO paper_version_state(paper_id,version,doc_model_ref,status) "
                    "VALUES(%s,%s,%s,'ACTIVE')",
                    (paper, version,
                     f"s3://docsuri-synthetic/doc-model/{paper}/v{version}.json"))
        for paper in ("2101.00001", "2101.00006"):
            conn.execute(
                "INSERT INTO paper_asset(paper_id,version,asset_id,type,caption,ordinal,"
                "source_mode,object_ref) VALUES(%s,1,'fig1','figure','A figure',1,"
                "'structured',%s)",
                (paper, f"s3://docsuri-synthetic/assets/{paper}/v1/fig1.webp"))

    def _saved(self, conn) -> None:
        rows = [
            ("saved-1", "active", "2101.00001v1", 1),
            ("saved-2", "active", "2101.00001v2", 2),
            ("saved-3", "active", "2101.00003", 3),
            ("saved-4", "pending", "2101.00001", 4),
            ("saved-5", "orcid", "2101.00001v2", 5),
            ("saved-6", "orcid", "2101.00006", 6),
        ]
        for source, owner, arxiv, minute in rows:
            conn.execute(
                "INSERT INTO library_items(id,owner_id,arxiv_id,meta,added_at) "
                "VALUES(%s,%s,%s,'{}',%s)",
                (f"{source}-{self.ids['active']}", self.ids[owner], arxiv,
                 NOW + dt.timedelta(minutes=minute)))

    def _not_in_scope(self, conn) -> None:
        owner = self.ids["active"]
        statements = (
            ("INSERT INTO followed_topics(id,owner_id,topic,created_at) VALUES(%s,%s,'nlp',%s)",
             (f"topic-{owner}", owner, NOW)),
            ("INSERT INTO digest_settings(owner_id,opted_in,updated_at) VALUES(%s,true,%s)",
             (owner, NOW)),
            ("INSERT INTO user_glossary(user_id,term_from,term_to) VALUES(%s,'a','b')", (owner,)),
            ("INSERT INTO saved_searches(id,owner_id,query,normalized_query,created_at) "
             "VALUES(%s,%s,'q','q',%s)", (f"search-{owner}", owner, NOW)),
            ("INSERT INTO search_history(id,owner_id,query,executed_at,result_count,dedupe_key) "
             "VALUES(%s,%s,'q',%s,1,'k')", (f"history-{owner}", owner, NOW)),
            ("INSERT INTO user_behavior_events(id,owner_id,event_type,subject,source,dedupe_key,"
             "occurred_at) VALUES(%s,%s,'view','{}','web','k',%s)", (f"event-{owner}", owner,
                                                                    NOW)),
        )
        for statement, params in statements:
            conn.execute(statement, params)

    def drop(self) -> None:
        rf.drop_database(self.realm, self.name)

    # --- v1's search index and object store ------------------------------------------------

    def index_documents(self) -> list[dict]:
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
        objects = {}
        for paper, (versions, kind) in PAPERS.items():
            for version in versions:
                key = f"doc-model/{paper}/v{version}.json"
                if kind == "too-large":
                    value = document(paper, version, blocks=2001)
                elif kind == "unconvertible":
                    value = {"meta": {"paperId": paper}, "sections": "not a tree"}
                else:
                    value = document(paper, version)
                objects[key] = json.dumps(value).encode()
        return objects

    def bucket_extras(self) -> dict[str, bytes]:
        """The bucket's objects beside the models: two figures, an upload under one of its
        own accounts and the orphan model no paper names."""
        return {
            "assets/2101.00001/v1/fig1.webp": WEBP_BODY,
            "assets/2101.00006/v1/fig1.webp": WEBP_BODY,
            f"uploads/evidence/{self.ids['active']}/attachment-1/attachment-1/paper.pdf":
                PDF_BODY,
            "doc-model/2109.99999/v1.json": json.dumps(document("2109.99999", 1)).encode(),
        }

    def listing(self) -> list[dict]:
        """The bucket's listing as `split_listing` yields it, sorted by key; each ETag is
        the quoted MD5 hex of its body, as a single-part S3 upload's."""
        import hashlib

        stored = {**self.objects(), **self.bucket_extras()}
        return [{"key": key, "size": len(body),
                 "etag": f'"{hashlib.md5(body).hexdigest()}"'}  # noqa: S324 - S3's ETag
                for key, body in sorted(stored.items())]
