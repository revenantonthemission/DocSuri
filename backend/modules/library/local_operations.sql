CREATE FUNCTION library.save_paper(p_account uuid,p_session uuid,p_paper text,p_version text,p_key uuid,p_expected uuid)
RETURNS jsonb LANGUAGE plpgsql SET search_path = pg_catalog AS $$
DECLARE intent text; prior library.receipt%ROWTYPE; target library.saved_paper%ROWTYPE; outcome jsonb;
BEGIN
    PERFORM accounts.guard_session(p_account,p_session,'local-research');
    PERFORM corpus.guard_version(p_version,'local-research');
    intent := encode(sha256(convert_to(jsonb_build_array(p_paper,p_version,p_expected)::text,'UTF8')),'hex');
    SELECT * INTO prior FROM library.receipt WHERE account_id=p_account AND kind='save-paper' AND key=p_key;
    IF FOUND THEN
        IF prior.intent_hash <> intent THEN RAISE EXCEPTION 'changed intended operation' USING ERRCODE='23505'; END IF;
        RETURN prior.outcome;
    END IF;
    SELECT * INTO target FROM library.saved_paper WHERE account_id=p_account AND paper_id=p_paper FOR UPDATE;
    IF (FOUND AND (p_expected IS NULL OR target.revision <> p_expected)) OR (NOT FOUND AND p_expected IS NOT NULL) THEN
       RAISE EXCEPTION 'revision conflict' USING ERRCODE='40001';
    END IF;
    INSERT INTO library.saved_paper(account_id,paper_id,version_id) VALUES(p_account,p_paper,p_version)
      ON CONFLICT(account_id,paper_id) DO UPDATE SET version_id=excluded.version_id,revision=gen_random_uuid()
      RETURNING * INTO target;
    outcome := jsonb_build_object('paperId',target.paper_id,'paperVersionId',target.version_id,'revision',target.revision,'savedAt',target.saved_at);
    INSERT INTO library.receipt(account_id,kind,key,intent_hash,outcome) VALUES(p_account,'save-paper',p_key,intent,outcome);
    RETURN outcome;
END $$;

CREATE FUNCTION library.clear_history(p_account uuid,p_session uuid,p_key uuid,p_expected uuid)
RETURNS jsonb LANGUAGE plpgsql SET search_path = pg_catalog AS $$
DECLARE intent text; prior library.receipt%ROWTYPE; boundary library.history_boundary%ROWTYPE; outcome jsonb;
BEGIN
    PERFORM accounts.guard_session(p_account,p_session,'local-research');
    intent := encode(sha256(convert_to(jsonb_build_array(p_expected)::text,'UTF8')),'hex');
    SELECT * INTO prior FROM library.receipt WHERE account_id=p_account AND kind='clear-history' AND key=p_key;
    IF FOUND THEN
        IF prior.intent_hash <> intent THEN RAISE EXCEPTION 'changed intended operation' USING ERRCODE='23505'; END IF;
        RETURN prior.outcome;
    END IF;
    SELECT * INTO boundary FROM library.history_boundary WHERE account_id=p_account FOR UPDATE;
    IF NOT FOUND OR p_expected IS NULL OR boundary.revision <> p_expected THEN
        RAISE EXCEPTION 'history revision conflict' USING ERRCODE='40001';
    END IF;
    UPDATE library.history_boundary SET generation=generation+1,eligible_after=clock_timestamp(),revision=gen_random_uuid()
      WHERE account_id=p_account RETURNING * INTO boundary;
    DELETE FROM library.history WHERE account_id=p_account;
    outcome := jsonb_build_object('generation',boundary.generation,'revision',boundary.revision,'eligibleAfter',boundary.eligible_after);
    INSERT INTO library.receipt(account_id,kind,key,intent_hash,outcome) VALUES(p_account,'clear-history',p_key,intent,outcome);
    RETURN outcome;
END $$;

CREATE FUNCTION library.accept_history_fact(p_account uuid,p_session uuid,p_execution uuid,p_generation bigint,p_completed timestamptz,p_query jsonb)
RETURNS boolean LANGUAGE plpgsql SET search_path = pg_catalog AS $$
DECLARE boundary library.history_boundary%ROWTYPE;
BEGIN
    PERFORM accounts.guard_session(p_account,p_session,'local-research');
    SELECT * INTO boundary FROM library.history_boundary WHERE account_id=p_account FOR UPDATE;
    IF NOT FOUND OR p_generation <> boundary.generation OR p_completed <= boundary.eligible_after THEN RETURN false; END IF;
    INSERT INTO library.history(account_id,execution_id,query,captured_generation,completed_at)
      VALUES(p_account,p_execution,p_query,p_generation,p_completed)
      ON CONFLICT(account_id,execution_id) DO NOTHING;
    RETURN true;
END $$;
REVOKE ALL ON FUNCTION library.save_paper(uuid,uuid,text,text,uuid,uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION library.clear_history(uuid,uuid,uuid,uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION library.accept_history_fact(uuid,uuid,uuid,bigint,timestamptz,jsonb) FROM PUBLIC;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA library TO docsuri_library;
