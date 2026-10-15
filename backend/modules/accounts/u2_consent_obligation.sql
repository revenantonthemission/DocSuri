CREATE TABLE accounts.consent_obligation (
  id uuid PRIMARY KEY, account_id uuid NOT NULL REFERENCES accounts.account(id),
  purpose text NOT NULL CHECK(purpose IN ('personalization','local-research')),
  consent_revision uuid NOT NULL, authority_revision uuid NOT NULL,
  granted boolean NOT NULL, accepted_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  disposition text NOT NULL DEFAULT 'pending' CHECK(disposition IN ('pending','complete')),
  evidence_ref uuid,
  CHECK(disposition<>'complete' OR evidence_ref IS NOT NULL)
);
GRANT SELECT,INSERT,UPDATE ON accounts.consent_obligation TO docsuri_accounts;
