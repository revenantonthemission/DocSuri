-- Closed admission is a durable, session-independent usage-release obligation.
ALTER TABLE research.admission ADD COLUMN release_reconciled boolean NOT NULL DEFAULT false;
ALTER TABLE research.admission ADD CONSTRAINT release_requires_closure
    CHECK (NOT release_reconciled OR state='closed');
CREATE INDEX research_pending_release ON research.admission(operation_id)
    WHERE state='closed' AND NOT release_reconciled;
