-- U8 (D13, NFR9.11; your decision of 2026-11-01, "Database default and U8 hooks", L1-6):
-- PaperAssistance's job keeps the identifier of the request that started it. No insert
-- names the column: the default reads the transaction-local setting U8's
-- CompleteTransactions sets in each owner transaction of a request, and gives NULL when
-- none is set (a pooled connection reads an empty string once an earlier transaction's
-- local setting has ended). The column stays a nullable uuid; no row is backfilled.
ALTER TABLE assistance.job
    ALTER COLUMN origin_request_id
    SET DEFAULT nullif(current_setting('docsuri.request_id', true), '')::uuid;
