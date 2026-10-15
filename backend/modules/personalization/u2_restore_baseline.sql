-- A fresh quarantined target may begin at its authenticated current checkpoint.
CREATE OR REPLACE FUNCTION personalization.reconcile_restore(p_context jsonb,p_fragment jsonb,p_digest text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE last_row personalization.restore_checkpoint%ROWTYPE; item jsonb; value jsonb;
  seq bigint; identifier uuid; evidence uuid; account uuid;
BEGIN
  IF current_database()<>'docsuri_u2_restore' OR session_user<>'postgres' THEN
    RAISE EXCEPTION 'quarantined operator connection required' USING ERRCODE='42501';
  END IF;
  IF p_context->>'restoreDatabase' IS DISTINCT FROM 'docsuri_u2_restore' OR
     p_context->>'runId' IS DISTINCT FROM (SELECT run_id FROM public.docsuri_local_identity) OR
     p_fragment->>'owner' IS DISTINCT FROM 'Personalization' OR
     p_fragment->>'version' IS DISTINCT FROM '1' OR
     p_fragment->>'runId' IS DISTINCT FROM p_context->>'runId' OR
     p_fragment->>'checkpointId' IS DISTINCT FROM p_context->>'checkpointId' OR
     p_fragment->>'sequence' IS DISTINCT FROM p_context->>'sequence' OR
     p_digest IS NULL OR p_digest !~ '^[0-9a-f]{64}$' OR
     p_context->>'checkpointDigest' IS NULL OR p_context->>'checkpointDigest' !~ '^[0-9a-f]{64}$' OR
     jsonb_typeof(p_fragment->'records') IS DISTINCT FROM 'array' OR
     jsonb_array_length(p_fragment->'records')>2000 OR octet_length(p_fragment::text)>300000 THEN
    RAISE EXCEPTION 'invalid Personalization checkpoint' USING ERRCODE='22023';
  END IF;
  seq:=(p_context->>'sequence')::bigint; identifier:=(p_context->>'checkpointId')::uuid;
  IF seq IS NULL OR seq<1 OR identifier IS NULL THEN RAISE EXCEPTION 'invalid checkpoint sequence'; END IF;
  PERFORM pg_advisory_xact_lock(hashtextextended('personalization-restore',1));
  SELECT * INTO last_row FROM personalization.restore_checkpoint ORDER BY sequence DESC LIMIT 1;
  IF FOUND THEN
    IF seq=last_row.sequence AND identifier=last_row.checkpoint_id AND
       p_digest=last_row.fragment_digest AND p_context->>'checkpointDigest'=last_row.checkpoint_digest THEN
      RETURN last_row.evidence_ref;
    END IF;
    IF seq<>last_row.sequence+1 OR p_context->>'previousDigest' IS DISTINCT FROM last_row.checkpoint_digest THEN
      RAISE EXCEPTION 'stale or conflicting Personalization checkpoint' USING ERRCODE='40001';
    END IF;
  ELSIF NOT EXISTS (
    SELECT 1 FROM public.docsuri_restore_guard g WHERE g.singleton AND g.quarantined
      AND g.run_id=p_context->>'runId' AND g.backup_digest=p_context->>'backupDigest'
      AND g.starting_context=p_context
  ) THEN
    RAISE EXCEPTION 'missing authenticated Personalization restore baseline' USING ERRCODE='40001';
  END IF;
  FOR item IN SELECT * FROM jsonb_array_elements(p_fragment->'records') LOOP
    value:=item->'value';
    IF item->>'kind'='settings' THEN
      INSERT INTO personalization.settings SELECT * FROM jsonb_populate_record(NULL::personalization.settings,value)
      ON CONFLICT(account_id) DO UPDATE SET revision=excluded.revision,appearance=excluded.appearance,
        language=excluded.language,defaults=excluded.defaults,onboarding=excluded.onboarding,
        input_boundary=excluded.input_boundary
      WHERE personalization.settings.input_boundary<=excluded.input_boundary;
    ELSIF item->>'kind'='reset' THEN
      INSERT INTO personalization.reset_responsibility
      SELECT * FROM jsonb_populate_record(NULL::personalization.reset_responsibility,value)
      ON CONFLICT(id) DO UPDATE SET status_revision=excluded.status_revision,
        disposition=excluded.disposition,reason_key=excluded.reason_key
      WHERE personalization.reset_responsibility.status_revision<excluded.status_revision;
    ELSIF item->>'kind'='scope' THEN
      -- Old worker claims cannot survive an isolated restore. Complete evidence
      -- remains complete; pending claims advance generation and lose their lease.
      value:=jsonb_set(value,'{lease_until}','null'::jsonb);
      IF value->>'disposition'<>'complete' THEN
        value:=jsonb_set(value,'{generation}',to_jsonb((value->>'generation')::bigint+1));
      END IF;
      INSERT INTO personalization.reset_scope SELECT * FROM jsonb_populate_record(NULL::personalization.reset_scope,value)
      ON CONFLICT(reset_id,participant,scope) DO UPDATE SET
        generation=CASE WHEN excluded.disposition='complete' THEN excluded.generation
          ELSE greatest(personalization.reset_scope.generation+1,excluded.generation) END,
        disposition=excluded.disposition,attempts=excluded.attempts,lease_until=NULL,
        reason_key=excluded.reason_key,evidence_ref=excluded.evidence_ref,updated_at=excluded.updated_at;
    ELSIF item->>'kind'='receipt' THEN
      IF EXISTS (SELECT 1 FROM personalization.receipt r WHERE r.account_id=(value->>'account_id')::uuid
          AND r.kind=value->>'kind' AND r.key=(value->>'key')::uuid
          AND (r.intent_hash IS DISTINCT FROM value->>'intent_hash' OR r.outcome IS DISTINCT FROM value->'outcome')) THEN
        RAISE EXCEPTION 'conflicting immutable Personalization receipt' USING ERRCODE='40001';
      END IF;
      INSERT INTO personalization.receipt SELECT * FROM jsonb_populate_record(NULL::personalization.receipt,value)
      ON CONFLICT DO NOTHING;
    ELSIF item->>'kind' IS DISTINCT FROM 'erased-owner' THEN
      RAISE EXCEPTION 'unknown Personalization restriction';
    END IF;
  END LOOP;
  DELETE FROM personalization.settings s WHERE NOT EXISTS (
    SELECT 1 FROM jsonb_array_elements(p_fragment->'records') r WHERE r->>'kind'='settings'
    AND r->'value'->>'account_id'=s.account_id::text);
  DELETE FROM personalization.behavior b WHERE NOT EXISTS (
    SELECT 1 FROM personalization.settings s WHERE s.account_id=b.account_id AND s.input_boundary=b.input_boundary);
  DELETE FROM personalization.projection p WHERE NOT EXISTS (
    SELECT 1 FROM personalization.settings s WHERE s.account_id=p.account_id AND s.input_boundary=p.input_boundary);
  FOR account IN SELECT (r->>'account_id')::uuid FROM jsonb_array_elements(p_fragment->'records') r
                WHERE r->>'kind'='erased-owner' LOOP
    DELETE FROM personalization.settings WHERE account_id=account;
    DELETE FROM personalization.behavior WHERE account_id=account;
    DELETE FROM personalization.projection WHERE account_id=account;
    DELETE FROM personalization.receipt WHERE account_id=account;
    UPDATE personalization.reset_scope s SET generation=generation+1,lease_until=NULL,
      attempts=3,disposition='blocked',reason_key='account-erased'
      FROM personalization.reset_responsibility r WHERE r.id=s.reset_id AND r.account_id=account
      AND s.disposition<>'complete';
    UPDATE personalization.reset_responsibility SET status_revision=status_revision+1,
      disposition='blocked',reason_key='account-erased' WHERE account_id=account AND disposition<>'complete';
  END LOOP;
  evidence:=gen_random_uuid();
  INSERT INTO personalization.restore_checkpoint VALUES(seq,identifier,p_context->>'checkpointDigest',p_digest,evidence);
  RETURN evidence;
END $$;
