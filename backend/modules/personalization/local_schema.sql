CREATE TABLE personalization.settings (
    account_id uuid PRIMARY KEY, revision uuid NOT NULL DEFAULT gen_random_uuid(),
    appearance text NOT NULL DEFAULT 'system' CHECK (appearance IN ('light','dark','system')),
    language text NOT NULL DEFAULT 'ko', defaults jsonb NOT NULL DEFAULT '{}',
    onboarding jsonb NOT NULL DEFAULT '{}', input_boundary bigint NOT NULL DEFAULT 0
);
CREATE TABLE personalization.behavior (
    account_id uuid NOT NULL, id uuid NOT NULL, purpose_revision uuid NOT NULL,
    fact jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (account_id, id)
);
