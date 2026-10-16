-- Durable acceptance fence precedes quota reservation; closure prevents late acceptance.
CREATE TABLE research.admission (
    operation_id uuid PRIMARY KEY, owner_id uuid NOT NULL, operation_key text NOT NULL,
    input_hash text NOT NULL, state text NOT NULL DEFAULT 'prepared' CHECK(state IN ('prepared','accepted','closed')),
    UNIQUE(owner_id,operation_key)
);
GRANT SELECT,INSERT,UPDATE ON research.admission TO docsuri_research;
