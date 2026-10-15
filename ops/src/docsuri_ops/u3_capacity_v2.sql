-- U3 amendment: the shared capacity probe name the control loop expects.
-- The prior u3_capacity_footprint name is superseded; this function observes
-- only aggregate sizes for the owned docsuri_u3 database.
CREATE FUNCTION operations.capacity_footprint()
RETURNS TABLE(database_bytes bigint,wal_bytes bigint)
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog AS $$
  SELECT pg_database_size(current_database()),coalesce(sum(size),0)::bigint
    FROM pg_ls_waldir()
    WHERE current_database()='docsuri_u3'
$$;
REVOKE ALL ON FUNCTION operations.capacity_footprint() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION operations.capacity_footprint() TO docsuri_operations;
