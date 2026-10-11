CREATE FUNCTION corpus.execution_eligibility(p_version text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE paper_key text; p corpus.paper%ROWTYPE; v corpus.version%ROWTYPE;
BEGIN
    SELECT paper_id INTO paper_key FROM corpus.version WHERE id=p_version;
    IF NOT FOUND THEN RETURN NULL; END IF;
    SELECT * INTO p FROM corpus.paper WHERE id=paper_key FOR SHARE;
    IF NOT FOUND OR p.withdrawn THEN RETURN NULL; END IF;
    SELECT * INTO v FROM corpus.version WHERE id=p_version FOR SHARE;
    IF NOT FOUND OR v.paper_id IS DISTINCT FROM paper_key OR NOT v.eligible
       OR v.purpose IS DISTINCT FROM 'local-research' THEN RETURN NULL; END IF;
    RETURN v.eligibility_revision;
END $$;
REVOKE ALL ON FUNCTION corpus.execution_eligibility(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION corpus.execution_eligibility(text) TO docsuri_assistance;

CREATE OR REPLACE FUNCTION corpus.guard_version(p_version text,p_purpose text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE revision uuid;
BEGIN
    IF p_purpose IS DISTINCT FROM 'local-research' THEN
        RAISE EXCEPTION 'source purpose denied' USING ERRCODE='42501';
    END IF;
    revision := corpus.execution_eligibility(p_version);
    IF revision IS NULL THEN
        RAISE EXCEPTION 'source denied' USING ERRCODE='42501';
    END IF;
    RETURN revision;
END $$;
