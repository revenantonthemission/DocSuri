"""v1's records, read from the run's snapshot (U8 plan Step 31; BR8.1, BR8.11, Workflow 9).

The import reads only the run's own copy of v1: its database through the run's import
database, restored from the snapshot's dump, and the search index's documents and the
selected objects from the snapshot's tar archives, whose member checksums were checked
before use. Nothing here reaches v1 itself.

`V1Source` reads v1's own tables by v1's own column names (its migrations under
`backend/migrations/registry.py`): `accounts`, `account_deletions`, `social_identities`,
`personalization_settings`, `user_interest_profiles`, `onboarding_status`,
`paper_version_state`, `paper_asset`, `library_items`, and, counted only, the tables of
the kinds Q13 did not name. A table a deployment lacks is read as empty.

v1's papers come from two sources (U8 plan Step 68(f), L1-57): the rows of
`paper_version_state`, and each distinct (`paperId`, `version`) pair of the snapshot's
search index documents that no row names, whose document model is v1's own key under
`doc-model/`. The bucket's whole listing (key, size and ETag of every object) travels
beside the document models (Step 68(c), L1-37), and v1's private uploads are counted from
it by a hashed source id, never by their key (Step 68(d), L1-20).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from .misfits import NOT_IN_SCOPE_KINDS

# v1's own document model prefix: `S3DocModelStore`'s default, `doc-model/{paperId}/
# v{version}.json` (ingestion/src/docsuri_ingestion/adapters/aws.py).
DOCMODEL_PREFIX = "doc-model/"
# The bucket's listing, as the objects part's reserved member: outside `doc-model/` and
# not `manifest.json`, so no member can take its name.
LISTING_MEMBER = "v1-object-listing.jsonl"
# v1's own upload prefixes (`object_key_for_upload`'s defaults).
UPLOAD_PREFIXES = ("uploads/", "novelty/")
# v1's private documents' paper ids (`docsuri_shared.private_docs`).
PRIVATE_PAPER_ID_PREFIX = "userdoc:"
# The status of a paper only v1's search index names.
INDEX_ONLY = "index-only"

STATUSES = {"PENDING": "pending", "ACTIVE": "active", "LOCKED": "locked",
            "DEACTIVATED": "deactivated"}
PROVIDERS = {"GOOGLE": "google", "ORCID": "orcid"}
# Each kind Q13 did not name: its v1 table and identifying column.
NOT_IN_SCOPE_TABLES = {
    "followed-topic": ("followed_topics", "id"),
    "digest-settings": ("digest_settings", "owner_id"),
    "glossary": ("user_glossary", "id"),
    "saved-search": ("saved_searches", "id"),
    "search-history": ("search_history", "id"),
    "behavior-event": ("user_behavior_events", "id"),
    "plan-record": ("plan_assignments", "id"),
    "private-upload": (None, None),
    "research-history": ("research_jobs", "job_id"),
    "novelty-history": ("novelty_jobs", "job_id"),
    "summary": ("content_jobs", "job_id"),
}
MAX_ROWS = 200_000


@dataclass(frozen=True)
class V1Account:
    source_id: str
    email: str | None
    password_hash: str | None
    state: str
    role: str
    created_at: dt.datetime


@dataclass(frozen=True)
class V1Link:
    provider: str
    subject: str
    account_id: str
    confirmed: bool
    linked_at: dt.datetime
    orcid_name: str | None


@dataclass(frozen=True)
class V1Preferences:
    owner_id: str
    enabled: bool
    summary_defaults: dict
    translation_defaults: dict
    has_weights: bool
    onboarded: bool


@dataclass(frozen=True)
class V1Paper:
    paper_id: str
    version: int
    doc_model_ref: str | None
    status: str
    figures: int


@dataclass(frozen=True)
class V1Saved:
    source_id: str
    owner_id: str
    arxiv_id: str
    added_at: dt.datetime


def encode_listing(entries: Iterable[Mapping]) -> bytes:
    """The listing's JSON Lines form, sorted by key: one `{"key", "size", "etag"}` per
    listed object."""
    rows = sorted(({"key": str(item["key"]), "size": int(item["size"]),
                    "etag": str(item["etag"])} for item in entries),
                  key=lambda item: item["key"])
    return b"".join(json.dumps(item, sort_keys=True, separators=(",", ":")).encode() + b"\n"
                    for item in rows)


def split_listing(payload: bytes) -> list[dict]:
    """The one parser of the listing (L1-37): each line's `{"key", "size", "etag"}`."""
    entries = []
    for line in payload.splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict) or set(value) != {"key", "size", "etag"}:
            raise ValueError("v1 object listing outside its form")
        entries.append({"key": str(value["key"]), "size": int(value["size"]),
                        "etag": str(value["etag"])})
    return entries


def split_objects(objects: Mapping[str, bytes]) -> tuple[dict[str, bytes], list[dict]]:
    """An objects part's members, with its reserved listing member taken out and parsed;
    a part without it reads as an empty listing."""
    members = {key: value for key, value in objects.items() if key != LISTING_MEMBER}
    payload = objects.get(LISTING_MEMBER)
    return members, split_listing(payload) if payload is not None else []


def upload_source_id(key: str) -> str:
    """A private upload's opaque source id: never its key, which names its owner and file."""
    return "upload:" + hashlib.sha256(key.encode()).hexdigest()[:16]


def _aware(moment: dt.datetime | None) -> dt.datetime:
    """v1 keeps some times without a zone; they are UTC."""
    if moment is None:
        return dt.datetime(1970, 1, 1, tzinfo=dt.UTC)
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=dt.UTC)


class V1Source:
    def __init__(self, conn, *, index_documents: list[dict] | None = None,
                 objects: Mapping[str, bytes] | None = None,
                 listing: Iterable[Mapping] | None = None):
        """`conn` reads the run's import database; `index_documents` and `objects` are
        the snapshot's archives, already checked against their manifests; `listing` is
        the bucket's listing (`split_listing`'s entries)."""
        self.conn = conn
        self.index_documents = list(index_documents or [])
        self.objects = dict(objects or {})
        self.listing = [dict(item) for item in listing or ()]

    def _exists(self, table: str) -> bool:
        row = self.conn.execute("SELECT to_regclass(%s) AS name", (f"public.{table}",)).fetchone()
        return (row["name"] if isinstance(row, dict) else row[0]) is not None

    def _rows(self, query: str, table: str, params: tuple = ()) -> list[dict]:
        if not self._exists(table):
            return []
        rows = self.conn.execute(query + f" LIMIT {MAX_ROWS + 1}", params).fetchall()
        if len(rows) > MAX_ROWS:
            raise ValueError("a v1 table exceeds the migration's bound")
        return rows

    # --- the Q13 groups ----------------------------------------------------------

    def accounts(self) -> list[V1Account]:
        closing = {row["account_id"] for row in self._rows(
            "SELECT account_id FROM account_deletions", "account_deletions")}
        accounts = []
        for row in self._rows("SELECT id,email,password_hash,status,role,created_at "
                              "FROM accounts ORDER BY id", "accounts"):
            # An account with a pending deletion is closed whatever its status says.
            state = ("pending_deletion" if row["id"] in closing
                     else STATUSES.get(row["status"], "pending"))
            accounts.append(V1Account(
                row["id"], row["email"], row["password_hash"], state,
                "admin" if (row["role"] or "").upper() == "ADMIN" else "user",
                _aware(row["created_at"])))
        return accounts

    def links(self) -> list[V1Link]:
        has_name = self._exists("social_identities") and self.conn.execute(
            "SELECT 1 FROM information_schema.columns WHERE table_name='social_identities' "
            "AND column_name='orcid_name'").fetchone() is not None
        name = "orcid_name" if has_name else "NULL AS orcid_name"
        return [
            V1Link(PROVIDERS.get(row["provider"], row["provider"].lower()),
                   row["provider_subject"], row["account_id"], row["status"] == "LINKED",
                   _aware(row["linked_at"]), row["orcid_name"])
            for row in self._rows(
                f"SELECT provider,provider_subject,account_id,status,linked_at,{name} "
                "FROM social_identities ORDER BY provider,provider_subject", "social_identities")
        ]

    def preferences(self) -> list[V1Preferences]:
        settings = {row["owner_id"]: row for row in self._rows(
            "SELECT owner_id,enabled FROM personalization_settings ORDER BY owner_id",
            "personalization_settings")}
        profiles = {row["owner_id"]: row for row in self._rows(
            "SELECT owner_id,category_weights,keyword_weights,summary_defaults,"
            "translation_defaults FROM user_interest_profiles ORDER BY owner_id",
            "user_interest_profiles")}
        onboarding = {row["owner_id"]: row["state"] for row in self._rows(
            "SELECT owner_id,state FROM onboarding_status ORDER BY owner_id",
            "onboarding_status")}
        result = []
        for owner in sorted(set(settings) | set(profiles) | set(onboarding)):
            profile = profiles.get(owner) or {}
            result.append(V1Preferences(
                owner, bool((settings.get(owner) or {}).get("enabled", True)),
                dict(profile.get("summary_defaults") or {}),
                dict(profile.get("translation_defaults") or {}),
                bool(profile.get("category_weights") or profile.get("keyword_weights")),
                onboarding.get(owner) == "completed"))
        return result

    def papers(self) -> list[V1Paper]:
        """The table's rows, each with its own reference and status, and each distinct
        (`paperId`, `version`) pair of the index documents that no row names, sorted by
        (`paper_id`, `version`)."""
        figures: dict[tuple[str, int], int] = {}
        for row in self._rows("SELECT paper_id,version,count(*) AS n FROM paper_asset "
                              "GROUP BY paper_id,version", "paper_asset"):
            figures[(row["paper_id"], int(row["version"]))] = int(row["n"])
        papers = {
            (row["paper_id"], int(row["version"])): V1Paper(
                row["paper_id"], int(row["version"]), row["doc_model_ref"], row["status"],
                figures.get((row["paper_id"], int(row["version"])), 0))
            for row in self._rows("SELECT paper_id,version,doc_model_ref,status FROM "
                                  "paper_version_state ORDER BY paper_id,version",
                                  "paper_version_state")
        }
        for pair in self._index_pairs():
            if pair not in papers:
                paper_id, version = pair
                papers[pair] = V1Paper(paper_id, version,
                                       f"{DOCMODEL_PREFIX}{paper_id}/v{version}.json",
                                       INDEX_ONLY, figures.get(pair, 0))
        return [papers[pair] for pair in sorted(papers)]

    def _index_pairs(self) -> set[tuple[str, int]]:
        """The index documents' (`paperId`, `version`) pairs that name a public paper: a
        non-empty paper id outside v1's private namespace, and a version of at least 1."""
        pairs = set()
        for document in self.index_documents:
            paper_id, version = document.get("paperId"), document.get("version")
            if (isinstance(paper_id, str) and paper_id
                    and not paper_id.startswith(PRIVATE_PAPER_ID_PREFIX)
                    and type(version) is int and version >= 1):
                pairs.add((paper_id, version))
        return pairs

    def saved(self) -> list[V1Saved]:
        return [
            V1Saved(row["id"], row["owner_id"], row["arxiv_id"], _aware(row["added_at"]))
            for row in self._rows("SELECT id,owner_id,arxiv_id,added_at FROM library_items "
                                  "ORDER BY owner_id,added_at,id", "library_items")
        ]

    # --- the snapshot's archives ------------------------------------------------------

    def metadata(self, paper_id: str, version: int) -> dict | None:
        """The paper's metadata from its index documents (title, authors, year, arXiv
        identifier, DOI, address), or None when the index holds none."""
        for document in self.index_documents:
            if document.get("paperId") == paper_id and int(document.get("version", 0)) == version:
                return document
        return None

    def embedded(self, paper_id: str, version: int) -> bool:
        """Whether v1's index holds vectors for this version (whose provenance is never
        proven, BR8.8)."""
        return any(
            document.get("paperId") == paper_id and int(document.get("version", 0)) == version
            and document.get("vector") for document in self.index_documents
        )

    @staticmethod
    def object_key(ref: str) -> str:
        """An object's key in the snapshot: v1's `s3://<bucket>/<key>` reference without
        its bucket."""
        if ref.startswith("s3://"):
            parts = ref.split("/", 3)
            return parts[3] if len(parts) == 4 else ""
        return ref

    def document(self, ref: str | None) -> dict | None:
        if not ref:
            return None
        ref = self.object_key(ref)
        if ref not in self.objects:
            return None
        try:
            value = json.loads(self.objects[ref])
        except ValueError:
            return None
        return value if isinstance(value, dict) else None

    # --- what is only counted -------------------------------------------------------------

    def not_in_scope(self) -> dict[str, list[str]]:
        """The source identifiers of each kind Q13 did not name."""
        result: dict[str, list[str]] = {}
        for kind in NOT_IN_SCOPE_KINDS:
            table, column = NOT_IN_SCOPE_TABLES[kind]
            if kind == "private-upload":
                # One opaque id per listed key under v1's upload prefixes; no body read.
                result[kind] = sorted({upload_source_id(item["key"]) for item in self.listing
                                       if str(item["key"]).startswith(UPLOAD_PREFIXES)})
                continue
            if table is None:
                result[kind] = []
                continue
            result[kind] = [str(row["source"]) for row in self._rows(
                f"SELECT {column}::text AS source FROM {table} ORDER BY 1", table)]
        return result
