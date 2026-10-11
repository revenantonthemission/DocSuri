ALTER TABLE assistance.job ADD CONSTRAINT complete_running_claim CHECK (
    state <> 'running' OR (worker_id IS NOT NULL AND lease_id IS NOT NULL
    AND lease_revision IS NOT NULL AND lease_expires_at IS NOT NULL
    AND started_at IS NOT NULL AND fence > 0)
);
CREATE OR REPLACE FUNCTION assistance.acquire_claim(p_job uuid,p_worker uuid)
RETURNS assistance.job LANGUAGE plpgsql SET search_path=pg_catalog AS $$
DECLARE j assistance.job%ROWTYPE; now_at timestamptz;
BEGIN
    SELECT * INTO j FROM assistance.job WHERE id=p_job;
    IF NOT FOUND THEN RAISE EXCEPTION 'job missing' USING ERRCODE='42501'; END IF;
    PERFORM accounts.guard_execution(j.account_id,j.authority_revision);
    PERFORM corpus.guard_version(j.version_id,'local-research');
    SELECT * INTO j FROM assistance.job WHERE id=p_job FOR UPDATE;
    now_at := clock_timestamp();
    IF j.state NOT IN ('accepted','running') OR p_worker IS NULL
       OR (j.lease_expires_at IS NOT NULL AND j.lease_expires_at > now_at)
       OR j.fence >= 3 OR j.accepted_at + interval '5 minutes' <= now_at
       OR (j.started_at IS NOT NULL AND j.started_at + interval '90 seconds' <= now_at)
    THEN RAISE EXCEPTION 'claim unavailable' USING ERRCODE='55000'; END IF;
    UPDATE assistance.job SET worker_id=p_worker,lease_id=gen_random_uuid(),
      fence=fence+1,lease_revision=gen_random_uuid(),started_at=coalesce(started_at,now_at),
      lease_expires_at=least(now_at+interval '30 seconds',coalesce(started_at,now_at)+interval '90 seconds'),
      state='running',phase='claimed',dispatch_pending=false,revision=gen_random_uuid(),sequence=sequence+1
      WHERE id=p_job RETURNING * INTO j;
    RETURN j;
END $$;

CREATE OR REPLACE FUNCTION assistance.guard_claim(p_job uuid,p_worker uuid,p_lease uuid,p_fence bigint)
RETURNS assistance.job LANGUAGE plpgsql SET search_path=pg_catalog AS $$
DECLARE j assistance.job%ROWTYPE;
BEGIN
    IF p_job IS NULL OR p_worker IS NULL OR p_lease IS NULL OR p_fence IS NULL OR p_fence < 1 THEN
        RAISE EXCEPTION 'incomplete execution claim' USING ERRCODE='42501';
    END IF;
    SELECT * INTO j FROM assistance.job WHERE id=p_job;
    IF NOT FOUND THEN RAISE EXCEPTION 'job missing' USING ERRCODE='42501'; END IF;
    PERFORM accounts.guard_execution(j.account_id,j.authority_revision);
    PERFORM corpus.guard_version(j.version_id,'local-research');
    SELECT * INTO j FROM assistance.job WHERE id=p_job FOR UPDATE;
    IF j.state <> 'running' OR j.worker_id IS DISTINCT FROM p_worker
       OR j.lease_id IS DISTINCT FROM p_lease OR j.fence IS DISTINCT FROM p_fence
       OR j.lease_revision IS NULL OR j.lease_expires_at IS NULL
       OR j.lease_expires_at <= clock_timestamp() THEN
        RAISE EXCEPTION 'stale execution claim' USING ERRCODE='42501';
    END IF;
    RETURN j;
END $$;
