-- U3 amendment: the vocabulary-bound virtual-empty glossary revision. Python's
-- GlossaryService and this SQL read must agree on the exact initial token, or
-- canonical acceptance would refuse every first glossary binding.
CREATE OR REPLACE FUNCTION assistance.read_glossary(p_account uuid)
RETURNS TABLE(revision text,snapshot jsonb) LANGUAGE sql SET search_path=pg_catalog AS $$
    SELECT revision,snapshot FROM assistance.glossary WHERE account_id=p_account
    UNION ALL
    SELECT 'empty:' || p_account::text || ':u3-owner-glossary-v1', '[]'::jsonb
      WHERE NOT EXISTS(SELECT 1 FROM assistance.glossary WHERE account_id=p_account)
$$;
REVOKE ALL ON FUNCTION assistance.read_glossary(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION assistance.read_glossary(uuid) TO docsuri_assistance;
