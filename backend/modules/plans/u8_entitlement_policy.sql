-- U8 (the person's decision of 2026-10-23, "Grant migrated accounts"): UsageEntitlements'
-- additive migration. U2's control path runs in the composed and production realms with
-- their own control policies, so an entitlement may carry `u8-synthetic-v1` or
-- `docsuri-production-v1` beside U2's two values; `u2_controls.sql` stays as applied.
ALTER TABLE usage.entitlement DROP CONSTRAINT entitlement_policy_check;
ALTER TABLE usage.entitlement ADD CONSTRAINT entitlement_policy_check CHECK(policy IN (
  'synthetic-four-no-reset','u2-synthetic-v1','u8-synthetic-v1','docsuri-production-v1'));
