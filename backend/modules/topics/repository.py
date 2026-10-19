"""Owner-scoped repository for every TopicsDigests entity.

One writer per owned table. Every owner-scoped unit rechecks live session
authority through `guard` before touching rows (BR5.1); worker units run in
their own bounded system transactions. Multi-step flows are atomic inside a
single serializable transaction: settings saves discard prepared runs
(BR1.3), send starts enforce active status, consent and the unreconciled-
unknown pause in the checked transition itself (BR3.1/BR3.2/BR4.2), and
terminal sends append the delivery watermark from the run's own content
(BR2.2). Window ordering and the run state machine are enforced in place by
the schema guards (BR2.4); this layer maps refusals to typed errors.
"""

import datetime as dt
from uuid import uuid4

import psycopg
from psycopg.types.json import Jsonb

from backend.modules.accounts.integrations.digest_email import (
    PROVIDER_REFUSAL,
    valid_provider_refusal,
)
from backend.transactions import Authority, OwnerTransactions, guard
from backend.u5_policy import REAL_EVIDENCE_RETENTION_DAYS_MAX

from .errors import TopicsError
from .presentation import preference_fingerprint, render_presentation

CADENCES = ("daily", "weekly")
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
WINDOW_DAYS = (7, 30)
DEFAULT_SETTINGS = {
    "cadence": "daily",
    "delivery_time_local": dt.time(8, 0),
    "delivery_day": None,
    "content_window_days": 7,
}
RUN_COLUMNS = (
    "id,topic_id,window_start,window_end,state,digest_content,settings_revision,"
    "created_at,updated_at,preference_snapshot,presentation,request_key"
)


def _invalid(message: str):
    raise TopicsError("INVALID_ARGUMENT", current={"field": message})


def _validated_recipient(recipient):
    """None (no address scope) or one bounded address string for the real adapter."""
    if recipient is None:
        return
    if not isinstance(recipient, str) or not 3 <= len(recipient) <= 320 or "@" not in recipient:
        _invalid("recipient")


def _validated_settings(cadence, delivery_time_local, delivery_day, content_window_days):
    if cadence not in CADENCES:
        _invalid("cadence")
    if not isinstance(delivery_time_local, dt.time):
        _invalid("deliveryTimeLocal")
    if delivery_day is not None and delivery_day not in WEEKDAYS:
        _invalid("deliveryDay")
    if content_window_days not in WINDOW_DAYS:
        _invalid("contentWindowDays")
    if (cadence == "weekly") != (delivery_day is not None):
        _invalid("cadence")


class TopicsRepository:
    def __init__(self, transactions: OwnerTransactions):
        self.transactions = transactions

    def run(self, authority: Authority, action):
        def guarded(conn):
            guard(conn, authority)
            return action(conn)

        return self.transactions.run("topics", guarded)

    def system(self, action):
        return self.transactions.run("topics", action)

    # -- owner-scoped helpers -------------------------------------------------

    @staticmethod
    def topic(conn, authority, topic_id, *, active=False):
        row = conn.execute(
            "SELECT * FROM topics.followed_topic WHERE id=%s AND account_id=%s FOR UPDATE",
            (topic_id, authority.account_id),
        ).fetchone()
        if not row:
            raise TopicsError("NOT_FOUND")
        if active and row["status"] != "active":
            raise TopicsError("NOT_FOUND")
        return row

    @staticmethod
    def discard_prepared(conn, topic_id):
        return [
            row["id"]
            for row in conn.execute(
                "UPDATE topics.digest_run SET state='discarded',updated_at=clock_timestamp() "
                "WHERE topic_id=%s AND state='prepared' RETURNING id",
                (topic_id,),
            ).fetchall()
        ]

    @staticmethod
    def apply_watermark(conn, run):
        """Append the run's own content to the topic watermark; repeats are no-ops."""
        items = run["digest_content"] if isinstance(run["digest_content"], list) else []
        identifiers = sorted(
            {
                item["versionId"]
                for item in items
                if isinstance(item, dict) and isinstance(item.get("versionId"), str)
            }
        )
        if not identifiers:
            return 0
        return len(
            conn.execute(
                "INSERT INTO topics.topic_delivery_watermark(id,topic_id,content_id,"
                "included_in_run_id) SELECT gen_random_uuid(),%s,c,%s "
                "FROM unnest(%s::text[]) AS c "
                "ON CONFLICT (topic_id,content_id) DO NOTHING RETURNING 1",
                (run["topic_id"], run["id"], identifiers),
            ).fetchall()
        )

    @staticmethod
    def _transition(conn, run_id, expected_state, next_state):
        return conn.execute(
            "UPDATE topics.digest_run SET state=%s,updated_at=clock_timestamp() "
            "WHERE id=%s AND state=%s RETURNING " + RUN_COLUMNS,
            (next_state, run_id, expected_state),
        ).fetchone()

    # -- owner-scoped units ---------------------------------------------------

    def follow(self, authority, topic_key, display_name):
        if not isinstance(topic_key, str) or not 1 <= len(topic_key.encode()) <= 160:
            _invalid("topicKey")
        if not isinstance(display_name, str) or not 1 <= len(display_name.encode()) <= 160:
            _invalid("displayName")

        def follow(conn):
            row = conn.execute(
                "SELECT * FROM topics.followed_topic WHERE account_id=%s AND topic_key=%s "
                "FOR UPDATE",
                (authority.account_id, topic_key),
            ).fetchone()
            if row and row["status"] == "active":
                raise TopicsError("DUPLICATE")
            if row:
                conn.execute(
                    "UPDATE topics.followed_topic SET status='active',updated_at="
                    "clock_timestamp() WHERE id=%s",
                    (row["id"],),
                )
                conn.execute(
                    "UPDATE topics.digest_settings SET cadence=%s,delivery_time_local=%s,"
                    "delivery_day=%s,content_window_days=%s,revision=revision+1,updated_at="
                    "clock_timestamp() WHERE topic_id=%s",
                    (
                        DEFAULT_SETTINGS["cadence"],
                        DEFAULT_SETTINGS["delivery_time_local"],
                        DEFAULT_SETTINGS["delivery_day"],
                        DEFAULT_SETTINGS["content_window_days"],
                        row["id"],
                    ),
                )
                refreshed = conn.execute(
                    "SELECT * FROM topics.followed_topic WHERE id=%s", (row["id"],)
                ).fetchone()
                return {"topic": refreshed, "reactivated": True}
            inserted = conn.execute(
                "INSERT INTO topics.followed_topic(id,account_id,topic_key,display_name) "
                "VALUES(%s,%s,%s,%s) RETURNING *",
                (uuid4(), authority.account_id, topic_key, display_name),
            ).fetchone()
            conn.execute(
                "INSERT INTO topics.digest_settings(id,topic_id,cadence,delivery_time_local,"
                "delivery_day,content_window_days) VALUES(%s,%s,%s,%s,%s,%s)",
                (
                    uuid4(),
                    inserted["id"],
                    DEFAULT_SETTINGS["cadence"],
                    DEFAULT_SETTINGS["delivery_time_local"],
                    DEFAULT_SETTINGS["delivery_day"],
                    DEFAULT_SETTINGS["content_window_days"],
                ),
            )
            return {"topic": inserted, "reactivated": False}

        return self.run(authority, follow)

    def list_topics(self, authority, limit=50):
        if type(limit) is not int or not 1 <= limit <= 50:
            _invalid("limit")
        return self.run(
            authority,
            lambda conn: conn.execute(
                "SELECT t.id,t.topic_key,t.display_name,t.status,t.followed_at,t.updated_at,"
                "s.cadence,s.delivery_time_local,s.delivery_day,s.content_window_days,"
                "s.revision AS settings_revision,lr.id AS last_run_id,"
                "lr.state AS last_run_state,"
                "lr.window_end AS last_run_window_end,lo.observed_state AS last_outcome_state "
                "FROM topics.followed_topic t "
                "JOIN topics.digest_settings s ON s.topic_id=t.id "
                "LEFT JOIN LATERAL (SELECT r.id,r.state,r.window_end FROM topics.digest_run r "
                "WHERE r.topic_id=t.id AND r.state <> 'discarded' "
                "ORDER BY r.window_start DESC,r.created_at DESC LIMIT 1) lr ON true "
                "LEFT JOIN LATERAL (SELECT o.observed_state FROM topics.delivery_outcome o "
                "JOIN topics.digest_run r2 ON r2.id=o.run_id WHERE r2.topic_id=t.id "
                "ORDER BY o.observed_at DESC LIMIT 1) lo ON true "
                "WHERE t.account_id=%s AND t.status='active' "
                "ORDER BY t.followed_at DESC,t.id DESC LIMIT %s",
                (authority.account_id, limit),
            ).fetchall(),
        )

    def read_topic(self, authority, topic_id, *, run_limit=10):
        if type(run_limit) is not int or not 1 <= run_limit <= 50:
            _invalid("runLimit")

        def read(conn):
            topic = self.topic(conn, authority, topic_id)
            settings = conn.execute(
                "SELECT * FROM topics.digest_settings WHERE topic_id=%s", (topic_id,)
            ).fetchone()
            runs = conn.execute(
                "SELECT r.id,r.topic_id,r.window_start,r.window_end,r.state,r.digest_content,"
                "r.settings_revision,r.created_at,r.updated_at,r.preference_snapshot,r.presentation,o.observed_state,"
                "o.reconciled_state,o.failure_reason,l.path_kind,l.transport_receipt,"
                "l.acknowledged_at FROM topics.digest_run r "
                "LEFT JOIN topics.delivery_outcome o ON o.run_id=r.id "
                "LEFT JOIN topics.send_log_entry l ON l.run_id=r.id "
                "WHERE r.topic_id=%s ORDER BY r.window_start DESC,r.created_at DESC LIMIT %s",
                (topic_id, run_limit),
            ).fetchall()
            return {
                "topic": topic,
                "settings": settings,
                "runs": runs,
                "effectivePreferences": conn.execute(
                    "SELECT personalization.digest_preferences(%s) AS value",
                    (authority.account_id,),
                ).fetchone()["value"],
            }

        return self.run(authority, read)

    def read_run(self, authority, topic_id, run_id):
        def read(conn):
            self.topic(conn, authority, topic_id)
            run = conn.execute(
                "SELECT r.id,r.topic_id,r.window_start,r.window_end,r.state,r.digest_content,"
                "r.settings_revision,r.created_at,r.updated_at,r.preference_snapshot,r.presentation,o.observed_state,"
                "o.reconciled_state,o.reconciled_at,o.failure_reason,o.observed_at,"
                "l.path_kind,l.transport_receipt,l.acknowledged_at "
                "FROM topics.digest_run r "
                "LEFT JOIN topics.delivery_outcome o ON o.run_id=r.id "
                "LEFT JOIN topics.send_log_entry l ON l.run_id=r.id "
                "WHERE r.id=%s AND r.topic_id=%s",
                (run_id, topic_id),
            ).fetchone()
            if not run:
                raise TopicsError("NOT_FOUND")
            return run

        return self.run(authority, read)

    def save_settings(
        self,
        authority,
        topic_id,
        expected_revision,
        cadence,
        delivery_time_local,
        delivery_day,
        content_window_days,
    ):
        if type(expected_revision) is not int or expected_revision < 1:
            _invalid("revision")
        _validated_settings(cadence, delivery_time_local, delivery_day, content_window_days)

        def save(conn):
            self.topic(conn, authority, topic_id, active=True)
            settings = conn.execute(
                "SELECT * FROM topics.digest_settings WHERE topic_id=%s FOR UPDATE", (topic_id,)
            ).fetchone()
            if not settings:
                raise TopicsError("NOT_FOUND")
            if settings["revision"] != expected_revision:
                raise TopicsError("CONFLICT", current={"revision": settings["revision"]})
            unchanged = (
                settings["cadence"] == cadence
                and settings["delivery_time_local"] == delivery_time_local
                and settings["delivery_day"] == delivery_day
                and settings["content_window_days"] == content_window_days
            )
            if unchanged:
                return {"settings": settings, "discarded": [], "unchanged": True}
            updated = conn.execute(
                "UPDATE topics.digest_settings SET cadence=%s,delivery_time_local=%s,"
                "delivery_day=%s,content_window_days=%s,revision=revision+1,updated_at="
                "clock_timestamp() WHERE id=%s RETURNING *",
                (
                    cadence,
                    delivery_time_local,
                    delivery_day,
                    content_window_days,
                    settings["id"],
                ),
            ).fetchone()
            discarded = self.discard_prepared(conn, topic_id)
            return {"settings": updated, "discarded": discarded, "unchanged": False}

        return self.run(authority, save)

    def unsubscribe(self, authority, topic_id):
        def unsubscribe(conn):
            topic = self.topic(conn, authority, topic_id)
            return self.unsubscribe_locked(conn, topic)

        return self.run(authority, unsubscribe)

    @staticmethod
    def unsubscribe_locked(conn, topic):
        """Cancellation only; caller must authorize and lock the topic first."""
        if topic["status"] == "unsubscribed":
            return {"topic": topic, "discarded": [], "unchanged": True}
        updated = conn.execute(
            "UPDATE topics.followed_topic SET status='unsubscribed',updated_at=clock_timestamp() "
            "WHERE id=%s RETURNING *",
            (topic["id"],),
        ).fetchone()
        discarded = TopicsRepository.discard_prepared(conn, topic["id"])
        return {"topic": updated, "discarded": discarded, "unchanged": False}

    def resolve_run(self, authority, topic_id, run_id, reconciled_state):
        if reconciled_state not in ("sent", "failed"):
            _invalid("decision")

        def resolve(conn):
            self.topic(conn, authority, topic_id)
            run = conn.execute(
                "SELECT * FROM topics.digest_run WHERE id=%s AND topic_id=%s FOR UPDATE",
                (run_id, topic_id),
            ).fetchone()
            if not run:
                raise TopicsError("NOT_FOUND")
            outcome = conn.execute(
                "SELECT * FROM topics.delivery_outcome WHERE run_id=%s FOR UPDATE", (run_id,)
            ).fetchone()
            if not outcome or outcome["observed_state"] != "unknown":
                raise TopicsError("INVALID_STATE")
            if outcome["reconciled_state"] is not None:
                raise TopicsError("INVALID_STATE")
            return self._reconcile(conn, run, outcome, reconciled_state)

        return self.run(authority, resolve)

    # -- worker units ---------------------------------------------------------

    def due_topics(self, now: dt.datetime, limit=50, *, recipient=None):
        """Actionable topics due in each owner's confirmed zone (BR1.2).

        The due filter lives in the read so the bounded page can never be
        Calendar, consent and outstanding-work filters precede the bounded page.
        Paused owners cannot monopolize it; reconciliation, queued sends and
        consent cleanup remain independent scheduler phases. Admission rechecks
        authority because it may change after this read. A real adapter passes
        its one permitted `recipient`, filtered before the page as well.
        """
        if not isinstance(now, dt.datetime) or now.tzinfo is None:
            _invalid("now")
        if type(limit) is not int or not 1 <= limit <= 50:
            _invalid("limit")
        _validated_recipient(recipient)
        return self.system(
            lambda conn: conn.execute(
                "SELECT t.id,t.account_id,t.topic_key,t.display_name,t.status,"
                "s.cadence,s.delivery_time_local,s.delivery_day,s.content_window_days,"
                "s.revision AS settings_revision,d.window_day,d.due_at,d.preferences "
                "FROM topics.followed_topic t "
                "JOIN topics.digest_settings s ON s.topic_id=t.id "
                "JOIN LATERAL topics.next_occurrence(t.id,%s) d ON true "
                "WHERE t.status='active' "
                "AND (SELECT granted FROM accounts.digest_recipient(t.account_id)) IS TRUE "
                "AND (%s::text IS NULL OR "
                "(SELECT email FROM accounts.digest_recipient(t.account_id)) = %s::text) "
                "AND NOT EXISTS (SELECT 1 FROM topics.digest_run r "
                "WHERE r.topic_id=t.id AND r.state IN ('prepared','sending','unknown')) "
                "ORDER BY d.due_at,t.followed_at,t.id LIMIT %s",
                (now, recipient, recipient, limit),
            ).fetchall()
        )

    def consent_stopped_runs(self, limit=10):
        """Prepared runs of topics whose effective consent is stopped (BR4.2)."""
        if type(limit) is not int or not 1 <= limit <= 50:
            _invalid("limit")
        return self.system(
            lambda conn: conn.execute(
                "SELECT r.id,r.topic_id FROM topics.digest_run r "
                "JOIN topics.followed_topic t ON t.id=r.topic_id "
                "WHERE r.state='prepared' "
                "AND (SELECT granted FROM accounts.digest_recipient(t.account_id)) IS NOT TRUE "
                "ORDER BY r.created_at,r.id LIMIT %s",
                (limit,),
            ).fetchall()
        )

    def latest_window(self, topic_id):
        row = self.system(
            lambda conn: conn.execute(
                "SELECT max(window_end) AS window_end FROM topics.digest_run "
                "WHERE topic_id=%s AND state <> 'discarded'",
                (topic_id,),
            ).fetchone()
        )
        return row["window_end"]

    def select_window_content(
        self, topic_id, window_start, window_end, *, selection_limit, content_limit
    ):
        """Eligible corpus inside the inclusive window, watermark excluded (BR2.1/BR2.2).

        The serializable read carries the whole eligibility contract, so a
        concurrent withdrawal surfaces as a serialization retry, never as
        ineligible content.
        """
        if not isinstance(window_start, dt.date) or not isinstance(window_end, dt.date):
            _invalid("window")
        if type(selection_limit) is not int or type(content_limit) is not int:
            _invalid("limits")

        def select(conn):
            rows = conn.execute(
                "SELECT v.id AS version_id,p.id AS paper_id,p.title,p.published_on "
                "FROM corpus.version v JOIN corpus.paper p ON p.id=v.paper_id "
                "LEFT JOIN topics.topic_delivery_watermark w "
                "ON w.topic_id=%s AND w.content_id=v.id "
                "WHERE v.eligible AND v.purpose='local-research' AND NOT p.withdrawn "
                "AND p.published_on IS NOT NULL "
                "AND p.published_on BETWEEN %s AND %s AND w.content_id IS NULL "
                "ORDER BY p.published_on,p.id,v.id LIMIT %s",
                (topic_id, window_start, window_end, selection_limit),
            ).fetchall()
            return [
                {
                    "versionId": row["version_id"],
                    "paperId": row["paper_id"],
                    "title": row["title"],
                    "publishedOn": row["published_on"].isoformat(),
                }
                for row in rows[:content_limit]
            ]

        return self.system(select)

    def prepare_run(
        self,
        topic_id,
        window_start,
        window_end,
        settings_revision,
        digest_content,
        *,
        expected_preferences=None,
    ):
        """Adopt the window's non-discarded run or create one; empty content is recorded.

        Returns (run, adopted). The chronology and revision gates are the
        schema's; their refusals map to typed errors the scheduler treats as
        skip-this-pass signals (BR2.4/BR1.3).
        """
        if not isinstance(window_start, dt.date) or not isinstance(window_end, dt.date):
            _invalid("window")
        if type(settings_revision) is not int or settings_revision < 1:
            _invalid("settingsRevision")
        if not isinstance(digest_content, list):
            _invalid("digestContent")

        def prepare(conn):
            topic = conn.execute(
                "SELECT * FROM topics.followed_topic WHERE id=%s FOR UPDATE", (topic_id,)
            ).fetchone()
            if not topic or topic["status"] != "active":
                raise TopicsError("NOT_FOUND")
            preferences = conn.execute(
                "SELECT personalization.digest_preferences(%s) AS value", (topic["account_id"],)
            ).fetchone()["value"]
            if expected_preferences is not None and (
                preference_fingerprint(preferences) != preference_fingerprint(expected_preferences)
                or preferences["effectiveAt"] != expected_preferences["effectiveAt"]
            ):
                raise TopicsError("CONFLICT", current={"field": "effectivePreferences"})
            if not preferences["timeZone"]:
                raise TopicsError("INVALID_ARGUMENT", current={"field": "timeZone"})
            presentation = render_presentation(topic["display_name"], digest_content, preferences)
            existing = conn.execute(
                "SELECT * FROM topics.digest_run WHERE topic_id=%s AND window_start=%s "
                "AND window_end=%s AND state <> 'discarded' FOR UPDATE",
                (topic_id, window_start, window_end),
            ).fetchone()
            if existing:
                return existing, True
            try:
                with conn.transaction():
                    run = conn.execute(
                        "INSERT INTO topics.digest_run(id,topic_id,window_start,window_end,"
                        "digest_content,settings_revision,preference_snapshot,presentation) "
                        "VALUES(%s,%s,%s,%s,%s,%s,%s,%s) "
                        "RETURNING " + RUN_COLUMNS,
                        (
                            uuid4(),
                            topic_id,
                            window_start,
                            window_end,
                            Jsonb(digest_content),
                            settings_revision,
                            Jsonb(preferences),
                            Jsonb(presentation),
                        ),
                    ).fetchone()
            except psycopg.errors.UniqueViolation:
                run = conn.execute(
                    "SELECT * FROM topics.digest_run WHERE topic_id=%s AND window_start=%s "
                    "AND window_end=%s AND state <> 'discarded' FOR UPDATE",
                    (topic_id, window_start, window_end),
                ).fetchone()
                return run, True
            except psycopg.errors.CheckViolation as exc:
                text = str(exc)
                if "earlier window" in text:
                    raise TopicsError("WINDOW_ORDER") from exc
                raise TopicsError(
                    "CONFLICT", current={"settingsRevision": settings_revision}
                ) from exc
            if not digest_content:
                run = self._transition(conn, run["id"], "prepared", "empty")
                conn.execute(
                    "INSERT INTO topics.delivery_outcome(id,run_id,observed_state) "
                    "VALUES(%s,%s,'empty')",
                    (uuid4(), run["id"]),
                )
            return run, False

        return self.system(prepare)

    def begin_send(self, run_id, path_kind, *, real_send_limit=0, evidence_retention_days=None):
        """Checked prepared->sending with active, consent and pause guards (BR3.1/3.2/4.1/4.2).

        Returns the sending run row with its send-log skeleton, or None when
        the run moved on, the topic is unsubscribed or consent-stopped, an
        unknown outcome is unreconciled, or another send is in flight. A real
        attempt stamps its evidence-retention bound (at most 30 days, also
        enforced by the database); without a stated period it is refused.
        """
        if path_kind not in ("real", "local-sink"):
            _invalid("pathKind")
        if path_kind == "real":
            if (
                type(evidence_retention_days) is not int
                or not 1 <= evidence_retention_days <= REAL_EVIDENCE_RETENTION_DAYS_MAX
            ):
                raise TopicsError("INVALID_ARGUMENT", current={"field": "evidenceRetention"})
        elif evidence_retention_days not in (None, 0):
            _invalid("evidenceRetention")

        def begin(conn):
            if path_kind == "real":
                if type(real_send_limit) is not int or not 1 <= real_send_limit <= 100:
                    raise TopicsError("INVALID_ARGUMENT", current={"field": "realSendAllocation"})
                conn.execute(
                    "SELECT pg_advisory_xact_lock(hashtext('topics-real-send-allocation'))"
                )
                spent = conn.execute(
                    "SELECT count(*) AS n FROM topics.send_log_entry WHERE path_kind='real'"
                ).fetchone()["n"]
                if spent >= real_send_limit:
                    return None
            run = conn.execute(
                "SELECT * FROM topics.digest_run WHERE id=%s FOR UPDATE", (run_id,)
            ).fetchone()
            if not run or run["state"] != "prepared":
                return None
            owner = conn.execute(
                "SELECT account_id FROM topics.followed_topic WHERE id=%s", (run["topic_id"],)
            ).fetchone()["account_id"]
            current = conn.execute(
                "SELECT personalization.digest_preferences(%s) AS value", (owner,)
            ).fetchone()["value"]
            if not run["preference_snapshot"] or preference_fingerprint(
                current
            ) != preference_fingerprint(run["preference_snapshot"]):
                self._transition(conn, run_id, "prepared", "discarded")
                return None
            try:
                with conn.transaction():
                    sending = conn.execute(
                        "UPDATE topics.digest_run r SET state='sending',updated_at="
                        "clock_timestamp() WHERE r.id=%s AND r.state='prepared' "
                        "AND EXISTS (SELECT 1 FROM topics.followed_topic t "
                        "WHERE t.id=r.topic_id AND t.status='active' "
                        "AND (SELECT granted FROM accounts.digest_recipient("
                        "t.account_id)) IS TRUE) "
                        "AND NOT EXISTS (SELECT 1 FROM topics.digest_run u "
                        "JOIN topics.delivery_outcome o ON o.run_id=u.id "
                        "WHERE u.topic_id=r.topic_id AND u.state='unknown' "
                        "AND o.reconciled_state IS NULL) RETURNING " + RUN_COLUMNS,
                        (run_id,),
                    ).fetchone()
            except psycopg.errors.UniqueViolation:
                return None
            if not sending:
                return None
            # One clock reading stamps both the attempt and its retention bound.
            log = conn.execute(
                "INSERT INTO topics.send_log_entry"
                "(id,run_id,path_kind,attempted_at,evidence_retain_until) "
                "SELECT %s,%s,%s,c.now,CASE WHEN %s::int IS NULL THEN NULL "
                "ELSE c.now + make_interval(days => %s::int) END "
                "FROM (SELECT clock_timestamp() AS now) c RETURNING id",
                (
                    uuid4(),
                    run_id,
                    path_kind,
                    evidence_retention_days if path_kind == "real" else None,
                    evidence_retention_days if path_kind == "real" else None,
                ),
            ).fetchone()
            return dict(sending, send_log_id=log["id"])

        return self.system(begin)

    def finish_send(
        self,
        run_id,
        observed_state,
        *,
        transport_receipt=None,
        acknowledged_at=None,
        failure_reason=None,
        provider_status=None,
        provider_error=None,
    ):
        """Checked sending->terminal; send-log facts set once; outcome recorded (BR3.2).

        A `sent` finish appends the watermark from the run's own content. A
        provider refusal may carry its HTTP status and validated error name,
        recorded once with the outcome. Returns the terminal run row, or None
        when the run is no longer sending.
        """
        if observed_state not in ("sent", "failed", "unknown"):
            _invalid("observedState")
        if failure_reason is not None and (
            not isinstance(failure_reason, str) or not 1 <= len(failure_reason.encode()) <= 160
        ):
            _invalid("failureReason")
        if (provider_status, provider_error) != (None, None) and (
            observed_state != "failed"
            or failure_reason != PROVIDER_REFUSAL
            or not valid_provider_refusal(provider_status, provider_error)
        ):
            _invalid("providerRefusal")

        def finish(conn):
            run = conn.execute(
                "SELECT * FROM topics.digest_run WHERE id=%s FOR UPDATE", (run_id,)
            ).fetchone()
            if not run or run["state"] != "sending":
                return None
            terminal = self._transition(conn, run_id, "sending", observed_state)
            if transport_receipt is not None or acknowledged_at is not None:
                conn.execute(
                    "UPDATE topics.send_log_entry SET transport_receipt="
                    "COALESCE(%s,transport_receipt),acknowledged_at=COALESCE(%s,acknowledged_at) "
                    "WHERE run_id=%s",
                    (transport_receipt, acknowledged_at, run_id),
                )
            conn.execute(
                "INSERT INTO topics.delivery_outcome(id,run_id,observed_state,failure_reason,"
                "provider_status,provider_error) VALUES(%s,%s,%s,%s,%s,%s)",
                (uuid4(), run_id, observed_state, failure_reason, provider_status, provider_error),
            )
            if observed_state == "sent":
                self.apply_watermark(conn, terminal)
            return terminal

        return self.system(finish)

    def record_transport_facts(self, run_id, *, transport_receipt=None, acknowledged_at=None):
        """Set the send log's transport facts once, before the outcome is known.

        A crash between this write and the outcome record leaves an unknown run
        whose send-log evidence still reconciles it (BR3.2); the facts are
        set-once and never rewritten.
        """
        if transport_receipt is None and acknowledged_at is None:
            return None

        def record(conn):
            return conn.execute(
                "UPDATE topics.send_log_entry SET transport_receipt="
                "COALESCE(%s,transport_receipt),acknowledged_at=COALESCE(%s,acknowledged_at) "
                "WHERE run_id=%s RETURNING id",
                (transport_receipt, acknowledged_at, run_id),
            ).fetchone()

        return self.system(record)

    def unknown_runs(self, limit=50):
        """Unreconciled unknown outcomes with their send-log evidence (BR3.2)."""
        if type(limit) is not int or not 1 <= limit <= 50:
            _invalid("limit")
        return self.system(
            lambda conn: conn.execute(
                "SELECT r.id,r.topic_id,r.window_start,r.window_end,r.state,r.digest_content,"
                "r.settings_revision,r.updated_at,o.observed_state,o.reconciled_state,"
                "o.observed_at,l.transport_receipt,l.acknowledged_at,l.path_kind "
                "FROM topics.digest_run r "
                "JOIN topics.delivery_outcome o ON o.run_id=r.id "
                "LEFT JOIN topics.send_log_entry l ON l.run_id=r.id "
                "WHERE r.state='unknown' AND o.reconciled_state IS NULL "
                "ORDER BY r.updated_at,r.id LIMIT %s",
                (limit,),
            ).fetchall()
        )

    def reconcile_run(self, run_id, reconciled_state):
        """Scheduled reconciliation of one unknown outcome (BR3.2).

        Returns the reconciled run row, the run row when already reconciled to
        the same state (idempotent), or None when the run is not awaiting
        reconciliation.
        """
        if reconciled_state not in ("sent", "failed"):
            _invalid("decision")

        def reconcile(conn):
            run = conn.execute(
                "SELECT * FROM topics.digest_run WHERE id=%s FOR UPDATE", (run_id,)
            ).fetchone()
            outcome = conn.execute(
                "SELECT * FROM topics.delivery_outcome WHERE run_id=%s FOR UPDATE", (run_id,)
            ).fetchone()
            if not run or not outcome or run["state"] != "unknown":
                return None
            if outcome["reconciled_state"] is not None:
                return run if outcome["reconciled_state"] == reconciled_state else None
            return self._reconcile(conn, run, outcome, reconciled_state)

        return self.system(reconcile)

    @staticmethod
    def _reconcile(conn, run, outcome, reconciled_state):
        transitioned = TopicsRepository._transition(conn, run["id"], "unknown", reconciled_state)
        if transitioned is None:
            raise TopicsError("INVALID_STATE")
        conn.execute(
            "UPDATE topics.delivery_outcome SET reconciled_state=%s,reconciled_at="
            "clock_timestamp() WHERE id=%s",
            (reconciled_state, outcome["id"]),
        )
        if reconciled_state == "sent":
            TopicsRepository.apply_watermark(conn, transitioned)
        return transitioned

    def orphaned_sending(self, cutoff, limit=10):
        """Runs stuck in `sending` past the cutoff with no recorded outcome (BR3.4)."""
        if not isinstance(cutoff, dt.datetime) or type(limit) is not int or not 1 <= limit <= 50:
            _invalid("cutoff")
        return self.system(
            lambda conn: conn.execute(
                "SELECT r.id,r.topic_id,r.window_start,r.window_end,r.state,r.digest_content,"
                "r.settings_revision,r.created_at,r.updated_at "
                "FROM topics.digest_run r "
                "LEFT JOIN topics.delivery_outcome o ON o.run_id=r.id "
                "WHERE r.state='sending' AND o.run_id IS NULL AND r.updated_at <= %s "
                "ORDER BY r.updated_at,r.id LIMIT %s",
                (cutoff, limit),
            ).fetchall()
        )

    def retire_orphan(self, run_id):
        """Move one orphaned sending run to unknown; its evidence gap stays visible
        as the absence of a send-log entry (BR3.4)."""

        def retire(conn):
            run = conn.execute(
                "SELECT * FROM topics.digest_run WHERE id=%s FOR UPDATE", (run_id,)
            ).fetchone()
            if not run or run["state"] != "sending":
                return None
            outcome = conn.execute(
                "SELECT id FROM topics.delivery_outcome WHERE run_id=%s FOR UPDATE", (run_id,)
            ).fetchone()
            if outcome:
                return None
            unknown = self._transition(conn, run_id, "sending", "unknown")
            conn.execute(
                "INSERT INTO topics.delivery_outcome(id,run_id,observed_state) "
                "VALUES(%s,%s,'unknown')",
                (uuid4(), run_id),
            )
            return unknown

        return self.system(retire)

    def discard_prepared_runs(self, topic_id):
        """Drop queued (prepared) work for a consent-stopped topic (BR4.2)."""
        return self.system(lambda conn: self.discard_prepared(conn, topic_id))

    def prepared_runs(self, limit=10, *, recipient=None):
        """Prepared runs with their topic facts, oldest first, for the send pass.

        With a real adapter's permitted `recipient`, other owners' queued runs
        are excluded before the page so they can never spend the allocation.
        """
        if type(limit) is not int or not 1 <= limit <= 50:
            _invalid("limit")
        _validated_recipient(recipient)
        return self.system(
            lambda conn: conn.execute(
                "SELECT r.id,r.topic_id,r.window_start,r.window_end,r.state,r.digest_content,"
                "r.settings_revision,r.created_at,r.updated_at,t.account_id,t.topic_key,"
                "t.display_name FROM topics.digest_run r "
                "JOIN topics.followed_topic t ON t.id=r.topic_id "
                "WHERE r.state='prepared' AND (%s::text IS NULL OR "
                "(SELECT email FROM accounts.digest_recipient(t.account_id)) = %s::text) "
                "ORDER BY r.created_at,r.id LIMIT %s",
                (recipient, recipient, limit),
            ).fetchall()
        )

    def expire_real_evidence(self, limit=10):
        """Clear provider receipts of settled real sends past their retention bound.

        Only `sent`, `failed` or owner/scheduler-reconciled `unknown` runs are
        eligible: an unresolved outcome keeps its evidence until it is settled.
        The row (path, attempt and acknowledgement times) stays, so the durable
        real-send allocation is never replenished. Returns the expired row ids.
        """
        if type(limit) is not int or not 1 <= limit <= 50:
            _invalid("limit")
        return self.system(
            lambda conn: [
                row["id"]
                for row in conn.execute(
                    "UPDATE topics.send_log_entry SET transport_receipt=NULL,"
                    "evidence_expired_at=clock_timestamp() WHERE id IN ("
                    "SELECT l.id FROM topics.send_log_entry l "
                    "JOIN topics.digest_run r ON r.id=l.run_id "
                    "LEFT JOIN topics.delivery_outcome o ON o.run_id=r.id "
                    "WHERE l.path_kind='real' AND l.evidence_expired_at IS NULL "
                    "AND l.evidence_retain_until <= clock_timestamp() "
                    "AND (r.state IN ('sent','failed') "
                    "OR (r.state='unknown' AND o.reconciled_state IS NOT NULL)) "
                    "ORDER BY l.evidence_retain_until,l.id LIMIT %s) RETURNING id",
                    (limit,),
                ).fetchall()
            ]
        )

    def digest_recipient(self, account_id):
        return self.system(
            lambda conn: conn.execute(
                "SELECT email,consent_revision,granted FROM accounts.digest_recipient(%s)",
                (account_id,),
            ).fetchone()
        )

    # -- lifecycle participation ----------------------------------------------
    # Disposition evidence and the account-scoped effects themselves are written
    # by lifecycle_effects.apply_owner_effect and the TopicsDigests participant
    # (backend/modules/topics/control_lifecycle.py): one writer per table, the
    # same shared coordinator contract every other participant uses.
