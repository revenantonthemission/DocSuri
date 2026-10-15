CREATE TABLE accounts.lifecycle_evidence (
  request_id uuid NOT NULL, scope text NOT NULL, generation bigint NOT NULL,
  policy_ref jsonb NOT NULL, manifest_revision text NOT NULL, evidence_ref uuid NOT NULL,
  PRIMARY KEY(request_id,scope)
);
GRANT SELECT,INSERT,UPDATE ON accounts.lifecycle_evidence TO docsuri_accounts;
CREATE FUNCTION accounts.erase_private_controls(p_request uuid,p_account uuid,p_generation bigint,p_policy jsonb,p_manifest text)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
  IF accounts.lifecycle_effect_action(p_request,p_account,'AccountAccess','live_records',p_generation,p_policy,p_manifest)<>'erase' THEN
    RAISE EXCEPTION 'erasure action required' USING ERRCODE='42501';
  END IF;
  IF NOT EXISTS(SELECT 1 FROM accounts.lifecycle_scope WHERE request_id=p_request AND participant='AccountAccess' AND scope='derived_artifacts' AND disposition='complete') THEN
    RAISE EXCEPTION 'private mail cleanup required' USING ERRCODE='42501';
  END IF;
  DELETE FROM accounts.delivery WHERE challenge_id IN (SELECT id FROM accounts.challenge WHERE account_id=p_account);
  DELETE FROM accounts.challenge WHERE account_id=p_account;
  DELETE FROM accounts.identity_link WHERE account_id=p_account;
  DELETE FROM accounts.identity_flow WHERE account_id=p_account;
  DELETE FROM accounts.mfa_recovery WHERE enrollment_id IN (SELECT id FROM accounts.mfa_enrollment WHERE account_id=p_account);
  DELETE FROM accounts.mfa_enrollment WHERE account_id=p_account;
  DELETE FROM accounts.control_proof WHERE account_id=p_account AND purpose<>'reauthenticate';
  DELETE FROM accounts.control_receipt WHERE account_id=p_account AND kind NOT IN ('lifecycle','lifecycle-confirm','reactivate');
  UPDATE accounts.account SET email='erased-'||id::text||'@erased.invalid',password_hash='!erased',
    display_name='삭제된 계정',profile='{}',profile_revision=gen_random_uuid() WHERE id=p_account;
END $$;
REVOKE ALL ON FUNCTION accounts.erase_private_controls(uuid,uuid,bigint,jsonb,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION accounts.erase_private_controls(uuid,uuid,bigint,jsonb,text) TO docsuri_accounts;
GRANT USAGE ON SCHEMA accounts TO docsuri_usage_owner,docsuri_discovery_owner,docsuri_assistance_owner;
GRANT EXECUTE ON FUNCTION accounts.lifecycle_effect_action(uuid,uuid,text,text,bigint,jsonb,text)
  TO docsuri_usage_owner,docsuri_discovery_owner,docsuri_assistance_owner;
CREATE FUNCTION accounts.lifecycle_scope_complete(p_request uuid,p_account uuid,p_participant text,p_scope text,p_generation bigint,p_policy jsonb,p_manifest text,p_required text)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
  PERFORM accounts.guard_lifecycle_effect(p_request,p_account,p_participant,p_scope,p_generation,p_policy,p_manifest);
  RETURN EXISTS(SELECT 1 FROM accounts.lifecycle_scope WHERE request_id=p_request AND participant=p_participant AND scope=p_required AND disposition='complete');
END $$;
REVOKE ALL ON FUNCTION accounts.lifecycle_scope_complete(uuid,uuid,text,text,bigint,jsonb,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION accounts.lifecycle_scope_complete(uuid,uuid,text,text,bigint,jsonb,text,text) TO docsuri_assistance_owner;
