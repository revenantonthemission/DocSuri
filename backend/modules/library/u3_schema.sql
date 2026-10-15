-- U3 Library: explicit saved-reference dispositions driven by corpus source-
-- change facts. U3 never writes Library records; this owner consumes the
-- ordered, replayable facts and records its own disposition per reference.
ALTER TABLE library.saved_paper
    ADD COLUMN disposition text NOT NULL DEFAULT 'active'
        CHECK (disposition IN ('active','unavailable','canonicalized','version-superseded')),
    ADD COLUMN disposition_revision uuid,
    ADD COLUMN disposition_position bigint;

CREATE TABLE library.disposition_cursor (
    singleton boolean PRIMARY KEY CHECK (singleton),
    position bigint NOT NULL DEFAULT 0 CHECK (position >= 0),
    revision uuid NOT NULL DEFAULT gen_random_uuid()
);
INSERT INTO library.disposition_cursor VALUES (true, 0);

GRANT SELECT,INSERT,UPDATE ON library.disposition_cursor TO docsuri_library;
GRANT UPDATE(disposition,disposition_revision,disposition_position)
    ON library.saved_paper TO docsuri_library;
