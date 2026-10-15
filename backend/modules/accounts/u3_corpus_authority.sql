-- U3: the corpus maintenance owner rechecks current session authority at every
-- protected boundary; grant exactly the shared session guard. No other
-- accounts objects are reachable from the corpus runtime role.
GRANT USAGE ON SCHEMA accounts TO docsuri_corpus;
GRANT EXECUTE ON FUNCTION accounts.guard_session(uuid,uuid,text) TO docsuri_corpus;
