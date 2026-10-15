-- Discovery's narrow SECURITY DEFINER history projections recheck AccountAccess.
GRANT USAGE ON SCHEMA accounts TO docsuri_discovery_owner;
GRANT EXECUTE ON FUNCTION accounts.guard_session(uuid,uuid,text) TO docsuri_discovery_owner;
