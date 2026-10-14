CREATE TABLE accounts.restore_checkpoint (
  checkpoint_id uuid PRIMARY KEY, sequence bigint UNIQUE NOT NULL,
  checkpoint_digest text NOT NULL, fragment_digest text NOT NULL, evidence_ref uuid NOT NULL
);
CREATE FUNCTION accounts.reconcile_restore(c jsonb,f jsonb,d text) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE prior accounts.restore_checkpoint%ROWTYPE; last_row accounts.restore_checkpoint%ROWTYPE;
  item jsonb; a accounts.account%ROWTYPE; r accounts.lifecycle_request%ROWTYPE;
  s accounts.lifecycle_scope%ROWTYPE; restriction accounts.current_restriction%ROWTYPE;
  evidence uuid:=gen_random_uuid(); credential text;
BEGIN
  IF current_database()<>'docsuri_u2_restore' OR session_user<>'postgres'
     OR c->>'restoreDatabase'<>'docsuri_u2_restore' OR f->>'owner'<>'accounts'
     OR f->>'version'<>'1' OR f->>'runId' IS DISTINCT FROM c->>'runId'
     OR f->>'checkpointId' IS DISTINCT FROM c->>'checkpointId'
     OR f->>'sequence' IS DISTINCT FROM c->>'sequence' OR d!~'^[0-9a-f]{64}$'
     OR (c->>'sequence')::bigint<1 OR jsonb_typeof(f->'records')<>'array'
     OR jsonb_array_length(f->'records')>2000 OR octet_length(f::text)>524288 THEN
    RAISE EXCEPTION 'quarantined owner restore denied' USING ERRCODE='42501';
  END IF;
  PERFORM pg_advisory_xact_lock(280201);
  SELECT * INTO prior FROM accounts.restore_checkpoint WHERE checkpoint_id=(c->>'checkpointId')::uuid;
  IF FOUND THEN
    IF prior.fragment_digest<>d OR prior.checkpoint_digest<>c->>'checkpointDigest'
       OR prior.sequence<>(c->>'sequence')::bigint THEN RAISE EXCEPTION 'checkpoint replay conflict'; END IF;
    RETURN prior.evidence_ref;
  END IF;
  SELECT * INTO last_row FROM accounts.restore_checkpoint ORDER BY sequence DESC LIMIT 1;
  IF FOUND AND ((c->>'sequence')::bigint<=last_row.sequence
      OR c->>'previousDigest' IS DISTINCT FROM last_row.checkpoint_digest) THEN
    RAISE EXCEPTION 'stale or unlinked checkpoint';
  END IF;
  FOR item IN SELECT value FROM jsonb_array_elements(f->'records') LOOP
    CASE item->>'kind'
    WHEN 'account' THEN
      SELECT * INTO a FROM accounts.account WHERE id=(item->>'accountId')::uuid FOR UPDATE;
      IF NOT FOUND THEN RAISE EXCEPTION 'newer account requires recoverable current data'; END IF;
      credential:=encode(sha256(convert_to(a.password_hash||'|'||a.email||'|'||a.role,'UTF8')),'hex');
      UPDATE accounts.account SET
        authority_revision=(item->>'authorityRevision')::uuid,
        lifecycle_revision=(item->>'lifecycleRevision')::uuid,
        lifecycle_state=item->>'lifecycleState',active=(item->>'active')::boolean,
        verified=(item->>'verified')::boolean,
        password_hash=CASE WHEN credential=item->>'credentialDigest' THEN password_hash ELSE '!restore-requires-credential-proof' END
        WHERE id=a.id;
      UPDATE accounts.session SET revoked=true WHERE account_id=a.id;
      -- Old bearer/proof/factor/provider state must never become current after restore.
      DELETE FROM accounts.delivery WHERE challenge_id IN(SELECT id FROM accounts.challenge WHERE account_id=a.id);
      DELETE FROM accounts.challenge WHERE account_id=a.id;
      DELETE FROM accounts.control_proof WHERE account_id=a.id;
      DELETE FROM accounts.identity_flow WHERE account_id=a.id;
      DELETE FROM accounts.identity_link WHERE account_id=a.id;
      UPDATE accounts.mfa_enrollment SET state='invalidated' WHERE account_id=a.id;
      IF item->>'lifecycleState'='erased' THEN
        DELETE FROM accounts.mfa_recovery WHERE enrollment_id IN(SELECT id FROM accounts.mfa_enrollment WHERE account_id=a.id);
        DELETE FROM accounts.mfa_enrollment WHERE account_id=a.id;
        DELETE FROM accounts.control_receipt WHERE account_id=a.id AND kind NOT IN('lifecycle','lifecycle-confirm','reactivate');
        UPDATE accounts.account SET email='erased-'||id::text||'@erased.invalid',password_hash='!erased',
          display_name='삭제된 계정',profile='{}' WHERE id=a.id;
      END IF;
    WHEN 'consent' THEN
      INSERT INTO accounts.consent(account_id,purpose,granted,revision,effective_at)
        VALUES((item->>'accountId')::uuid,item->>'purpose',(item->>'granted')::boolean,
          (item->>'revision')::uuid,(item->>'effectiveAt')::timestamptz)
        ON CONFLICT(account_id,purpose) DO UPDATE SET granted=excluded.granted,
          revision=excluded.revision,effective_at=excluded.effective_at;
    WHEN 'restriction' THEN
      restriction:=jsonb_populate_record(NULL::accounts.current_restriction,item->'row');
      INSERT INTO accounts.current_restriction SELECT restriction.* ON CONFLICT(account_id)
        DO UPDATE SET generation=greatest(accounts.current_restriction.generation,excluded.generation),
        lifecycle_revision=excluded.lifecycle_revision,disposition=excluded.disposition,
        consent=excluded.consent,updated_at=excluded.updated_at;
    WHEN 'request' THEN
      r:=jsonb_populate_record(NULL::accounts.lifecycle_request,item->'row');
      INSERT INTO accounts.lifecycle_request SELECT r.* ON CONFLICT(id) DO UPDATE
        SET disposition=excluded.disposition,reason_key=excluded.reason_key,
          status_generation=greatest(accounts.lifecycle_request.status_generation,excluded.status_generation);
    WHEN 'scope' THEN
      s:=jsonb_populate_record(NULL::accounts.lifecycle_scope,item->'row');
      s.lease_until:=NULL;
      INSERT INTO accounts.lifecycle_scope SELECT s.* ON CONFLICT(request_id,participant,scope)
        DO UPDATE SET generation=greatest(accounts.lifecycle_scope.generation,excluded.generation),
          lease_until=NULL,attempts=greatest(accounts.lifecycle_scope.attempts,excluded.attempts),
          disposition=excluded.disposition,evidence_ref=excluded.evidence_ref,
          reason_key=excluded.reason_key,updated_at=excluded.updated_at;
    ELSE RAISE EXCEPTION 'unknown accounts checkpoint record';
    END CASE;
  END LOOP;
  INSERT INTO accounts.restore_checkpoint VALUES((c->>'checkpointId')::uuid,(c->>'sequence')::bigint,c->>'checkpointDigest',d,evidence);
  RETURN evidence;
END $$;
REVOKE ALL ON FUNCTION accounts.reconcile_restore(jsonb,jsonb,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION accounts.reconcile_restore(jsonb,jsonb,text) TO docsuri_accounts;
