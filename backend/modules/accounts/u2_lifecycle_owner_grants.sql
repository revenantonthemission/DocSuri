-- Only owner definer functions may remove immutable private receipts on erasure.
GRANT USAGE ON SCHEMA accounts TO docsuri_library_owner,docsuri_personalization_owner;
GRANT EXECUTE ON FUNCTION accounts.lifecycle_effect_action(uuid,uuid,text,text,bigint,jsonb,text)
  TO docsuri_library_owner,docsuri_personalization_owner;
