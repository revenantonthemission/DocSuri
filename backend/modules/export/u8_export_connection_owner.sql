-- U8 (BR7.3, BR7.5; your answer of 2026-11-11 on build batch 7's review, "Wire the owner
-- read"): ProviderActivation's rehearsal recipients ask whose a Notion connection is, so
-- that the maintainer's first configure, checked on a candidate token that carries only
-- its pending row's id, is known as the maintainer's own. ApprovedExport answers through
-- this owner's definer function and nothing else: one connection id in, its owning
-- account out (pending rows included, NULL for an unknown id), never a token, a
-- workspace or a list of connections. ServiceOperations' login gets EXECUTE on it and the
-- USAGE on this schema that reaching it needs, and no privilege on any table.
CREATE FUNCTION export.connection_owner(p_connection uuid)
RETURNS uuid LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog AS $$
  SELECT c.account_id FROM export.connection c WHERE c.id = p_connection
$$;
REVOKE ALL ON FUNCTION export.connection_owner(uuid) FROM PUBLIC;
GRANT USAGE ON SCHEMA export TO docsuri_operations;
GRANT EXECUTE ON FUNCTION export.connection_owner(uuid) TO docsuri_operations;
