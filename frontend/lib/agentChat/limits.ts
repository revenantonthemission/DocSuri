// Shared U13 upload cap — single source for the 10 MiB limit enforced both on
// attachment intake (agentChat/state.ts) and on the PDF upload path
// (lib/api/apiClient.ts). Mirrors the backend contract (USER_DOCMODEL_MAX_BYTES):
// change it here and both client guards move together.
export const MAX_AGENT_UPLOAD_BYTES = 10 * 1024 * 1024;
