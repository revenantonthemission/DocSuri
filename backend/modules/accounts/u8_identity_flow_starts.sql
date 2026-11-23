-- U8 (Step 19; the person's decision of 2026-10-25, "Count every start, free places at
-- once"): a correction added after u8_identity_flow_address_release.sql; it replaces no
-- file. Every provider sign-in start, a link included, now counts under the keyed digest
-- of its client address bucket, and a signed-in start also under its account, for as long
-- as the flow is kept. A flow is kept until one minute after it expires, then deleted
-- with its digest by AccountAccess's own bounded pass (`expire_identity_flows`), which the
-- runtime login may only call: it holds no DELETE on the table (security-design § 3.2).

-- The digest is no longer cleared when a flow leaves 'pending'/'exchanging': a finished
-- start still counts against its bucket's starts until it expires.
DROP TRIGGER identity_flow_address_release ON accounts.identity_flow;
DROP FUNCTION accounts.identity_flow_address_release();
DROP INDEX accounts.identity_flow_open_address;
DROP INDEX accounts.identity_flow_address_expiry;
-- A link's start carries its address digest too.
ALTER TABLE accounts.identity_flow DROP CONSTRAINT identity_flow_address_anonymous_sign_in;

-- The counts read unexpired flows by address digest, by account and for the site; the
-- browser's own latest pending flows by binding; the deletion pass by expiry.
CREATE INDEX identity_flow_expiry ON accounts.identity_flow (expires_at);
CREATE INDEX identity_flow_address_starts ON accounts.identity_flow
    (client_address_digest, expires_at) WHERE client_address_digest IS NOT NULL;
CREATE INDEX identity_flow_account_starts ON accounts.identity_flow
    (account_id, expires_at) WHERE account_id IS NOT NULL;
CREATE INDEX identity_flow_pending_binding ON accounts.identity_flow
    (binding_hash, expires_at) WHERE disposition = 'pending';

-- Deletes at most `p_limit` flows that expired more than a minute ago, with their address
-- digests, and returns how many it deleted.
CREATE FUNCTION accounts.expire_identity_flows(p_limit integer) RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE removed integer;
BEGIN
  IF p_limit IS NULL OR p_limit < 1 OR p_limit > 10000 THEN
    RAISE EXCEPTION 'expiry outside its bound' USING ERRCODE='22023';
  END IF;
  DELETE FROM accounts.identity_flow WHERE ctid IN (
    SELECT ctid FROM accounts.identity_flow
     WHERE expires_at < clock_timestamp() - interval '1 minute' LIMIT p_limit);
  GET DIAGNOSTICS removed = ROW_COUNT;
  RETURN removed;
END $$;
REVOKE ALL ON FUNCTION accounts.expire_identity_flows(integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION accounts.expire_identity_flows(integer) TO docsuri_accounts;
