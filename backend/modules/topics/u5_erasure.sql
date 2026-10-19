CREATE FUNCTION topics.erase_private_controls(p_request uuid,p_account uuid,p_generation bigint,p_policy jsonb,p_manifest text)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
  IF accounts.lifecycle_effect_action(p_request,p_account,'TopicsDigests','live_records',p_generation,p_policy,p_manifest)<>'erase' THEN
    RAISE EXCEPTION 'erasure action required' USING ERRCODE='42501';
  END IF;
  DELETE FROM topics.followed_topic WHERE account_id=p_account;
END $$;
REVOKE ALL ON FUNCTION topics.erase_private_controls(uuid,uuid,bigint,jsonb,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION topics.erase_private_controls(uuid,uuid,bigint,jsonb,text) TO docsuri_topics;
