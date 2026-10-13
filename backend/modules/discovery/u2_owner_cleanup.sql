CREATE TABLE discovery.lifecycle_evidence (
  request_id uuid NOT NULL, scope text NOT NULL, generation bigint NOT NULL,
  policy_ref jsonb NOT NULL, manifest_revision text NOT NULL, evidence_ref uuid NOT NULL,
  PRIMARY KEY(request_id,scope)
);
GRANT SELECT,INSERT,UPDATE ON discovery.lifecycle_evidence TO docsuri_discovery;
CREATE FUNCTION discovery.erase_private_controls(p_request uuid,p_account uuid,p_generation bigint,p_policy jsonb,p_manifest text)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
  IF accounts.lifecycle_effect_action(p_request,p_account,'DiscoveryCitations','live_records',p_generation,p_policy,p_manifest)<>'erase' THEN
    RAISE EXCEPTION 'erasure action required' USING ERRCODE='42501';
  END IF;
  DELETE FROM discovery.execution WHERE account_id=p_account;
END $$;
REVOKE ALL ON FUNCTION discovery.erase_private_controls(uuid,uuid,bigint,jsonb,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION discovery.erase_private_controls(uuid,uuid,bigint,jsonb,text) TO docsuri_discovery;
