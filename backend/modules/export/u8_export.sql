-- U8 (O6, NFR9.11): ApprovedExport's additive migration. The accept path writes the
-- request identifier the host gave the request; nullable, null for every existing row.
ALTER TABLE export.effect ADD COLUMN origin_request_id uuid;
