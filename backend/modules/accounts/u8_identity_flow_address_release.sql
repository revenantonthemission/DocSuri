-- U8 (Step 19): a correction added after u8_identity_flow_address.sql; it replaces no
-- file. A flow's keyed address digest is kept only while it is counted (security-design
-- § 3.2: addresses are kept only as keyed digests, and only for as long as a limit reads
-- them). A flow that leaves 'pending'/'exchanging' (completed, denied, unknown, expired)
-- loses it in that same write; an expired flow still pending loses it in the entry
-- limits' bounded expiry pass (`EntryLimits.expire`), as a per-address entry row is
-- deleted when its minute ends. The flow itself is otherwise unchanged.
CREATE FUNCTION accounts.identity_flow_address_release() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
  NEW.client_address_digest := NULL;
  RETURN NEW;
END $$;
CREATE TRIGGER identity_flow_address_release BEFORE UPDATE ON accounts.identity_flow
  FOR EACH ROW
  WHEN (NEW.client_address_digest IS NOT NULL
        AND NEW.disposition NOT IN ('pending', 'exchanging'))
  EXECUTE FUNCTION accounts.identity_flow_address_release();
REVOKE ALL ON FUNCTION accounts.identity_flow_address_release() FROM PUBLIC;
-- The expiry pass reads flows still holding a digest by their expiry.
CREATE INDEX identity_flow_address_expiry ON accounts.identity_flow (expires_at)
    WHERE client_address_digest IS NOT NULL;
-- Every flow that already left 'pending'/'exchanging' loses its digest now.
UPDATE accounts.identity_flow SET client_address_digest = NULL
 WHERE client_address_digest IS NOT NULL AND disposition NOT IN ('pending', 'exchanging');
