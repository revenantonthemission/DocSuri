CREATE TABLE library.lifecycle_evidence (
  request_id uuid NOT NULL, scope text NOT NULL, generation bigint NOT NULL,
  policy_ref jsonb NOT NULL, manifest_revision text NOT NULL, evidence_ref uuid NOT NULL,
  PRIMARY KEY(request_id,scope)
);
CREATE TABLE library.restriction (
  account_id uuid PRIMARY KEY, lifecycle_revision uuid NOT NULL,
  disposition text NOT NULL CHECK(disposition IN ('withdrawn','erased','active')),
  updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
GRANT SELECT,INSERT,UPDATE ON library.lifecycle_evidence,library.restriction TO docsuri_library;
