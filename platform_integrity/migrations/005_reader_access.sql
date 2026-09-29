-- Explicit bootstrap only. The login/certificate/HBA mapping is a separate operator action.
DO $$
DECLARE name text;
BEGIN
    FOREACH name IN ARRAY ARRAY['r1_control_owner','r1_control_reader','r1_read_grant_admin'] LOOP
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname=name) THEN
            EXECUTE format('CREATE ROLE %I NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS', name);
        ELSIF EXISTS (SELECT FROM pg_roles WHERE rolname=name AND
            (rolcanlogin OR rolinherit OR rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls)) THEN
            RAISE EXCEPTION 'existing REM-1 group role is not safe';
        END IF;
    END LOOP;
END $$;

CREATE TABLE r1_control.reader_grants (
    fingerprint text NOT NULL CHECK (fingerprint ~ '^[0-9a-f]{64}$'),
    subject text NOT NULL CHECK (subject ~ '^[A-Za-z0-9_.:@/-]{1,200}$'),
    revision numeric(20,0) NOT NULL CHECK (revision BETWEEN 1 AND 18446744073709551615),
    valid_from numeric(20,0) NOT NULL CHECK (valid_from >= 0),
    valid_until numeric(20,0) NOT NULL CHECK (valid_until <= 18446744073709551615),
    revoked boolean NOT NULL,
    PRIMARY KEY (fingerprint, subject),
    CHECK (valid_until > valid_from AND valid_until - valid_from <= 1800000000)
);
ALTER TABLE r1_control.reader_grants OWNER TO r1_control_owner;
REVOKE ALL ON r1_control.reader_grants FROM PUBLIC;
GRANT USAGE ON SCHEMA r1_control TO r1_control_owner, r1_control_reader, r1_read_grant_admin;
GRANT CREATE ON SCHEMA r1_control TO r1_control_owner;
GRANT USAGE ON SCHEMA r1_audit TO r1_control_owner;
GRANT SELECT ON r1_control.heads, r1_control.evidence, r1_control.reader_grants TO r1_control_reader;
GRANT INSERT ON r1_audit.events, r1_control.outbox TO r1_control_owner;

CREATE FUNCTION r1_control.set_reader_grant(
    certificate_fingerprint text, subject_id text, expected_revision numeric,
    starts numeric, expires numeric, is_revoked boolean
) RETURNS numeric
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE previous numeric; next_revision numeric; payload text; event_digest text;
BEGIN
    IF session_user !~ '^[A-Za-z0-9_]{1,63}$' OR expected_revision IS NULL
       OR expected_revision < 0 OR expected_revision <> trunc(expected_revision)
       OR starts IS NULL OR expires IS NULL OR starts <> trunc(starts) OR expires <> trunc(expires) THEN
        RAISE EXCEPTION 'invalid read grant command';
    END IF;
    starts := trunc(starts); expires := trunc(expires);
    -- Serialize initial insertion as well as revisions; no caller-selected SQL or lock scope.
    PERFORM pg_advisory_xact_lock(hashtextextended(certificate_fingerprint || ':' || subject_id, 0));
    SELECT revision INTO previous FROM r1_control.reader_grants
        WHERE fingerprint=certificate_fingerprint AND subject=subject_id FOR UPDATE;
    IF coalesce(previous,0) <> expected_revision THEN RAISE EXCEPTION 'read grant revision conflict'; END IF;
    next_revision := trunc(expected_revision) + 1;
    INSERT INTO r1_control.reader_grants VALUES
        (certificate_fingerprint,subject_id,next_revision,starts,expires,is_revoked)
    ON CONFLICT (fingerprint,subject) DO UPDATE SET
        revision=excluded.revision,valid_from=excluded.valid_from,
        valid_until=excluded.valid_until,revoked=excluded.revoked;
    -- Fixed ASCII keys/validated scalar strings, lexical ordering, lossless integer strings: JCS.
    payload := format('{"actor":%s,"code":"reader_grant_changed","fingerprint":%s,"revision":%s,"revoked":%s,"subject":%s,"validFrom":%s,"validUntil":%s}',
        to_json(session_user)::text,to_json(certificate_fingerprint)::text,
        to_json(next_revision::text)::text,to_json(is_revoked)::text,to_json(subject_id)::text,
        to_json(starts::text)::text,to_json(expires::text)::text);
    event_digest := 'sha256:' || encode(sha256(convert_to(payload,'UTF8')),'hex');
    INSERT INTO r1_audit.events(event_id,payload,digest) VALUES (event_digest,payload::jsonb,event_digest);
    INSERT INTO r1_control.outbox(event_id) VALUES (event_digest);
    RETURN next_revision;
END $$;
ALTER FUNCTION r1_control.set_reader_grant(text,text,numeric,numeric,numeric,boolean)
    OWNER TO r1_control_owner;
REVOKE ALL ON FUNCTION r1_control.set_reader_grant(text,text,numeric,numeric,numeric,boolean) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION r1_control.set_reader_grant(text,text,numeric,numeric,numeric,boolean)
    TO r1_read_grant_admin;
