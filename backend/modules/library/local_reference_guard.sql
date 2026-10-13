CREATE FUNCTION library.guard_saved_reference() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
    PERFORM corpus.guard_paper_reference(NEW.paper_id,NEW.version_id);
    RETURN NEW;
END $$;
CREATE TRIGGER guard_saved_reference BEFORE INSERT OR UPDATE ON library.saved_paper
FOR EACH ROW EXECUTE FUNCTION library.guard_saved_reference();
REVOKE ALL ON FUNCTION library.guard_saved_reference() FROM PUBLIC;
