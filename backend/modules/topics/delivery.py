"""Digest email delivery through the built email capability.

The send attempt moves a run `prepared -> sending -> sent|failed|unknown` via
the repository's checked transitions (single-flight, active status, consent
and reconciliation-pause guards live in the transition itself). The account
consent is re-checked at send start; a local sink carries synthetic-profile
sends, and a real send is recorded with `pathKind: real` only when a
maintainer-configured path actually carried it (BR1.4). The email seam is
`backend/modules/accounts/integrations/email.py` through the additive
`send_digest_email` primitive; no provider SDK or paid provider is added.
"""

import asyncio

from backend.modules.accounts.integrations.digest_email import digest_mail_binding
from backend.transactions import OwnerTransactions
from backend.u5_policy import SYNTHETIC_TOPICS

from .repository import TopicsRepository


class DigestDelivery:
    send_seconds = 3.0

    def __init__(
        self,
        transactions: OwnerTransactions,
        corpus,
        *,
        mail=None,
        unsubscribe=None,
        policy=SYNTHETIC_TOPICS,
    ):
        self.repository = TopicsRepository(transactions)
        self.corpus = corpus
        self.policy = policy
        self.unsubscribe = unsubscribe
        self.mail = (
            mail if mail is not None else digest_mail_binding(synthetic=policy.synthetic_only)
        )
        if getattr(self.mail, "path_kind", None) not in ("real", "local-sink"):
            raise ValueError("digest adapter identity required")
        if policy.synthetic_only and self.mail.path_kind != "local-sink":
            raise ValueError("synthetic delivery cannot use real transport")
        if not policy.synthetic_only and self.mail.path_kind != "real":
            raise ValueError("real delivery requires a real adapter")
        if not policy.synthetic_only and unsubscribe is None:
            raise ValueError("real delivery requires the owner-bound cancellation capability")

    def path_kind(self):
        """`local-sink` unless a maintainer-configured path carried the send.

        The synthetic profile is synthetic-only, so its sends always record the
        truthful degraded path (BR1.4): no send claims `real` without a
        configured path.
        """
        return self.mail.path_kind

    def attempt(self, sending, topic):
        """Deliver one sending run; the outcome is recorded before returning."""
        recipient = self.repository.digest_recipient(topic["account_id"])
        if not recipient["granted"] or not recipient["email"]:
            return self.repository.finish_send(
                sending["id"], "failed", failure_reason="recipient-unavailable"
            )
        try:
            unsubscribe_url = (
                self.unsubscribe.issue(sending["id"]) if self.path_kind() == "real" else None
            )
            delivered = asyncio.run(
                asyncio.wait_for(
                    self.mail.send(
                        recipient["email"],
                        sending["presentation"],
                        sending["request_key"],
                        **({"unsubscribe_url": unsubscribe_url} if unsubscribe_url else {}),
                    ),
                    timeout=self.send_seconds,
                )
            )
        except Exception:
            # An interrupted or timed-out transport leaves the outcome unobserved:
            # the run pauses as unknown until reconciliation (BR3.2).
            return self.repository.finish_send(sending["id"], "unknown")
        # Transport facts land before the outcome: a crash between the two
        # leaves an unknown run whose send log still reconciles it (BR3.2).
        if delivered.state == "accepted":
            self.repository.record_transport_facts(
                sending["id"],
                transport_receipt=delivered.receipt,
                acknowledged_at=delivered.acknowledged_at,
            )
            return self.repository.finish_send(sending["id"], "sent")
        if delivered.state == "unknown":
            return self.repository.finish_send(sending["id"], "unknown")
        return self.repository.finish_send(
            sending["id"], "failed", failure_reason="delivery-path-refused"
        )

    def reconcile_decision(self, run):
        """Evidence-based reconciliation for one unknown outcome (BR3.2).

        An acknowledgment or transport receipt means the path accepted the
        message. Their absence is an evidence gap: silence alone never
        reconciles, so the decision stays with the owner's explicit resolve.
        """
        if run.get("path_kind") == "real":
            if run["acknowledged_at"] is not None and run["transport_receipt"]:
                return "sent"
            return None
        if run["acknowledged_at"] is not None or run["transport_receipt"] is not None:
            return "sent"
        return None
