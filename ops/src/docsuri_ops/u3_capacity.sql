-- U3 aggregate footprint observation for the owned docsuri_u3 realm only.
-- Ops exposes only aggregate sizes; no directory names, paths or content.
-- The migration runner grants pg_ls_waldir() to this non-login schema owner
-- and CONNECT on docsuri_u3 for pg_database_size inside the definer function.
CREATE FUNCTION operations.u3_capacity_footprint()
RETURNS TABLE(database_bytes bigint,wal_bytes bigint)
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog AS $$
  SELECT pg_database_size(current_database()),coalesce(sum(size),0)::bigint
    FROM pg_ls_waldir()
    WHERE current_database()='docsuri_u3'
$$;
REVOKE ALL ON FUNCTION operations.u3_capacity_footprint() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION operations.u3_capacity_footprint() TO docsuri_operations;
