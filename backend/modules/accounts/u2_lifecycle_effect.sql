-- An owner can apply only its own live, current generation ticket. These locks
-- remain held through the caller owner's effect transaction and its evidence.
CREATE FUNCTION accounts.guard_lifecycle_effect(p_request uuid,p_account uuid,p_participant text,p_scope text,
    p_generation bigint,p_policy jsonb,p_manifest text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE a accounts.account%ROWTYPE; r accounts.lifecycle_request%ROWTYPE; s accounts.lifecycle_scope%ROWTYPE;
        expected_role text;
BEGIN
  expected_role:=CASE p_participant
    WHEN 'AccountAccess' THEN 'docsuri_accounts' WHEN 'Library' THEN 'docsuri_library'
    WHEN 'Personalization' THEN 'docsuri_personalization' WHEN 'UsageEntitlements' THEN 'docsuri_usage'
    WHEN 'PaperAssistance' THEN 'docsuri_assistance' WHEN 'DiscoveryCitations' THEN 'docsuri_discovery'
    WHEN 'ServiceOperations' THEN 'docsuri_operations' ELSE NULL END;
  IF expected_role IS NULL OR session_user<>expected_role THEN
    RAISE EXCEPTION 'lifecycle owner denied' USING ERRCODE='42501';
  END IF;
  SELECT * INTO a FROM accounts.account WHERE id=p_account FOR SHARE;
  SELECT * INTO r FROM accounts.lifecycle_request WHERE id=p_request AND account_id=p_account FOR SHARE;
  SELECT * INTO s FROM accounts.lifecycle_scope WHERE request_id=p_request AND participant=p_participant AND scope=p_scope FOR SHARE;
  IF a.id IS NULL OR r.id IS NULL OR s.request_id IS NULL OR a.lifecycle_revision<>r.revision
      OR r.policy_ref<>p_policy OR r.manifest_revision<>p_manifest OR s.generation<>p_generation
      OR s.lease_until IS NULL OR s.lease_until<=clock_timestamp() OR s.disposition='complete' THEN
    RAISE EXCEPTION 'lifecycle effect denied' USING ERRCODE='42501';
  END IF;
  RETURN r.revision;
END $$;
REVOKE ALL ON FUNCTION accounts.guard_lifecycle_effect(uuid,uuid,text,text,bigint,jsonb,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION accounts.guard_lifecycle_effect(uuid,uuid,text,text,bigint,jsonb,text)
  TO docsuri_accounts,docsuri_library,docsuri_personalization,docsuri_usage,docsuri_assistance,docsuri_discovery,docsuri_operations;
