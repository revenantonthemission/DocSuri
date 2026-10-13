ALTER TABLE library.saved_paper ADD COLUMN eligibility_revision uuid, ADD COLUMN saved_title text;
ALTER TABLE library.history_boundary ADD COLUMN admission_cutoff bigint NOT NULL DEFAULT 0 CHECK(admission_cutoff>=0);
ALTER TABLE library.history ADD COLUMN admission_sequence bigint, ADD COLUMN completion_sequence bigint;
