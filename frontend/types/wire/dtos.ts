/* DO NOT EDIT. Declared public schema closure, offline. SHA256:20ef1e9e96010afd4c23735c341814725e10be3785d4b7f72ce97ad23079dcf6 */

/**
 * Which rung of the fallback ladder produced this doc-model: native arXiv HTML -> ar5iv -> e-print LaTeX -> (last resort) PDF parse. User-uploaded PDFs also use the "pdf" tier — the user-vs-arXiv origin is carried by the paperId "userdoc:" namespace, not a separate tier. Trace: Q6, BR-29, TD-11.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "DocmodelSourceTier".
 */
export type DocmodelSourceTier = "native_html" | "ar5iv" | "eprint_latex" | "pdf";
/**
 * A content block, discriminated by `type`. Headings are NOT blocks — they are carried by Section.title.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "DocmodelBlock".
 */
export type DocmodelBlock =
  | DocmodelParagraphBlock
  | DocmodelTableBlock
  | DocmodelFormulaBlock
  | DocmodelFigureBlock
  | DocmodelListBlock
  | DocmodelCodeBlock;
/**
 * doc-model contract (DocModel pivot — SSOT spec: aidlc-docs/construction/shared/docmodel.md; gate: construction/plans/docmodel-foundation-pivot-plan.md, D1/D2/D4/D6/D8). The ROOT schema is DocModelResponse — the union (oneOf) returned by getDocModel and branched by U5 ApiClient to surface status (ok | building | license_unavailable | source_unavailable). The bare DocModel artifact (the JSON stored at doc-model/{paperId}/v{version}.json and consumed as the U7 summary input) is defined at #/$defs/DocModel. STATUS: FROZEN for U1 Corpus build v1. Footnotes/references/page numbers are intentionally out of scope; Citation Graph owns structured references and DocModel block ids replace page anchors. Trace: FR-12, FR-17, BR-30, BR-S2.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "DocmodelResponse".
 */
export type DocmodelResponse =
  | DocmodelDocModelResultDTO
  | DocmodelBuildingDTO
  | DocmodelLicenseUnavailableDTO
  | DocmodelSourceUnavailableDTO;
/**
 * 근거 모을 논문 집합 범위(Q4=A 혼합). auto: 질의 주도 자동 검색. explicit: 사용자 명시 paper 집합만. mixed: 자동 검색 + 명시 집합 병합.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "EvidenceEvidenceScope".
 */
export type EvidenceEvidenceScope = "auto" | "explicit" | "mixed";
/**
 * 논문 집합 범위(Q4=A). 생략 시 auto.
 */
export type EvidenceEvidenceScope1 = "auto" | "explicit" | "mixed";
/**
 * U4 문헌탐색·근거형성 Agent 출력 DTO 계약. ROOT = EvidenceResult (터미널 상태 유니온). 페이즈 5(연구아이디어 Agent)가 EvidenceFormationPort.form_evidence() 반환값으로 소비한다 (D5 공유 계약). 근거 출력 깊이(Q3=B): EvidenceItem{ statement, supporting[], conflicting[] } — confidence 제외(FR-5 그라운딩 원칙·환각 위험). 검색 scope(Q4=A): auto|explicit|mixed. 첨부(Q6=A): attachments? 지원. 기권(FR-5/SEC-9): state=abstain + 비기술 abstainReason, 내부 위반 상세 비노출. 생성 산문 금지(C-2): statement 필드는 논문에서 추출한 근거 명제만, 새로운 산문 생성 금지. Producer: U4; Consumer: U12. Trace: Q1, Q2, Q3, Q4, Q6, FR-5, SEC-9, C-2, D5.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "EvidenceResponse".
 */
export type EvidenceResponse = EvidenceEvidenceResult | EvidenceEvidenceAbstainResult;
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedBehaviorEventType".
 */
export type ExtendedBehaviorEventType =
  | "search_executed"
  | "paper_opened"
  | "library_added"
  | "library_removed"
  | "summary_translation_requested"
  | "source_anchor_clicked"
  | "glossary_updated"
  | "read_completed";
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedOnboardingState".
 */
export type ExtendedOnboardingState = "pending" | "completed" | "skipped";
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedLoginProvider".
 */
export type ExtendedLoginProvider = "GOOGLE" | "ORCID" | "EMAIL";
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedDigestCadence".
 */
export type ExtendedDigestCadence = "daily" | "weekly";
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedCitationTreeStatus".
 */
export type ExtendedCitationTreeStatus = "Success" | "Partial" | "Unavailable" | "RateLimited";
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedPlanTier".
 */
export type ExtendedPlanTier = "free" | "plus";
/**
 * Optional. Present when degraded=true to indicate the fallback mode (e.g. lexical-only). Trace: NFR-C1, US-R2, QT-3.
 */
export type SearchDegradationMode = string;
/**
 * Subscription plan tier. Trace: U10.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "MypageSubscriptionPlan".
 */
export type MypageSubscriptionPlan = "FREE" | "PREMIUM";
/**
 * Lifecycle status. NONE = never subscribed. CANCELED = cancellation requested but the PREMIUM benefit is retained through currentPeriodEnd (no immediate cutoff). Trace: U10.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "MypageSubscriptionStatusValue".
 */
export type MypageSubscriptionStatusValue = "NONE" | "ACTIVE" | "CANCELED";
/**
 * Degradation/fallback mode hint (e.g. lexical-only fallback when the cost circuit is OPEN). Provisional type name — SSOT is the field usage in ResultMeta.degradationMode and DegradedResultDTO.mode. Concrete enum values are refined in U2/U6 FD. Trace: NFR-C1, US-R2, QT-3.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "SearchDegradationMode".
 */
export type SearchDegradationMode1 = string;
/**
 * The degradation mode in effect for this response. Trace: NFR-C1, US-R2.
 */
export type SearchDegradationMode2 = string;
/**
 * U2 Discovery/Search DTO contract (dtos.md §1). The ROOT schema describes SearchResponse — the terminal-state union (oneOf) returned by QueryIntakeController.search(request: SearchRequest, ctx) -> SearchResponse and branched by U5 ApiClient.search to surface status (FR-11). All named DTOs (SearchRequest, SearchResultPageDTO, ResultCardVM, ResultMeta, AbstainDTO, DegradedResultDTO, ValidationErrorDTO) are defined in $defs for per-track type generation. 🟡 PROVISIONAL, but card fields are FROZEN-adjacent. Producer: U2; Consumer: U5. Grounding premise (FR-5): every exposed card maps to a real IndexRecord (real arXiv ID/link); U6.GroundingEnforcementHook validates at the response edge — zero fabrication. Internal fields (raw scores, timings, vector/lexicalTerms/chunkId/section) are NOT exposed (SEC-9). Trace: FR-1, FR-3, FR-4, FR-5, FR-11, SEC-5, SEC-9, US-D1..D7.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "SearchResponse".
 */
export type SearchResponse =
  | SearchSearchResultPageDTO
  | SearchAbstainDTO
  | SearchDegradedResultDTO
  | SearchValidationErrorDTO;
/**
 * The specific summarization task: core summary generation or language translation. Trace: FR-12, FR-13.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "SummarizationSummarizeTask".
 */
export type SummarizationSummarizeTask = "summary" | "translate";
/**
 * The scope of source text used: abstract-only or full paper text. Trace: FR-13.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "SummarizationSummarizeScope".
 */
export type SummarizationSummarizeScope = "abstract" | "full";
/**
 * The target persona for summary generation: expert-level or beginner-level. Trace: FR-14.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "SummarizationPersona".
 */
export type SummarizationPersona = "expert" | "beginner";
/**
 * Target type for a grounding anchor reference. Trace: FR-12.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "SummarizationAnchorTarget".
 */
export type SummarizationAnchorTarget = "section" | "table" | "figure";
/**
 * GET /api/papers/{id}/assets terminal union (FR-17). OA-license-gated like full-text (BR-SF-11).
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "SummarizationPaperAssetsResponse".
 */
export type SummarizationPaperAssetsResponse =
  | SummarizationAssetsOkDTO
  | SummarizationAssetsLicenseUnavailableDTO
  | SummarizationAssetsUnauthorizedDTO;
/**
 * U7 Summarization DTO contract. The ROOT schema describes SummaryResponse — the union (oneOf) returned by on-demand actions (FR-12/13/14) and branched by U5 ApiClient to surface status. All named DTOs (SummaryRequest, SummaryResultDTO, SummaryDraft, Anchor, TranslationDraft, PendingDTO, AbstainDTO, CostDegradedDTO, SourceUnavailableDTO) are defined in $defs for type generation.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "SummarizationResponse".
 */
export type SummarizationResponse =
  | SummarizationSummaryResultDTO
  | SummarizationPendingDTO
  | SummarizationAbstainDTO
  | SummarizationCostDegradedDTO
  | SummarizationSourceUnavailableDTO;

export interface PublicWire {}
/**
 * Self-signup input. Source: AccountController.signup(req: SignupRequest, ctx) (component-methods U3). `password` is INPUT-ONLY and NOT logged (SEC-3); policy/breach checks are server-side (PasswordPolicy). Trace: dtos.md §2, FR-7, US-A1, SEC-12.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "AccountsSignupRequest".
 */
export interface AccountsSignupRequest {
  /**
   * Account email (signup identity). Trace: FR-7, US-A1.
   */
  email: string;
  /**
   * INPUT-ONLY plaintext password. NEVER returned in any response and NEVER logged (SEC-12/SEC-3). Policy/breach validation is server-side (PasswordPolicy). Trace: FR-7, SEC-3, SEC-12.
   */
  password: string;
  [k: string]: unknown;
}
/**
 * Signup success response — returns the new account identifier only. No credentials or internal state exposed; conflicts/policy violations surface as generalized errors (409/400/429 — non-normative API-Design hint). Trace: dtos.md §2, FR-7, US-A1, SEC-9.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "AccountsSignupResult".
 */
export interface AccountsSignupResult {
  /**
   * Created account identifier (success identity only). Trace: FR-7, US-A1, SEC-9.
   */
  accountId: unknown;
}
/**
 * Login input. Source: AccountController.login(req: LoginRequest, ctx) (component-methods U3). `password` is INPUT-ONLY and NOT logged. Failures surface as a generalized auth error (401/429 — credential existence not disclosed). Trace: dtos.md §2, FR-7, US-A2, SEC-12.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "AccountsLoginRequest".
 */
export interface AccountsLoginRequest {
  /**
   * Account email (login identity). Trace: FR-7, US-A2.
   */
  email: string;
  /**
   * INPUT-ONLY plaintext password. NEVER returned in any response and NEVER logged (SEC-12/SEC-3). Trace: FR-7, SEC-3, SEC-12.
   */
  password: string;
  [k: string]: unknown;
}
/**
 * currentSession non-sensitive session info (front-end session sync). Source: AccountController.currentSession(ctx) -> HttpResponse<SessionInfo>. Token/credentials/internal handles NOT exposed (SEC-9). NOTE: the session token itself is carried by the secure SessionCookie (transport), NOT by this body DTO. Trace: dtos.md §2, FR-7, US-A2, SEC-9.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "AccountsSessionInfo".
 */
export interface AccountsSessionInfo {
  /**
   * Authenticated user identifier (non-sensitive). Trace: FR-7, US-A2, SEC-9.
   */
  userId: string;
  /**
   * Session expiry instant (serialized as RFC 3339 / ISO 8601 date-time — concrete wire format is API/Infra Design). Trace: FR-7, US-A2.
   */
  expiresAt: string;
}
/**
 * Forgot-password request input (FR-26/BR-A8). Enumeration-safe: the response is identical regardless of account existence/state. `email` only. Public auth input → unknown fields ignored (FR-29/BR-A12). Trace: FR-26, US-A3, SEC-9.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "AccountsPasswordResetRequest".
 */
export interface AccountsPasswordResetRequest {
  /**
   * Account email to send the reset link to. Trace: FR-26, US-A3.
   */
  email: string;
  [k: string]: unknown;
}
/**
 * Forgot-password confirm input (FR-26/BR-A8). Single-use token + new password (re-validated against BR-A1); on success all sessions are invalidated. Public auth input → unknown fields ignored (FR-29/BR-A12). Trace: FR-26, US-A3, SEC-12.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "AccountsPasswordResetConfirm".
 */
export interface AccountsPasswordResetConfirm {
  /**
   * Single-use reset token from the emailed link. INPUT-ONLY, never logged (SEC-3). Trace: FR-26.
   */
  token: string;
  /**
   * INPUT-ONLY new plaintext password; policy/breach validated server-side (PasswordPolicy/BR-A1). Never logged/returned (SEC-3/SEC-12). Trace: FR-26, SEC-12.
   */
  newPassword: string;
  [k: string]: unknown;
}
/**
 * Request to fetch (and lazily build+cache on miss) the doc-model for a paper version. Trace: BR-30 (lazy on-demand + (paperId, version) cache), D6.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "DocmodelDocModelRequest".
 */
export interface DocmodelDocModelRequest {
  /**
   * Source document id — the doc-model cache key together with version. arXiv papers: bare arXiv id (e.g. "2304.10557"). User uploads: "userdoc:{uuid}" namespace — no arXiv id exists, so consumers MUST NOT synthesize an arxiv.org URL from it. Trace: FR-12.
   */
  paperId: string;
  /**
   * Paper version; doc-model cache key is (paperId, version). User uploads are single-version (1). Trace: D6, BR-30.
   */
  version: number;
}
/**
 * Successful response carrying the structured doc-model. Trace: D4 (self rich-view render), BR-S2 (summary input).
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "DocmodelDocModelResultDTO".
 */
export interface DocmodelDocModelResultDTO {
  status: "ok";
  /**
   * True if served from the (paperId, version) cache; false if built on this request (lazy). Trace: D6, BR-30.
   */
  cached?: boolean;
  docModel: DocmodelDocModel;
}
/**
 * The structured paper artifact: fullText plus a nested section tree of typed content blocks. fullText is the complete reading-order text projection of the paper. Tables are DATA (rows/cols), formulas are LaTeX (page-crop image fallback when no LaTeX is recoverable — PDF/GROBID path), figures/table-images are webp references by assetId (pixels are NOT embedded — base64 bloat avoided; reuse assets/{paperId}/{version}/{assetId}.webp). Deterministic: same source HTML -> same DocModel (LLM extraction forbidden). Trace: D1, D8, P7.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "DocmodelDocModel".
 */
export interface DocmodelDocModel {
  meta: DocmodelDocModelMeta;
  /**
   * Complete reading-order text projection of the paper. Includes section titles, paragraphs, table captions/cells, formula LaTeX, figure captions, list items, and code text. Excludes image bytes, base64 payloads, presigned URLs, and internal object refs. Trace: FR-6, FR-18, QT-9.
   */
  fullText: string;
  /**
   * Top-level sections in reading order; each may nest subsections (recursive). The rich-view DocTOC and the summary map-reduce split (P3) both consume this tree. Trace: Q1-decision (nested section tree).
   */
  sections: DocmodelSection[];
}
/**
 * doc-model identity, title/abstract, and provenance.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "DocmodelDocModelMeta".
 */
export interface DocmodelDocModelMeta {
  /**
   * Source document id — the doc-model cache key together with version. arXiv papers: bare arXiv id (e.g. "2304.10557"). User uploads: "userdoc:{uuid}" namespace — no arXiv id exists, so consumers MUST NOT synthesize an arxiv.org URL from it. Trace: FR-12.
   */
  paperId: string;
  /**
   * Paper version; doc-model is keyed (paperId, version). User uploads are single-version (1). Trace: D6.
   */
  version: number;
  /**
   * Paper title (rendered as document title in the rich view).
   */
  title: string;
  /**
   * Optional abstract plain text (translate task uses the abstract directly; rich view shows it). Trace: BR-S2.
   */
  abstract?: string;
  /**
   * Optional KaTeX macro map ("\\name" -> expansion) extracted from the e-print LaTeX preamble (\newcommand / \providecommand / \DeclareMathOperator / \def). The renderer passes it to KaTeX so author-defined commands in formula LaTeX resolve instead of rendering as red unsupported-command errors. Additive/optional — absent when no e-print preamble was available; consumers ignore it if unset. Trace: BR-30, TD-16.
   */
  macros?: {
    [k: string]: string;
  };
  provenance: DocmodelProvenance;
}
/**
 * How this doc-model was produced — for cache invalidation, debugging, and coverage telemetry. No PII (SEC-3).
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "DocmodelProvenance".
 */
export interface DocmodelProvenance {
  sourceTier: DocmodelSourceTier;
  /**
   * Deterministic parser build identifier; bumping it invalidates cached doc-models. Trace: BR-30, TD-16.
   */
  parserVersion: string;
  /**
   * doc-model schema version for additive evolution (consumers ignore unknown fields). Trace: shared/README Versioning.
   */
  schemaVersion: string;
  /**
   * UTC timestamp of generation.
   */
  generatedAt: string;
}
/**
 * A heading-delimited section. `id` is the deterministic anchor handle (see Anchor binding in the spec). Subsections recurse via `sections`. Trace: Q1-decision (nested tree), Q2-decision (block id anchors).
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "DocmodelSection".
 */
export interface DocmodelSection {
  /**
   * Deterministic section id / anchor handle, e.g. "s3", "s3.2". Stable across rebuilds of the same source (P7). Anchor.target may reference this id. Trace: Q2-decision, BR-S7.
   */
  id: string;
  /**
   * Heading text; may be empty when source headings are absent (span-only section). Trace: BR-S3 (section derivation).
   */
  title: string;
  /**
   * Ordered content blocks directly in this section (before any subsection).
   */
  blocks: DocmodelBlock[];
  /**
   * Nested subsections (recursive).
   */
  sections?: DocmodelSection[];
}
/**
 * Body text. Inline mathematics is embedded as LaTeX delimited by \( ... \) within `text` (KaTeX renders it; the summary prompt and agents read the LaTeX verbatim). Trace: D1.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "DocmodelParagraphBlock".
 */
export interface DocmodelParagraphBlock {
  /**
   * Deterministic block id / anchor handle, e.g. "s3.p2". Trace: Q2-decision.
   */
  id: string;
  type: "paragraph";
  /**
   * Paragraph text; may contain inline LaTeX in \( ... \) delimiters. Rendered escaped except for trusted KaTeX (SEC-5).
   */
  text: string;
}
/**
 * A table as STRUCTURED DATA (rows/cols), NOT a cropped image — so table numbers are visible to the summary LLM, grounding numeric-match, and agents (D8). A crop image may be carried in `assetRef` ONLY as a last-resort fallback (e.g. pdf source tier). Trace: D8, TD-12.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "DocmodelTableBlock".
 */
export interface DocmodelTableBlock {
  /**
   * Deterministic block id / anchor handle, e.g. "s3.tbl2". Trace: Q2-decision.
   */
  id: string;
  type: "table";
  /**
   * Table caption text (preserved — a results-number source). Trace: BR-S3 (preserve captions).
   */
  caption?: string;
  /**
   * Human label as it appears in the paper, e.g. "Table 3" — used by the asset-anchor matcher and AnchorChip display. Trace: FR-12.
   */
  anchorLabel?: string;
  /**
   * All rows in order; header rows are marked via cell.isHeader.
   */
  rows: DocmodelTableRow[];
  assetRef?: DocmodelAssetRef;
}
/**
 * A table row.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "DocmodelTableRow".
 */
export interface DocmodelTableRow {
  cells: DocmodelTableCell[];
}
/**
 * A table cell. `text` may contain inline LaTeX in \( ... \) delimiters.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "DocmodelTableCell".
 */
export interface DocmodelTableCell {
  /**
   * Cell content as text (inline LaTeX allowed).
   */
  text: string;
  /**
   * True for header (th) cells.
   */
  isHeader?: boolean;
  /**
   * Column span (default 1).
   */
  colspan?: number;
  /**
   * Row span (default 1).
   */
  rowspan?: number;
}
/**
 * Optional table crop image (page-crop fallback only). The PRIMARY representation is `rows` data; this is a degraded fallback for non-HTML sources. Trace: TD-11 (last-resort), D8.
 */
export interface DocmodelAssetRef {
  /**
   * Deterministic asset id keying assets/{paperId}/{version}/{assetId}.webp and the paper_asset row. Trace: FR-17.
   */
  assetId: string;
  /**
   * Asset kind. "formula" is a page-crop equation image used only as the FormulaBlock fallback when no LaTeX is recoverable (PDF/GROBID path). Trace: FR-17, TD-12.
   */
  type: "figure" | "table" | "formula";
  /**
   * Display order within its type (figure/table). Trace: FR-17.
   */
  ordinal: number;
  /**
   * Caption (mirrors the parent block caption; convenience for asset-only views).
   */
  caption?: string;
  /**
   * How the image was obtained: structured graphic extraction or page-crop fallback. Trace: TD-11/TD-12.
   */
  sourceMode?: "structured" | "page-crop";
}
/**
 * A display (block-level) equation. LaTeX is preferred (KaTeX renders it; agents read it verbatim and it is indexed for search). When the source carries no recoverable LaTeX (the PDF/GROBID path: a formula is rendered pixels, not LaTeX source) the equation degrades to a page-crop image via `assetRef` — display-only, not searchable. Exactly one of `latex` / `assetRef` is the render source; `latex` wins when both are present. Inline math lives in ParagraphBlock.text instead. Trace: D1, TD-16.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "DocmodelFormulaBlock".
 */
export interface DocmodelFormulaBlock {
  /**
   * Deterministic block id / anchor handle, e.g. "s3.eq2". Trace: Q2-decision.
   */
  id: string;
  type: "formula";
  /**
   * LaTeX (converted from source MathML when needed; HTML-borne <math> coverage ~94% per Q1 spike). Rendered by KaTeX/MathJax. Absent on the PDF/GROBID path when no LaTeX is recoverable — `assetRef` carries the image instead. Trace: D1, TD-16.
   */
  latex?: string;
  assetRef?: DocmodelAssetRef1;
  /**
   * Always true for a FormulaBlock (display/block equation); present for renderer clarity.
   */
  display?: boolean;
  /**
   * Equation number as in the paper, e.g. "(3)".
   */
  anchorLabel?: string;
  /**
   * Optional original MathML, retained for fidelity/debugging.
   */
  mathmlSource?: string;
}
/**
 * Page-crop image fallback for a formula with no recoverable LaTeX (PDF/GROBID path). assetRef.type is "formula". Display-only — not indexed for search. Trace: FR-17, TD-12.
 */
export interface DocmodelAssetRef1 {
  /**
   * Deterministic asset id keying assets/{paperId}/{version}/{assetId}.webp and the paper_asset row. Trace: FR-17.
   */
  assetId: string;
  /**
   * Asset kind. "formula" is a page-crop equation image used only as the FormulaBlock fallback when no LaTeX is recoverable (PDF/GROBID path). Trace: FR-17, TD-12.
   */
  type: "figure" | "table" | "formula";
  /**
   * Display order within its type (figure/table). Trace: FR-17.
   */
  ordinal: number;
  /**
   * Caption (mirrors the parent block caption; convenience for asset-only views).
   */
  caption?: string;
  /**
   * How the image was obtained: structured graphic extraction or page-crop fallback. Trace: TD-11/TD-12.
   */
  sourceMode?: "structured" | "page-crop";
}
/**
 * A figure: a webp image referenced by assetId (pixels reused from the FR-17 assets pipeline; reuses U5 AssetGallery + asset-anchor matcher for render). Trace: FR-17, D5.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "DocmodelFigureBlock".
 */
export interface DocmodelFigureBlock {
  /**
   * Deterministic block id / anchor handle, e.g. "s3.fig1". Trace: Q2-decision.
   */
  id: string;
  type: "figure";
  assetRef: DocmodelAssetRef2;
  /**
   * Figure caption text (preserved). Trace: BR-S3.
   */
  caption?: string;
  /**
   * Human label, e.g. "Figure 2" — used by the asset-anchor matcher. Trace: FR-12.
   */
  anchorLabel?: string;
}
/**
 * A REFERENCE to a stored image asset — assetId, not pixels and not an object_ref. The read API (GET /api/papers/{id}/assets) returns a same-origin delivery path at read time; the doc-model artifact never stores the URL or object_ref (SEC-9, REM-2 F07). Mirrors the existing AssetRef in summarization.schema.json minus the runtime-only `url`. Trace: FR-17, SEC-9, D8/D5.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "DocmodelAssetRef".
 */
export interface DocmodelAssetRef2 {
  /**
   * Deterministic asset id keying assets/{paperId}/{version}/{assetId}.webp and the paper_asset row. Trace: FR-17.
   */
  assetId: string;
  /**
   * Asset kind. "formula" is a page-crop equation image used only as the FormulaBlock fallback when no LaTeX is recoverable (PDF/GROBID path). Trace: FR-17, TD-12.
   */
  type: "figure" | "table" | "formula";
  /**
   * Display order within its type (figure/table). Trace: FR-17.
   */
  ordinal: number;
  /**
   * Caption (mirrors the parent block caption; convenience for asset-only views).
   */
  caption?: string;
  /**
   * How the image was obtained: structured graphic extraction or page-crop fallback. Trace: TD-11/TD-12.
   */
  sourceMode?: "structured" | "page-crop";
}
/**
 * An ordered or unordered list. Nested lists are an additive future extension.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "DocmodelListBlock".
 */
export interface DocmodelListBlock {
  /**
   * Deterministic block id, e.g. "s3.list1".
   */
  id: string;
  type: "list";
  /**
   * True for an ordered (numbered) list.
   */
  ordered: boolean;
  items: DocmodelListItem[];
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "DocmodelListItem".
 */
export interface DocmodelListItem {
  /**
   * List item text; inline LaTeX allowed in \( ... \) delimiters.
   */
  text: string;
}
/**
 * A verbatim/code/algorithm block (rendered monospace, not interpreted).
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "DocmodelCodeBlock".
 */
export interface DocmodelCodeBlock {
  /**
   * Deterministic block id, e.g. "s3.code1".
   */
  id: string;
  type: "code";
  /**
   * Verbatim text.
   */
  text: string;
  /**
   * Optional language hint.
   */
  language?: string;
}
/**
 * The doc-model is being built asynchronously (lazy on-demand, D6/BR-30): a cache miss enqueued a build job and the client should poll getDocModel again after retryAfterMs. Distinct from source_unavailable (a build that ran and failed every source tier) — building is transient/in-flight. Trace: BR-30, BR-S8 (async job), D6.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "DocmodelBuildingDTO".
 */
export interface DocmodelBuildingDTO {
  status: "building";
  /**
   * Suggested client poll backoff in milliseconds before re-requesting.
   */
  retryAfterMs?: number;
}
/**
 * OA license does not permit in-app rich rendering of this paper; client links out to arXiv instead. Trace: BR-SF-11, SEC-9.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "DocmodelLicenseUnavailableDTO".
 */
export interface DocmodelLicenseUnavailableDTO {
  status: "license_unavailable";
  /**
   * Non-technical reason for the license gate (display copy).
   */
  reason?: string;
  /**
   * Safe arXiv link-out target (http/https). Trace: BR-U5-7.
   */
  arxivUrl?: string;
}
/**
 * doc-model could not be produced from any source tier (HTML/ar5iv/e-print/PDF all failed). Trace: Q6 fallback ladder.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "DocmodelSourceUnavailableDTO".
 */
export interface DocmodelSourceUnavailableDTO {
  status: "source_unavailable";
  /**
   * Non-technical reason (display copy).
   */
  reason?: string;
}
/**
 * 단일 출처 핸들 — 기존 계약 재사용. paperId = IndexRecord.arxivId(vector-spec §2). 사용자 업로드 문서는 paperId="userdoc:{uuid}", recordRef="upload:{ownerId}:{jobId}:{attachmentId}" — 실재 arXiv id가 없으므로 arxiv.org URL 조립 금지(무날조). recordRef = IndexRecord 식별자(실재성 검증 핸들). anchor = DocModel Section/Block id(summarization AnchorTarget 동일 방식). quote = 원문 스니펫(근거 인용, 선택). 내부 벡터/청크/점수 미노출(SEC-9). Trace: FR-5, SEC-9, vector-spec §2, summarization.schema.json AnchorTarget.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "EvidenceSourceRef".
 */
export interface EvidenceSourceRef {
  /**
   * 출처 문서 id. arXiv: 표시용 arXiv ID(버전 포함 가능, Source: IndexRecord.arxivId). 사용자 업로드: "userdoc:{uuid}" 네임스페이스 — 실재 arXiv id 없음, arxiv.org URL 조립 금지(무날조). Trace: FR-5, vector-spec §2.
   */
  paperId: string;
  /**
   * IndexRecord 식별자(실재성 검증 핸들). 사용자 업로드: "upload:{ownerId}:{jobId}:{attachmentId}". 내부 벡터·청크 정보 미포함. Trace: FR-5, vector-spec §2.
   */
  recordRef: string;
  /**
   * DocModel Section/Block 결정적 id(선택). 요약 AnchorTarget 계약과 동일 방식. Trace: summarization.schema.json.
   */
  anchor?: string;
  /**
   * 원문 인용 스니펫(선택, 추출 근거 표시용). 생성 산문 금지(C-2) — 논문 원문만.
   */
  quote?: string;
}
/**
 * 단일 근거 명제 + 지지/상충 출처(Q3=B). statement = 논문에서 추출한 근거 명제(핵심 주장·방법·결과 수치·한계 — Q1=A). supporting = 명제를 지지하는 출처. conflicting = 명제와 상충하는 출처(페이즈 5 novelty 판단 입력). confidence 제외(FR-5 그라운딩·환각 위험 — Q3=B). 생성 산문 금지(C-2). Trace: Q1, Q3, FR-5, C-2, D5.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "EvidenceEvidenceItem".
 */
export interface EvidenceEvidenceItem {
  /**
   * 추출된 근거 명제(핵심 주장·방법·결과 수치·한계). 생성 산문 금지 — 논문 기반 추출만(C-2, FR-5).
   */
  statement: string;
  /**
   * 명제를 지지하는 출처 목록. Trace: FR-5.
   */
  supporting: EvidenceSourceRef[];
  /**
   * 명제와 상충하는 출처 목록(페이즈 5 novelty 판단 입력). 빈 배열 = 상충 없음. Trace: D5.
   */
  conflicting: EvidenceSourceRef[];
}
/**
 * 표시 전용 웹 레퍼런스(U11 웹레퍼런스 확장 §4, FR-49). SourceRef가 아니며 claims의 supporting/conflicting과 무관 — 링크백 전용 프로바이더 메타만(C-11: 본문·초록 저장 금지, web: 네임스페이스 신설 없음). 프로바이더 반환 URL/DOI 원본만(BR-WR4 무날조 — 조립·생성 금지). Trace: FR-49, C-11, US-WR1, BR-WR1, BR-WR4.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "EvidenceWebReferenceRef".
 */
export interface EvidenceWebReferenceRef {
  /**
   * 프로바이더가 반환한 논문 제목(표시용). Trace: FR-49.
   */
  title: string;
  /**
   * 프로바이더 반환 원본 URL — https·허용 호스트 검증 통과분만, 조립 금지(BR-WR4). Trace: BR-WR4.
   */
  url: string;
  /**
   * 프로바이더 반환 DOI(선택, dedupe 키·표시용). Trace: BR-WR4.
   */
  doi?: string;
  /**
   * 표시용 상위 저자 몇 명(선택). Trace: FR-49.
   */
  authors?: string[];
  /**
   * 출판 연도(선택, 표시용). Trace: FR-49.
   */
  year?: number;
  /**
   * 출처 프로바이더 식별자: semantic_scholar | openalex. Trace: FR-49.
   */
  source: string;
}
/**
 * 근거형성에 사용된 논문·쿼리 요약 메타(투명성). 내부 점수·타이밍 미노출(SEC-9).
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "EvidenceEvidenceCoverage".
 */
export interface EvidenceEvidenceCoverage {
  /**
   * 근거 추출에 사용된 논문 수.
   */
  paperCount: number;
  /**
   * 자동 검색 시 사용된 쿼리(auto·mixed scope). explicit scope이면 생략.
   */
  queryUsed?: string;
}
/**
 * 근거형성 성공 산출(state=ok). claims = 추출된 근거 명제 목록(Q2=A 논문 비교형 + 쟁점 오버레이의 데이터 기반). coverage = 사용 논문·쿼리 요약. answer = claims를 대화체로 풀어 쓴 요약(전적으로 claims/quote에서만 구성 — 새 사실 도입 금지, C-2 동일 적용). Trace: Q2, FR-5, D5.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "EvidenceEvidenceResult".
 */
export interface EvidenceEvidenceResult {
  /**
   * ok 고정(성공). Trace: FR-5.
   */
  state: "ok";
  /**
   * 추출된 근거 명제 목록. 각 항목은 EvidenceItem{ statement, supporting[], conflicting[] }. Trace: Q1, Q3.
   */
  claims: EvidenceEvidenceItem[];
  coverage: EvidenceEvidenceCoverage1;
  /**
   * claims를 대화체 한국어 문단으로 풀어 쓴 요약. 오직 claims[].statement/supporting/conflicting에서만 조립되며 새 사실을 도입하지 않는다(C-2 동일 적용 — 생성 산문 금지 원칙은 '새 사실 금지'이지 '요약 표현 금지'가 아니다). 하위호환을 위해 선택 필드.
   */
  answer?: string | null;
  /**
   * 표시 전용 웹 레퍼런스 목록(선택 — U11 웹레퍼런스 확장 §4). LLM 추출 완료 후 post-hoc으로만 동봉되며 프롬프트·추출 입력에 절대 불포함(BR-WR2). 실패·타임아웃·0건이면 생략 — 턴 결과 불변(BR-WR5). 하위호환: optional — 기존 저장 결과·구 클라이언트 무영향. Trace: FR-49, C-11, US-WR1, BR-WR2, BR-WR5.
   */
  webReferences?: EvidenceWebReferenceRef[];
}
/**
 * 사용 논문 수·쿼리 요약. Trace: SEC-9.
 */
export interface EvidenceEvidenceCoverage1 {
  /**
   * 근거 추출에 사용된 논문 수.
   */
  paperCount: number;
  /**
   * 자동 검색 시 사용된 쿼리(auto·mixed scope). explicit scope이면 생략.
   */
  queryUsed?: string;
}
/**
 * 근거 부족·범위 밖 기권(state=abstain). 날조 대신 기권(FR-5). abstainReason = 비기술 사유만(내부 위반 상세 비노출 — SEC-9). Trace: FR-5, SEC-9, C-2.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "EvidenceEvidenceAbstainResult".
 */
export interface EvidenceEvidenceAbstainResult {
  /**
   * abstain 고정. Trace: FR-5.
   */
  state: "abstain";
  /**
   * 비기술 기권 사유(내부 위반 상세·점수 비노출 — SEC-9). 예: out_of_corpus, insufficient_evidence.
   */
  abstainReason: string;
}
/**
 * 근거형성 입력. topic = 연구 주제·질문. scope = 논문 집합 범위(Q4=A 혼합). paperIds = explicit·mixed scope 시 사용자 명시 paper 집합. attachments = 사용자 첨부(Q6=A, doc-model 파이프라인 재사용). constraints = 기간·분야·논문 수 제한(상세는 FD 이월). Trace: Q4, Q6.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "EvidenceEvidenceRequest".
 */
export interface EvidenceEvidenceRequest {
  /**
   * 연구 주제 또는 근거형성 질문. Trace: FR-1, SEC-5.
   */
  topic: string;
  scope?: EvidenceEvidenceScope1;
  /**
   * explicit·mixed scope 시 사용자 명시 arXiv ID 목록. auto scope이면 무시.
   */
  paperIds?: string[];
  /**
   * 사용자 첨부 문서 핸들 목록(Q6=A, doc-model 파이프라인 재사용). 형식·크기 한도는 FD 이월.
   */
  attachments?: string[];
  /**
   * PROVISIONAL — 기간·분야·최대 논문수 제한. 상세 형태는 FD 이월.
   */
  constraints?: {
    [k: string]: unknown;
  };
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedGlossaryTermUpsertDTO".
 */
export interface ExtendedGlossaryTermUpsertDTO {
  termFrom: string;
  termTo: string;
  promptEnforced?: boolean;
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedGlossaryUpsertResultDTO".
 */
export interface ExtendedGlossaryUpsertResultDTO {
  status: "ok";
  glossaryVer: number;
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedGlossaryTermDTO".
 */
export interface ExtendedGlossaryTermDTO {
  termFrom: string;
  termTo: string;
  promptEnforced?: boolean;
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedGlossaryListDTO".
 */
export interface ExtendedGlossaryListDTO {
  status: "ok";
  terms: ExtendedGlossaryTermDTO[];
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedBehaviorSubject".
 */
export interface ExtendedBehaviorSubject {
  kind: "paper" | "search" | "summary" | "translation" | "source_anchor" | "glossary";
  paperId?: string;
  queryHash?: string;
  category?: string;
  anchorId?: string;
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedBehaviorEventCreate".
 */
export interface ExtendedBehaviorEventCreate {
  eventType: ExtendedBehaviorEventType;
  subject: ExtendedBehaviorSubject;
  occurredAt?: string;
  source?: "backend" | "frontend_anchor";
  metadata?: {
    [k: string]: unknown;
  };
  dedupeKey: string;
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedEventRecordResult".
 */
export interface ExtendedEventRecordResult {
  recorded: boolean;
  duplicate: boolean;
  reason: "recorded" | "duplicate" | "disabled" | "degraded";
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedPersonalizationSettings".
 */
export interface ExtendedPersonalizationSettings {
  userId: string;
  enabled: boolean;
  rawEventsDeletedAt?: string | null;
  profileResetAt?: string | null;
  updatedAt: string;
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedDeletePersonalizationEventsResult".
 */
export interface ExtendedDeletePersonalizationEventsResult {
  deletedEvents: number;
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedResetPersonalizationProfileResult".
 */
export interface ExtendedResetPersonalizationProfileResult {
  status: "reset";
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedOnboardingStatusResponse".
 */
export interface ExtendedOnboardingStatusResponse {
  state: ExtendedOnboardingState;
  categories: string[];
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedInterestSelectionCreate".
 */
export interface ExtendedInterestSelectionCreate {
  categories: string[];
  keywords: string[];
  source: "onboarding_picker" | "orcid_derived";
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedInterestsResult".
 */
export interface ExtendedInterestsResult {
  state: ExtendedOnboardingState;
  eventRecorded: boolean;
  reason: "recorded" | "duplicate" | "disabled" | "degraded";
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedSkipResult".
 */
export interface ExtendedSkipResult {
  state: ExtendedOnboardingState;
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedOrcidSuggestion".
 */
export interface ExtendedOrcidSuggestion {
  kind: "category" | "keyword";
  value: string;
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedOrcidSuggestionsResponse".
 */
export interface ExtendedOrcidSuggestionsResponse {
  suggestions: ExtendedOrcidSuggestion[];
  degraded: boolean;
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedAccountProfileVM".
 */
export interface ExtendedAccountProfileVM {
  loginProvider: ExtendedLoginProvider;
  createdAt: string;
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedOrcidWorkVM".
 */
export interface ExtendedOrcidWorkVM {
  title: string;
  year: number | null;
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedOrcidProfileVM".
 */
export interface ExtendedOrcidProfileVM {
  orcidId: string;
  name: string;
  affiliation: string | null;
  works: ExtendedOrcidWorkVM[];
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedRecentlyViewedItemVM".
 */
export interface ExtendedRecentlyViewedItemVM {
  arxivId: string;
  title: string;
  viewedAt: string;
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedConsentSettingsVM".
 */
export interface ExtendedConsentSettingsVM {
  privacyPolicyAgreed: boolean;
  termsOfServiceAgreed: boolean;
  nightlyPushAgreed: boolean;
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedFollowedTopicVM".
 */
export interface ExtendedFollowedTopicVM {
  id: string;
  topic: string;
  createdAt: string;
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedFollowListVM".
 */
export interface ExtendedFollowListVM {
  topics: ExtendedFollowedTopicVM[];
  maxTopics: number;
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedDigestSettingsVM".
 */
export interface ExtendedDigestSettingsVM {
  optedIn: boolean;
  cadence: ExtendedDigestCadence;
  lastSentAt: string | null;
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedUnsubscribeResultVM".
 */
export interface ExtendedUnsubscribeResultVM {
  optedIn: boolean;
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedCitationNode".
 */
export interface ExtendedCitationNode {
  nodeId: string;
  title: string;
  year?: number | null;
  citationCount?: number | null;
  depth: number;
  arxivId?: string | null;
  url?: string | null;
  inCorpus?: boolean;
  saveable: boolean;
  alreadyShown: boolean;
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedCitationEdge".
 */
export interface ExtendedCitationEdge {
  source: string;
  target: string;
  depth: number;
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedUnresolvedCitation".
 */
export interface ExtendedUnresolvedCitation {
  title: string;
  year?: number | null;
  reason: string;
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedCitationTreeResponse".
 */
export interface ExtendedCitationTreeResponse {
  status: ExtendedCitationTreeStatus;
  rootPaperId: string;
  nodes: ExtendedCitationNode[];
  edges: ExtendedCitationEdge[];
  unresolved: ExtendedUnresolvedCitation[];
  depthReturned: number;
  truncated: boolean;
  remainingEstimate?: number | null;
  cacheHit: boolean;
  providerStatus: string;
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedCitationTreeQuery".
 */
export interface ExtendedCitationTreeQuery {
  expandNodeId?: string;
  refresh?: boolean;
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedPlanQuotasVM".
 */
export interface ExtendedPlanQuotasVM {
  evidenceDaily: number;
  noveltyDaily: number;
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedMyPlanVM".
 */
export interface ExtendedMyPlanVM {
  tier: ExtendedPlanTier;
  quotas: ExtendedPlanQuotasVM;
  expiresAt?: string;
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedPaperMetaVM".
 */
export interface ExtendedPaperMetaVM {
  arxivId: string;
  title: string;
  authors: string[];
  year?: number;
  abstract: string;
  arxivUrl?: string;
  sourceName?: string;
  sourceUrl?: string;
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedBackendResearchJob".
 */
export interface ExtendedBackendResearchJob {
  jobId: string;
  title: string;
  state: "active" | "completed" | "failed" | "cancelled";
  updatedAt: string;
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedBackendResearchMessage".
 */
export interface ExtendedBackendResearchMessage {
  messageId: string;
  role: "user" | "assistant" | "system";
  content: string;
  attachments?: unknown[];
  createdAt: string;
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedBackendNoveltyJob".
 */
export interface ExtendedBackendNoveltyJob {
  jobId: string;
  topic: string;
  state: string;
  updatedAt: string;
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedBackendNoveltyMessage".
 */
export interface ExtendedBackendNoveltyMessage {
  messageId: string;
  role: "user" | "assistant" | "system";
  content: string;
  attachments?: unknown[];
  createdAt: string;
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedBackendNoveltyEvent".
 */
export interface ExtendedBackendNoveltyEvent {
  eventId: string;
  state: string;
  message: string;
  payload?: {
    [k: string]: unknown;
  };
  createdAt: string;
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedBackendNoveltyArtifact".
 */
export interface ExtendedBackendNoveltyArtifact {
  artifactId: string;
  kind: string;
  title: string;
  payload?: {
    [k: string]: unknown;
  };
  createdAt: string;
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedNotionConnectionStatusVM".
 */
export interface ExtendedNotionConnectionStatusVM {
  connected: boolean;
  parentPageId?: string | null;
  updatedAt?: string | null;
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedNotionExportVM".
 */
export interface ExtendedNotionExportVM {
  status: string;
  notionPageId?: string | null;
  errorMessage?: string | null;
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedNotionExportPreviewVM".
 */
export interface ExtendedNotionExportPreviewVM {
  export: ExtendedNotionExportVM;
  preview: {
    title: string;
    artifacts: {
      kind: string;
      title: string;
    }[];
  };
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedSummarizeValidationErrorDTO".
 */
export interface ExtendedSummarizeValidationErrorDTO {
  status: "validation_error";
  field?: string;
  message: string;
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedUnauthorizedDTO".
 */
export interface ExtendedUnauthorizedDTO {
  status: "unauthorized";
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedJobAcceptedDTO".
 */
export interface ExtendedJobAcceptedDTO {
  jobId: string;
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedAgentJobsDTO".
 */
export interface ExtendedAgentJobsDTO {
  jobs?: (ExtendedBackendResearchJob | ExtendedBackendNoveltyJob)[];
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedResearchJobDTO".
 */
export interface ExtendedResearchJobDTO {
  job: ExtendedBackendResearchJob;
  messages?: ExtendedBackendResearchMessage[];
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedNoveltyJobDTO".
 */
export interface ExtendedNoveltyJobDTO {
  job: ExtendedBackendNoveltyJob;
  events?: ExtendedBackendNoveltyEvent[];
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedNoveltyMessagesDTO".
 */
export interface ExtendedNoveltyMessagesDTO {
  messages?: ExtendedBackendNoveltyMessage[];
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedNoveltyArtifactsDTO".
 */
export interface ExtendedNoveltyArtifactsDTO {
  artifacts?: ExtendedBackendNoveltyArtifact[];
}
/**
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "ExtendedRecentlyViewedDTO".
 */
export interface ExtendedRecentlyViewedDTO {
  items: ExtendedRecentlyViewedItemVM[];
}
/**
 * Cursor-based pagination input common to all collection queries. Source: component-methods U4. Trace: dtos.md §3, FR-8, FR-9, FR-10.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "LibraryPageParams".
 */
export interface LibraryPageParams {
  /**
   * Page size (>= 1; a page of 0 or fewer is meaningless). The upper bound (max page size) is set in U4 FD. Trace: FR-8, FR-9, FR-10.
   */
  limit: number;
  /**
   * Optional. Opaque pagination cursor (continuation token); ABSENT on the first-page request and supplied from the previous page's nextCursor (symmetric with the optional nextCursor in the page DTOs). Exact semantics refined in U4 FD. Trace: FR-8, FR-9, FR-10.
   */
  cursor?: string;
}
/**
 * New saved-search input. owner is server-determined from the session context (NOT in the body, SEC-8). Trace: dtos.md §3, FR-8, US-L1.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "LibrarySavedSearchCreateDTO".
 */
export interface LibrarySavedSearchCreateDTO {
  /**
   * Search query to save. Trace: FR-8, US-L1.
   */
  query: string;
  /**
   * Optional user label for the saved search. Trace: FR-8, US-L1.
   */
  label?: string;
}
/**
 * Single saved search (owner userId NOT exposed, SEC-9). Trace: dtos.md §3, FR-8, US-L1, SEC-9.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "LibrarySavedSearchDTO".
 */
export interface LibrarySavedSearchDTO {
  /**
   * Saved-search identifier. Trace: FR-8, US-L1.
   */
  id: unknown;
  /**
   * Saved query string. Trace: FR-8, US-L1.
   */
  query: string;
  /**
   * Optional user label. Trace: FR-8, US-L1.
   */
  label?: string;
  /**
   * Creation instant (serialized as RFC 3339 / ISO 8601 date-time — concrete wire format is API/Infra Design). Trace: FR-8, US-L1.
   */
  createdAt: string;
}
/**
 * Page of the user's saved searches, most-recent first (owner-scoped server-side). Trace: dtos.md §3, FR-8, US-L1.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "LibrarySavedSearchPageDTO".
 */
export interface LibrarySavedSearchPageDTO {
  /**
   * Saved searches in this page. Trace: FR-8, US-L1.
   */
  items: LibrarySavedSearchDTO[];
  /**
   * Optional. Continuation cursor for the next page (absent on the last page). Trace: FR-8, US-L1.
   */
  nextCursor?: string;
}
/**
 * Idempotent library-add input. (userId, arXivId) is idempotent server-side. Meta snapshot is preserved (NOT dependent on U2/index availability). owner NOT in the body (SEC-8). Trace: dtos.md §3, FR-9, US-L2.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "LibraryLibraryItemCreateDTO".
 */
export interface LibraryLibraryItemCreateDTO {
  /**
   * arXiv ID of the paper to add (field name per dtos.md §3; display arXiv ID, may include version). Trace: FR-9, US-L2.
   */
  arXivId: string;
  /**
   * Metadata snapshot captured at add time (preserved independent of the live index, availability isolation). Shape refined in U4 FD. Trace: FR-9, US-L2.
   */
  meta: unknown;
}
/**
 * Single library item (owner userId NOT exposed, SEC-9). Idempotent add returns the same shape whether new or existing. Trace: dtos.md §3, FR-9, US-L2, SEC-9.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "LibraryLibraryItemDTO".
 */
export interface LibraryLibraryItemDTO {
  /**
   * Library-item identifier. Trace: FR-9, US-L2.
   */
  id: unknown;
  /**
   * arXiv ID (field name per dtos.md §3; display arXiv ID, may include version). Trace: FR-9, US-L2.
   */
  arXivId: string;
  /**
   * Preserved metadata snapshot (returned as captured; availability isolation). Shape refined in U4 FD. Trace: FR-9, US-L2.
   */
  meta: unknown;
  /**
   * Add instant (serialized as RFC 3339 / ISO 8601 date-time — concrete wire format is API/Infra Design). Trace: FR-9, US-L2.
   */
  addedAt: string;
}
/**
 * Page of the user's library (owner-scoped server-side). Returns preserved meta snapshots only (availability isolation). Trace: dtos.md §3, FR-9, US-L2.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "LibraryLibraryPageDTO".
 */
export interface LibraryLibraryPageDTO {
  /**
   * Library items in this page. Trace: FR-9, US-L2.
   */
  items: LibraryLibraryItemDTO[];
  /**
   * Optional. Continuation cursor for the next page (absent on the last page). Trace: FR-9, US-L2.
   */
  nextCursor?: string;
}
/**
 * Single search-history entry (source: SearchExecutedEvent async record; owner userId NOT exposed, SEC-9). Trace: dtos.md §3, FR-10, US-L3, SEC-9.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "LibraryHistoryEntry".
 */
export interface LibraryHistoryEntry {
  /**
   * History-entry identifier. Trace: FR-10, US-L3.
   */
  id: unknown;
  /**
   * Executed query string. Trace: FR-10, US-L3.
   */
  query: string;
  /**
   * Search execution instant (serialized as RFC 3339 / ISO 8601 date-time — concrete wire format is API/Infra Design). Source maps to SearchExecutedEvent.timestamp. Trace: FR-10, US-L3.
   */
  executedAt: string;
  /**
   * Number of results returned for this search (int). Source maps to SearchExecutedEvent.resultCount. Trace: FR-10, US-L3.
   */
  resultCount: number;
}
/**
 * Page of recent search history, most-recent first (owner-scoped server-side). Trace: dtos.md §3, FR-10, US-L3.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "LibraryHistoryPageDTO".
 */
export interface LibraryHistoryPageDTO {
  /**
   * History entries in this page. Trace: FR-10, US-L3.
   */
  items: LibraryHistoryEntry[];
  /**
   * Optional. Continuation cursor for the next page (absent on the last page). Trace: FR-10, US-L3.
   */
  nextCursor?: string;
}
/**
 * Saved-search / history RERUN result. Surfaces a gateway-fronted search (U6.ApiGatewayMiddleware -> U2) as the §1 search card DTO — REUSES the SearchResultPageDTO shape from search.schema.json (NOT a direct U2 call). Trace: dtos.md §3, FR-8, FR-10, US-L1, US-L3.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "LibrarySearchResultSetDTO".
 */
export interface LibrarySearchResultSetDTO {
  /**
   * Result cards in ranking order. Trace: FR-3, FR-4, PBT-03.
   */
  cards: SearchResultCardVM[];
  meta: SearchResultMeta;
}
/**
 * Single-paper phone card view-model. Consumed by U5 ResultCard.render(card). The 6 fields title/authors/year/arxivId/abstractSnippet/arxivUrl are the external-exposure PROJECTION of vector-spec.md §2 IndexRecord card fields (FR-4), 1:1, and are NOT added/removed without an IndexRecord change (FROZEN-adjacent). `relevance` does NOT belong to IndexRecord — it is a display-only value derived from ranking (raw scores NOT exposed, SEC-9). Internal IndexRecord fields (vector, lexicalTerms, chunkId, section, categories) are NOT exposed on the card (SEC-9). Phase 2 (Q2): the card additively exposes source-neutral `sourceName`/`sourceUrl` (derived from IndexRecord.sourceProvenance; the arXiv path keeps arxivId/arxivUrl). Internal `blockRefs`/`sourceProvenance` themselves stay unexposed (Q3). Trace: dtos.md §1.1, FR-4, FR-5.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "SearchResultCardVM".
 */
export interface SearchResultCardVM {
  /**
   * Paper title. Source: IndexRecord.title (vector-spec.md §2). Trace: FR-4.
   */
  title: string;
  /**
   * Authors. Source: IndexRecord.authors (vector-spec.md §2). Trace: FR-4.
   */
  authors: string[];
  /**
   * Publication year. Source: IndexRecord.year (vector-spec.md §2). Trace: FR-4.
   */
  year: number;
  /**
   * Display arXiv ID (may include version). Source: IndexRecord.arxivId (vector-spec.md §2). Trace: FR-4.
   */
  arxivId: string;
  /**
   * Card abstract snippet, derived from the full IndexRecord.abstract (the full abstract is NOT exposed — snippet only). Source: IndexRecord.abstractSnippet (vector-spec.md §2). Trace: FR-4, FR-5.
   */
  abstractSnippet: string;
  /**
   * Display-only relevance (ranking order / display grade, derived). Internal raw scores and debug signals are NOT exposed (SEC-9). NOT an IndexRecord field. Display type is refined in U2 FD. Trace: FR-3, FR-4, SEC-9.
   */
  relevance: unknown;
  /**
   * Resolvable real link (FR-5 grounding — no fabrication; arXiv path). Source: IndexRecord.arxivUrl (vector-spec.md §2). Trace: FR-4, FR-5.
   */
  arxivUrl: string;
  /**
   * Phase 2 (Q2). Source label for the multi-source corpus (arXiv / Semantic Scholar / OpenAlex). Derived from IndexRecord.sourceProvenance.sourceName; defaults to "arXiv" for legacy/arXiv-only records. Optional (additive, backward-compatible) but always populated by the assembler. Trace: FR-4, FR-5.
   */
  sourceName?: string;
  /**
   * Phase 2 (Q2). Source-neutral resolvable real link (FR-5 grounding — no fabrication): arXiv = arxivUrl, non-arXiv = sourceProvenance.sourceUrl / DOI. Optional (additive) but always populated by the assembler. Trace: FR-4, FR-5.
   */
  sourceUrl?: string;
}
/**
 * Result metadata (count, degradation hints). Trace: FR-11.
 */
export interface SearchResultMeta {
  /**
   * Number of results returned (int). Trace: FR-11.
   */
  resultCount: number;
  /**
   * Degraded-result banner hint (true when results came from a degraded/fallback path). Trace: FR-11, QT-3.
   */
  degraded: boolean;
  degradationMode?: SearchDegradationMode;
  /**
   * Optional (additive, backward-compatible). True when the US-P4 personalization re-rank actually boosted this page's order for the requesting user (SEARCH_RERANK_LIVE gate on AND profile boosts matched the top band). Absent/false = baseline order (no profile, 맞춤 서비스 off, shadow mode, or fail-soft). U5 shows the '내 관심 주제 반영' indicator with an off entry point (설정 킬스위치) when true. Trace: US-P4 (#155), BR-P8, BR-P13.
   */
  personalized?: boolean;
}
/**
 * Current subscription snapshot (owner userId NOT exposed, SEC-9). Mock-only — no real PG/billing behind this. Trace: U10.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "MypageSubscriptionDTO".
 */
export interface MypageSubscriptionDTO {
  plan: MypageSubscriptionPlan;
  status: MypageSubscriptionStatusValue;
  /**
   * Subscription start instant. Absent when status=NONE. Trace: U10.
   */
  startedAt?: string;
  /**
   * Current mock billing-period end. The PREMIUM benefit remains active through this instant even after cancellation (no immediate cutoff). Absent when status=NONE. Trace: U10.
   */
  currentPeriodEnd?: string;
  /**
   * Cancellation-request instant. Present only once a cancellation has been requested. Trace: U10.
   */
  canceledAt?: string;
}
/**
 * Result-count and degradation banner hints. Internal scores/timings NOT exposed (SEC-9). Trace: dtos.md §1, FR-11, QT-3.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "SearchResultMeta".
 */
export interface SearchResultMeta1 {
  /**
   * Number of results returned (int). Trace: FR-11.
   */
  resultCount: number;
  /**
   * Degraded-result banner hint (true when results came from a degraded/fallback path). Trace: FR-11, QT-3.
   */
  degraded: boolean;
  degradationMode?: SearchDegradationMode;
  /**
   * Optional (additive, backward-compatible). True when the US-P4 personalization re-rank actually boosted this page's order for the requesting user (SEARCH_RERANK_LIVE gate on AND profile boosts matched the top band). Absent/false = baseline order (no profile, 맞춤 서비스 off, shadow mode, or fail-soft). U5 shows the '내 관심 주제 반영' indicator with an off entry point (설정 킬스위치) when true. Trace: US-P4 (#155), BR-P8, BR-P13.
   */
  personalized?: boolean;
}
/**
 * Synchronous search entry input. Source: QueryIntakeController.search(request: SearchRequest, ctx) (component-methods U2). Trace: dtos.md §1, FR-1, SEC-5, US-H1.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "SearchSearchRequest".
 */
export interface SearchSearchRequest {
  /**
   * Search query. Validated per FR-1/SEC-5 (non-empty, <=500 chars, sanitized). Trace: FR-1, SEC-5.
   */
  query: string;
  /**
   * Retrieval breadth. "lite" (default): BM25 over title+abstract only, no k-NN — the low-latency human search box (P50<3s). "full": hybrid (title+abstract+full-body chunks + k-NN) for deep recall — the literature/evidence agent and the opt-in "본문까지 검색" toggle. Absent ⇒ lite. Trace: FR-2.
   */
  scope?: "lite" | "full";
  /**
   * PROVISIONAL — optional search options. Type name is provisional; SSOT (dtos.md §1) records only the field `options?` (shape refined when the type is finalized in U2 FD). Trace: dtos.md §1.
   */
  options?: unknown;
}
/**
 * Successful search response: order-preserving top-N card page (FR-3). The card array is in RANKING ORDER (PBT-03). Trace: dtos.md §1, FR-3, FR-4.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "SearchSearchResultPageDTO".
 */
export interface SearchSearchResultPageDTO {
  /**
   * Result cards in ranking order. Trace: FR-3, FR-4, PBT-03.
   */
  cards: SearchResultCardVM[];
  meta: SearchResultMeta;
}
/**
 * Grounding abstain / out-of-corpus response — non-technical message, NO fabricated results (maps to U6 verdict=abstain). Internal violation detail NOT exposed. Provisional type name — SSOT (dtos.md §1) is AbstainResult{reason}. Trace: dtos.md §1, FR-5, US-D5, US-D6.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "SearchAbstainDTO".
 */
export interface SearchAbstainDTO {
  /**
   * Abstain reason code (non-technical; internal violation detail NOT exposed). Trace: FR-5, US-D5, US-D6, SEC-9.
   */
  reason: unknown;
}
/**
 * Partial / lexical-only fallback results returned WITH explicit degradation (NFR-C1 / US-R2). Card shape is identical to the success page. meta.degraded MUST be true. Trace: dtos.md §1, NFR-C1, US-R2, US-R3, QT-3.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "SearchDegradedResultDTO".
 */
export interface SearchDegradedResultDTO {
  /**
   * Degraded result cards (same shape as success). Trace: NFR-C1, US-R2.
   */
  cards: SearchResultCardVM[];
  meta: SearchResultMeta2;
  mode: SearchDegradationMode2;
}
/**
 * Result metadata with degraded=true. Trace: FR-11, QT-3.
 */
export interface SearchResultMeta2 {
  /**
   * Number of results returned (int). Trace: FR-11.
   */
  resultCount: number;
  /**
   * Degraded-result banner hint (true when results came from a degraded/fallback path). Trace: FR-11, QT-3.
   */
  degraded: boolean;
  degradationMode?: SearchDegradationMode;
  /**
   * Optional (additive, backward-compatible). True when the US-P4 personalization re-rank actually boosted this page's order for the requesting user (SEARCH_RERANK_LIVE gate on AND profile boosts matched the top band). Absent/false = baseline order (no profile, 맞춤 서비스 off, shadow mode, or fail-soft). U5 shows the '내 관심 주제 반영' indicator with an off entry point (설정 킬스위치) when true. Trace: US-P4 (#155), BR-P8, BR-P13.
   */
  personalized?: boolean;
}
/**
 * FR-1/SEC-5 validation failure inline error (non-technical, internal info blocked, fail-closed). Trace: dtos.md §1, FR-1, SEC-5, FR-11.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "SearchValidationErrorDTO".
 */
export interface SearchValidationErrorDTO {
  /**
   * Optional. Offending field name (e.g. query). Trace: FR-1, SEC-5.
   */
  field?: string;
  /**
   * Non-technical validation message (stack/internal identifiers blocked, fail-closed). Trace: FR-1, SEC-5, FR-11.
   */
  message: string;
}
/**
 * Request payload to trigger summarization or translation (FR-12/13/14).
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "SummarizationSummaryRequest".
 */
export interface SummarizationSummaryRequest {
  /**
   * The unique identifier of the paper (arXiv ID). Trace: FR-12.
   */
  paperId: string;
  /**
   * The version of the paper. Trace: FR-12.
   */
  version: number;
  task: SummarizationSummarizeTask;
  /**
   * Target language for translation. Trace: FR-13.
   */
  targetLang?: "ko";
  persona?: SummarizationPersona;
  scope?: SummarizationSummarizeScope;
  /**
   * Optional raw abstract string carried for full-text fallback or abstract-only translation. Trace: FR-13.
   */
  abstract?: string;
}
/**
 * A structured citation anchor mapping a claim back to source paper evidence (FR-12/US-S3).
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "SummarizationAnchor".
 */
export interface SummarizationAnchor {
  /**
   * The summary field name this anchor belongs to. Trace: FR-12.
   */
  field: string;
  target: SummarizationAnchorTarget;
  /**
   * The exact source quote or text span. Trace: FR-12.
   */
  span: string;
  /**
   * Derived section, table, or figure label (e.g. 'Section 3.1'). Trace: FR-12.
   */
  label: string;
}
/**
 * Quick assessment of code and data availability. Trace: FR-12.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "SummarizationReproducibility".
 */
export interface SummarizationReproducibility {
  /**
   * Exposed code repository link or availability statement. Trace: FR-12.
   */
  code: string;
  /**
   * Exposed dataset link or availability statement. Trace: FR-12.
   */
  data: string;
}
/**
 * Structured research paper summary containing key dimensions and citation anchors.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "SummarizationSummaryDraft".
 */
export interface SummarizationSummaryDraft {
  /**
   * A single-sentence TL;DR of the paper. Trace: FR-12.
   */
  tldr: string;
  /**
   * Key contributions identified. Trace: FR-12.
   */
  contributions: string[];
  /**
   * The methodology/approach description. Trace: FR-12.
   */
  method: string;
  /**
   * Key findings/results. Trace: FR-12.
   */
  results: string;
  /**
   * Limitations noted by the authors or pipeline. Trace: FR-12.
   */
  limitations: string;
  reproducibility: SummarizationReproducibility;
  /**
   * Grounding anchors for claims. Trace: FR-12.
   */
  anchors: SummarizationAnchor[];
  /**
   * Flag indicating if the summary draft was truncated. Trace: FR-12.
   */
  truncated?: boolean;
}
/**
 * Structured Korean translation as a 'translated doc-model' mirroring the source structure (FR-13): section titles, paragraphs, list items, and table/figure captions are translated to Korean, while structural/verbatim fields — block & section ids, formula LaTeX, table numeric cells, figure assetRefs — are copied from the source doc-model unchanged (numbers/equations are never translated; D8). Block & section ids mirror the source doc-model so the client renders it with the SAME rich viewer as the original body. Trace: FR-13, BR-S3.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "SummarizationTranslationDraft".
 */
export interface SummarizationTranslationDraft {
  docModel: DocmodelDocModel1;
  /**
   * Untranslated terminology or glossary terms kept as-is. Trace: FR-13.
   */
  keptTerms: string[];
  /**
   * DocSuri standard glossary terms (shared seed) that appear in THIS paper: keep-as-is terms the model kept in English (no 'translated'), plus mapping terms whose standard Korean appears in the translation ('translated' set). The client renders a 표준 용어집; both kinds are editable as strong, prompt-enforced overrides (re-translation) — a mapping chip pre-fills its editor with the standard rendering. Trace: BR-S4.
   */
  standardGlossary?: {
    /**
     * The English (source) term.
     */
    term: string;
    /**
     * Standard Korean rendering — present only for mapping terms (e.g. attention→어텐션), where it pre-fills the editor; absent for keep-as-is terms (kept in English).
     */
    translated?: string;
  }[];
}
/**
 * The translated doc-model: Korean text over the source structure (ids mirror the source). Rendered by the same rich viewer as the original body. Trace: FR-13.
 */
export interface DocmodelDocModel1 {
  meta: DocmodelDocModelMeta;
  /**
   * Complete reading-order text projection of the paper. Includes section titles, paragraphs, table captions/cells, formula LaTeX, figure captions, list items, and code text. Excludes image bytes, base64 payloads, presigned URLs, and internal object refs. Trace: FR-6, FR-18, QT-9.
   */
  fullText: string;
  /**
   * Top-level sections in reading order; each may nest subsections (recursive). The rich-view DocTOC and the summary map-reduce split (P3) both consume this tree. Trace: Q1-decision (nested section tree).
   */
  sections: DocmodelSection[];
}
/**
 * Summary metadata including fallback information.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "SummarizationSummaryMeta".
 */
export interface SummarizationSummaryMeta {
  /**
   * Source text indicator (e.g. 'full_text'). Trace: FR-12.
   */
  source?: string;
  /**
   * Fallback reason if processing was degraded (e.g., 'abstract'). Trace: FR-13.
   */
  fallback?: string;
}
/**
 * Successful summary or translation response. Only SEC-9 white-listed fields are exposed.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "SummarizationSummaryResultDTO".
 */
export interface SummarizationSummaryResultDTO {
  /**
   * Successful status indicator. Trace: FR-11.
   */
  status: "ok";
  task: SummarizationSummarizeTask;
  meta: SummarizationSummaryMeta;
  /**
   * Indicates if the response was served from cache. Trace: FR-11.
   */
  cached: boolean;
  summary?: SummarizationSummaryDraft;
  translation?: SummarizationTranslationDraft;
}
/**
 * A long-input summary (LengthRouter MAP_REDUCE band) is being produced asynchronously as a background job (BR-S6/BR-S8): a cache miss enqueued a summary job. The client re-requests the same action after retryAfterMs and gets the result on a cache hit once the worker finishes. Trace: BR-S6, BR-S8, #135.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "SummarizationPendingDTO".
 */
export interface SummarizationPendingDTO {
  status: "pending";
  /**
   * Suggested client poll backoff in milliseconds before re-requesting.
   */
  retryAfterMs?: number;
}
/**
 * Returned when summary is abstained due to failure to pass grounding validation rules. Trace: FR-12.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "SummarizationAbstainDTO".
 */
export interface SummarizationAbstainDTO {
  status: "abstain";
  /**
   * Non-technical reason for abstaining. Trace: SEC-9.
   */
  reason: string;
}
/**
 * Returned when the budget circuit is OPEN and operations are degraded. Trace: NFR-C1.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "SummarizationCostDegradedDTO".
 */
export interface SummarizationCostDegradedDTO {
  status: "cost_degraded";
  /**
   * User-facing message. Trace: SEC-9.
   */
  message: string;
}
/**
 * Returned when source content is unavailable for processing. Trace: FR-12.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "SummarizationSourceUnavailableDTO".
 */
export interface SummarizationSourceUnavailableDTO {
  status: "source_unavailable";
  /**
   * Reason for source unavailability. Trace: SEC-9.
   */
  reason: string;
}
/**
 * FR-17 figure/table view-model (display-only). Produced by U1 ingestion (paper_asset), served by U7's same-origin delivery endpoint. SEC-9: a delivery `url` only — the S3 object_ref, bucket, storage host and internal manifest columns are NEVER exposed (REM-2 F07 replaced the short-lived presigned URL, which leaked the object key and outlived the decision behind it).
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "SummarizationAssetRef".
 */
export interface SummarizationAssetRef {
  /**
   * Deterministic asset id. Trace: FR-17.
   */
  assetId: string;
  /**
   * Asset kind. Trace: FR-17.
   */
  type: "figure" | "table";
  /**
   * Display order within its type. Trace: FR-17.
   */
  ordinal: number;
  /**
   * Figure/table caption (escaped on render). Trace: FR-17.
   */
  caption: string;
  /**
   * How the asset was extracted (hybrid). Trace: FR-17.
   */
  sourceMode: "structured" | "page-crop";
  /**
   * Same-origin delivery path (`/api/papers/<paperId>/assets/<assetId>`), resolved to bytes server-side (SEC-9). The browser must load it through the same-origin BFF (`/bff` + this path) so the httpOnly session cookie is sent. Trace: FR-17, SEC-9, REM-2 F07.
   */
  url: string;
  /**
   * Source page (page-crop). Trace: FR-17.
   */
  pageRef?: number | null;
  /**
   * Source bbox (page-crop). Trace: FR-17.
   */
  bbox?: number[] | null;
}
/**
 * Successful asset manifest. Trace: FR-17.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "SummarizationAssetsOkDTO".
 */
export interface SummarizationAssetsOkDTO {
  status: "ok";
  /**
   * Figure/table assets in display order. Trace: FR-17.
   */
  assets: SummarizationAssetRef[];
}
/**
 * OA license not permitted (or assets not configured) → no assets shown. Trace: FR-17, BR-SF-11.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "SummarizationAssetsLicenseUnavailableDTO".
 */
export interface SummarizationAssetsLicenseUnavailableDTO {
  status: "license_unavailable";
}
/**
 * Authentication required (401). Trace: FR-17, SEC-8.
 *
 * This interface was referenced by `PublicWire`'s JSON-Schema
 * via the `definition` "SummarizationAssetsUnauthorizedDTO".
 */
export interface SummarizationAssetsUnauthorizedDTO {
  status: "unauthorized";
}
