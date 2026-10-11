CREATE FUNCTION corpus.guard_paper_reference(p_paper text,p_version text)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
    PERFORM corpus.guard_version(p_version,'local-research');
    IF NOT EXISTS(SELECT 1 FROM corpus.version WHERE id=p_version AND paper_id=p_paper) THEN
      RAISE EXCEPTION 'source reference mismatch' USING ERRCODE='42501';
    END IF;
END $$;
REVOKE ALL ON FUNCTION corpus.guard_paper_reference(text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION corpus.guard_paper_reference(text,text) TO docsuri_library;
