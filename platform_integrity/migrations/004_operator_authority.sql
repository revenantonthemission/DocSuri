-- The database is the current source for explicitly provisioned operator grants.
-- Legacy rows are not backfilled with invented artifact/policy/validity evidence.
ALTER TABLE r1_control.authority
    ADD COLUMN artifact_digest text,
    ADD COLUMN policy_digest text,
    ADD COLUMN namespace text,
    ADD COLUMN valid_from timestamptz;
CREATE TABLE r1_control.target_identity (
    target_id text NOT NULL,
    namespace text NOT NULL,
    incarnation text NOT NULL,
    epoch numeric(20, 0) NOT NULL CHECK (epoch BETWEEN 1 AND 18446744073709551615),
    PRIMARY KEY (target_id, namespace)
);
REVOKE ALL ON r1_control.target_identity FROM PUBLIC;
