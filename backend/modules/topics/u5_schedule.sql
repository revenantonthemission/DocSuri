-- Recover the earliest pending occurrence, including a late weekly tick. The
-- owner's confirmed zone and schedule-change boundary never invent past zones.
CREATE FUNCTION topics.next_occurrence(p_topic uuid, p_now timestamptz)
RETURNS TABLE(window_day date, due_at timestamptz, preferences jsonb)
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
DECLARE t topics.followed_topic%ROWTYPE; s topics.digest_settings%ROWTYPE;
  prefs jsonb; zone text; boundary timestamptz; candidate date; latest date;
  wall timestamp; instant timestamptz; target_day integer; tries integer; gap_minutes integer;
BEGIN
  SELECT * INTO t FROM topics.followed_topic WHERE id=p_topic;
  SELECT * INTO s FROM topics.digest_settings WHERE topic_id=p_topic;
  prefs := personalization.digest_preferences(t.account_id);
  zone := prefs->>'timeZone';
  IF zone IS NULL OR prefs->>'effectiveAt' IS NULL THEN RETURN; END IF;
  IF prefs->>'languageId' NOT IN ('en','ko') OR prefs->>'presentationLevelId'<>'standard' THEN RETURN; END IF;
  boundary := greatest(t.followed_at,s.updated_at,(prefs->>'effectiveAt')::timestamptz);
  candidate := (boundary AT TIME ZONE zone)::date;
  SELECT max(r.window_end) INTO latest FROM topics.digest_run r
    WHERE r.topic_id=p_topic AND r.state<>'discarded';
  IF latest IS NOT NULL THEN candidate := greatest(candidate,latest+1); END IF;
  target_day := array_position(ARRAY['mon','tue','wed','thu','fri','sat','sun'],s.delivery_day)-1;
  -- At most the next week plus one boundary adjustment; no unbounded catch-up.
  FOR tries IN 0..8 LOOP
    IF s.cadence='daily' OR extract(isodow FROM candidate)::integer-1=target_day THEN
      wall := candidate+s.delivery_time_local;
      instant := wall AT TIME ZONE zone;
      -- A missing wall minute is due at the first valid minute after the gap.
      gap_minutes := 0;
      WHILE (instant AT TIME ZONE zone)<>wall AND gap_minutes<1560 LOOP
        wall := wall+interval '1 minute';
        instant := wall AT TIME ZONE zone;
        gap_minutes := gap_minutes+1;
      END LOOP;
      IF (instant AT TIME ZONE zone)<>wall THEN RETURN; END IF;
      -- Select the first valid occurrence during a fold, including 30-minute
      -- transitions. The bounded scan also covers a skipped calendar date.
      SELECT min(v) INTO instant FROM generate_series(instant-interval '26 hours',instant,interval '1 minute') v
        WHERE (v AT TIME ZONE zone)=wall;
      IF instant>=boundary THEN
        IF instant<=p_now THEN RETURN QUERY SELECT candidate,instant,prefs; END IF;
        RETURN;
      END IF;
    END IF;
    candidate := candidate+1;
  END LOOP;
END $$;
REVOKE ALL ON FUNCTION topics.next_occurrence(uuid,timestamptz) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION topics.next_occurrence(uuid,timestamptz) TO docsuri_topics;
