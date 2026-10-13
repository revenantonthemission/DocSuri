-- The five-minute recovery window is an absolute accepted-work lifetime.
-- No renewal advertises time beyond it or the original 90-second execution.
CREATE FUNCTION assistance.bound_execution_deadline() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
    IF NEW.lease_expires_at IS NOT NULL AND NEW.started_at IS NOT NULL THEN
        NEW.lease_expires_at := least(NEW.lease_expires_at,
          NEW.started_at + interval '90 seconds', NEW.accepted_at + interval '5 minutes');
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER bound_execution_deadline BEFORE INSERT OR UPDATE ON assistance.job
FOR EACH ROW EXECUTE FUNCTION assistance.bound_execution_deadline();
REVOKE ALL ON FUNCTION assistance.bound_execution_deadline() FROM PUBLIC;
