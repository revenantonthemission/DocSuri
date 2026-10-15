CREATE TABLE library.restore_checkpoint (
  sequence bigint PRIMARY KEY CHECK(sequence>0), checkpoint_id uuid UNIQUE NOT NULL,
  checkpoint_digest text NOT NULL, fragment_digest text NOT NULL, evidence_ref uuid NOT NULL
);
REVOKE ALL ON library.restore_checkpoint FROM PUBLIC,docsuri_library;

CREATE FUNCTION library.reconcile_restore(p_context jsonb,p_fragment jsonb,p_digest text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE last_row library.restore_checkpoint%ROWTYPE; item jsonb; value jsonb;
  seq bigint; identifier uuid; evidence uuid; account uuid;
BEGIN
  IF current_database()<>'docsuri_u2_restore' OR session_user<>'postgres' THEN
    RAISE EXCEPTION 'quarantined operator connection required' USING ERRCODE='42501';
  END IF;
  IF p_context->>'restoreDatabase' IS DISTINCT FROM 'docsuri_u2_restore' OR
     p_context->>'runId' IS DISTINCT FROM (SELECT run_id FROM public.docsuri_local_identity) OR
     p_fragment->>'owner' IS DISTINCT FROM 'Library' OR p_fragment->>'version' IS DISTINCT FROM '1' OR
     p_fragment->>'runId' IS DISTINCT FROM p_context->>'runId' OR
     p_fragment->>'checkpointId' IS DISTINCT FROM p_context->>'checkpointId' OR
     p_fragment->>'sequence' IS DISTINCT FROM p_context->>'sequence' OR
     p_digest IS NULL OR p_digest !~ '^[0-9a-f]{64}$' OR
     p_context->>'checkpointDigest' IS NULL OR p_context->>'checkpointDigest' !~ '^[0-9a-f]{64}$' OR
     jsonb_typeof(p_fragment->'records') IS DISTINCT FROM 'array' OR jsonb_array_length(p_fragment->'records')>2000 OR
     octet_length(p_fragment::text)>300000 THEN
    RAISE EXCEPTION 'invalid Library checkpoint' USING ERRCODE='22023';
  END IF;
  seq:=(p_context->>'sequence')::bigint; identifier:=(p_context->>'checkpointId')::uuid;
  IF seq IS NULL OR seq<1 OR identifier IS NULL THEN RAISE EXCEPTION 'invalid checkpoint sequence'; END IF;
  PERFORM pg_advisory_xact_lock(hashtextextended('library-restore',1));
  SELECT * INTO last_row FROM library.restore_checkpoint ORDER BY sequence DESC LIMIT 1;
  IF FOUND THEN
    IF seq=last_row.sequence AND identifier=last_row.checkpoint_id AND
       p_digest=last_row.fragment_digest AND p_context->>'checkpointDigest'=last_row.checkpoint_digest THEN
      RETURN last_row.evidence_ref;
    END IF;
    IF seq<>last_row.sequence+1 OR p_context->>'previousDigest' IS DISTINCT FROM last_row.checkpoint_digest THEN
      RAISE EXCEPTION 'stale or conflicting Library checkpoint' USING ERRCODE='40001';
    END IF;
  ELSIF seq<>1 OR p_context->>'previousDigest' IS NOT NULL THEN
    RAISE EXCEPTION 'missing Library checkpoint predecessor' USING ERRCODE='40001';
  END IF;
  FOR item IN SELECT * FROM jsonb_array_elements(p_fragment->'records') LOOP
    value:=item->'value';
    IF item->>'kind'='boundary' THEN
      account:=(value->>'account_id')::uuid;
      INSERT INTO library.history_boundary(account_id,generation,revision,eligible_after,admission_cutoff)
      VALUES(account,(value->>'generation')::bigint,(value->>'revision')::uuid,
             (value->>'eligible_after')::timestamptz,(value->>'admission_cutoff')::bigint)
      ON CONFLICT(account_id) DO UPDATE SET generation=excluded.generation,revision=excluded.revision,
        eligible_after=excluded.eligible_after,admission_cutoff=excluded.admission_cutoff
      WHERE library.history_boundary.generation<=excluded.generation;
    ELSIF item->>'kind'='restriction' THEN
      INSERT INTO library.restriction SELECT * FROM jsonb_populate_record(NULL::library.restriction,value)
      ON CONFLICT(account_id) DO UPDATE SET lifecycle_revision=excluded.lifecycle_revision,
        disposition=excluded.disposition,updated_at=excluded.updated_at;
    ELSIF item->>'kind'='receipt' THEN
      IF value->>'kind' NOT IN ('clear-history','remove-paper','remove-query') THEN
        RAISE EXCEPTION 'non-restriction receipt refused';
      END IF;
      IF EXISTS (SELECT 1 FROM library.receipt r WHERE r.account_id=(value->>'account_id')::uuid
          AND r.kind=value->>'kind' AND r.key=(value->>'key')::uuid
          AND (r.intent_hash IS DISTINCT FROM value->>'intent_hash' OR r.outcome IS DISTINCT FROM value->'outcome')) THEN
        RAISE EXCEPTION 'conflicting immutable Library receipt' USING ERRCODE='40001';
      END IF;
      INSERT INTO library.receipt SELECT * FROM jsonb_populate_record(NULL::library.receipt,value)
      ON CONFLICT DO NOTHING;
    ELSIF item->>'kind' IS NULL OR item->>'kind' NOT IN ('saved-paper','saved-query','erased-owner') THEN
      RAISE EXCEPTION 'unknown Library restriction';
    END IF;
  END LOOP;
  DELETE FROM library.history h USING library.history_boundary b WHERE h.account_id=b.account_id AND
    (h.captured_generation<>b.generation OR h.completed_at<=b.eligible_after OR
     h.admission_sequence<=b.admission_cutoff);
  -- A complete current key/revision inventory suppresses removed or superseded
  -- saved references without copying private query text into the journal.
  DELETE FROM library.saved_paper s WHERE NOT EXISTS (
    SELECT 1 FROM jsonb_array_elements(p_fragment->'records') r WHERE r->>'kind'='saved-paper'
    AND r->'value'->>'account_id'=s.account_id::text AND r->'value'->>'paper_id'=s.paper_id
    AND r->'value'->>'revision'=s.revision::text);
  DELETE FROM library.saved_query s WHERE NOT EXISTS (
    SELECT 1 FROM jsonb_array_elements(p_fragment->'records') r WHERE r->>'kind'='saved-query'
    AND r->'value'->>'account_id'=s.account_id::text AND r->'value'->>'id'=s.id::text
    AND r->'value'->>'revision'=s.revision::text);
  FOR account IN SELECT (r->>'account_id')::uuid FROM jsonb_array_elements(p_fragment->'records') r
                WHERE r->>'kind'='erased-owner' LOOP
    DELETE FROM library.saved_paper WHERE account_id=account;
    DELETE FROM library.saved_query WHERE account_id=account;
    DELETE FROM library.history WHERE account_id=account;
    DELETE FROM library.receipt WHERE account_id=account;
  END LOOP;
  evidence:=gen_random_uuid();
  INSERT INTO library.restore_checkpoint VALUES(seq,identifier,p_context->>'checkpointDigest',p_digest,evidence);
  RETURN evidence;
END $$;
REVOKE ALL ON FUNCTION library.reconcile_restore(jsonb,jsonb,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION library.reconcile_restore(jsonb,jsonb,text) TO docsuri_library;
