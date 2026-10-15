CREATE TABLE assistance.lifecycle_evidence (
  request_id uuid NOT NULL, scope text NOT NULL, generation bigint NOT NULL,
  policy_ref jsonb NOT NULL, manifest_revision text NOT NULL, evidence_ref uuid NOT NULL,
  PRIMARY KEY(request_id,scope)
);
CREATE TABLE assistance.erased_admission (
  operation_id uuid PRIMARY KEY, account_id uuid NOT NULL, intent_hash text NOT NULL,
  generation bigint NOT NULL, disposition text NOT NULL, erased_by uuid NOT NULL
);
GRANT SELECT,INSERT,UPDATE ON assistance.lifecycle_evidence TO docsuri_assistance;
GRANT SELECT ON assistance.erased_admission TO docsuri_assistance;
CREATE FUNCTION assistance.erase_private_controls(p_request uuid,p_account uuid,p_generation bigint,p_policy jsonb,p_manifest text)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
  IF accounts.lifecycle_effect_action(p_request,p_account,'PaperAssistance','live_records',p_generation,p_policy,p_manifest)<>'erase' THEN
    RAISE EXCEPTION 'erasure action required' USING ERRCODE='42501';
  END IF;
  IF EXISTS(SELECT 1 FROM assistance.job WHERE account_id=p_account AND (state NOT IN ('succeeded','failed') OR settlement_pending))
      OR EXISTS(SELECT 1 FROM assistance.admission WHERE account_id=p_account AND disposition='open') THEN
    RAISE EXCEPTION 'durable responsibility remains' USING ERRCODE='42501';
  END IF;
  IF NOT accounts.lifecycle_scope_complete(p_request,p_account,'PaperAssistance','live_records',p_generation,p_policy,p_manifest,'derived_artifacts') THEN
    RAISE EXCEPTION 'private result cleanup required' USING ERRCODE='42501';
  END IF;
  INSERT INTO assistance.erased_admission SELECT operation_id,account_id,intent_hash,generation,disposition,p_request FROM assistance.admission WHERE account_id=p_account ON CONFLICT DO NOTHING;
  DELETE FROM assistance.event WHERE job_id IN (SELECT id FROM assistance.job WHERE account_id=p_account);
  DELETE FROM assistance.result WHERE account_id=p_account;
  DELETE FROM assistance.job WHERE account_id=p_account;
  DELETE FROM assistance.admission WHERE account_id=p_account;
  DELETE FROM assistance.glossary WHERE account_id=p_account;
END $$;
REVOKE ALL ON FUNCTION assistance.erase_private_controls(uuid,uuid,bigint,jsonb,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION assistance.erase_private_controls(uuid,uuid,bigint,jsonb,text) TO docsuri_assistance;
