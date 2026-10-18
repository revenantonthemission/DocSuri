-- TopicsDigests selects digest content from eligible corpus versions only; it
-- holds no content bytes and never writes corpus records. Every candidate is
-- re-checked through corpus.guard_version at selection time.
GRANT USAGE ON SCHEMA corpus TO docsuri_topics;
GRANT EXECUTE ON FUNCTION corpus.guard_version(text,text) TO docsuri_topics;
GRANT SELECT ON corpus.paper,corpus.version TO docsuri_topics;
