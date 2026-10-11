CREATE FUNCTION corpus.preserve_version_binding() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF ROW(NEW.id,NEW.paper_id,NEW.source_url,NEW.source_hash,NEW.version_label,NEW.private_path,NEW.purpose,NEW.provenance,NEW.content)
       IS DISTINCT FROM ROW(OLD.id,OLD.paper_id,OLD.source_url,OLD.source_hash,OLD.version_label,OLD.private_path,OLD.purpose,OLD.provenance,OLD.content)
    THEN RAISE EXCEPTION 'immutable source binding' USING ERRCODE = '23514'; END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER preserve_version_binding BEFORE UPDATE ON corpus.version
FOR EACH ROW EXECUTE FUNCTION corpus.preserve_version_binding();
REVOKE ALL ON FUNCTION corpus.preserve_version_binding() FROM PUBLIC;
