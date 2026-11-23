-- U8 (P1, NFR8.4): CorpusContent's search migration for the complete application.
-- The existing projection.embedding array, the per-chunk lexical column and their
-- indexes stay, so U3-U6 keep working unchanged (C2). pgvector lives in schema public
-- (D14), installed by the superuser into template1 and the realm database.

-- By meaning: a pgvector column beside the array, backfilled now and kept equal to it
-- by a row trigger whenever a chunk is written, with an HNSW index for cosine distance.
ALTER TABLE corpus.projection ADD COLUMN embedding_vector public.vector(1024);
UPDATE corpus.projection SET embedding_vector = embedding::public.vector(1024)
 WHERE embedding IS NOT NULL;

CREATE FUNCTION corpus.projection_embedding_vector() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
  NEW.embedding_vector := CASE WHEN NEW.embedding IS NULL THEN NULL
                               ELSE NEW.embedding::public.vector(1024) END;
  RETURN NEW;
END $$;
CREATE TRIGGER projection_embedding_vector
  BEFORE INSERT OR UPDATE OF embedding ON corpus.projection
  FOR EACH ROW EXECUTE FUNCTION corpus.projection_embedding_vector();

CREATE INDEX projection_embedding_hnsw ON corpus.projection
  USING hnsw (embedding_vector public.vector_cosine_ops) WITH (m = 16, ef_construction = 64);

-- By words: one tsvector per paper version over all its chunks, so a term spread
-- across two chunks of one version matches; written with the chunks by a statement
-- trigger, backfilled now, with a GIN index. tsvector holds at most 1 MB: a version
-- whose positional vector would pass it keeps its distinct lexemes without positions.
ALTER TABLE corpus.version ADD COLUMN lexical_all tsvector;

CREATE FUNCTION corpus.refresh_lexical_all(p_versions text[]) RETURNS void
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
DECLARE v text; combined text;
BEGIN
  FOREACH v IN ARRAY coalesce(p_versions, ARRAY[]::text[]) LOOP
    SELECT string_agg(text_content, ' ' ORDER BY ordinal) INTO combined
      FROM corpus.projection WHERE version_id = v;
    BEGIN
      UPDATE corpus.version SET lexical_all = to_tsvector('simple', combined) WHERE id = v;
    EXCEPTION WHEN program_limit_exceeded THEN
      UPDATE corpus.version
         SET lexical_all = array_to_tsvector(ARRAY(
               SELECT DISTINCT lexeme FROM corpus.projection p,
                      unnest(tsvector_to_array(p.lexical)) AS lexeme
                WHERE p.version_id = v))
       WHERE id = v;
    END;
  END LOOP;
END $$;

CREATE FUNCTION corpus.projection_lexical_all() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
  PERFORM corpus.refresh_lexical_all(ARRAY(SELECT DISTINCT version_id FROM changed));
  RETURN NULL;
END $$;
CREATE TRIGGER projection_lexical_all_insert AFTER INSERT ON corpus.projection
  REFERENCING NEW TABLE AS changed FOR EACH STATEMENT EXECUTE FUNCTION corpus.projection_lexical_all();
CREATE TRIGGER projection_lexical_all_update AFTER UPDATE ON corpus.projection
  REFERENCING NEW TABLE AS changed FOR EACH STATEMENT EXECUTE FUNCTION corpus.projection_lexical_all();
CREATE TRIGGER projection_lexical_all_delete AFTER DELETE ON corpus.projection
  REFERENCING OLD TABLE AS changed FOR EACH STATEMENT EXECUTE FUNCTION corpus.projection_lexical_all();

SELECT corpus.refresh_lexical_all(ARRAY(SELECT DISTINCT version_id FROM corpus.projection));

CREATE INDEX version_lexical_all ON corpus.version USING gin (lexical_all);

-- The trigger functions run as the writing login, so it may call the refresh.
REVOKE ALL ON FUNCTION corpus.refresh_lexical_all(text[]) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION corpus.refresh_lexical_all(text[]) TO docsuri_corpus;
GRANT EXECUTE ON FUNCTION corpus.projection_embedding_vector(),corpus.projection_lexical_all()
  TO docsuri_corpus;
