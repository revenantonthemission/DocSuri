-- U8 (BR3.1-BR3.6, O1, observability-design § 3.1): ServiceOperations' observation
-- records for the complete application. The built operations.observation (one row per
-- capability, upserted) stays as it is for the earlier assemblies (C2); the complete
-- assembly keeps every admitted observation here, reads the latest per capability on
-- the index and deletes records older than 14 days through the bounded function only.
-- Records hold registered keys, counts and identifiers, never private text (BR3.4).
CREATE TABLE operations.observation_record (
    id uuid PRIMARY KEY,
    capability text NOT NULL CHECK (capability ~ '^[a-z][a-z0-9.-]{0,63}$'),
    producer text NOT NULL CHECK (producer ~ '^[a-z][a-z0-9.-]{0,63}$'),
    outcome text NOT NULL CHECK (outcome IN ('available','degraded','unavailable','unknown')),
    reason_key text CHECK (reason_key IS NULL OR reason_key ~ '^[a-z][a-z0-9.-]{0,63}$'),
    limitation_keys text[] NOT NULL DEFAULT '{}'
        CHECK (cardinality(limitation_keys) <= 16
               AND array_to_string(limitation_keys, ',') ~ '^([a-z][a-z0-9.-]{0,63}(,|$))*$'),
    error_count integer NOT NULL DEFAULT 0 CHECK (error_count >= 0),
    total_count integer NOT NULL DEFAULT 0 CHECK (total_count >= error_count),
    request_id uuid,
    revision bigint NOT NULL CHECK (revision >= 1),
    observed_at timestamptz NOT NULL,
    CHECK (outcome = 'available' OR reason_key IS NOT NULL)
);
CREATE INDEX observation_record_latest ON operations.observation_record (capability, observed_at DESC);
GRANT SELECT,INSERT ON operations.observation_record TO docsuri_operations;

-- Bounded deletion (observability-design § 3.1): at most p_limit records older than
-- 14 days before the caller's clock, oldest first. The runtime login has no DELETE.
CREATE FUNCTION operations.delete_old_observations(p_now timestamptz, p_limit integer)
RETURNS integer LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE removed integer;
BEGIN
  IF p_now IS NULL OR p_limit IS NULL OR p_limit < 1 OR p_limit > 10000 THEN
    RAISE EXCEPTION 'observation deletion bound invalid' USING ERRCODE='22023';
  END IF;
  WITH doomed AS (
    SELECT id FROM operations.observation_record
     WHERE observed_at < p_now - interval '14 days'
     ORDER BY observed_at, id LIMIT p_limit
  )
  DELETE FROM operations.observation_record r USING doomed WHERE r.id = doomed.id;
  GET DIAGNOSTICS removed = ROW_COUNT;
  RETURN removed;
END $$;
REVOKE ALL ON FUNCTION operations.delete_old_observations(timestamptz,integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION operations.delete_old_observations(timestamptz,integer) TO docsuri_operations;
