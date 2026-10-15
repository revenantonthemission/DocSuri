-- The runner grants CONNECT only on the live U2 database to the non-login Ops
-- schema owner. PostgreSQL requires this for pg_database_size inside the
-- aggregate SECURITY DEFINER function; runtime roles gain no new privileges.
SELECT pg_database_size(current_database());
