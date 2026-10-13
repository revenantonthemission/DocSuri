-- Result identity revision for canonical ResultRef bindings.
ALTER TABLE assistance.result
    ADD COLUMN IF NOT EXISTS revision uuid NOT NULL DEFAULT gen_random_uuid();
