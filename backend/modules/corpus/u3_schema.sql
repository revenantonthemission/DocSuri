-- U3 CorpusContent: processing runs, stage effects, watermarks, change facts,
-- projection batches, publication generations, opaque assets and quarantine.
-- Extends the U1 corpus owner in place; one writer (CorpusContent) per table.

CREATE TABLE corpus.run (
    id uuid PRIMARY KEY,
    operation text NOT NULL CHECK (operation IN ('ingest','incremental-refresh','rebuild','reprocess')),
    source_scope jsonb NOT NULL CHECK (jsonb_typeof(source_scope) = 'array'
        AND jsonb_array_length(source_scope) BETWEEN 1 AND 8),
    source_policy jsonb NOT NULL,
    compatibility_revision text NOT NULL CHECK (length(compatibility_revision) BETWEEN 1 AND 64),
    authoritative_input_revision text NOT NULL CHECK (length(authoritative_input_revision) BETWEEN 1 AND 160),
    input_manifest_hash text NOT NULL CHECK (input_manifest_hash ~ '^[0-9a-f]{64}$'),
    intent_hash text NOT NULL CHECK (intent_hash ~ '^[0-9a-f]{64}$'),
    idempotency_key uuid NOT NULL UNIQUE,
    state text NOT NULL DEFAULT 'accepted'
        CHECK (state IN ('accepted','running','completed','failed','unknown')),
    revision uuid NOT NULL DEFAULT gen_random_uuid(),
    watermark jsonb,
    retry_of uuid REFERENCES corpus.run(id),
    attempts integer NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 2),
    dispatch_pending boolean NOT NULL DEFAULT true,
    accepted_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    completed_at timestamptz
);
CREATE INDEX run_pending ON corpus.run(accepted_at, id)
    WHERE state IN ('accepted','running');

CREATE TABLE corpus.run_effect (
    run_id uuid NOT NULL REFERENCES corpus.run(id),
    stage text NOT NULL CHECK (stage IN ('source','control','content','projection','publication')),
    subject text NOT NULL CHECK (length(subject) BETWEEN 1 AND 160),
    state text NOT NULL CHECK (state IN ('pending','committed','failed','unknown')),
    evidence_hash text CHECK (evidence_hash IS NULL OR evidence_hash ~ '^[0-9a-f]{64}$'),
    error_code text CHECK (error_code IS NULL OR length(error_code) BETWEEN 1 AND 64),
    attempt integer NOT NULL DEFAULT 1 CHECK (attempt BETWEEN 1 AND 3),
    revision bigint NOT NULL DEFAULT 1 CHECK (revision > 0),
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (run_id, stage, subject)
);

CREATE TABLE corpus.change_sequence (
    singleton boolean PRIMARY KEY CHECK (singleton),
    fact_position bigint NOT NULL DEFAULT 0 CHECK (fact_position >= 0)
);
INSERT INTO corpus.change_sequence VALUES (true, 0);

CREATE TABLE corpus.change_fact (
    id uuid PRIMARY KEY,
    paper_id text NOT NULL REFERENCES corpus.paper(id),
    version_id text,
    change_kind text NOT NULL
        CHECK (change_kind IN ('withdrawal','license-change','access-change','canonicalization','version-change')),
    eligibility_revision uuid NOT NULL,
    fact_position bigint NOT NULL CHECK (fact_position > 0),
    detail jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (octet_length(detail::text) <= 4096),
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (paper_id, fact_position)
);
CREATE INDEX change_fact_order ON corpus.change_fact(fact_position, id);

CREATE TABLE corpus.projection_batch (
    id uuid PRIMARY KEY,
    generation_id uuid NOT NULL,
    batch_hash text NOT NULL CHECK (batch_hash ~ '^[0-9a-f]{64}$'),
    receipt jsonb NOT NULL CHECK (octet_length(receipt::text) <= 4096),
    claimed_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX batch_generation ON corpus.projection_batch(generation_id, id);

CREATE TABLE corpus.generation (
    id uuid PRIMARY KEY,
    manifest_hash text NOT NULL CHECK (manifest_hash ~ '^[0-9a-f]{64}$'),
    compatibility_revision text NOT NULL CHECK (length(compatibility_revision) BETWEEN 1 AND 64),
    state text NOT NULL DEFAULT 'building'
        CHECK (state IN ('building','verified','published','failed','quarantined')),
    publication_attempts integer NOT NULL DEFAULT 0 CHECK (publication_attempts BETWEEN 0 AND 8),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    verified_at timestamptz,
    published_at timestamptz
);
ALTER TABLE corpus.publication ADD COLUMN published_generation uuid;

CREATE TABLE corpus.quarantine (
    marker text PRIMARY KEY CHECK (length(marker) BETWEEN 1 AND 160),
    target text NOT NULL CHECK (length(target) BETWEEN 1 AND 160),
    detail jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (octet_length(detail::text) <= 4096),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    released_at timestamptz
);

CREATE TABLE corpus.asset (
    id uuid PRIMARY KEY,
    version_id text NOT NULL REFERENCES corpus.version(id),
    section_id text CHECK (section_id IS NULL OR length(section_id) BETWEEN 1 AND 160),
    media_type text NOT NULL CHECK (length(media_type) BETWEEN 1 AND 64),
    content_hash text NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
    storage text NOT NULL CHECK (storage IN ('private','unavailable')),
    byte_length integer CHECK (byte_length IS NULL OR byte_length BETWEEN 0 AND 8388608),
    alt_text text NOT NULL CHECK (length(alt_text) BETWEEN 1 AND 400),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (version_id, content_hash)
);

-- Explicit corpus-maintenance authority: account membership or a session
-- alone is insufficient. The owner role provisions actors; the runtime role
-- may read them and may provision only through the reviewed synthetic runner.
CREATE TABLE corpus.maintenance_actor (
    account_id uuid PRIMARY KEY,
    granted_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    revision uuid NOT NULL DEFAULT gen_random_uuid()
);

GRANT SELECT,INSERT,UPDATE ON corpus.run,corpus.run_effect TO docsuri_corpus;
GRANT SELECT,INSERT,UPDATE ON corpus.change_sequence,corpus.change_fact TO docsuri_corpus;
GRANT SELECT,INSERT,UPDATE ON corpus.projection_batch,corpus.generation TO docsuri_corpus;
GRANT SELECT,INSERT,UPDATE ON corpus.quarantine,corpus.asset TO docsuri_corpus;
GRANT SELECT ON corpus.run,corpus.run_effect,corpus.generation,corpus.asset TO docsuri_discovery;
GRANT SELECT ON corpus.change_fact,corpus.change_sequence TO docsuri_library;
GRANT SELECT ON corpus.asset,corpus.generation TO docsuri_assistance;
GRANT SELECT ON corpus.maintenance_actor TO docsuri_corpus;
