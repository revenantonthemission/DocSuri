-- U8 (NFR9.2, Build and Test loop-back 1, Step 47(c)): ServiceOperations' count of the
-- observations a producer's full buffer dropped before this record was admitted. The
-- table's grants (SELECT, INSERT to docsuri_operations, u8_operations.sql) cover it.
ALTER TABLE operations.observation_record
    ADD COLUMN dropped_count integer NOT NULL DEFAULT 0 CHECK (dropped_count >= 0);
