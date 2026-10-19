"""Operator steps for the one bounded real digest demonstration. Never sends.

  check      validate the realm's activation record, report whether the provider
             variables are set (names only, never values) and the remaining allocation
  provision  ensure the permitted recipient's account, consent, settings and topic
  prepare    prepare (never send) today's digest run for that topic
  preview    print the exact provider submission with the bearer token redacted
  outcome    read the newest run's recorded outcome, refusal detail (who refused;
             the provider's HTTP status and error name) and receipt (read-only)

No action constructs the Resend adapter, issues a cancellation capability or
reads the credential's value. A send happens only after the operator starts the
owned host with `scripts/serve_docsuri_u5.py --real-delivery`, which spends the
single allocation on the prepared run. The host must be stopped for every
action that writes (provision, prepare), so nothing can send meanwhile.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "ops/src"))

from psycopg.types.json import Jsonb

from backend.modules.accounts.integrations.digest_email import (
    LOCAL_REFUSALS,
    PROVIDER_REFUSAL,
)
from backend.modules.personalization.guarded_service import ASSISTANCE_DEFAULTS
from backend.modules.topics.preparation import DigestPreparation
from backend.modules.topics.repository import RUN_COLUMNS, TopicsRepository
from backend.transactions import OwnerTransactions
from backend.u5_policy import REAL_DEMONSTRATION_TOPICS
from backend.u5_real_delivery import (
    RealDeliveryRefused,
    load_activation,
    message_preview,
    provider_configuration,
)

TOPIC_KEY = "real-delivery-demonstration"
LANGUAGES = ("en", "ko")
ACCOUNT_ALLOCATION = 20
# Failures decided on this host before any provider call: the delivery service's
# recipient check plus the adapter's own pre-network refusals.
LOCAL_FAILURE_REASONS = ("recipient-unavailable", *LOCAL_REFUSALS)


def stable_id(run_id: str, purpose: str) -> UUID:
    return uuid5(NAMESPACE_URL, run_id + ":u5-real:" + purpose)


def allocation(transactions) -> dict:
    spent = TopicsRepository(transactions).system(
        lambda conn: conn.execute(
            "SELECT count(*) AS n FROM topics.send_log_entry WHERE path_kind='real'"
        ).fetchone()["n"]
    )
    limit = REAL_DEMONSTRATION_TOPICS.real_send_limit
    return {"limit": limit, "spent": spent, "remaining": max(0, limit - spent)}


def check(profile, transactions, environ: Mapping[str, str]) -> dict:
    """Read-only readiness report; refusals are reported, never bypassed."""
    report = {
        "emailProviderIsResend": environ.get("EMAIL_PROVIDER") == "resend",
        "resendApiKeyPresent": bool(environ.get("RESEND_API_KEY")),
        "allocation": allocation(transactions),
        "evidenceRetentionDays": REAL_DEMONSTRATION_TOPICS.real_evidence_retention_days,
    }
    try:
        activation = load_activation(profile)
    except RealDeliveryRefused as refusal:
        return dict(report, activation=str(refusal), ready=False)
    try:
        provider_configuration(activation, environ)
        provider = "ok"
    except RealDeliveryRefused as refusal:
        provider = str(refusal)
    recipient = _recipient_state(transactions, profile, activation)
    ready = (
        provider == "ok"
        and report["allocation"]["remaining"] > 0
        and recipient["granted"]
    )
    return dict(
        report,
        activation="ok",
        provider=provider,
        capabilityExpiresAt=activation.capability_expires_at.isoformat(),
        recipient=recipient,
        ready=ready,
    )


def _recipient_state(transactions, profile, activation) -> dict:
    account_id = stable_id(profile.run_id, "recipient")
    row = TopicsRepository(transactions).digest_recipient(account_id)
    return {
        "provisioned": row["email"] == activation.permitted_recipient,
        "granted": bool(row["granted"])
        and row["email"] == activation.permitted_recipient,
    }


def _validated_choices(language: str, time_zone: str, delivery_time: str) -> dt.time:
    if language not in LANGUAGES:
        raise RealDeliveryRefused("language must be en or ko")
    try:
        ZoneInfo(time_zone)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise RealDeliveryRefused("time zone must be an installed IANA zone") from error
    try:
        return dt.time.fromisoformat(delivery_time)
    except ValueError as error:
        raise RealDeliveryRefused("delivery time must be HH:MM") from error


def _ensure_account(conn, account_id: UUID, activation, run_id: str) -> None:
    conn.execute("SELECT pg_advisory_xact_lock(hashtext('u5-real-recipient-account'))")
    existing = conn.execute(
        "SELECT email FROM accounts.account WHERE id=%s", (account_id,)
    ).fetchone()
    if existing is None:
        if conn.execute("SELECT count(*) AS n FROM accounts.account").fetchone()[
            "n"
        ] >= (ACCOUNT_ALLOCATION):
            raise RealDeliveryRefused("finite account allocation exhausted")
        taken = conn.execute(
            "SELECT 1 FROM accounts.account WHERE email=%s",
            (activation.permitted_recipient,),
        ).fetchone()
        if taken:
            raise RealDeliveryRefused(
                "the permitted address belongs to another account"
            )
        # No sign-in credential exists for this account: delivery needs none, and
        # cancellation uses only the emailed single-use capability.
        conn.execute(
            "INSERT INTO accounts.account(id,email,password_hash,verified,active,"
            "authority_revision,display_name) "
            "VALUES(%s,%s,'not-login-material',true,true,%s,'real-delivery recipient')",
            (
                account_id,
                activation.permitted_recipient,
                stable_id(run_id, "authority"),
            ),
        )
    elif existing["email"] != activation.permitted_recipient:
        raise RealDeliveryRefused(
            "the provisioned recipient differs from the activation"
        )
    # The recipient's explicit authorization for this demonstration is the consent.
    conn.execute(
        "INSERT INTO accounts.consent(account_id,purpose,granted) "
        "VALUES(%s,'local-research',true) ON CONFLICT(account_id,purpose) DO NOTHING",
        (account_id,),
    )


def provision(
    profile, transactions, activation, *, language, time_zone, topic_name, delivery_time
):
    """Idempotently create the permitted recipient's owned demonstration records."""
    scheduled = _validated_choices(language, time_zone, delivery_time)
    if not isinstance(topic_name, str) or not 1 <= len(topic_name) <= 80:
        raise RealDeliveryRefused("topic name must be 1-80 characters")
    account_id = stable_id(profile.run_id, "recipient")
    topic_id = stable_id(profile.run_id, "topic")
    transactions.run(
        "accounts",
        lambda conn: _ensure_account(conn, account_id, activation, profile.run_id),
    )
    defaults = {
        "timeZone": time_zone,
        "assistanceDefaults": dict(ASSISTANCE_DEFAULTS, languageId=language),
    }
    transactions.run(
        "personalization",
        lambda conn: conn.execute(
            "INSERT INTO personalization.settings(account_id,revision,defaults) "
            "VALUES(%s,%s,%s) ON CONFLICT(account_id) DO NOTHING",
            (account_id, uuid4(), Jsonb(defaults)),
        ),
    )

    def follow(conn):
        conn.execute(
            "INSERT INTO topics.followed_topic(id,account_id,topic_key,display_name) "
            "VALUES(%s,%s,%s,%s) ON CONFLICT(id) DO NOTHING",
            (topic_id, account_id, TOPIC_KEY, topic_name),
        )
        conn.execute(
            "INSERT INTO topics.digest_settings"
            "(id,topic_id,cadence,delivery_time_local,content_window_days) "
            "VALUES(%s,%s,'daily',%s,7) ON CONFLICT(topic_id) DO NOTHING",
            (stable_id(profile.run_id, "settings"), topic_id, scheduled),
        )

    transactions.run("topics", follow)
    preferences = _preferences(transactions, account_id)
    return {
        "state": "provisioned",
        "topicId": str(topic_id),
        "effectivePreferences": {
            key: preferences.get(key)
            for key in ("languageId", "presentationLevelId", "timeZone")
        },
        "recipient": _recipient_state(transactions, profile, activation),
    }


def _preferences(transactions, account_id: UUID) -> dict:
    return TopicsRepository(transactions).system(
        lambda conn: conn.execute(
            "SELECT personalization.digest_preferences(%s) AS value", (account_id,)
        ).fetchone()["value"]
    )


def _topic(transactions, profile) -> dict:
    row = TopicsRepository(transactions).system(
        lambda conn: conn.execute(
            "SELECT t.id,t.account_id,t.status,s.revision,s.content_window_days "
            "FROM topics.followed_topic t JOIN topics.digest_settings s ON s.topic_id=t.id "
            "WHERE t.id=%s",
            (stable_id(profile.run_id, "topic"),),
        ).fetchone()
    )
    if row is None or row["status"] != "active":
        raise RealDeliveryRefused(
            "provision the permitted recipient's active topic first"
        )
    return row


def prepare(
    profile, transactions, activation, *, now: dt.datetime | None = None
) -> dict:
    """Prepare (adopt) today's window in the recipient's zone; never begins a send."""
    if not _recipient_state(transactions, profile, activation)["granted"]:
        raise RealDeliveryRefused(
            "the permitted recipient is not provisioned with consent"
        )
    topic = _topic(transactions, profile)
    zone = _preferences(transactions, topic["account_id"]).get("timeZone")
    if not zone:
        raise RealDeliveryRefused("the recipient has no confirmed time zone")
    today = (now or dt.datetime.now(dt.UTC)).astimezone(ZoneInfo(zone)).date()
    window = (today - dt.timedelta(days=topic["content_window_days"] - 1), today)
    preparation = DigestPreparation(
        transactions, None, policy=REAL_DEMONSTRATION_TOPICS
    )
    run, adopted = preparation.prepare(topic["id"], window, topic["revision"])
    return {
        "runId": str(run["id"]),
        "state": run["state"],
        "adopted": adopted,
        "window": [window[0].isoformat(), window[1].isoformat()],
        "items": len(run["digest_content"] or []),
    }


def preview(profile, transactions, activation) -> dict:
    """The exact submission for the newest prepared run, bearer token redacted."""
    topic = _topic(transactions, profile)
    run = TopicsRepository(transactions).system(
        lambda conn: conn.execute(
            "SELECT " + RUN_COLUMNS + " FROM topics.digest_run WHERE topic_id=%s "
            "AND state='prepared' ORDER BY created_at DESC,id LIMIT 1",
            (topic["id"],),
        ).fetchone()
    )
    if run is None:
        raise RealDeliveryRefused("no prepared run to preview; run prepare first")
    return dict(message_preview(run, activation), allocation=allocation(transactions))


def refusal_view(row) -> dict | None:
    """Who refused a failed run, from recorded facts only (never provider text).

    Local reasons were decided on this host before any network call. A provider
    refusal shows the recorded HTTP status and validated error name; a provider-
    path refusal recorded without them (before refusal detail existed) says so
    instead of guessing whether the provider was reached.
    """
    if row.get("state") != "failed" or not row.get("failure_reason"):
        return None
    reason = row["failure_reason"]
    if reason in LOCAL_FAILURE_REASONS:
        return {"decidedBy": "local", "reason": reason, "reachedProvider": False}
    if reason != PROVIDER_REFUSAL:
        return {"decidedBy": "unclassified", "reason": reason, "reachedProvider": None}
    status = row.get("provider_status")
    return {
        "decidedBy": "provider",
        "reason": reason,
        "reachedProvider": True if status is not None else None,
        "httpStatus": status,
        "errorName": row.get("provider_error"),
        "detailRecorded": status is not None,
    }


def outcome_view(row) -> dict:
    """Recorded facts of one run; the receipt also as a digest for long-lived evidence."""
    receipt = row.get("transport_receipt")
    send_log = None
    if row.get("path_kind") is not None:
        send_log = {
            "pathKind": row["path_kind"],
            "attemptedAt": row["attempted_at"],
            "acknowledgedAt": row["acknowledged_at"],
            "providerReceipt": receipt,
            "providerReceiptSha256": hashlib.sha256(receipt.encode()).hexdigest()
            if receipt
            else None,
            "evidenceRetainUntil": row["evidence_retain_until"],
            "evidenceExpired": row["evidence_expired_at"] is not None,
        }
    return {
        "runId": str(row["id"]),
        "state": row["state"],
        "window": [str(row["window_start"]), str(row["window_end"])],
        "observedState": row.get("observed_state"),
        "reconciledState": row.get("reconciled_state"),
        "failureReason": row.get("failure_reason"),
        "refusal": refusal_view(row),
        "sendLog": send_log,
    }


def outcome(profile, transactions) -> dict:
    """Read-only: the newest non-discarded run of the demonstration topic."""
    topic = _topic(transactions, profile)
    row = TopicsRepository(transactions).system(
        lambda conn: conn.execute(
            "SELECT r.id,r.state,r.window_start,r.window_end,o.observed_state,"
            "o.reconciled_state,o.failure_reason,o.provider_status,o.provider_error,"
            "l.path_kind,l.attempted_at,"
            "l.acknowledged_at,l.transport_receipt,l.evidence_retain_until,"
            "l.evidence_expired_at FROM topics.digest_run r "
            "LEFT JOIN topics.delivery_outcome o ON o.run_id=r.id "
            "LEFT JOIN topics.send_log_entry l ON l.run_id=r.id "
            "WHERE r.topic_id=%s AND r.state<>'discarded' "
            "ORDER BY r.created_at DESC,r.id LIMIT 1",
            (topic["id"],),
        ).fetchone()
    )
    if row is None:
        raise RealDeliveryRefused("no run recorded for the demonstration topic")
    return dict(outcome_view(row), allocation=allocation(transactions))


def run_action(args, profile, transactions, environ) -> dict:
    if args.action == "check":
        return check(profile, transactions, environ)
    if args.action == "outcome":
        return outcome(profile, transactions)
    activation = load_activation(profile)
    if args.action == "provision":
        return provision(
            profile,
            transactions,
            activation,
            language=args.language,
            time_zone=args.time_zone,
            topic_name=args.topic_name,
            delivery_time=args.delivery_time,
        )
    if args.action == "prepare":
        return prepare(profile, transactions, activation)
    return preview(profile, transactions, activation)


def main() -> int:
    from scripts import verify_docsuri_u5 as runner

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment-file", type=Path, required=True)
    parser.add_argument(
        "--action",
        choices=["check", "provision", "prepare", "preview", "outcome"],
        required=True,
    )
    parser.add_argument("--language", choices=LANGUAGES)
    parser.add_argument("--time-zone")
    parser.add_argument("--topic-name", default="DocSuri real delivery check")
    parser.add_argument("--delivery-time", default="09:00")
    args = parser.parse_args()
    if args.action == "provision" and (not args.language or not args.time_zone):
        parser.error("provision requires --language and --time-zone")
    with runner.exclusive():
        profile, value = runner.manifest(args.environment_file)
        runner.require_resources(value)
        # Writing and preview actions run with the host stopped, so nothing can
        # send meanwhile; check and outcome only read and may run beside the host.
        if args.action not in ("check", "outcome"):
            runner.require_stopped()
        transactions = OwnerTransactions(profile, process="maintenance")
        try:
            result = run_action(args, profile, transactions, os.environ)
        except RealDeliveryRefused as refusal:
            print(json.dumps({"state": "refused", "reason": str(refusal)}))
            return 1
        finally:
            transactions.close()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
