-- The untouched live database anchors current restriction evidence. A restored
-- older copy cannot advance or authorize this checkpoint. No API role receives
-- access; calls require the original synthetic maintenance session as postgres.
CREATE TABLE operations.restore_checkpoint (
  run_id text NOT NULL,
  sequence bigint NOT NULL CHECK(sequence>0),
  checkpoint_id uuid NOT NULL,
  checkpoint_digest text NOT NULL CHECK(checkpoint_digest ~ '^[0-9a-f]{64}$'),
  previous_digest text,
  context jsonb NOT NULL,
  recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY(run_id,sequence),
  UNIQUE(run_id,checkpoint_id),
  CHECK((sequence=1 AND previous_digest IS NULL) OR
        (sequence>1 AND previous_digest ~ '^[0-9a-f]{64}$')),
  CHECK(octet_length(context::text)<=8192)
);
REVOKE ALL ON operations.restore_checkpoint FROM PUBLIC,docsuri_operations;

CREATE FUNCTION operations.read_restore_checkpoint()
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE run text; result jsonb;
BEGIN
  IF current_database()<>'docsuri_u2' OR session_user<>'postgres' THEN
    RAISE EXCEPTION 'live maintenance checkpoint only' USING ERRCODE='42501';
  END IF;
  SELECT run_id INTO STRICT run FROM public.docsuri_local_identity WHERE singleton;
  SELECT context INTO result FROM operations.restore_checkpoint
    WHERE run_id=run ORDER BY sequence DESC LIMIT 1;
  RETURN result;
END $$;
REVOKE ALL ON FUNCTION operations.read_restore_checkpoint() FROM PUBLIC,docsuri_operations;

CREATE FUNCTION operations.advance_restore_checkpoint(p_context jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE run text; next_sequence bigint; prior operations.restore_checkpoint%ROWTYPE;
  digest_key text; actual_keys text[];
BEGIN
  IF current_database()<>'docsuri_u2' OR session_user<>'postgres' THEN
    RAISE EXCEPTION 'live maintenance checkpoint only' USING ERRCODE='42501';
  END IF;
  SELECT run_id INTO STRICT run FROM public.docsuri_local_identity WHERE singleton;
  IF jsonb_typeof(p_context)<>'object' OR octet_length(p_context::text)>8192 THEN
    RAISE EXCEPTION 'bounded context required' USING ERRCODE='23514';
  END IF;
  SELECT array_agg(key ORDER BY key) INTO actual_keys FROM jsonb_object_keys(p_context) AS key;
  IF actual_keys IS DISTINCT FROM ARRAY['backupDigest','checkpointDigest','checkpointId',
      'manifestDigest','policyDigest','previousDigest','restoreDatabase','runId',
      'schemaDigest','sequence','sourceDigest']::text[] OR
      p_context->>'runId' IS DISTINCT FROM run OR
      p_context->>'restoreDatabase' IS DISTINCT FROM 'docsuri_u2_restore' OR
      jsonb_typeof(p_context->'sequence') IS DISTINCT FROM 'number' OR
      p_context->>'sequence' !~ '^[1-9][0-9]{0,18}$' OR
      (p_context->>'checkpointId')::uuid='00000000-0000-0000-0000-000000000000'::uuid THEN
    RAISE EXCEPTION 'checkpoint context binding differs' USING ERRCODE='23514';
  END IF;
  FOREACH digest_key IN ARRAY ARRAY['backupDigest','checkpointDigest','sourceDigest',
      'schemaDigest','policyDigest','manifestDigest'] LOOP
    IF jsonb_typeof(p_context->digest_key) IS DISTINCT FROM 'string' OR
       p_context->>digest_key !~ '^[0-9a-f]{64}$' THEN
      RAISE EXCEPTION 'checkpoint digest invalid' USING ERRCODE='23514';
    END IF;
  END LOOP;
  next_sequence:=(p_context->>'sequence')::bigint;
  PERFORM pg_advisory_xact_lock(hashtextextended(run,9412));
  SELECT * INTO prior FROM operations.restore_checkpoint WHERE run_id=run
    ORDER BY sequence DESC LIMIT 1 FOR UPDATE;
  IF FOUND THEN
    IF next_sequence=prior.sequence AND p_context=prior.context THEN
      RETURN prior.context;
    END IF;
    IF next_sequence<>prior.sequence+1 OR
       p_context->>'previousDigest' IS DISTINCT FROM prior.checkpoint_digest THEN
      RAISE EXCEPTION 'checkpoint cannot regress or fork' USING ERRCODE='40001';
    END IF;
  ELSIF next_sequence<>1 OR jsonb_typeof(p_context->'previousDigest') IS DISTINCT FROM 'null' THEN
    RAISE EXCEPTION 'initial checkpoint binding differs' USING ERRCODE='23514';
  END IF;
  INSERT INTO operations.restore_checkpoint(run_id,sequence,checkpoint_id,checkpoint_digest,
      previous_digest,context) VALUES(run,next_sequence,(p_context->>'checkpointId')::uuid,
      p_context->>'checkpointDigest',p_context->>'previousDigest',p_context);
  RETURN p_context;
END $$;
REVOKE ALL ON FUNCTION operations.advance_restore_checkpoint(jsonb) FROM PUBLIC,docsuri_operations;
