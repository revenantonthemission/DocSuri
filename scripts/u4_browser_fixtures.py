"""Explicit, restartable U4 browser fixture provisioning in its owned realm.

Two synthetic accounts and two tiny synthetic documents; no real user data,
external content or provider calls. Retry preserves account/source restrictions,
spent usage, sessions and research work. Secret fixture bytes never print.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import sys
from dataclasses import asdict
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "ops/src"))

from psycopg.types.json import Jsonb

from backend.artifacts import Artifact, PrivateArtifacts
from backend.local_profile import private_bytes
from backend.modules.accounts.services.guarded_entry import GuardedEntryService
from backend.transactions import OwnerTransactions
from scripts import verify_docsuri_u4 as runner

FIXTURE_VERSION = "u4-browser-v1"
PAPERS = (
    {
        "paperId": "u4-paper-alpha",
        "versionId": "u4-paper-alpha/v1",
        "title": "Synthetic retrieval study alpha",
        "text": "Synthetic fixture alpha: retrieval selects a relevant passage before producing a source-bound answer. This text is a test fixture, not a published study.",
    },
    {
        "paperId": "u4-paper-beta",
        "versionId": "u4-paper-beta/v1",
        "title": "Synthetic retrieval study beta",
        "text": "Synthetic fixture beta: an unread source cannot establish a novelty claim. This example requires explicit uncertainty and is not a published study.",
    },
)


def stable_id(run_id: str, purpose: str) -> UUID:
    return uuid5(NAMESPACE_URL, run_id + ":u4-browser:" + purpose)


def fixture_record(profile) -> dict:
    target = profile.root / "browser-fixtures.json"
    if target.exists() or target.is_symlink():
        value = json.loads(private_bytes(target))
        if (
            value.get("runId") != profile.run_id
            or value.get("fixtureVersion") != FIXTURE_VERSION
            or value.get("state") not in {"prepared", "ready"}
            or set(value.get("accounts", {})) != {"memberA", "memberB"}
            or value.get("papers") != list(PAPERS)
        ):
            raise runner.Refused(
                "browser fixture identity differs; preserve for reconciliation"
            )
        for key, record in value["accounts"].items():
            if (
                set(record) != {"email", "password", "accountId"}
                or record["accountId"] != str(stable_id(profile.run_id, key))
                or record["email"] != f"{key.lower()}@u4.fixture.example.com"
                or not isinstance(record["password"], str)
                or not 24 <= len(record["password"]) <= 100
            ):
                raise runner.Refused("browser fixture account binding differs")
        if not isinstance(value.get("artifacts"), dict) or not set(
            value["artifacts"]
        ).issubset({p["paperId"] for p in PAPERS}):
            raise runner.Refused("browser fixture artifact bindings differ")
        if value["state"] == "ready" and set(value["artifacts"]) != {
            p["paperId"] for p in PAPERS
        }:
            raise runner.Refused("acknowledged fixture artifact binding is missing")
        for artifact in value["artifacts"].values():
            if (
                not isinstance(artifact, dict)
                or set(artifact) != {"name", "sha256", "size"}
                or not isinstance(artifact["name"], str)
                or not isinstance(artifact["sha256"], str)
                or not isinstance(artifact["size"], int)
                or not 0 < artifact["size"] <= 131072
            ):
                raise runner.Refused("browser fixture artifact record differs")
        return value
    value = {
        "runId": profile.run_id,
        "fixtureVersion": FIXTURE_VERSION,
        "state": "prepared",
        "accounts": {
            key: {
                "email": f"{key.lower()}@u4.fixture.example.com",
                "password": "U4!" + secrets.token_urlsafe(24),
                "accountId": str(stable_id(profile.run_id, key)),
            }
            for key in ("memberA", "memberB")
        },
        "papers": list(PAPERS),
        "artifacts": {},
    }
    # Persist credentials before their first database write; retry cannot invent
    # a different password after an interrupted acknowledgement.
    runner.private_json(target, value)
    return value


def document(paper: dict) -> dict:
    return {
        "title": paper["title"],
        "sections": [
            {
                "heading": "Synthetic abstract",
                "anchor": "abstract",
                "text": paper["text"],
            }
        ],
        "provenance": {"fixtureVersion": FIXTURE_VERSION, "synthetic": True},
    }


def prepare_artifacts(profile, fixtures: dict) -> None:
    files = PrivateArtifacts(profile.root / "corpus-files")
    for paper in PAPERS:
        content = json.dumps(document(paper), sort_keys=True).encode()
        existing = fixtures["artifacts"].get(paper["paperId"])
        if existing:
            if files.read(Artifact(**existing)) != content:
                raise runner.Refused("fixture bytes differ; no automatic replacement")
            continue
        entries = list(files.root.iterdir())
        if len(entries) >= 8 or sum(p.lstat().st_size for p in entries) >= 1024**2:
            raise runner.Refused(
                "fixture artifact allocation exhausted; preserve interrupted publications"
            )
        fixtures["artifacts"][paper["paperId"]] = asdict(files.publish(content))
        runner.private_json(profile.root / "browser-fixtures.json", fixtures)


def seed_accounts(conn, fixtures: dict, hashes: dict, run_id: str) -> None:
    identifiers = [
        UUID(account["accountId"]) for account in fixtures["accounts"].values()
    ]
    conn.execute(
        "SELECT pg_advisory_xact_lock(hashtext('u4-browser-fixture-accounts'))"
    )
    existing = conn.execute(
        "SELECT id,email FROM accounts.account WHERE id=ANY(%s)", (identifiers,)
    ).fetchall()
    count = conn.execute("SELECT count(*) AS count FROM accounts.account").fetchone()[
        "count"
    ]
    if count + len(identifiers) - len(existing) > 20:
        raise runner.Refused("finite account fixture allocation exhausted")
    expected = {
        UUID(value["accountId"]): value["email"]
        for value in fixtures["accounts"].values()
    }
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
            "INSERT INTO accounts.consent(account_id,purpose,granted) VALUES(%s,'local-research',true) ON CONFLICT(account_id,purpose) DO NOTHING",
            (UUID(account["accountId"]),),
        )


def seed_usage(conn, fixtures: dict) -> None:
    for account in fixtures["accounts"].values():
        conn.execute(
            "INSERT INTO usage.entitlement(account_id,allocation,policy) VALUES(%s,4,'synthetic-four-no-reset') ON CONFLICT(account_id) DO NOTHING",
            (UUID(account["accountId"]),),
        )


def seed_corpus(conn, fixtures: dict, run_id: str) -> None:
    changed = False
    for paper in PAPERS:
        artifact = fixtures["artifacts"][paper["paperId"]]
        metadata = {
            "fixtureVersion": FIXTURE_VERSION,
            "runId": run_id,
            "synthetic": True,
        }
        conn.execute(
            "INSERT INTO corpus.paper(id,title,authors,metadata) VALUES(%s,%s,%s,%s) ON CONFLICT(id) DO NOTHING",
            (
                paper["paperId"],
                paper["title"],
                Jsonb(["Synthetic fixture author"]),
                Jsonb(metadata),
            ),
        )
        created = conn.execute(
            "INSERT INTO corpus.version(id,paper_id,source_url,source_hash,version_label,private_path,eligible,purpose,provenance,content) "
            "VALUES(%s,%s,%s,%s,'v1',%s,true,'local-research',%s,%s) ON CONFLICT(id) DO NOTHING RETURNING id",
            (
                paper["versionId"],
                paper["paperId"],
                f"https://u4-fixture.invalid/{paper['paperId']}",
                artifact["sha256"],
                artifact["name"],
                Jsonb(metadata),
                Jsonb(document(paper)),
            ),
        ).fetchone()
        known = conn.execute(
            "SELECT source_hash,private_path FROM corpus.version WHERE id=%s",
            (paper["versionId"],),
        ).fetchone()
        if known != {
            "source_hash": artifact["sha256"],
            "private_path": artifact["name"],
        }:
            raise runner.Refused("existing synthetic source binding differs")
        if created:
            changed = True
            conn.execute(
                "INSERT INTO corpus.projection(version_id,ordinal,content_hash,anchor,section,text_content) VALUES(%s,0,%s,'abstract','Synthetic abstract',%s)",
                (
                    paper["versionId"],
                    hashlib.sha256(paper["text"].encode()).hexdigest(),
                    paper["text"],
                ),
            )
    if changed:
        # Publish only the acknowledged synthetic addition; a retry performs no
        # update and cannot resurrect a withdrawn version or rewrite history.
        generation = stable_id(run_id, "corpus-generation")
        snapshot = conn.execute(
            "SELECT encode(sha256(convert_to(COALESCE(jsonb_agg(snapshot ORDER BY id),'[]'::jsonb)::text,'UTF8')),'hex') AS digest FROM (SELECT v.id,v.source_hash,v.eligibility_revision,v.eligible,p.withdrawn,count(c.ordinal) AS chunks FROM corpus.version v JOIN corpus.paper p ON p.id=v.paper_id LEFT JOIN corpus.projection c ON c.version_id=v.id GROUP BY v.id,p.withdrawn) snapshot"
        ).fetchone()["digest"]
        conn.execute(
            "INSERT INTO corpus.generation(id,manifest_hash,compatibility_revision,state,verified_at,published_at) VALUES(%s,%s,'u4-synthetic-1','published',clock_timestamp(),clock_timestamp()) ON CONFLICT(id) DO NOTHING",
            (generation, snapshot),
        )
        conn.execute(
            "UPDATE corpus.publication SET generation_id=%s,revision=gen_random_uuid(),manifest_hash=%s,published_generation=%s,published_at=clock_timestamp() WHERE singleton",
            (generation, snapshot, generation),
        )


def setup(path: Path) -> dict:
    profile, value = runner.manifest(path)
    runner.require_resources(value)
    runner.require_stopped()
    fixtures = fixture_record(profile)
    prepare_artifacts(profile, fixtures)
    transactions = OwnerTransactions(profile, process="maintenance")
    try:
        entry = GuardedEntryService(transactions)
        hashes = {
            key: entry._hash_password(account["password"])
            for key, account in fixtures["accounts"].items()
        }
        transactions.run(
            "accounts",
            lambda conn: seed_accounts(conn, fixtures, hashes, profile.run_id),
        )
        transactions.run("usage", lambda conn: seed_usage(conn, fixtures))
        transactions.run(
            "corpus", lambda conn: seed_corpus(conn, fixtures, profile.run_id)
        )
    finally:
        transactions.close()
    if fixtures["state"] != "ready":
        fixtures["state"] = "ready"
        runner.private_json(profile.root / "browser-fixtures.json", fixtures)
    return {"state": "fixtures-ready", "accounts": 2, "papers": 2, "synthetic": True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment-file", type=Path, required=True)
    parser.add_argument("--action", choices=["setup"], required=True)
    args = parser.parse_args()
    with runner.exclusive():
        result = setup(args.environment_file)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (runner.Refused, ValueError, OSError) as error:
        print(json.dumps({"state": "refused", "category": type(error).__name__}))
        raise SystemExit(1) from None
