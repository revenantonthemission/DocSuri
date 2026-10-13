CREATE FUNCTION assistance.preserve_result_binding() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF (to_jsonb(NEW) - 'availability') IS DISTINCT FROM (to_jsonb(OLD) - 'availability')
    THEN RAISE EXCEPTION 'immutable result binding' USING ERRCODE = '23514'; END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER preserve_result_binding BEFORE UPDATE ON assistance.result
FOR EACH ROW EXECUTE FUNCTION assistance.preserve_result_binding();

CREATE FUNCTION assistance.append_event() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF TG_OP = 'INSERT' OR NEW.sequence > OLD.sequence THEN
        INSERT INTO assistance.event(job_id,sequence,snapshot) VALUES
          (NEW.id,NEW.sequence,jsonb_build_object('jobId',NEW.id,'state',NEW.state,
           'revision',NEW.revision,'sequence',NEW.sequence,'phase',NEW.phase,
           'acceptedAt',NEW.accepted_at,'failureCode',NEW.failure_code));
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER append_event AFTER INSERT OR UPDATE ON assistance.job
FOR EACH ROW EXECUTE FUNCTION assistance.append_event();
REVOKE ALL ON FUNCTION assistance.preserve_result_binding() FROM PUBLIC;
REVOKE ALL ON FUNCTION assistance.append_event() FROM PUBLIC;
