"""Explicit, restartable U5 browser fixture provisioning in its owned realm.

Two synthetic accounts and two synthetic papers dated inside the rolling
digest window; no real user data, external content or provider calls. Retry
preserves account restrictions, spent usage, sessions and existing topics.
Secret fixture bytes never print.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import secrets
import sys
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "ops/src"))

from psycopg.types.json import Jsonb

from backend.local_profile import private_bytes
from backend.transactions import OwnerTransactions
from scripts import verify_docsuri_u5 as runner

FIXTURE_VERSION = "u5-browser-v1"
PAPERS = (
    {
        "paperId": "u5-paper-alpha",
        "versionId": "u5-paper-alpha/v1",
        "title": "Synthetic digest study alpha",
        "text": "Synthetic fixture alpha: a topic digest lists the papers published for the followed key inside the configured window. This text is a test fixture, not a published study.",
    },
    {
        "paperId": "u5-paper-beta",
        "versionId": "u5-paper-beta/v1",
        "title": "Synthetic digest study beta",
        "text": "Synthetic fixture beta: delivery repeats are prevented by the per-topic watermark, never by resending a failed run. This example is a test fixture.",
    },
)


def stable_id(run_id: str, purpose: str) -> UUID:
    return uuid5(NAMESPACE_URL, run_id + ":u5-browser:" + purpose)


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
                or record["email"] != f"{key.lower()}@u5.fixture.example.com"
                or not isinstance(record["password"], str)
                or not 24 <= len(record["password"]) <= 100
            ):
                raise runner.Refused("browser fixture account binding differs")
        return value
    value = {
        "runId": profile.run_id,
        "fixtureVersion": FIXTURE_VERSION,
        "state": "prepared",
        "accounts": {
            key: {
                "email": f"{key.lower()}@u5.fixture.example.com",
                "password": "U5!" + secrets.token_urlsafe(24),
                "accountId": str(stable_id(profile.run_id, key)),
            }
            for key in ("memberA", "memberB")
        },
        "papers": list(PAPERS),
    }
    # Persist credentials before their first database write; retry cannot invent
    # a different password after an interrupted acknowledgement.
    runner.private_json(target, value)
    return value


def seed_accounts(conn, fixtures: dict, hashes: dict, run_id: str) -> None:
    identifiers = [UUID(account["accountId"]) for account in fixtures["accounts"].values()]
    conn.execute(
        "SELECT pg_advisory_xact_lock(hashtext('u5-browser-fixture-accounts'))"
    )
    existing = conn.execute(
        "SELECT id,email FROM accounts.account WHERE id=ANY(%s)", (identifiers,)
    ).fetchall()
    count = conn.execute("SELECT count(*) AS count FROM accounts.account").fetchone()["count"]
    if count + len(identifiers) - len(existing) > 20:
        raise runner.Refused("finite account fixture allocation exhausted")
    expected = {UUID(value["accountId"]): value["email"] for value in fixtures["accounts"].values()}
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


def seed_corpus(conn, fixtures: dict) -> None:
    """Synthetic papers dated today: inside every rolling digest window."""
    for paper in PAPERS:
        metadata = {"fixtureVersion": FIXTURE_VERSION, "runId": fixtures["runId"], "synthetic": True}
        conn.execute(
            "INSERT INTO corpus.paper(id,title,authors,metadata,published_on,withdrawn) "
            "VALUES(%s,%s,%s,%s,CURRENT_DATE,false) ON CONFLICT(id) DO NOTHING",
            (
                paper["paperId"],
                paper["title"],
                Jsonb(["Synthetic fixture author"]),
                Jsonb(metadata),
            ),
        )
        conn.execute(
            "INSERT INTO corpus.version(id,paper_id,source_url,source_hash,version_label,"
            "private_path,eligible,purpose,provenance,content) "
            "VALUES(%s,%s,%s,%s,'v1','synthetic',true,'local-research',%s,%s) "
            "ON CONFLICT(id) DO NOTHING",
            (
                paper["versionId"],
                paper["paperId"],
                f"https://u5-fixture.invalid/{paper['paperId']}",
                "0" * 64,
                Jsonb(metadata),
                Jsonb(
                    {
                        "title": paper["title"],
                        "sections": [
                            {"heading": "Synthetic abstract", "anchor": "abstract", "text": paper["text"]}
                        ],
                        "provenance": {"fixtureVersion": FIXTURE_VERSION, "synthetic": True},
                    }
                ),
            ),
        )
        known = conn.execute(
            "SELECT eligible FROM corpus.version WHERE id=%s", (paper["versionId"],)
        ).fetchone()
        if not known or not known["eligible"]:
            raise runner.Refused("existing synthetic source binding differs")


def seed_resolve_fixture(conn, account_id: UUID) -> None:
    """Guarantee memberA's fixture topic carries one unresolved unknown outcome.

    The run is a genuine BR3.2 reconciliation case: it entered `sending` with a
    send-log skeleton and died before any transport fact or outcome was
    recorded, so the scheduled check finds no evidence (silence never
    reconciles) and the owner's explicit resolve control is the only path. A
    re-run closes leftovers through the legal unknown->failed transition and
    re-seeds on the first free fixture window; each earlier attempt's evidence
    gap stays recorded.
    """
    conn.execute("SELECT pg_advisory_xact_lock(hashtext('u5-browser-resolve-fixture'))")
    topic = conn.execute(
        "SELECT t.id,s.revision FROM topics.followed_topic t "
        "JOIN topics.digest_settings s ON s.topic_id=t.id "
        "WHERE t.account_id=%s AND t.topic_key='fixture-resolve-topic'",
        (account_id,),
    ).fetchone()
    if not topic:
        topic_id = uuid4()
        conn.execute(
            "INSERT INTO topics.followed_topic(id,account_id,topic_key,display_name) "
            "VALUES(%s,%s,'fixture-resolve-topic','해결 확인 주제')",
            (topic_id, account_id),
        )
        conn.execute(
            "INSERT INTO topics.digest_settings(id,topic_id,cadence,delivery_time_local,"
            "delivery_day,content_window_days) VALUES(%s,%s,'daily','23:59',NULL,7)",
            (uuid4(), topic_id),
        )
        revision = 1
    else:
        topic_id, revision = topic["id"], topic["revision"]
        # Component-suite quieting may have unsubscribed the shared fixture:
        # the browser fixture topic stays active with its settings intact.
        conn.execute(
            "UPDATE topics.followed_topic SET status='active',updated_at=clock_timestamp() "
            "WHERE id=%s AND status <> 'active'",
            (topic_id,),
        )
    # Leftovers from an earlier journey are closed honestly; the outcome rows
    # record that reconciliation, never a silent rewrite.
    conn.execute(
        "UPDATE topics.digest_run SET state='failed',updated_at=clock_timestamp() "
        "WHERE topic_id=%s AND state='unknown'",
        (topic_id,),
    )
    conn.execute(
        "UPDATE topics.delivery_outcome o SET reconciled_state='failed',reconciled_at="
        "clock_timestamp() FROM topics.digest_run r WHERE o.run_id=r.id AND r.state='failed' "
        "AND o.observed_state='unknown' AND o.reconciled_state IS NULL"
    )
    unresolved = conn.execute(
        "SELECT count(*) AS n FROM topics.digest_run WHERE topic_id=%s AND state='unknown'",
        (topic_id,),
    ).fetchone()["n"]
    if unresolved:
        return  # an interrupted retry left the case open: it stays open
    # Forward windows keep the seeded unknown the topic's latest run: real
    # chronology (BR2.4) can never place an open unknown behind a newer run,
    # so the fixture must not either. A future-window run also keeps the
    # scheduler from re-preparing over the fixture case.
    base = dt.datetime.now(dt.UTC).date()
    for offset in range(60):
        window = base + dt.timedelta(days=offset)
        taken = conn.execute(
            "SELECT 1 FROM topics.digest_run WHERE topic_id=%s AND window_start=%s "
            "AND window_end=%s AND state <> 'discarded'",
            (topic_id, window, window),
        ).fetchone()
        if taken:
            continue
        run_id = uuid4()
        conn.execute(
            "INSERT INTO topics.digest_run(id,topic_id,window_start,window_end,state,"
            "digest_content,settings_revision) VALUES(%s,%s,%s,%s,'prepared',%s,%s)",
            (run_id, topic_id, window, window, Jsonb([]), revision),
        )
        conn.execute(
            "UPDATE topics.digest_run SET state='sending',updated_at=clock_timestamp() "
            "WHERE id=%s",
            (run_id,),
        )
        conn.execute(
            "INSERT INTO topics.send_log_entry(id,run_id,path_kind) VALUES(%s,%s,'local-sink')",
            (uuid4(), run_id),
        )
        conn.execute(
            "UPDATE topics.digest_run SET state='unknown',updated_at=clock_timestamp() "
            "WHERE id=%s",
            (run_id,),
        )
        conn.execute(
            "INSERT INTO topics.delivery_outcome(id,run_id,observed_state) VALUES(%s,%s,'unknown')",
            (uuid4(), run_id),
        )
        return
    raise runner.Refused("fixture resolve-window allocation exhausted")


def setup(path: Path) -> dict:
    profile, value = runner.manifest(path)
    runner.require_resources(value)
    runner.require_stopped()
    fixtures = fixture_record(profile)
    transactions = OwnerTransactions(profile, process="maintenance")
    try:
        from backend.modules.accounts.services.guarded_entry import GuardedEntryService

        entry = GuardedEntryService(transactions)
        hashes = {
            key: entry._hash_password(account["password"])
            for key, account in fixtures["accounts"].items()
        }
        transactions.run(
            "accounts",
            lambda conn: seed_accounts(conn, fixtures, hashes, profile.run_id),
        )
        transactions.run("corpus", lambda conn: seed_corpus(conn, fixtures))
        transactions.run(
            "topics",
            lambda conn: seed_resolve_fixture(
                conn, UUID(fixtures["accounts"]["memberA"]["accountId"])
            ),
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
