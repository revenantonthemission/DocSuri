-- Personalization consumes a reauthenticated confirmation in its effect transaction.
CREATE TABLE accounts.reset_confirmation (
  id uuid PRIMARY KEY, account_id uuid NOT NULL REFERENCES accounts.account(id),
  session_id uuid NOT NULL, authority_revision uuid NOT NULL,
  action text NOT NULL CHECK (action IN ('delete_behavior','reset_profile')),
  settings_revision uuid NOT NULL, policy_ref jsonb NOT NULL,
  prepare_key uuid NOT NULL, intent_hash text NOT NULL CHECK (length(intent_hash)=64),
  expires_at timestamptz NOT NULL, public_value jsonb NOT NULL,
  consumed_operation uuid, UNIQUE(account_id,prepare_key)
);
GRANT SELECT,INSERT ON accounts.reset_confirmation TO docsuri_accounts;
CREATE FUNCTION accounts.consume_reset_confirmation(
  p_id uuid,p_account uuid,p_session uuid,p_action text,p_revision uuid,p_policy jsonb,p_operation uuid
) RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE r accounts.reset_confirmation%ROWTYPE; current_authority uuid;
BEGIN
  current_authority := accounts.guard_session(p_account,p_session,'account-control');
  SELECT * INTO r FROM accounts.reset_confirmation WHERE id=p_id FOR UPDATE;
  IF NOT FOUND OR r.account_id<>p_account OR r.session_id<>p_session
    OR r.authority_revision<>current_authority OR r.action<>p_action
    OR r.settings_revision<>p_revision OR r.policy_ref<>p_policy
    OR r.expires_at<=clock_timestamp()
    OR (r.consumed_operation IS NOT NULL AND r.consumed_operation<>p_operation) THEN
    RAISE EXCEPTION 'reset confirmation unavailable' USING ERRCODE='42501';
  END IF;
  UPDATE accounts.reset_confirmation SET consumed_operation=p_operation WHERE id=p_id;
END $$;
REVOKE ALL ON FUNCTION accounts.consume_reset_confirmation(uuid,uuid,uuid,text,uuid,jsonb,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION accounts.consume_reset_confirmation(uuid,uuid,uuid,text,uuid,jsonb,uuid)
  TO docsuri_personalization;
