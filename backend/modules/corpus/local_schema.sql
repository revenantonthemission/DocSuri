-- CorpusContent owns authoritative content and its derived projection.
CREATE TABLE corpus.paper (
    id text PRIMARY KEY CHECK (length(id) BETWEEN 1 AND 160),
    title text NOT NULL, authors jsonb NOT NULL, published_on date,
    metadata jsonb NOT NULL, withdrawn boolean NOT NULL DEFAULT false,
    revision uuid NOT NULL DEFAULT gen_random_uuid()
);
CREATE TABLE corpus.version (
    id text PRIMARY KEY, paper_id text NOT NULL REFERENCES corpus.paper(id),
    source_url text NOT NULL, source_hash text NOT NULL CHECK (source_hash ~ '^[0-9a-f]{64}$'),
    version_label text NOT NULL, private_path text NOT NULL,
    eligible boolean NOT NULL DEFAULT false, purpose text NOT NULL CHECK (purpose = 'local-research'),
    eligibility_revision uuid NOT NULL DEFAULT gen_random_uuid(),
    provenance jsonb NOT NULL, content jsonb NOT NULL,
    UNIQUE (paper_id, version_label)
);
CREATE TABLE corpus.projection (
    version_id text NOT NULL REFERENCES corpus.version(id), ordinal integer NOT NULL CHECK (ordinal >= 0),
    content_hash text NOT NULL, anchor text NOT NULL, section text NOT NULL, text_content text NOT NULL,
    embedding double precision[] CHECK (embedding IS NULL OR cardinality(embedding) = 1024),
    vector_policy text, lexical tsvector GENERATED ALWAYS AS
      (to_tsvector('simple', text_content)) STORED,
    PRIMARY KEY (version_id, ordinal)
);
CREATE INDEX projection_lexical ON corpus.projection USING gin(lexical);
CREATE FUNCTION corpus.guard_version(p_version text, p_purpose text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE p corpus.paper%ROWTYPE; v corpus.version%ROWTYPE; paper_key text;
BEGIN
    IF p_purpose IS DISTINCT FROM 'local-research' THEN
        RAISE EXCEPTION 'source purpose denied' USING ERRCODE = '42501';
    END IF;
    SELECT paper_id INTO paper_key FROM corpus.version WHERE id = p_version;
    IF NOT FOUND THEN RAISE EXCEPTION 'source denied' USING ERRCODE = '42501'; END IF;
    SELECT * INTO p FROM corpus.paper WHERE id = paper_key FOR SHARE;
    IF NOT FOUND OR p.withdrawn THEN
        RAISE EXCEPTION 'paper denied' USING ERRCODE = '42501';
    END IF;
    SELECT * INTO v FROM corpus.version WHERE id = p_version FOR SHARE;
    IF NOT FOUND OR NOT v.eligible OR v.purpose <> p_purpose THEN
        RAISE EXCEPTION 'version denied' USING ERRCODE = '42501';
    END IF;
    RETURN v.eligibility_revision;
END $$;
REVOKE ALL ON FUNCTION corpus.guard_version(text,text) FROM PUBLIC;
