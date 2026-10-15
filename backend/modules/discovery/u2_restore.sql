CREATE TABLE discovery.restore_checkpoint (
  checkpoint_id uuid PRIMARY KEY, sequence bigint UNIQUE NOT NULL,
  checkpoint_digest text NOT NULL, fragment_digest text NOT NULL, evidence_ref uuid NOT NULL
);
CREATE FUNCTION discovery.reconcile_restore(c jsonb,f jsonb,d text) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE prior discovery.restore_checkpoint%ROWTYPE; last_row discovery.restore_checkpoint%ROWTYPE;
  item jsonb; a discovery.admission%ROWTYPE; evidence uuid:=gen_random_uuid();
BEGIN
  IF current_database()<>'docsuri_u2_restore' OR session_user<>'postgres'
     OR c->>'restoreDatabase'<>'docsuri_u2_restore' OR f->>'owner'<>'discovery'
     OR f->>'version'<>'1' OR f->>'runId' IS DISTINCT FROM c->>'runId'
     OR f->>'checkpointId' IS DISTINCT FROM c->>'checkpointId'
     OR f->>'sequence' IS DISTINCT FROM c->>'sequence' OR d!~'^[0-9a-f]{64}$'
     OR (c->>'sequence')::bigint<1 OR jsonb_typeof(f->'records')<>'array'
     OR jsonb_array_length(f->'records')>2000 OR octet_length(f::text)>524288 THEN
    RAISE EXCEPTION 'quarantined owner restore denied' USING ERRCODE='42501';
  END IF;
  PERFORM pg_advisory_xact_lock(280204);
  SELECT * INTO prior FROM discovery.restore_checkpoint WHERE checkpoint_id=(c->>'checkpointId')::uuid;
  IF FOUND THEN
    IF prior.fragment_digest<>d OR prior.checkpoint_digest<>c->>'checkpointDigest'
       OR prior.sequence<>(c->>'sequence')::bigint THEN RAISE EXCEPTION 'checkpoint replay conflict'; END IF;
    RETURN prior.evidence_ref;
  END IF;
  SELECT * INTO last_row FROM discovery.restore_checkpoint ORDER BY sequence DESC LIMIT 1;
  IF FOUND AND ((c->>'sequence')::bigint<=last_row.sequence
      OR c->>'previousDigest' IS DISTINCT FROM last_row.checkpoint_digest) THEN
    RAISE EXCEPTION 'stale or unlinked checkpoint';
  END IF;
  FOR item IN SELECT value FROM jsonb_array_elements(f->'records') LOOP
    CASE item->>'kind'
    WHEN 'boundary' THEN
      INSERT INTO discovery.owner_admission(account_id,sequence)
        VALUES((item->>'accountId')::uuid,(item->>'sequence')::bigint)
        ON CONFLICT(account_id) DO UPDATE SET sequence=greatest(discovery.owner_admission.sequence,excluded.sequence);
    WHEN 'admission' THEN
      a:=jsonb_populate_record(NULL::discovery.admission,item->'row');
      IF EXISTS(SELECT 1 FROM discovery.admission WHERE execution_id=a.execution_id AND
          ROW(account_id,sequence,authority_revision,query_hash) IS DISTINCT FROM
          ROW(a.account_id,a.sequence,a.authority_revision,a.query_hash)) THEN
        RAISE EXCEPTION 'search admission identity conflict';
      END IF;
      INSERT INTO discovery.admission SELECT a.* ON CONFLICT DO NOTHING;
    WHEN 'execution' THEN
      -- A restored search never relays an old event into newly cleared history.
      UPDATE discovery.execution SET relay_state='suppressed' WHERE id=(item->>'id')::uuid
        AND account_id=(item->>'accountId')::uuid;
    ELSE RAISE EXCEPTION 'unknown discovery checkpoint record';
    END CASE;
  END LOOP;
  -- Current absence is a complete owner export, so removed private queries stay removed.
  DELETE FROM discovery.execution e WHERE NOT EXISTS(SELECT 1 FROM jsonb_array_elements(f->'records') x
      WHERE x->>'kind'='execution' AND (x->>'id')::uuid=e.id);
  INSERT INTO discovery.restore_checkpoint VALUES((c->>'checkpointId')::uuid,(c->>'sequence')::bigint,c->>'checkpointDigest',d,evidence);
  RETURN evidence;
END $$;
REVOKE ALL ON FUNCTION discovery.reconcile_restore(jsonb,jsonb,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION discovery.reconcile_restore(jsonb,jsonb,text) TO docsuri_discovery;
