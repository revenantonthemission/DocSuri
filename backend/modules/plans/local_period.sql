-- Entitlement provisioning time for the finite synthetic no-reset period.
ALTER TABLE usage.entitlement
    ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT clock_timestamp();
