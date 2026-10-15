-- U3 Discovery authority grants: the search owner rechecks its own producer
-- checkpoint through the narrow SECURITY DEFINER projection.
GRANT EXECUTE ON FUNCTION discovery.history_checkpoint(uuid,uuid) TO docsuri_discovery;
GRANT EXECUTE ON FUNCTION discovery.history_fact(uuid,uuid,uuid) TO docsuri_discovery;
