-- Target-side effect ledger. An effect and its ledger row are written in ONE target
-- transaction, so a committed ledger row is proof the effect committed with it.
-- This is the target plane, deliberately separate from the r1_control control plane:
-- control records intent, the target records what actually happened.
CREATE SCHEMA IF NOT EXISTS r1_target;
REVOKE ALL ON SCHEMA r1_target FROM PUBLIC;

-- The exact native state a compare-and-set effect moves between. The executor refuses
-- unless the current digest equals expected_before, so an effect can never be applied twice.
CREATE TABLE IF NOT EXISTS r1_target.state (
    target_id text NOT NULL,
    namespace text NOT NULL,
    incarnation text NOT NULL,
    digest text NOT NULL,
    PRIMARY KEY (target_id, namespace, incarnation)
);

-- Append-only. One row per attempt per step, bound to the fence epoch that authorized it.
CREATE TABLE IF NOT EXISTS r1_target.effect_ledger (
    run_id text NOT NULL,
    step text NOT NULL,
    attempt_id text NOT NULL,
    definition_digest text NOT NULL,
    expected_before text NOT NULL,
    expected_after text NOT NULL,
    fence_epoch bigint NOT NULL CHECK (fence_epoch > 0),
    actor_role text NOT NULL,
    authorization_revision bigint NOT NULL CHECK (authorization_revision >= 0),
    applied_at timestamptz NOT NULL,
    digest text NOT NULL,
    PRIMARY KEY (run_id, step, attempt_id)
);

-- Defense in depth behind the session lock: even if two writers somehow reach the effect in
-- the same fence epoch, the database refuses the second one.
CREATE UNIQUE INDEX IF NOT EXISTS effect_ledger_one_per_fence
    ON r1_target.effect_ledger (run_id, step, fence_epoch);

-- Reconciliation reads by binding; keep it a pure index scan.
CREATE INDEX IF NOT EXISTS effect_ledger_by_step
    ON r1_target.effect_ledger (run_id, step, applied_at DESC);
