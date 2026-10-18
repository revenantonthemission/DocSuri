"""Digest content selection and rendering from the eligible corpus.

Eligible versions inside the inclusive window, per-topic watermark excluded
(BR2.1/BR2.2), bounded by the policy's selection budget and digest size. A
window with no eligible content is recorded explicitly as an empty digest by
the repository (BR2.3) — preparation never turns a quiet window into a
failure. Language/level are read from the account's preferences at
preparation time by the rendering layer, not stored per topic.
"""

from backend.u5_policy import SYNTHETIC_TOPICS

from .repository import TopicsRepository


class DigestPreparation:
    def __init__(self, transactions, corpus, *, policy=SYNTHETIC_TOPICS):
        self.repository = TopicsRepository(transactions)
        self.corpus = corpus
        self.policy = policy

    def select(self, topic_id, window_start, window_end):
        return self.repository.select_window_content(
            topic_id,
            window_start,
            window_end,
            selection_limit=self.policy.selection_limit,
            content_limit=self.policy.digest_items_max,
        )

    def prepare(self, topic_id, window, settings_revision, *, expected_preferences=None):
        """Select content and create (or adopt) the window's run (BR2.4)."""
        window_start, window_end = window
        items = self.select(topic_id, window_start, window_end)
        return self.repository.prepare_run(
            topic_id,
            window_start,
            window_end,
            settings_revision,
            items,
            expected_preferences=expected_preferences,
        )
