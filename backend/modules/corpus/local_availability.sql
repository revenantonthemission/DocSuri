-- Metadata-only disposition for already owner-authorized saved references.
-- This does not grant content access and never exposes corpus text or credentials.
CREATE FUNCTION corpus.reference_availability(p_version text)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE v corpus.version%ROWTYPE; p corpus.paper%ROWTYPE; paper_key text;
BEGIN
    SELECT paper_id INTO paper_key FROM corpus.version WHERE id=p_version;
    IF NOT FOUND THEN RETURN 'unavailable'; END IF;
    SELECT * INTO p FROM corpus.paper WHERE id=paper_key FOR SHARE;
    IF NOT FOUND THEN RETURN 'unavailable'; END IF;
    SELECT * INTO v FROM corpus.version WHERE id=p_version FOR SHARE;
    IF NOT FOUND OR v.paper_id IS DISTINCT FROM paper_key THEN RETURN 'unavailable'; END IF;
    IF p.withdrawn OR NOT v.eligible THEN RETURN 'withdrawn'; END IF;
    IF v.purpose <> 'local-research' THEN RETURN 'unavailable'; END IF;
    RETURN 'available';
END $$;
REVOKE ALL ON FUNCTION corpus.reference_availability(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION corpus.reference_availability(text)
    TO docsuri_library,docsuri_assistance;
