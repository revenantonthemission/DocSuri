-- D13: the sealed token is reachable only through these owner-rights functions. The
-- runtime role gets the three owner-scoped envelope functions and the identifier-free
-- key counts; the two re-seal functions belong to the operator acting as the schema
-- owner (security design §4.5, §5.3).

-- First configure (p_expected_revision = 0): writes only while the owner's row is still
-- pending and held by this check, moving revision 0 to 1 (R-02). Replace or reconnect:
-- writes only at the expected revision, moving it up by one; never from unavailable.
-- Either way the creation capability resets to unknown. Returns the new revision, or
-- NULL when the row moved on and nothing was written.
CREATE FUNCTION export.store_token_envelope(p_account uuid,p_connection uuid,p_expected_revision integer,
    p_holder uuid,p_envelope bytea,p_key_version text,p_workspace_name text,p_workspace_id text,
    p_connection_user_id text,p_validated_at timestamptz)
RETURNS integer LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE stored integer;
BEGIN
  IF p_expected_revision IS NULL OR p_expected_revision < 0 OR p_envelope IS NULL OR p_key_version IS NULL
     OR (p_expected_revision = 0 AND p_holder IS NULL) THEN
    RAISE EXCEPTION 'envelope store arguments invalid' USING ERRCODE='22023';
  END IF;
  IF p_expected_revision = 0 THEN
    UPDATE export.connection
       SET state='connected', revision=1, pending_holder=NULL, pending_started_at=NULL,
           sealed_token=p_envelope, token_key_version=p_key_version, validated_at=p_validated_at,
           workspace_name=p_workspace_name, workspace_id=p_workspace_id,
           connection_user_id=p_connection_user_id, creation_capability='unknown',
           updated_at=clock_timestamp()
     WHERE id=p_connection AND account_id=p_account AND state='pending' AND pending_holder=p_holder
    RETURNING revision INTO stored;
  ELSE
    UPDATE export.connection
       SET state='connected', revision=revision+1,
           sealed_token=p_envelope, token_key_version=p_key_version, validated_at=p_validated_at,
           workspace_name=p_workspace_name, workspace_id=p_workspace_id,
           connection_user_id=p_connection_user_id, creation_capability='unknown',
           updated_at=clock_timestamp()
     WHERE id=p_connection AND account_id=p_account AND revision=p_expected_revision
       AND state IN ('connected','disconnected','revoked')
    RETURNING revision INTO stored;
  END IF;
  RETURN stored;
END $$;

-- The adapter's only way to the envelope: that owner's connected or unavailable row.
CREATE FUNCTION export.open_token_envelope(p_account uuid,p_connection uuid)
RETURNS TABLE(sealed_token bytea,revision integer,token_key_version text,state text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog AS $$
  SELECT c.sealed_token, c.revision, c.token_key_version, c.state
    FROM export.connection c
   WHERE c.id=p_connection AND c.account_id=p_account AND c.state IN ('connected','unavailable');
$$;

-- Disconnect or revocation: clears the envelope and advances the revision by one in one
-- step, by compare-and-set on the expected revision. Returns NULL if the revision moved.
CREATE FUNCTION export.clear_token_envelope(p_account uuid,p_connection uuid,p_expected_revision integer,
    p_next_state text)
RETURNS integer LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE cleared integer;
BEGIN
  IF p_next_state IS NULL OR p_next_state NOT IN ('disconnected','revoked') THEN
    RAISE EXCEPTION 'envelope clear state invalid' USING ERRCODE='22023';
  END IF;
  UPDATE export.connection
     SET state=p_next_state, revision=revision+1, sealed_token=NULL, token_key_version=NULL,
         updated_at=clock_timestamp()
   WHERE id=p_connection AND account_id=p_account AND revision=p_expected_revision
     AND state IN ('connected','unavailable')
  RETURNING revision INTO cleared;
  RETURN cleared;
END $$;

-- The first-start witness (security design §4.4): sealed tokens per key version, with
-- no identifiers.
CREATE FUNCTION export.token_key_counts()
RETURNS TABLE(token_key_version text,sealed_tokens bigint)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog AS $$
  SELECT c.token_key_version, count(*)
    FROM export.connection c
   WHERE c.sealed_token IS NOT NULL
   GROUP BY c.token_key_version
   ORDER BY c.token_key_version;
$$;

-- Operator only: one bounded page of envelopes under a key version, with the binding
-- facts the re-seal needs (account, connection, revision).
CREATE FUNCTION export.token_envelopes_for_reseal(p_version text,p_limit integer)
RETURNS TABLE(connection_id uuid,account_id uuid,revision integer,sealed_token bytea)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog AS $$
  SELECT c.id, c.account_id, c.revision, c.sealed_token
    FROM export.connection c
   WHERE c.token_key_version=p_version AND c.sealed_token IS NOT NULL
   ORDER BY c.id
   LIMIT least(greatest(coalesce(p_limit,0),0),1000);
$$;

-- Operator only: replace one envelope by compare-and-set on the current envelope's
-- digest, keeping the revision, so a concurrent replace is never overwritten.
CREATE FUNCTION export.reseal_token(p_connection uuid,p_expected_envelope_sha256 text,p_new_envelope bytea,
    p_new_version text)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE resealed boolean;
BEGIN
  UPDATE export.connection
     SET sealed_token=p_new_envelope, token_key_version=p_new_version
   WHERE id=p_connection AND sealed_token IS NOT NULL
     AND encode(sha256(sealed_token),'hex')=p_expected_envelope_sha256
  RETURNING true INTO resealed;
  RETURN coalesce(resealed,false);
END $$;

REVOKE ALL ON ALL FUNCTIONS IN SCHEMA export FROM PUBLIC;
GRANT EXECUTE ON FUNCTION export.store_token_envelope(uuid,uuid,integer,uuid,bytea,text,text,text,text,timestamptz),
    export.open_token_envelope(uuid,uuid),
    export.clear_token_envelope(uuid,uuid,integer,text),
    export.token_key_counts()
  TO docsuri_export;
