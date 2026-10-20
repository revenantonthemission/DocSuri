-- The runtime role deletes nothing (D13). Every delete runs here, with the schema
-- owner's rights and an owner or compare-and-set predicate: the pending reservation
-- release and sweep (R-02), the unapproved-preview purge (NFR1.5), and the lifecycle
-- functions guarded by AccountAccess's ticket (BR6.1, BR6.2). Every due time is the
-- caller's `p_now` (one clock); only the pace reservation uses the database clock.

-- A check that ends any other way releases only the row it still holds; the pace row
-- goes with it. False when the row moved on (taken over or already gone).
CREATE FUNCTION export.release_pending(p_account uuid,p_holder uuid)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE released boolean;
BEGIN
  DELETE FROM export.connection
   WHERE account_id=p_account AND state='pending' AND pending_holder=p_holder
  RETURNING true INTO released;
  RETURN coalesce(released,false);
END $$;

-- Housekeeping: removes stale reservations whose holder and start time still match what
-- the bounded selection observed, past the takeover time. Returns the number removed.
CREATE FUNCTION export.sweep_stale_pending(p_now timestamptz,p_older_than_seconds integer,p_limit integer)
RETURNS integer LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE removed integer;
BEGIN
  IF p_now IS NULL OR p_older_than_seconds IS NULL OR p_older_than_seconds <= 0
     OR p_limit IS NULL OR p_limit <= 0 THEN
    RAISE EXCEPTION 'stale pending sweep arguments invalid' USING ERRCODE='22023';
  END IF;
  WITH observed AS (
    SELECT c.id, c.pending_holder, c.pending_started_at FROM export.connection c
     WHERE c.state='pending' AND c.pending_started_at <= p_now - make_interval(secs => p_older_than_seconds)
     ORDER BY c.pending_started_at, c.id LIMIT p_limit FOR UPDATE SKIP LOCKED
  ), gone AS (
    DELETE FROM export.connection c USING observed o
     WHERE c.id=o.id AND c.state='pending' AND c.pending_holder=o.pending_holder
       AND c.pending_started_at=o.pending_started_at
    RETURNING 1
  )
  SELECT count(*) INTO removed FROM gone;
  RETURN removed;
END $$;

-- Removes preview revisions that were never approved and are past retention, then any
-- pair left with no revision. The approval foreign key does not cascade, so an
-- approved revision can never be removed. Returns the number of revisions removed.
CREATE FUNCTION export.purge_unapproved_previews(p_now timestamptz,p_retention_days integer,p_limit integer)
RETURNS integer LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE removed integer;
BEGIN
  IF p_now IS NULL OR p_retention_days IS NULL OR p_retention_days <= 0
     OR p_limit IS NULL OR p_limit <= 0 THEN
    RAISE EXCEPTION 'preview purge arguments invalid' USING ERRCODE='22023';
  END IF;
  WITH expired AS (
    SELECT r.preview_id, r.revision FROM export.preview_revision r
     WHERE r.prepared_at <= p_now - make_interval(days => p_retention_days)
       AND NOT EXISTS (SELECT 1 FROM export.approval a
                        WHERE a.preview_id=r.preview_id AND a.preview_revision=r.revision)
     ORDER BY r.prepared_at, r.preview_id, r.revision LIMIT p_limit FOR UPDATE SKIP LOCKED
  ), gone AS (
    DELETE FROM export.preview_revision r USING expired e
     WHERE r.preview_id=e.preview_id AND r.revision=e.revision
    RETURNING r.preview_id
  )
  SELECT count(*) INTO removed FROM gone;
  DELETE FROM export.preview_pair p
   WHERE p.current_revision > 0
     AND NOT EXISTS (SELECT 1 FROM export.preview_revision r WHERE r.preview_id=p.preview_id);
  RETURN removed;
END $$;

-- Withdraw and erase: a pending reservation cannot become disconnected, so the
-- participant removes the account's reservation here. Refuses unless AccountAccess's
-- live ticket for ApprovedExport carries a withdraw or erase action.
CREATE FUNCTION export.lifecycle_release_pending(p_request uuid,p_account uuid,p_scope text,p_generation bigint,
    p_policy jsonb,p_manifest text)
RETURNS integer LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE removed integer;
BEGIN
  IF p_scope IS NULL OR p_scope NOT IN ('live_records','pending_work')
     OR accounts.lifecycle_effect_action(p_request,p_account,'ApprovedExport',p_scope,p_generation,p_policy,p_manifest)
        NOT IN ('withdraw','erase') THEN
    RAISE EXCEPTION 'withdraw or erase action required' USING ERRCODE='42501';
  END IF;
  WITH gone AS (
    DELETE FROM export.connection WHERE account_id=p_account AND state='pending' RETURNING 1
  )
  SELECT count(*) INTO removed FROM gone;
  RETURN removed;
END $$;

-- BR6.2: deletes, in order, the account's approvals (cascading to effects, attempts and
-- reconciliation checks), its preview pairs (cascading to revisions), its replay
-- records and its connection (cascading to its pace row). Count-only lifecycle
-- evidence carries no account column and stays.
CREATE FUNCTION export.erase_account_records(p_request uuid,p_account uuid,p_generation bigint,p_policy jsonb,
    p_manifest text)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
  IF accounts.lifecycle_effect_action(p_request,p_account,'ApprovedExport','live_records',p_generation,p_policy,p_manifest)<>'erase' THEN
    RAISE EXCEPTION 'erasure action required' USING ERRCODE='42501';
  END IF;
  DELETE FROM export.approval WHERE account_id=p_account;
  DELETE FROM export.preview_pair WHERE account_id=p_account;
  DELETE FROM export.replay_record WHERE account_id=p_account;
  DELETE FROM export.connection WHERE account_id=p_account;
END $$;

-- What U6 offers U8 to watch (logical-components §8): counts and ages only, never an
-- identifier, title or content.
CREATE FUNCTION export.status_counts(p_now timestamptz)
RETURNS jsonb LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE effects jsonb; connections jsonb; lane jsonb; oldest_accepted bigint; oldest_unknown bigint;
BEGIN
  IF p_now IS NULL THEN
    RAISE EXCEPTION 'status counts need the caller clock' USING ERRCODE='22023';
  END IF;
  SELECT jsonb_build_object(
      'accepted', count(*) FILTER (WHERE e.state='accepted'),
      'executing', count(*) FILTER (WHERE e.state='executing'),
      'unknown', count(*) FILTER (WHERE e.state='unknown'),
      'succeededLast24h', count(*) FILTER (WHERE e.state='succeeded' AND e.ended_at > p_now - interval '24 hours'),
      'failedLast24h', count(*) FILTER (WHERE e.state='failed' AND e.ended_at > p_now - interval '24 hours'),
      'cancelledLast24h', count(*) FILTER (WHERE e.state='cancelled' AND e.ended_at > p_now - interval '24 hours'),
      'invalidatedLast24h', count(*) FILTER (WHERE e.state='invalidated' AND e.ended_at > p_now - interval '24 hours'))
    INTO effects FROM export.effect e;
  SELECT floor(extract(epoch FROM p_now - min(e.accepted_at)))::bigint INTO oldest_accepted
    FROM export.effect e WHERE e.state='accepted';
  -- An unknown effect's settling wait counts from its latest attempt's deadline (§8.6).
  SELECT floor(extract(epoch FROM p_now - min(t.deadline_at)))::bigint INTO oldest_unknown
    FROM export.effect e
    JOIN LATERAL (SELECT a.deadline_at FROM export.attempt a WHERE a.effect_id=e.id
                   ORDER BY a.attempt_number DESC LIMIT 1) t ON true
   WHERE e.state='unknown';
  SELECT jsonb_build_object(
      'connected', count(*) FILTER (WHERE c.state='connected'),
      'disconnected', count(*) FILTER (WHERE c.state='disconnected'),
      'revoked', count(*) FILTER (WHERE c.state='revoked'),
      'unavailable', count(*) FILTER (WHERE c.state='unavailable'))
    INTO connections FROM export.connection c;
  SELECT jsonb_build_object('outcome', s.outcome, 'observedAt', s.observed_at)
    INTO lane FROM export.lane_status s WHERE s.singleton;
  RETURN jsonb_build_object(
      'effects', effects,
      'oldestAcceptedSeconds', oldest_accepted,
      'oldestUnknownSeconds', oldest_unknown,
      'connections', connections,
      'lane', lane);
END $$;

REVOKE ALL ON ALL FUNCTIONS IN SCHEMA export FROM PUBLIC;
GRANT EXECUTE ON FUNCTION export.release_pending(uuid,uuid),
    export.sweep_stale_pending(timestamptz,integer,integer),
    export.purge_unapproved_previews(timestamptz,integer,integer),
    export.lifecycle_release_pending(uuid,uuid,text,bigint,jsonb,text),
    export.erase_account_records(uuid,uuid,bigint,jsonb,text),
    export.status_counts(timestamptz)
  TO docsuri_export;
