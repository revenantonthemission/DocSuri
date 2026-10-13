-- Metadata-only identity for owner-authorized saved references; no content bytes.
CREATE FUNCTION corpus.reference_metadata(p_version text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE v corpus.version%ROWTYPE; p corpus.paper%ROWTYPE; paper_key text; disposition text;
BEGIN
    SELECT paper_id INTO paper_key FROM corpus.version WHERE id=p_version;
    IF NOT FOUND THEN RETURN NULL; END IF;
    SELECT * INTO p FROM corpus.paper WHERE id=paper_key FOR SHARE;
    IF NOT FOUND THEN RETURN NULL; END IF;
    SELECT * INTO v FROM corpus.version WHERE id=p_version FOR SHARE;
    IF NOT FOUND OR v.paper_id IS DISTINCT FROM paper_key THEN RETURN NULL; END IF;
    IF p.withdrawn OR NOT v.eligible THEN disposition := 'withdrawn';
    ELSIF v.purpose <> 'local-research' THEN disposition := 'unavailable';
    ELSE disposition := 'available'; END IF;
    RETURN jsonb_build_object(
        'paperId',p.id,'versionId',v.id,'title',p.title,'authors',p.authors,
        'publishedOn',p.published_on,'sourceUrl',v.source_url,
        'eligibilityRevision',v.eligibility_revision,'disposition',disposition);
END $$;
REVOKE ALL ON FUNCTION corpus.reference_metadata(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION corpus.reference_metadata(text)
    TO docsuri_library,docsuri_assistance;
