-- Personalization remains the sole settings writer. Topics receives a narrow
-- background read and shares the settings owner's lock for send admission.
CREATE FUNCTION personalization.guard_digest_preferences() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
DECLARE zone text;
BEGIN
  zone := NEW.defaults->>'timeZone';
  IF zone IS NOT NULL AND NOT EXISTS (SELECT 1 FROM pg_timezone_names WHERE name=zone) THEN
    RAISE EXCEPTION 'unsupported timezone' USING ERRCODE='23514';
  END IF;
  IF TG_OP='INSERT' OR (NEW.defaults->>'timeZone') IS DISTINCT FROM (OLD.defaults->>'timeZone') THEN
    NEW.defaults := NEW.defaults - 'timeZoneEffectiveAt';
    IF zone IS NOT NULL THEN
      NEW.defaults := NEW.defaults || jsonb_build_object('timeZoneEffectiveAt',clock_timestamp());
    END IF;
  ELSE
    NEW.defaults := (NEW.defaults - 'timeZoneEffectiveAt') ||
      jsonb_build_object('timeZoneEffectiveAt',OLD.defaults->'timeZoneEffectiveAt');
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER digest_preferences BEFORE INSERT OR UPDATE ON personalization.settings
FOR EACH ROW EXECUTE FUNCTION personalization.guard_digest_preferences();

CREATE FUNCTION personalization.digest_preferences(p_account uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE s personalization.settings%ROWTYPE;
BEGIN
  PERFORM pg_advisory_xact_lock(hashtextextended(p_account::text,22));
  SELECT * INTO s FROM personalization.settings WHERE account_id=p_account FOR SHARE;
  RETURN jsonb_build_object(
    'languageId',COALESCE(s.defaults#>>'{assistanceDefaults,languageId}','en'),
    'presentationLevelId',COALESCE(s.defaults#>>'{assistanceDefaults,presentationLevelId}','standard'),
    'timeZone',s.defaults->>'timeZone',
    'effectiveAt',s.defaults->>'timeZoneEffectiveAt',
    'sourceRevision',s.revision,
    'usesDefaults',s.defaults->'assistanceDefaults' IS NULL);
END $$;
REVOKE ALL ON FUNCTION personalization.guard_digest_preferences() FROM PUBLIC;
REVOKE ALL ON FUNCTION personalization.digest_preferences(uuid) FROM PUBLIC;
GRANT USAGE ON SCHEMA personalization TO docsuri_topics;
GRANT EXECUTE ON FUNCTION personalization.digest_preferences(uuid) TO docsuri_topics;
