-- Explicit REM-1 control bootstrap. Never run by a readonly health/check endpoint.
CREATE SCHEMA IF NOT EXISTS r1_control;
CREATE SCHEMA IF NOT EXISTS r1_audit;
REVOKE ALL ON SCHEMA r1_control, r1_audit FROM PUBLIC;

CREATE TABLE IF NOT EXISTS r1_control.authority (
    binding_id text PRIMARY KEY,
    actor text NOT NULL,
    purpose text NOT NULL,
    target text NOT NULL,
    incarnation text NOT NULL,
    plan_digest text NOT NULL,
    revision bigint NOT NULL CHECK (revision >= 0),
    valid_until timestamptz NOT NULL,
    revoked boolean NOT NULL DEFAULT false
);
CREATE TABLE IF NOT EXISTS r1_control.runs (
    run_id text PRIMARY KEY,
    semantic_key text NOT NULL UNIQUE,
    plan_digest text NOT NULL,
    state text NOT NULL CHECK (state IN ('PLANNED','RUNNING','PAUSED','SUCCEEDED','RECONCILE_REQUIRED'))
);
CREATE TABLE IF NOT EXISTS r1_control.checkpoints (
    run_id text NOT NULL REFERENCES r1_control.runs(run_id),
    sequence bigint NOT NULL CHECK (sequence >= 0),
    payload jsonb NOT NULL,
    digest text NOT NULL,
    PRIMARY KEY (run_id, sequence)
);
CREATE TABLE IF NOT EXISTS r1_control.evidence (
    evidence_id text PRIMARY KEY,
    subject text NOT NULL,
    payload jsonb NOT NULL,
    digest text NOT NULL
);
CREATE TABLE IF NOT EXISTS r1_control.heads (
    subject text NOT NULL,
    slot text NOT NULL,
    revision bigint NOT NULL CHECK (revision >= 0),
    state text NOT NULL CHECK (state IN ('PENDING','RESOLVED')),
    evidence_id text REFERENCES r1_control.evidence(evidence_id),
    PRIMARY KEY (subject, slot)
);
CREATE TABLE IF NOT EXISTS r1_audit.events (
    event_id text PRIMARY KEY,
    occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    payload jsonb NOT NULL,
    digest text NOT NULL
);
CREATE TABLE IF NOT EXISTS r1_control.outbox (
    event_id text PRIMARY KEY REFERENCES r1_audit.events(event_id),
    delivered_at timestamptz
);
CREATE OR REPLACE FUNCTION r1_audit.reject_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable integrity record'; END $$;
CREATE TRIGGER immutable_audit BEFORE UPDATE OR DELETE ON r1_audit.events
FOR EACH ROW EXECUTE FUNCTION r1_audit.reject_mutation();
CREATE TRIGGER immutable_evidence BEFORE UPDATE OR DELETE ON r1_control.evidence
FOR EACH ROW EXECUTE FUNCTION r1_audit.reject_mutation();
CREATE TRIGGER immutable_checkpoint BEFORE UPDATE OR DELETE ON r1_control.checkpoints
FOR EACH ROW EXECUTE FUNCTION r1_audit.reject_mutation();
REVOKE ALL ON ALL TABLES IN SCHEMA r1_control, r1_audit FROM PUBLIC;
