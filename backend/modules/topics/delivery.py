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
import datetime as dt
import html as html_module

from backend.modules.accounts.integrations.email import get_email_client
from backend.transactions import OwnerTransactions
from backend.u5_policy import SYNTHETIC_TOPICS

from .repository import TopicsRepository

TITLE_LIMIT = 200


def render_digest_email(topic, items):
    """(subject, text, html) for one digest; recipient-derived values escaped."""
    name = html_module.escape(str(topic["display_name"])[:160], quote=True)
    count = len(items)
    subject = f"[DocSuri] '{name}' 주제 다이제스트 ({count}편)"
    lines = []
    for item in items:
        title = str(item.get("title", ""))[:TITLE_LIMIT]
        published = str(item.get("publishedOn", ""))
        lines.append(f"- {title} ({published})")
    body_text = (
        f"'{topic['display_name']}' 주제의 최신 논문 {count}편입니다.\n\n" + "\n".join(lines)
        if items
        else f"'{topic['display_name']}' 주제의 새 소식이 없습니다."
    )
    rows = "".join(
        f"<li>{html_module.escape(str(item.get('title', ''))[:TITLE_LIMIT], quote=True)} "
        f"({html_module.escape(str(item.get('publishedOn', '')), quote=True)})</li>"
        for item in items
    )
    body_html = (
        f"<html><body><h3>'{name}' 주제 다이제스트</h3>"
        f"<p>최신 논문 {count}편입니다.</p><ul>{rows}</ul></body></html>"
        if items
        else (
            f"<html><body><h3>'{name}' 주제 다이제스트</h3>"
            "<p>새 소식이 없습니다.</p></body></html>"
        )
    )
    return subject, body_text, body_html


class DigestDelivery:
    send_seconds = 3.0

    def __init__(
        self,
        transactions: OwnerTransactions,
        corpus,
        *,
        mail=None,
        policy=SYNTHETIC_TOPICS,
    ):
        self.repository = TopicsRepository(transactions)
        self.corpus = corpus
        self.policy = policy
        self.mail = mail if mail is not None else get_email_client(env="local")

    def path_kind(self):
        """`local-sink` unless a maintainer-configured path carried the send.

        The synthetic profile is synthetic-only, so its sends always record the
        truthful degraded path (BR1.4): no send claims `real` without a
        configured path.
        """
        return "local-sink"

    def attempt(self, sending, topic):
        """Deliver one sending run; the outcome is recorded before returning."""
        recipient = self.repository.digest_recipient(topic["account_id"])
        if not recipient["granted"] or not recipient["email"]:
            return self.repository.finish_send(
                sending["id"], "failed", failure_reason="recipient-unavailable"
            )
        subject, text, html = render_digest_email(topic, sending["digest_content"])
        try:
            delivered = asyncio.run(
                asyncio.wait_for(
                    self.mail.send_digest_email(recipient["email"], subject, text, html),
                    timeout=self.send_seconds,
                )
            )
        except Exception:
            # An interrupted or timed-out transport leaves the outcome unobserved:
            # the run pauses as unknown until reconciliation (BR3.2).
            return self.repository.finish_send(sending["id"], "unknown")
        # Transport facts land before the outcome: a crash between the two
        # leaves an unknown run whose send log still reconciles it (BR3.2).
        if delivered is True:
            self.repository.record_transport_facts(
                sending["id"], acknowledged_at=dt.datetime.now(dt.UTC)
            )
            return self.repository.finish_send(sending["id"], "sent")
        return self.repository.finish_send(
            sending["id"], "failed", failure_reason="delivery-path-refused"
        )

    def reconcile_decision(self, run):
        """Evidence-based reconciliation for one unknown outcome (BR3.2).

        An acknowledgment or transport receipt means the path accepted the
        message. Their absence is an evidence gap: silence alone never
        reconciles, so the decision stays with the owner's explicit resolve.
        """
        if run["acknowledged_at"] is not None or run["transport_receipt"] is not None:
            return "sent"
        return None
