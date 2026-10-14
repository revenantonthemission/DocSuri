CREATE TABLE assistance.consent_evidence (
  obligation_id uuid PRIMARY KEY, account_id uuid NOT NULL,
  consent_revision uuid NOT NULL, authority_revision uuid NOT NULL,
  evidence_ref uuid NOT NULL, disposition text NOT NULL CHECK(disposition IN ('applied','superseded'))
);
GRANT SELECT,INSERT ON assistance.consent_evidence TO docsuri_assistance;
