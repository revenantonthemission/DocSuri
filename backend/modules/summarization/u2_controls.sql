-- Extend the accepting owner's existing admission, not a parallel usage ledger.
-- The physical U1 'rejected' state maps to C03 'closed' at the U2 adapter.
ALTER TABLE assistance.admission
  ADD COLUMN generation bigint NOT NULL DEFAULT 1 CHECK(generation>0),
  ADD COLUMN period_id text NOT NULL DEFAULT 'synthetic-environment-retention',
  ADD COLUMN quantity integer NOT NULL DEFAULT 1 CHECK(quantity BETWEEN 1 AND 3),
  ADD COLUMN policy_ref jsonb NOT NULL DEFAULT '{"policyId":"synthetic-four-no-reset","revision":"1"}',
  ADD COLUMN closure_ref uuid,
  ADD COLUMN closed_at timestamptz,
  ADD COLUMN closure_reason text;
CREATE FUNCTION assistance.preserve_admission_binding() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
  IF TG_OP='UPDATE' THEN
    IF ROW(NEW.operation_id,NEW.account_id,NEW.intent_hash,NEW.intent,NEW.created_at,
           NEW.generation,NEW.period_id,NEW.quantity,NEW.policy_ref) IS DISTINCT FROM
       ROW(OLD.operation_id,OLD.account_id,OLD.intent_hash,OLD.intent,OLD.created_at,
           OLD.generation,OLD.period_id,OLD.quantity,OLD.policy_ref) THEN
      RAISE EXCEPTION 'immutable admission identity' USING ERRCODE='23514';
    END IF;
    IF OLD.disposition<>'open' AND NEW.disposition<>OLD.disposition THEN
      RAISE EXCEPTION 'terminal admission cannot reopen' USING ERRCODE='23514';
    END IF;
    IF OLD.disposition='rejected' AND ROW(NEW.closure_ref,NEW.closed_at,NEW.closure_reason)
        IS DISTINCT FROM ROW(OLD.closure_ref,OLD.closed_at,OLD.closure_reason) THEN
      RAISE EXCEPTION 'immutable closure evidence' USING ERRCODE='23514';
    END IF;
  END IF;
  IF NEW.disposition='rejected' AND NEW.closure_ref IS NULL THEN
    NEW.closure_ref:=gen_random_uuid();
    NEW.closed_at:=clock_timestamp();
    NEW.closure_reason:='owner-closed-before-acceptance';
  END IF;
  IF NEW.disposition='accepted' AND NEW.reservation_id IS NULL THEN
    RAISE EXCEPTION 'acceptance requires reservation' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER preserve_admission_binding BEFORE INSERT OR UPDATE ON assistance.admission
FOR EACH ROW EXECUTE FUNCTION assistance.preserve_admission_binding();
REVOKE ALL ON FUNCTION assistance.preserve_admission_binding() FROM PUBLIC;
