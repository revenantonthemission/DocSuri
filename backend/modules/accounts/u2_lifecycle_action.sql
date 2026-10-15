CREATE FUNCTION accounts.lifecycle_effect_action(p_request uuid,p_account uuid,p_participant text,p_scope text,
    p_generation bigint,p_policy jsonb,p_manifest text)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE action_value text;
BEGIN
  PERFORM accounts.guard_lifecycle_effect(p_request,p_account,p_participant,p_scope,p_generation,p_policy,p_manifest);
  SELECT action INTO action_value FROM accounts.lifecycle_request WHERE id=p_request;
  RETURN action_value;
END $$;
REVOKE ALL ON FUNCTION accounts.lifecycle_effect_action(uuid,uuid,text,text,bigint,jsonb,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION accounts.lifecycle_effect_action(uuid,uuid,text,text,bigint,jsonb,text)
  TO docsuri_accounts,docsuri_library,docsuri_personalization,docsuri_usage,docsuri_assistance,docsuri_discovery,docsuri_operations;
