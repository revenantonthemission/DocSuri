-- U15 Trends — race-safe follow uniqueness (FR-48/BR-TN5 review fix).
-- follow_topic is check-then-act in the service: two concurrent double-submits can both pass
-- the read and insert case-insensitive duplicates. The functional unique index makes the
-- database the arbiter; the service maps the unique-violation (IntegrityError) to the same
-- DuplicateTopic → 409 the app-level check produces.

-- Dedupe first (keep the earliest row per (owner, lower(topic))) so the index builds even if
-- the race already produced duplicates; both rows meant the same follow for the user.
DELETE FROM followed_topics a
USING followed_topics b
WHERE a.owner_id = b.owner_id
  AND lower(a.topic) = lower(b.topic)
  AND (b.created_at, b.id) < (a.created_at, a.id);

CREATE UNIQUE INDEX IF NOT EXISTS ux_followed_topics_owner_lower_topic
    ON followed_topics (owner_id, lower(topic));
