-- U3 Discovery: snapshot-bound executions and bounded citation snapshots.
-- Search executions remain the single history-fact source; citations carry
-- provenance/freshness/coverage labels and never fabricate edges.

ALTER TABLE discovery.execution
    ADD COLUMN snapshot_revision uuid,
    ADD COLUMN degradation text NOT NULL DEFAULT 'none'
        CHECK (degradation IN ('none','semantic-unavailable','partial','provider-limited'));

CREATE TABLE discovery.citation_snapshot (
    id uuid PRIMARY KEY,
    root_version_id text NOT NULL CHECK (length(root_version_id) BETWEEN 1 AND 160),
    direction text NOT NULL CHECK (direction IN ('cited','citing','both')),
    depth integer NOT NULL CHECK (depth BETWEEN 0 AND 2),
    nodes jsonb NOT NULL CHECK (jsonb_typeof(nodes) = 'array' AND jsonb_array_length(nodes) <= 32),
    edges jsonb NOT NULL CHECK (jsonb_typeof(edges) = 'array' AND jsonb_array_length(edges) <= 64),
    provenance jsonb NOT NULL CHECK (octet_length(provenance::text) <= 4096),
    freshness text NOT NULL CHECK (freshness IN ('fresh','stale','unknown')),
    coverage text NOT NULL CHECK (coverage IN ('complete','partial','unavailable')),
    provider_revision text NOT NULL CHECK (length(provider_revision) BETWEEN 1 AND 64),
    account_id uuid,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX citation_snapshot_root
    ON discovery.citation_snapshot(root_version_id, created_at DESC);

-- Provider request accounting for the finite traversal envelope. One row per
-- account and provider window; exhaustion is an explicit bounded outcome.
CREATE TABLE discovery.provider_budget (
    account_id uuid NOT NULL,
    window_start timestamptz NOT NULL,
    requests integer NOT NULL DEFAULT 0 CHECK (requests BETWEEN 0 AND 64),
    PRIMARY KEY (account_id, window_start)
);

GRANT SELECT,INSERT,UPDATE ON discovery.citation_snapshot,discovery.provider_budget
    TO docsuri_discovery;
GRANT SELECT ON discovery.citation_snapshot TO docsuri_library;
