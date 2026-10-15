CREATE FUNCTION accounts.assignment_target_available(p_account uuid)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE a accounts.account%ROWTYPE;
BEGIN
  SELECT * INTO a FROM accounts.account WHERE id=p_account FOR SHARE;
  RETURN FOUND AND a.active AND a.verified AND a.lifecycle_state='active';
END $$;
REVOKE ALL ON FUNCTION accounts.assignment_target_available(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION accounts.assignment_target_available(uuid) TO docsuri_usage;
