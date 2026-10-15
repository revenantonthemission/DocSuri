-- U2 only. Original settings control remains the sole explicit-default store.
CREATE TABLE personalization.reset_responsibility (
  id uuid PRIMARY KEY, account_id uuid NOT NULL,
  action text NOT NULL CHECK (action IN ('delete_behavior','reset_profile')),
  accepted_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  accepted_settings_revision uuid NOT NULL, input_boundary bigint NOT NULL CHECK(input_boundary>=0),
  policy_ref jsonb NOT NULL, manifest_revision text NOT NULL,
  status_revision bigint NOT NULL DEFAULT 1 CHECK(status_revision>0),
  disposition text NOT NULL CHECK(disposition IN ('pending','blocked','complete')),
  reason_key text NOT NULL,
  UNIQUE(account_id,input_boundary)
);
CREATE INDEX reset_owner_page ON personalization.reset_responsibility(account_id,accepted_at DESC,id DESC);
CREATE TABLE personalization.reset_scope (
  reset_id uuid NOT NULL REFERENCES personalization.reset_responsibility(id),
  participant text NOT NULL, scope text NOT NULL, manifest_revision text NOT NULL,
  generation bigint NOT NULL DEFAULT 0 CHECK(generation>=0),
  disposition text NOT NULL DEFAULT 'pending' CHECK(disposition IN ('pending','blocked','complete')),
  attempts integer NOT NULL DEFAULT 0 CHECK(attempts BETWEEN 0 AND 3),
  lease_until timestamptz, reason_key text NOT NULL DEFAULT 'pending',
  evidence_ref uuid, updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY(reset_id,participant,scope),
  CHECK(disposition<>'complete' OR evidence_ref IS NOT NULL)
);
ALTER TABLE personalization.behavior ADD COLUMN input_boundary bigint NOT NULL DEFAULT 0,
  ADD COLUMN authority_revision uuid,
  ADD COLUMN paper_version_id text,
  ADD COLUMN activity text;
CREATE INDEX behavior_owner_boundary ON personalization.behavior(account_id,input_boundary,created_at DESC,id DESC);
CREATE TABLE personalization.projection (
  account_id uuid PRIMARY KEY, revision uuid NOT NULL, input_boundary bigint NOT NULL,
  consent_revision uuid NOT NULL, interest_ids jsonb NOT NULL,
  disposition text NOT NULL CHECK(disposition IN ('ready','cold_start','disabled','unavailable')),
  CHECK(jsonb_array_length(interest_ids)<=8)
);
CREATE TABLE personalization.lifecycle_evidence (
  request_id uuid NOT NULL, scope text NOT NULL, generation bigint NOT NULL,
  policy_ref jsonb NOT NULL, manifest_revision text NOT NULL, evidence_ref uuid NOT NULL,
  PRIMARY KEY(request_id,scope)
);
GRANT SELECT,INSERT,UPDATE ON personalization.reset_responsibility,personalization.reset_scope,
  personalization.projection,personalization.lifecycle_evidence TO docsuri_personalization;

CREATE FUNCTION personalization.preserve_reset_acceptance() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
  IF ROW(NEW.id,NEW.account_id,NEW.action,NEW.accepted_at,NEW.accepted_settings_revision,
         NEW.input_boundary,NEW.policy_ref,NEW.manifest_revision) IS DISTINCT FROM
     ROW(OLD.id,OLD.account_id,OLD.action,OLD.accepted_at,OLD.accepted_settings_revision,
         OLD.input_boundary,OLD.policy_ref,OLD.manifest_revision) THEN
    RAISE EXCEPTION 'immutable reset acceptance' USING ERRCODE='23514';
  END IF;
  IF NEW.status_revision<OLD.status_revision OR
     (ROW(NEW.disposition,NEW.reason_key) IS DISTINCT FROM ROW(OLD.disposition,OLD.reason_key)
       AND NEW.status_revision<=OLD.status_revision) OR
     (OLD.disposition='complete' AND NEW.disposition<>'complete') THEN
    RAISE EXCEPTION 'reset status cannot regress' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER preserve_reset_acceptance BEFORE UPDATE ON personalization.reset_responsibility
FOR EACH ROW EXECUTE FUNCTION personalization.preserve_reset_acceptance();
REVOKE ALL ON FUNCTION personalization.preserve_reset_acceptance() FROM PUBLIC;
