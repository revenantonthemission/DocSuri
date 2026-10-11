CREATE TABLE library.saved_paper (
    account_id uuid NOT NULL, paper_id text NOT NULL, version_id text NOT NULL,
    revision uuid NOT NULL DEFAULT gen_random_uuid(), saved_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (account_id, paper_id)
);
CREATE TABLE library.saved_query (
    account_id uuid NOT NULL, id uuid NOT NULL, query jsonb NOT NULL,
    revision uuid NOT NULL DEFAULT gen_random_uuid(), saved_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (account_id, id)
);
CREATE TABLE library.history_boundary (
    account_id uuid PRIMARY KEY, generation bigint NOT NULL DEFAULT 0 CHECK (generation >= 0),
    revision uuid NOT NULL DEFAULT gen_random_uuid(),
    eligible_after timestamptz NOT NULL DEFAULT '-infinity'
);
CREATE TABLE library.history (
    account_id uuid NOT NULL, execution_id uuid NOT NULL, query jsonb NOT NULL,
    captured_generation bigint NOT NULL CHECK (captured_generation >= 0),
    completed_at timestamptz NOT NULL, PRIMARY KEY (account_id, execution_id)
);
