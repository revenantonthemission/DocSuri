-- Additive control protocol. Unbound pre-existing run/checkpoint rows deliberately fail
-- NOT NULL validation: no invented intent, target, attempt or historical execution proof.
ALTER TABLE r1_control.runs
    ADD COLUMN plan_payload jsonb NOT NULL,
    ADD COLUMN intent_payload jsonb NOT NULL,
    ADD COLUMN intent_digest text NOT NULL,
    ADD COLUMN checkpoint_revision numeric(20, 0) NOT NULL DEFAULT 0
        CHECK (checkpoint_revision BETWEEN 0 AND 18446744073709551615),
    ADD COLUMN current_attempt text;

CREATE TABLE r1_control.submissions (
    submission_key text PRIMARY KEY,
    run_id text NOT NULL REFERENCES r1_control.runs(run_id)
);
CREATE TABLE r1_control.attempts (
    run_id text NOT NULL REFERENCES r1_control.runs(run_id),
    attempt_id text NOT NULL,
    ordinal bigint NOT NULL CHECK (ordinal BETWEEN 1 AND 9007199254740991),
    invocation text NOT NULL,
    payload jsonb NOT NULL,
    digest text NOT NULL,
    PRIMARY KEY (run_id, attempt_id),
    UNIQUE (run_id, ordinal),
    UNIQUE (run_id, invocation)
);
ALTER TABLE r1_control.runs ADD CONSTRAINT current_attempt_binding
    FOREIGN KEY (run_id, current_attempt) REFERENCES r1_control.attempts(run_id, attempt_id);
ALTER TABLE r1_control.checkpoints
    ALTER COLUMN sequence TYPE numeric(20, 0),
    ADD CONSTRAINT uint64_sequence CHECK (sequence BETWEEN 1 AND 18446744073709551615),
    ADD COLUMN step text NOT NULL,
    ADD COLUMN attempt_id text NOT NULL,
    ADD COLUMN assurance text NOT NULL CHECK (assurance IN
        ('NOT_STARTED', 'UNKNOWN', 'COMMITTED', 'NO_EFFECT_CONFIRMED')),
    ADD CONSTRAINT checkpoint_attempt_binding
        FOREIGN KEY (run_id, attempt_id) REFERENCES r1_control.attempts(run_id, attempt_id);
CREATE INDEX checkpoint_latest_effect ON r1_control.checkpoints (run_id, step, sequence DESC);

CREATE FUNCTION r1_control.protect_intent() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'immutable run intent'; END IF;
    IF ROW(NEW.run_id, NEW.semantic_key, NEW.plan_digest, NEW.plan_payload,
           NEW.intent_payload, NEW.intent_digest) IS DISTINCT FROM
       ROW(OLD.run_id, OLD.semantic_key, OLD.plan_digest, OLD.plan_payload,
           OLD.intent_payload, OLD.intent_digest) THEN
        RAISE EXCEPTION 'immutable run intent';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER immutable_run_intent BEFORE UPDATE OR DELETE ON r1_control.runs
FOR EACH ROW EXECUTE FUNCTION r1_control.protect_intent();
CREATE TRIGGER immutable_submission BEFORE UPDATE OR DELETE ON r1_control.submissions
FOR EACH ROW EXECUTE FUNCTION r1_audit.reject_mutation();
CREATE TRIGGER immutable_attempt BEFORE UPDATE OR DELETE ON r1_control.attempts
FOR EACH ROW EXECUTE FUNCTION r1_audit.reject_mutation();

CREATE TRIGGER no_truncate_runs BEFORE TRUNCATE ON r1_control.runs
FOR EACH STATEMENT EXECUTE FUNCTION r1_audit.reject_mutation();
CREATE TRIGGER no_truncate_submissions BEFORE TRUNCATE ON r1_control.submissions
FOR EACH STATEMENT EXECUTE FUNCTION r1_audit.reject_mutation();
CREATE TRIGGER no_truncate_attempts BEFORE TRUNCATE ON r1_control.attempts
FOR EACH STATEMENT EXECUTE FUNCTION r1_audit.reject_mutation();
CREATE TRIGGER no_truncate_checkpoints BEFORE TRUNCATE ON r1_control.checkpoints
FOR EACH STATEMENT EXECUTE FUNCTION r1_audit.reject_mutation();
CREATE TRIGGER no_truncate_audit BEFORE TRUNCATE ON r1_audit.events
FOR EACH STATEMENT EXECUTE FUNCTION r1_audit.reject_mutation();
CREATE TRIGGER no_truncate_evidence BEFORE TRUNCATE ON r1_control.evidence
FOR EACH STATEMENT EXECUTE FUNCTION r1_audit.reject_mutation();
REVOKE ALL ON ALL TABLES IN SCHEMA r1_control, r1_audit FROM PUBLIC;
REVOKE ALL ON FUNCTION r1_control.protect_intent() FROM PUBLIC;
