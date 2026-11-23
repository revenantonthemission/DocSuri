-- U8 (A2, O6, BR2.3): ResearchWorkspace's additive migration for the complete
-- application, applied after U4's files in U8's composed chain.

-- The owner job list (A2) reads newest first on its own index, never the whole table.
CREATE INDEX job_owner_list ON research.job (owner_id, accepted_at DESC, id);

-- Origin request identifiers (O6, NFR9.11): nullable, null for every existing row.
ALTER TABLE research.job ADD COLUMN origin_request_id uuid;

-- ResearchWorkspace's lifecycle evidence (BR2.3), in the shape the other owners use:
-- one row per request and scope, written once by the participant.
CREATE TABLE research.lifecycle_evidence (
    request_id uuid NOT NULL, scope text NOT NULL, generation bigint NOT NULL,
    policy_ref jsonb NOT NULL, manifest_revision text NOT NULL, evidence_ref uuid NOT NULL,
    PRIMARY KEY (request_id, scope)
);
GRANT SELECT,INSERT,UPDATE ON research.lifecycle_evidence TO docsuri_research;
