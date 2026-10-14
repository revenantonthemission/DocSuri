-- Tighten domain identity, current run, null handling and checkpoint ordering.
CREATE OR REPLACE FUNCTION usage.reconcile_restore(c jsonb,f jsonb,d text) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE prior usage.restore_checkpoint%ROWTYPE; last_row usage.restore_checkpoint%ROWTYPE;
  item jsonb; e usage.entitlement%ROWTYPE; r usage.reservation%ROWTYPE;
  old usage.reservation%ROWTYPE; rejected usage.rejected_operation%ROWTYPE;
  evidence uuid:=gen_random_uuid();
BEGIN
  IF NOT coalesce(current_database()='docsuri_u2_restore' AND session_user='postgres'
     AND c->>'restoreDatabase'='docsuri_u2_restore' AND f->>'owner'='UsageEntitlements'
     AND f->>'version'='1' AND f->>'runId'=c->>'runId'
     AND f->>'checkpointId'=c->>'checkpointId' AND f->>'sequence'=c->>'sequence'
     AND d~'^[0-9a-f]{64}$' AND c->>'checkpointDigest'~'^[0-9a-f]{64}$'
     AND (c->>'sequence')::bigint>=1 AND jsonb_typeof(f->'records')='array'
     AND jsonb_array_length(f->'records')<=2000 AND octet_length(f::text)<=524288
     AND EXISTS(SELECT 1 FROM public.docsuri_local_identity WHERE run_id=c->>'runId'),false) THEN
    RAISE EXCEPTION 'quarantined owner restore denied' USING ERRCODE='42501';
  END IF;
  PERFORM pg_advisory_xact_lock(280202);
  SELECT * INTO last_row FROM usage.restore_checkpoint ORDER BY sequence DESC LIMIT 1;
  IF FOUND THEN
    IF (c->>'sequence')::bigint<last_row.sequence
        OR ((c->>'sequence')::bigint=last_row.sequence AND (c->>'checkpointId')::uuid<>last_row.checkpoint_id)
        OR ((c->>'sequence')::bigint>last_row.sequence AND
          ((c->>'sequence')::bigint<>last_row.sequence+1 OR c->>'previousDigest' IS DISTINCT FROM last_row.checkpoint_digest)) THEN
      RAISE EXCEPTION 'stale or unlinked checkpoint';
    END IF;
  ELSIF (c->>'sequence')::bigint<>1 OR c->>'previousDigest' IS NOT NULL THEN
    RAISE EXCEPTION 'initial checkpoint must begin authenticated chain';
  END IF;
  SELECT * INTO prior FROM usage.restore_checkpoint WHERE checkpoint_id=(c->>'checkpointId')::uuid;
  IF FOUND THEN
    IF prior.fragment_digest<>d OR prior.checkpoint_digest<>c->>'checkpointDigest'
       OR prior.sequence<>(c->>'sequence')::bigint THEN RAISE EXCEPTION 'checkpoint replay conflict'; END IF;
    RETURN prior.evidence_ref;
  END IF;
  FOR item IN SELECT value FROM jsonb_array_elements(f->'records') LOOP
    CASE item->>'kind'
    WHEN 'entitlement' THEN
      e:=jsonb_populate_record(NULL::usage.entitlement,item->'row');
      INSERT INTO usage.entitlement SELECT e.* ON CONFLICT(account_id) DO UPDATE SET
        revision=excluded.revision,allocation=excluded.allocation,policy=excluded.policy,
        revoked=excluded.revoked,assignment_revision=excluded.assignment_revision,
        period_id=excluded.period_id,created_at=excluded.created_at;
    WHEN 'reservation' THEN
      r:=jsonb_populate_record(NULL::usage.reservation,item->'row');
      SELECT * INTO old FROM usage.reservation WHERE id=r.id FOR UPDATE;
      IF FOUND AND (ROW(old.account_id,old.operation_id,old.intent_hash,old.operation_generation,
          old.period_id,old.quantity,old.policy_ref) IS DISTINCT FROM ROW(r.account_id,r.operation_id,
          r.intent_hash,r.operation_generation,r.period_id,r.quantity,r.policy_ref)
          OR (old.disposition<>'reserved' AND old.disposition<>r.disposition)) THEN
        RAISE EXCEPTION 'ledger identity or terminal conflict';
      END IF;
      INSERT INTO usage.reservation SELECT r.* ON CONFLICT(id) DO UPDATE SET
        disposition=excluded.disposition,settlement_key=excluded.settlement_key,
        settlement_hash=excluded.settlement_hash,revision=excluded.revision,
        closure_evidence=excluded.closure_evidence;
    WHEN 'rejected' THEN
      rejected:=jsonb_populate_record(NULL::usage.rejected_operation,item->'row');
      INSERT INTO usage.rejected_operation SELECT rejected.* ON CONFLICT DO NOTHING;
    ELSE RAISE EXCEPTION 'unknown usage checkpoint record';
    END CASE;
  END LOOP;
  -- Absence never releases a reservation, and no period is recalculated during restore.
  INSERT INTO usage.restore_checkpoint VALUES((c->>'checkpointId')::uuid,(c->>'sequence')::bigint,c->>'checkpointDigest',d,evidence);
  RETURN evidence;
END $$;
REVOKE ALL ON FUNCTION usage.reconcile_restore(jsonb,jsonb,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION usage.reconcile_restore(jsonb,jsonb,text) TO docsuri_usage;
