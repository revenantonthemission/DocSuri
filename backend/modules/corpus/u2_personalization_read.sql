-- Public source disposition only. No content, storage paths or metadata escape.
CREATE FUNCTION corpus.personalization_source(p_paper text,p_version text)
RETURNS TABLE(eligibility_revision uuid,disposition text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE p corpus.paper%ROWTYPE; v corpus.version%ROWTYPE;
BEGIN
  SELECT * INTO p FROM corpus.paper WHERE id=p_paper FOR SHARE;
  IF NOT FOUND THEN RETURN QUERY SELECT NULL::uuid,'unavailable'::text; RETURN; END IF;
  SELECT * INTO v FROM corpus.version WHERE id=p_version AND paper_id=p_paper FOR SHARE;
  IF NOT FOUND THEN RETURN QUERY SELECT NULL::uuid,'unavailable'::text; RETURN; END IF;
  RETURN QUERY SELECT v.eligibility_revision,
    CASE WHEN p.withdrawn THEN 'withdrawn' WHEN NOT v.eligible THEN 'restricted'
      WHEN v.purpose<>'local-research' THEN 'restricted' ELSE 'available' END;
END $$;
REVOKE ALL ON FUNCTION corpus.personalization_source(text,text) FROM PUBLIC;
GRANT USAGE ON SCHEMA corpus TO docsuri_personalization;
GRANT EXECUTE ON FUNCTION corpus.personalization_source(text,text) TO docsuri_personalization;
