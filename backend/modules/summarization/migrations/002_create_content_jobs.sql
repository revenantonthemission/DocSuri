-- U7 Summarization — schema migration 002 (PostgreSQL, inherited RDS instance).
-- The durable content-job contract (REM-2 / plan items 20-26).
--
-- Why this table exists at all: before it, POST /api/summarize handed work to SQS, answered
-- "pending", and returned nothing the caller could look up again. Acceptance was a claim rather
-- than a receipt (RJ-AC01), a retry was a second billable job (RJ-AC06), history was invisible
-- (RJ-AC04), and holding a job id was treated as authorization (RJ-AC05).
--
-- Three tables, one per promise:
--   content_jobs              the durable receipt: what exists, whose it is, where it got to
--   content_job_events        append-only history, resumable per job by seq (RJ-AC02/RJ-AC04)
--   content_job_effect_ledger one externally observable effect per attempt (ND-Q8)

CREATE TABLE IF NOT EXISTS content_jobs (
    job_id           VARCHAR(64)  PRIMARY KEY,
    owner_id         VARCHAR(36)  NOT NULL,
    task_type        VARCHAR(32)  NOT NULL,
    input            JSONB        NOT NULL DEFAULT '{}'::jsonb,
    state            VARCHAR(16)  NOT NULL,
    -- Set only for accepted work. The partial unique index below makes "one key, one job" a
    -- database fact rather than a read-then-write in application code, so two concurrent retries
    -- cannot both insert (RJ-AC06). NULL keys are unconstrained: a caller who supplies no key has
    -- said nothing about intent, and collapsing two deliberate identical submissions would drop
    -- a re-run the user asked for.
    idempotency_key  VARCHAR(128),
    result_ref       TEXT,
    -- The delivery window is stamped when the work finishes, not read from config at delivery
    -- time, so an expiry cannot drift when config changes (RJ-AC07).
    result_expires_at TIMESTAMPTZ,
    attempt          INTEGER      NOT NULL DEFAULT 1,
    -- This job's own event counter. The sequence lives on the job row, not derived from the
    -- events table, so the number that assigns seq is assigned by the same UPDATE that changes the
    -- state -- two concurrent writers cannot both read the same seq.
    seq              INTEGER      NOT NULL DEFAULT 0,
    -- Machine-readable code plus the caller-safe message. Internal detail never lands here
    -- (SEC-15); the worker maps its own failure onto this pair before writing.
    error            JSONB,
    -- An abstention is a real domain answer ("we chose not to"), kept distinct from both success
    -- and failure so it can never be laundered into an empty result (RJ-AC03).
    abstain_reason   TEXT,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT ck_content_jobs_state CHECK (
        state IN ('SUBMITTED', 'ACCEPTED', 'QUEUED', 'RUNNING',
                  'COMPLETED', 'FAILED', 'ABSTAINED')
    ),
    CONSTRAINT ck_content_jobs_terminal_result CHECK (
        -- A non-success state must not carry a result, or a stale ref could be delivered after a
        -- failure or an abstention.
        (state = 'COMPLETED') OR result_ref IS NULL
    )
);

-- One accepted submission per (owner, key). Scoped to the owner: a shared key space would either
-- hand one caller's job to another or silently merge two different callers' work (SEC-8).
CREATE UNIQUE INDEX IF NOT EXISTS ux_content_jobs_owner_idempotency
    ON content_jobs (owner_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

-- Owner-scoped reads (every job query filters on owner_id, SEC-8) and purge.
CREATE INDEX IF NOT EXISTS ix_content_jobs_owner_created
    ON content_jobs (owner_id, created_at DESC);

-- Recovery sweep for work that was accepted durably and then lost before dispatch (a crash in the
-- gap between accept and enqueue, or an enqueue that never landed). Without this index the
-- readiness/recovery pass would have to scan the whole table.
CREATE INDEX IF NOT EXISTS ix_content_jobs_pending
    ON content_jobs (state, updated_at)
    WHERE state IN ('SUBMITTED', 'ACCEPTED', 'QUEUED');

CREATE TABLE IF NOT EXISTS content_job_events (
    event_id   BIGSERIAL    PRIMARY KEY,
    job_id     VARCHAR(64)  NOT NULL REFERENCES content_jobs (job_id) ON DELETE CASCADE,
    owner_id   VARCHAR(36)  NOT NULL,
    -- Per-job, gapless, starting at 1. This is the client's resume point: reconnecting with the
    -- last seq it saw replays exactly the gap, so a dropped stream neither repeats the whole log
    -- nor silently skips the states in between (RJ-AC02/RJ-AC04).
    seq        INTEGER      NOT NULL,
    state      VARCHAR(16)  NOT NULL,
    payload    JSONB        NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT ux_content_job_events_seq UNIQUE (job_id, seq)
);

-- Replay order for one job; also the SSE read path.
CREATE INDEX IF NOT EXISTS ix_content_job_events_job_seq
    ON content_job_events (job_id, seq);

-- Owner purge: deleting jobs cascades to their events, so no history outlives the account (G3).
CREATE INDEX IF NOT EXISTS ix_content_job_events_owner
    ON content_job_events (owner_id);

CREATE TABLE IF NOT EXISTS content_job_effect_ledger (
    job_id     VARCHAR(64) NOT NULL REFERENCES content_jobs (job_id) ON DELETE CASCADE,
    attempt    INTEGER     NOT NULL,
    -- Which effect the budget was spent on. Recorded for audit; it is deliberately NOT part of the
    -- key. The key is (job_id, attempt) so one attempt buys one externally observable effect, and
    -- a redelivery relabelled with a different effect name still cannot buy a second one (ND-Q8).
    effect     VARCHAR(64) NOT NULL,
    claimed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT pk_content_job_effect_ledger PRIMARY KEY (job_id, attempt)
);