-- U8 (BR2.3, U8 plan Step 17): ResearchWorkspace's lifecycle participant needs, a
-- correction added after u8_research_job_times.sql; it replaces no file. The runtime
-- login holds no DELETE on research's tables, so erasure runs as this owner's definer
-- function behind AccountAccess's live, current-generation ticket, as every other
-- owner's erasure does. Evidence is counts only, with no account column, so it
-- survives the erasure it describes.
CREATE TABLE research.lifecycle_counts (
    request_id uuid NOT NULL,
    scope text NOT NULL CHECK (scope IN ('live_records','derived_artifacts','pending_work')),
    action text NOT NULL CHECK (action IN ('withdraw','erase','reactivate')),
    contexts integer NOT NULL DEFAULT 0 CHECK (contexts >= 0),
    sessions integer NOT NULL DEFAULT 0 CHECK (sessions >= 0),
    jobs integer NOT NULL DEFAULT 0 CHECK (jobs >= 0),
    artifacts integer NOT NULL DEFAULT 0 CHECK (artifacts >= 0),
    evidence integer NOT NULL DEFAULT 0 CHECK (evidence >= 0),
    attachments integer NOT NULL DEFAULT 0 CHECK (attachments >= 0),
    drafts integer NOT NULL DEFAULT 0 CHECK (drafts >= 0),
    jobs_stopped integer NOT NULL DEFAULT 0 CHECK (jobs_stopped >= 0),
    admissions_closed integer NOT NULL DEFAULT 0 CHECK (admissions_closed >= 0),
    PRIMARY KEY (request_id, scope)
);
GRANT SELECT,INSERT ON research.lifecycle_counts TO docsuri_research;

-- Erase every research record of the account (BR2.3): contexts, sessions, turns and
-- jobs, artifacts with their evidence and assessments, attachments and drafts, and the
-- account's admission and receipt rows. Refused while accepted work is open or a job's
-- usage is not yet settled, so no UsageEntitlements reservation is left without the
-- job that settles it.
CREATE FUNCTION research.erase_account_records(p_request uuid,p_account uuid,p_scope text,
    p_generation bigint,p_policy jsonb,p_manifest text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE
  n_contexts integer; n_sessions integer; n_jobs integer; n_artifacts integer;
  n_evidence integer; n_attachments integer; n_drafts integer; n_revisions integer;
  n_assessments integer;
BEGIN
  IF p_scope NOT IN ('live_records','derived_artifacts') THEN
    RAISE EXCEPTION 'erasure scope required' USING ERRCODE='42501';
  END IF;
  IF accounts.lifecycle_effect_action(p_request,p_account,'ResearchWorkspace',p_scope,
      p_generation,p_policy,p_manifest)<>'erase' THEN
    RAISE EXCEPTION 'erasure action required' USING ERRCODE='42501';
  END IF;
  -- Derived artifacts: the results, their evidence and assessments.
  DELETE FROM research.evidence WHERE owner_id=p_account;
  GET DIAGNOSTICS n_evidence = ROW_COUNT;
  DELETE FROM research.assessment WHERE artifact_id IN
    (SELECT id FROM research.artifact WHERE owner_id=p_account);
  GET DIAGNOSTICS n_assessments = ROW_COUNT;
  DELETE FROM research.artifact WHERE owner_id=p_account;
  GET DIAGNOSTICS n_artifacts = ROW_COUNT;
  IF p_scope = 'derived_artifacts' THEN
    RETURN jsonb_build_object('artifacts', n_artifacts, 'evidence', n_evidence + n_assessments);
  END IF;
  IF EXISTS (SELECT 1 FROM research.job WHERE owner_id=p_account
             AND (state IN ('accepted','running','cancel_requested') OR usage_state='reserved')) THEN
    RAISE EXCEPTION 'research work or usage settlement pending' USING ERRCODE='55000';
  END IF;
  DELETE FROM research.draft_revision WHERE draft_id IN
    (SELECT id FROM research.draft WHERE owner_id=p_account);
  GET DIAGNOSTICS n_revisions = ROW_COUNT;
  DELETE FROM research.draft WHERE owner_id=p_account;
  GET DIAGNOSTICS n_drafts = ROW_COUNT;
  DELETE FROM research.attachment WHERE owner_id=p_account;
  GET DIAGNOSTICS n_attachments = ROW_COUNT;
  DELETE FROM research.dispatch WHERE job_id IN
    (SELECT id FROM research.job WHERE owner_id=p_account);
  DELETE FROM research.job WHERE owner_id=p_account;
  GET DIAGNOSTICS n_jobs = ROW_COUNT;
  DELETE FROM research.session WHERE owner_id=p_account;
  GET DIAGNOSTICS n_sessions = ROW_COUNT;
  DELETE FROM research.context WHERE owner_id=p_account;
  GET DIAGNOSTICS n_contexts = ROW_COUNT;
  DELETE FROM research.receipt WHERE owner_id=p_account;
  DELETE FROM research.admission WHERE owner_id=p_account;
  RETURN jsonb_build_object(
    'contexts', n_contexts, 'sessions', n_sessions, 'jobs', n_jobs,
    'artifacts', n_artifacts, 'evidence', n_evidence + n_assessments,
    'attachments', n_attachments, 'drafts', n_drafts + n_revisions);
END $$;
REVOKE ALL ON FUNCTION research.erase_account_records(uuid,uuid,text,bigint,jsonb,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION research.erase_account_records(uuid,uuid,text,bigint,jsonb,text)
  TO docsuri_research;
