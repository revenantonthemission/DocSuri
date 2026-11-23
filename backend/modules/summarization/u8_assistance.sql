-- U8 (O6, NFR9.11): PaperAssistance's additive migration. The accept path writes the
-- request identifier the host gave the request; nullable, null for every existing row.
ALTER TABLE assistance.job ADD COLUMN origin_request_id uuid;
