CREATE TABLE assistance.restore_checkpoint (
  checkpoint_id uuid PRIMARY KEY, sequence bigint UNIQUE NOT NULL,
  checkpoint_digest text NOT NULL, fragment_digest text NOT NULL, evidence_ref uuid NOT NULL
);
CREATE FUNCTION assistance.reconcile_restore(c jsonb,f jsonb,d text) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE prior assistance.restore_checkpoint%ROWTYPE; last_row assistance.restore_checkpoint%ROWTYPE;
  item jsonb; a assistance.admission%ROWTYPE; j assistance.job%ROWTYPE;
  erased assistance.erased_admission%ROWTYPE; evidence uuid:=gen_random_uuid();
BEGIN
  IF current_database()<>'docsuri_u2_restore' OR session_user<>'postgres'
     OR c->>'restoreDatabase'<>'docsuri_u2_restore' OR f->>'owner'<>'assistance'
     OR f->>'version'<>'1' OR f->>'runId' IS DISTINCT FROM c->>'runId'
     OR f->>'checkpointId' IS DISTINCT FROM c->>'checkpointId'
     OR f->>'sequence' IS DISTINCT FROM c->>'sequence' OR d!~'^[0-9a-f]{64}$'
     OR (c->>'sequence')::bigint<1 OR jsonb_typeof(f->'records')<>'array'
     OR jsonb_array_length(f->'records')>2000 OR octet_length(f::text)>524288 THEN
    RAISE EXCEPTION 'quarantined owner restore denied' USING ERRCODE='42501';
  END IF;
  PERFORM pg_advisory_xact_lock(280203);
  SELECT * INTO prior FROM assistance.restore_checkpoint WHERE checkpoint_id=(c->>'checkpointId')::uuid;
  IF FOUND THEN
    IF prior.fragment_digest<>d OR prior.checkpoint_digest<>c->>'checkpointDigest'
       OR prior.sequence<>(c->>'sequence')::bigint THEN RAISE EXCEPTION 'checkpoint replay conflict'; END IF;
    RETURN prior.evidence_ref;
  END IF;
  SELECT * INTO last_row FROM assistance.restore_checkpoint ORDER BY sequence DESC LIMIT 1;
  IF FOUND AND ((c->>'sequence')::bigint<=last_row.sequence
      OR c->>'previousDigest' IS DISTINCT FROM last_row.checkpoint_digest) THEN
    RAISE EXCEPTION 'stale or unlinked checkpoint';
  END IF;
  FOR item IN SELECT value FROM jsonb_array_elements(f->'records') LOOP
    CASE item->>'kind'
    WHEN 'admission' THEN
      SELECT * INTO a FROM assistance.admission WHERE operation_id=(item->>'operationId')::uuid FOR UPDATE;
      IF NOT FOUND THEN
        IF item->>'disposition'<>'rejected' THEN
          RAISE EXCEPTION 'newer accepted work requires recoverable current payload';
        END IF;
        INSERT INTO assistance.admission(operation_id,account_id,intent_hash,intent,disposition,
            generation,period_id,quantity,policy_ref,closure_ref,closed_at,closure_reason)
          VALUES((item->>'operationId')::uuid,(item->>'accountId')::uuid,item->>'intentHash','{}',
            'rejected',(item->>'generation')::bigint,item->>'periodId',(item->>'quantity')::integer,
            item->'policyRef',(item->>'closureRef')::uuid,(item->>'closedAt')::timestamptz,item->>'closureReason');
      ELSE
        IF a.account_id<>(item->>'accountId')::uuid OR a.intent_hash<>item->>'intentHash'
            OR a.generation<>(item->>'generation')::bigint OR a.period_id<>item->>'periodId'
            OR a.policy_ref<>item->'policyRef' OR a.quantity<>(item->>'quantity')::integer
            OR (a.disposition<>'open' AND a.disposition<>item->>'disposition') THEN
          RAISE EXCEPTION 'admission identity or terminal conflict';
        END IF;
        IF a.disposition='open' AND item->>'disposition'='accepted' AND NOT EXISTS(
            SELECT 1 FROM assistance.job WHERE id=a.operation_id) THEN
          RAISE EXCEPTION 'accepted payload absent from backup';
        END IF;
        UPDATE assistance.admission SET disposition=item->>'disposition',
          reservation_id=(item->>'reservationId')::uuid,closure_ref=(item->>'closureRef')::uuid,
          closed_at=(item->>'closedAt')::timestamptz,closure_reason=item->>'closureReason'
          WHERE operation_id=a.operation_id;
      END IF;
    WHEN 'job' THEN
      SELECT * INTO j FROM assistance.job WHERE id=(item->>'id')::uuid FOR UPDATE;
      IF NOT FOUND OR j.account_id<>(item->>'accountId')::uuid THEN
        RAISE EXCEPTION 'accepted job recovery data missing';
      END IF;
      IF item->>'state' IN ('accepted','running') THEN
        RAISE EXCEPTION 'in-flight work requires explicit recovery before restore completion';
      END IF;
      UPDATE assistance.job SET state=item->>'state',sequence=greatest(sequence,(item->>'sequence')::bigint),
        fence=greatest(fence,(item->>'fence')::bigint)+1,revision=(item->>'revision')::uuid,
        phase=item->>'phase',failure_code=item->>'failureCode',
        settlement_pending=(item->>'settlementPending')::boolean,
        settlement_receipt=item->'settlementReceipt',dispatch_pending=false,
        worker_id=NULL,lease_id=NULL,lease_revision=NULL,lease_expires_at=NULL WHERE id=j.id;
    WHEN 'result' THEN
      IF NOT EXISTS(SELECT 1 FROM assistance.result WHERE id=(item->>'id')::uuid
          AND account_id=(item->>'accountId')::uuid) THEN
        RAISE EXCEPTION 'permitted result requires recoverable current artifact';
      END IF;
      UPDATE assistance.result SET availability=CASE WHEN item->>'availability'='retained'
        THEN 'restricted' ELSE item->>'availability' END WHERE id=(item->>'id')::uuid;
    WHEN 'erased' THEN
      erased:=jsonb_populate_record(NULL::assistance.erased_admission,item->'row');
      INSERT INTO assistance.erased_admission SELECT erased.* ON CONFLICT DO NOTHING;
      DELETE FROM assistance.event WHERE job_id=erased.operation_id;
      DELETE FROM assistance.result WHERE job_id=erased.operation_id;
      DELETE FROM assistance.job WHERE id=erased.operation_id;
      DELETE FROM assistance.admission WHERE operation_id=erased.operation_id;
      DELETE FROM assistance.glossary WHERE account_id=erased.account_id;
    ELSE RAISE EXCEPTION 'unknown assistance checkpoint record';
    END CASE;
  END LOOP;
  INSERT INTO assistance.restore_checkpoint VALUES((c->>'checkpointId')::uuid,(c->>'sequence')::bigint,c->>'checkpointDigest',d,evidence);
  RETURN evidence;
END $$;
REVOKE ALL ON FUNCTION assistance.reconcile_restore(jsonb,jsonb,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION assistance.reconcile_restore(jsonb,jsonb,text) TO docsuri_assistance;
