-- A publication barrier serializes corpus allocation and snapshot changes.
CREATE TABLE corpus.publication (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    generation_id uuid NOT NULL DEFAULT gen_random_uuid(),
    revision uuid NOT NULL DEFAULT gen_random_uuid(),
    manifest_hash text NOT NULL CHECK (manifest_hash ~ '^[0-9a-f]{64}$'),
    published_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
INSERT INTO corpus.publication(singleton,manifest_hash)
SELECT true,encode(sha256(convert_to(COALESCE(jsonb_agg(snapshot ORDER BY id),
    '[]'::jsonb)::text,'UTF8')),'hex') FROM (
    SELECT v.id,v.source_hash,v.eligibility_revision,v.eligible,p.withdrawn,
           count(c.ordinal) AS chunks
    FROM corpus.version v JOIN corpus.paper p ON p.id=v.paper_id
    LEFT JOIN corpus.projection c ON c.version_id=v.id
    GROUP BY v.id,p.withdrawn
) snapshot;
GRANT SELECT,UPDATE ON corpus.publication TO docsuri_corpus;
GRANT SELECT ON corpus.publication TO docsuri_discovery;
CREATE FUNCTION corpus.guard_publication()
RETURNS corpus.publication LANGUAGE sql SECURITY DEFINER
SET search_path = pg_catalog AS $$
    SELECT * FROM corpus.publication WHERE singleton FOR SHARE;
$$;
REVOKE ALL ON FUNCTION corpus.guard_publication() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION corpus.guard_publication() TO docsuri_discovery;
