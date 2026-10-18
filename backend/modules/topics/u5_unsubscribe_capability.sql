-- Only the Topics writer owns hashed, single-purpose email cancellation.
CREATE TABLE topics.email_unsubscribe (
    token_hash text PRIMARY KEY CHECK (token_hash ~ '^[0-9a-f]{64}$'),
    account_id uuid NOT NULL,
    topic_id uuid NOT NULL REFERENCES topics.followed_topic(id) ON DELETE CASCADE,
    run_id uuid NOT NULL UNIQUE REFERENCES topics.digest_run(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    expires_at timestamptz NOT NULL,
    consumed_at timestamptz,
    revoked_at timestamptz,
    CHECK (expires_at > created_at)
);
REVOKE ALL ON topics.email_unsubscribe FROM PUBLIC;
GRANT SELECT,INSERT,UPDATE,DELETE ON topics.email_unsubscribe TO docsuri_topics;
CREATE FUNCTION topics.revoke_email_unsubscribe() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
    IF OLD.status='unsubscribed' AND NEW.status='active' THEN
        UPDATE topics.email_unsubscribe SET revoked_at=clock_timestamp()
        WHERE topic_id=NEW.id AND revoked_at IS NULL;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER email_unsubscribe_reactivation BEFORE UPDATE ON topics.followed_topic
FOR EACH ROW EXECUTE FUNCTION topics.revoke_email_unsubscribe();
