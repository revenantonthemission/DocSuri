-- U3 CorpusContent guards: watermark/terminal discipline, append-only change
-- facts, generation state machine and the bounded ordered fact read for Library.

CREATE FUNCTION corpus.guard_run_state() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF OLD.state IN ('completed','failed') AND NEW.state IS DISTINCT FROM OLD.state THEN
        RAISE EXCEPTION 'terminal run state cannot regress' USING ERRCODE = '23514';
    END IF;
    IF NEW.watermark IS DISTINCT FROM OLD.watermark AND NEW.watermark IS NOT NULL THEN
        IF EXISTS (SELECT 1 FROM corpus.run_effect
                   WHERE run_id = NEW.id AND state <> 'committed') THEN
            RAISE EXCEPTION 'watermark cannot advance past unverified work' USING ERRCODE = '23514';
        END IF;
    END IF;
    IF NEW.state = 'completed' THEN
        IF EXISTS (SELECT 1 FROM corpus.run_effect
                   WHERE run_id = NEW.id AND state <> 'committed') THEN
            RAISE EXCEPTION 'run cannot complete with outstanding effects' USING ERRCODE = '23514';
        END IF;
        NEW.completed_at := coalesce(NEW.completed_at, clock_timestamp());
        NEW.dispatch_pending := false;
    END IF;
    IF NEW.state = 'failed' THEN
        NEW.completed_at := coalesce(NEW.completed_at, clock_timestamp());
        NEW.dispatch_pending := false;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER guard_run_state BEFORE UPDATE ON corpus.run
FOR EACH ROW EXECUTE FUNCTION corpus.guard_run_state();

CREATE FUNCTION corpus.preserve_change_fact() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    RAISE EXCEPTION 'source-change facts are append-only' USING ERRCODE = '23514';
END $$;
CREATE TRIGGER preserve_change_fact BEFORE UPDATE OR DELETE ON corpus.change_fact
FOR EACH ROW EXECUTE FUNCTION corpus.preserve_change_fact();

CREATE FUNCTION corpus.guard_generation_state() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF OLD.state = 'published' AND NEW.state IS DISTINCT FROM OLD.state THEN
        RAISE EXCEPTION 'published generation is terminal' USING ERRCODE = '23514';
    END IF;
    IF OLD.state = 'building' AND NEW.state NOT IN ('building','verified','failed') THEN
        RAISE EXCEPTION 'generation cannot skip verification' USING ERRCODE = '23514';
    END IF;
    IF OLD.state = 'verified' AND NEW.state NOT IN ('verified','published','failed') THEN
        RAISE EXCEPTION 'unverified generation transition refused' USING ERRCODE = '23514';
    END IF;
    IF NEW.state = 'verified' THEN
        NEW.verified_at := coalesce(NEW.verified_at, clock_timestamp());
    END IF;
    IF NEW.state = 'published' THEN
        NEW.published_at := coalesce(NEW.published_at, clock_timestamp());
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER guard_generation_state BEFORE UPDATE ON corpus.generation
FOR EACH ROW EXECUTE FUNCTION corpus.guard_generation_state();

-- Bounded, ordered fact read for Library disposition consumers (C04 readSourceChanges).
CREATE FUNCTION corpus.read_change_facts(p_after bigint, p_limit integer)
RETURNS TABLE(fact_id uuid, paper_id text, version_id text, change_kind text,
              eligibility_revision uuid, fact_position bigint, recorded_at timestamptz,
              detail jsonb)
LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog AS $$
    SELECT f.id, f.paper_id, f.version_id, f.change_kind, f.eligibility_revision,
           f.fact_position, f.recorded_at, f.detail
      FROM corpus.change_fact f
     WHERE f.fact_position > p_after AND p_limit BETWEEN 1 AND 100
     ORDER BY f.fact_position, f.id
     LIMIT LEAST(p_limit, 100)
$$;
REVOKE ALL ON FUNCTION corpus.read_change_facts(bigint,integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION corpus.read_change_facts(bigint,integer) TO docsuri_library,docsuri_corpus;

-- Current eligibility boundary for one version; used by discovery/assistance
-- rechecks and by the restore rehearsal before serving anything.
CREATE FUNCTION corpus.current_eligibility(p_version text)
RETURNS TABLE(eligibility_revision uuid, disposition text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE p corpus.paper%ROWTYPE; v corpus.version%ROWTYPE; paper_key text;
BEGIN
    SELECT paper_id INTO paper_key FROM corpus.version WHERE id = p_version;
    IF NOT FOUND THEN
        RETURN QUERY SELECT NULL::uuid, 'absent'::text; RETURN;
    END IF;
    SELECT * INTO p FROM corpus.paper WHERE id = paper_key FOR SHARE;
    IF NOT FOUND THEN
        RETURN QUERY SELECT NULL::uuid, 'absent'::text; RETURN;
    END IF;
    SELECT * INTO v FROM corpus.version WHERE id = p_version AND paper_id = paper_key FOR SHARE;
    IF NOT FOUND THEN
        RETURN QUERY SELECT NULL::uuid, 'absent'::text; RETURN;
    END IF;
    RETURN QUERY SELECT v.eligibility_revision,
        CASE WHEN p.withdrawn OR NOT v.eligible THEN 'withdrawn'
             WHEN v.purpose <> 'local-research' THEN 'restricted'
             ELSE 'available' END;
END $$;
REVOKE ALL ON FUNCTION corpus.current_eligibility(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION corpus.current_eligibility(text)
    TO docsuri_corpus,docsuri_discovery,docsuri_library,docsuri_assistance;

REVOKE ALL ON ALL FUNCTIONS IN SCHEMA corpus FROM PUBLIC;
GRANT EXECUTE ON FUNCTION corpus.guard_run_state() TO docsuri_corpus;
GRANT EXECUTE ON FUNCTION corpus.preserve_change_fact() TO docsuri_corpus;
GRANT EXECUTE ON FUNCTION corpus.guard_generation_state() TO docsuri_corpus;
