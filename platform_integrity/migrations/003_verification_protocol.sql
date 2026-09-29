-- Legacy evidence stays unbound history; no verification identity is invented for it.
CREATE TABLE r1_control.verifications (
    verification_id text PRIMARY KEY,
    subject text NOT NULL,
    slot text NOT NULL,
    revision numeric(20, 0) NOT NULL CHECK (revision BETWEEN 1 AND 18446744073709551615),
    previous_revision numeric(20, 0) NOT NULL CHECK (previous_revision >= 0),
    request jsonb NOT NULL,
    digest text NOT NULL,
    CHECK (revision = previous_revision + 1),
    UNIQUE (subject, slot, revision),
    UNIQUE (subject, slot, revision, verification_id)
);
ALTER TABLE r1_control.evidence
    ADD COLUMN verification_id text UNIQUE REFERENCES r1_control.verifications(verification_id),
    ADD COLUMN slot text,
    ADD COLUMN selection_revision numeric(20, 0),
    ADD CONSTRAINT evidence_request_binding FOREIGN KEY
        (subject, slot, selection_revision, verification_id)
        REFERENCES r1_control.verifications(subject, slot, revision, verification_id),
    ADD CONSTRAINT complete_evidence_binding CHECK (
        (verification_id IS NULL AND slot IS NULL AND selection_revision IS NULL) OR
        (verification_id IS NOT NULL AND slot IS NOT NULL AND selection_revision IS NOT NULL)
    ),
    ADD CONSTRAINT unique_evidence_selection UNIQUE
        (subject, slot, selection_revision, verification_id, evidence_id);
ALTER TABLE r1_control.heads
    ALTER COLUMN revision TYPE numeric(20, 0),
    ADD CONSTRAINT uint64_head_revision CHECK (revision BETWEEN 1 AND 18446744073709551615),
    ADD COLUMN binding jsonb,
    ADD COLUMN verification_id text,
    ADD CONSTRAINT complete_head_binding CHECK (
        (binding IS NULL AND verification_id IS NULL) OR
        (binding IS NOT NULL AND verification_id IS NOT NULL)
    ),
    ADD CONSTRAINT head_request_binding FOREIGN KEY (subject, slot, revision, verification_id)
        REFERENCES r1_control.verifications(subject, slot, revision, verification_id),
    ADD CONSTRAINT head_evidence_binding FOREIGN KEY
        (subject, slot, revision, verification_id, evidence_id)
        REFERENCES r1_control.evidence
            (subject, slot, selection_revision, verification_id, evidence_id),
    ADD CONSTRAINT head_outcome_binding CHECK (
        (state = 'PENDING' AND evidence_id IS NULL) OR
        (state = 'RESOLVED' AND evidence_id IS NOT NULL)
    );
CREATE TRIGGER immutable_verification BEFORE UPDATE OR DELETE ON r1_control.verifications
FOR EACH ROW EXECUTE FUNCTION r1_audit.reject_mutation();
CREATE TRIGGER no_truncate_verification BEFORE TRUNCATE ON r1_control.verifications
FOR EACH STATEMENT EXECUTE FUNCTION r1_audit.reject_mutation();

CREATE FUNCTION r1_control.protect_evidence_head() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
DECLARE expected_binding jsonb;
BEGIN
    IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'evidence head requires retained history'; END IF;
    IF NEW.verification_id IS NULL OR NEW.binding IS NULL THEN
        RAISE EXCEPTION 'unbound evidence head';
    END IF;
    SELECT request->'subject' INTO expected_binding FROM r1_control.verifications
        WHERE verification_id = NEW.verification_id;
    IF expected_binding IS NULL OR NEW.binding IS DISTINCT FROM expected_binding THEN
        RAISE EXCEPTION 'evidence head binding mismatch';
    END IF;
    IF TG_OP = 'INSERT' THEN
        IF NEW.revision <> 1 OR NEW.state <> 'PENDING' THEN
            RAISE EXCEPTION 'invalid initial evidence head';
        END IF;
    ELSIF NEW.subject IS DISTINCT FROM OLD.subject OR NEW.slot IS DISTINCT FROM OLD.slot THEN
        RAISE EXCEPTION 'evidence head scope changed';
    ELSIF NEW.revision = OLD.revision THEN
        IF NOT (OLD.state = 'PENDING' AND NEW.state = 'RESOLVED'
                AND NEW.verification_id IS NOT DISTINCT FROM OLD.verification_id
                AND NEW.binding IS NOT DISTINCT FROM OLD.binding) THEN
            RAISE EXCEPTION 'invalid evidence finalization';
        END IF;
    ELSIF NEW.revision <> OLD.revision + 1 OR NEW.state <> 'PENDING' THEN
        RAISE EXCEPTION 'evidence head revision conflict';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER monotonic_evidence_head BEFORE INSERT OR UPDATE OR DELETE ON r1_control.heads
FOR EACH ROW EXECUTE FUNCTION r1_control.protect_evidence_head();

CREATE FUNCTION r1_control.check_evidence_floor() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
DECLARE head_revision numeric(20, 0); latest_revision numeric(20, 0);
BEGIN
    SELECT revision INTO head_revision FROM r1_control.heads
        WHERE subject = NEW.subject AND slot = NEW.slot;
    SELECT MAX(revision) INTO latest_revision FROM r1_control.verifications
        WHERE subject = NEW.subject AND slot = NEW.slot;
    IF head_revision IS DISTINCT FROM latest_revision THEN
        RAISE EXCEPTION 'incomplete evidence selection transaction';
    END IF;
    RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER complete_verification_reservation AFTER INSERT ON r1_control.verifications
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION r1_control.check_evidence_floor();
CREATE TRIGGER no_truncate_heads BEFORE TRUNCATE ON r1_control.heads
FOR EACH STATEMENT EXECUTE FUNCTION r1_audit.reject_mutation();
REVOKE ALL ON r1_control.verifications FROM PUBLIC;
REVOKE ALL ON FUNCTION r1_control.protect_evidence_head() FROM PUBLIC;
REVOKE ALL ON FUNCTION r1_control.check_evidence_floor() FROM PUBLIC;
