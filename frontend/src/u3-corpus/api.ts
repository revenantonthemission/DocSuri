/**
 * U3 corpus workspace transport bindings (C04–C06 browser operations).
 *
 * Same-origin `/api/v2` calls only, over the shared C13 Transport: server-
 * derived principal, session/anonymous bootstrap, Origin/CSRF and idempotency
 * conventions. No storage paths, worker routes or private identifiers change.
 */

import type { Transport } from '../api';

export const CORPUS_POLICY = { policyId: 'u3-corpus-maintenance', revision: '1' } as const;
export const ELIGIBILITY_POLICY = { policyId: 'u3-source-eligibility', revision: '1' } as const;
export const SEARCH_POLICY = { policyId: 'u3-paper-search', revision: '1' } as const;
export const READING_POLICY = { policyId: 'u3-paper-reading', revision: '1' } as const;
export const CITATION_POLICY = { policyId: 'u3-citation-traversal', revision: '1' } as const;
export const ASSISTANCE_POLICY = { policyId: 'u3-paper-assistance', revision: '1' } as const;
export const GLOSSARY_POLICY = { policyId: 'u3-owner-glossary', revision: '1' } as const;
export const PROCESSING_POLICY = { policyId: 'local-research', revision: '1' } as const;
export const VOCABULARY = 'u3-paper-options-1';

export type PolicyRef = { policyId: string; revision: string };
export type PaperRef = { paperId: string; versionId: string; eligibilityRevision: string };
export type QueryFilter = { filterId: string; operatorId: string; values: (string | number)[] };
export type QueryContext = {
  query: string;
  modeId: 'lexical' | 'semantic';
  orderId: 'relevance' | 'newest';
  filters: QueryFilter[];
  vocabularyRevision: string;
  policyRef: PolicyRef;
};

export type SearchHit = {
  paper: PaperRef;
  title: string;
  authors: string[];
  publishedAt?: string;
  snippet: string;
  sourceUrl: string;
  availability: string;
  matchExplanation: string;
};
export type SearchResponse = {
  executionId: string;
  query: QueryContext;
  hits: SearchHit[];
  page: { nextCursor?: string; snapshotRevision: string };
  publication: {
    generationId: string;
    publicationRevision: string;
    manifestHash: string;
    compatibilityRevision: string;
    eligibilityRevision: string;
    publishedAt: string;
    complete: true;
  };
  outcome: 'complete' | 'partial' | 'degraded';
  effectiveModeId: string;
  limitations: string[];
};

export type ContentRead =
  | {
      availability: 'ready';
      content: {
        paper: PaperRef;
        contentRevision: string;
        contentHash: string;
        sections: { sectionId: string; heading: string; text: string; anchor: string }[];
        assets: {
          assetId: string;
          mediaType: string;
          contentHash: string;
          altText: string;
          sectionId?: string;
        }[];
        sourceUrls: string[];
        coverage: 'complete' | 'partial';
        limitations: string[];
        policy: PolicyRef;
      };
    }
  | {
      availability:
        | 'absent'
        | 'building'
        | 'unsupported'
        | 'failed'
        | 'withdrawn'
        | 'restricted';
      paper: PaperRef;
      reasonKey: string;
      retryable: boolean;
    };

export type CitationNode = {
  nodeId: string;
  paper: PaperRef | null;
  title: string | null;
  sourceUrl: string | null;
  disposition: 'eligible' | 'unknown' | 'incomplete' | 'restricted' | 'withdrawn';
};
export type CitationResponse = {
  snapshotId: string;
  revision: string;
  root: PaperRef;
  nodes: CitationNode[];
  edges: { fromNodeId: string; toNodeId: string; sourceUrl: string; observedAt: string }[];
  freshness: 'current' | 'stale' | 'unknown';
  coverage: 'complete' | 'partial';
  limitations: string[];
  page: { nextCursor?: string; snapshotRevision: string };
};

export type AssistanceOption = {
  optionId: string;
  operation: 'summary' | 'translation';
  sourceLanguageId: string;
  targetLanguageId: string;
  presentationLevelId: string;
  labelKey: string;
};
export type AssistanceOptions = {
  revision: string;
  options: AssistanceOption[];
  policy: PolicyRef;
  limitations: string[];
};
export type JobReceipt = {
  jobId: string;
  revision: string;
  seq: number;
  state: 'accepted' | 'running' | 'succeeded' | 'failed';
  requestId: string;
  acceptedAt: string;
};
export type JobSnapshot = {
  jobId: string;
  kind: string;
  state: string;
  revision: string;
  seq: number;
  ownerId: string;
  progress: { mode: 'indeterminate' } | { mode: 'determinate'; current: number; total: number };
  result: { resultId: string; revision: string; contentHash: string; mediaType: string } | null;
  error: { code: string; requestId: string; retryable: boolean; messageKey: string } | null;
  acceptedAt: string;
};
export type PreparedResult =
  | {
      availability: 'ready';
      prepared: {
        result: { resultId: string; revision: string; contentHash: string };
        ownerId: string;
        jobId: string;
        paper: PaperRef;
        sourceContentHash: string;
        operation: string;
        optionId: string;
        glossaryRevision: string;
        sections: { sectionId: string; heading: string; text: string; anchor: string }[];
        coverage: 'complete' | 'partial';
        limitations: string[];
        methodRevision: string;
      };
    }
  | {
      availability: 'pending' | 'failed' | 'expired' | 'withdrawn' | 'restricted';
      jobId: string;
      reasonKey: string;
    };
export type Glossary = {
  ownerId: string;
  revision: string;
  normalizationPolicy: PolicyRef;
  terms: { termId: string; source: string; preferred: string; languageId: string }[];
};

export type JobEvent = Partial<JobSnapshot> & { sequence?: number; phase?: string };

export const api = {
  async search(client: Transport, query: QueryContext, page: { limit?: number; cursor?: string } = {}) {
    return client.post<SearchResponse>('/api/v2/c05/search', {
      query,
      page,
    });
  },
  async readContent(client: Transport, paper: PaperRef, purpose = 'read') {
    return client.post<ContentRead>('/api/v2/c04/read-content', { paper, purpose });
  },
  async resolve(client: Transport, identifier: string, versionLabel?: string) {
    return client.post<{
      paper: PaperRef;
      requestedIdentifier: string;
      canonicalDisposition: string;
      metadataRevision: string;
      title: string;
      sourceUrls: string[];
      policy: PolicyRef;
    }>('/api/v2/c04/resolve-paper', {
      identifier,
      ...(versionLabel ? { versionLabel } : {}),
    });
  },
  async citations(
    client: Transport,
    paper: PaperRef,
    direction: 'cited' | 'citing' | 'both',
    snapshotRevision?: string,
  ) {
    return client.post<CitationResponse>('/api/v2/c05/read-citations', {
      paper,
      direction,
      page: { limit: 32 },
      traversalPolicy: CITATION_POLICY,
      ...(snapshotRevision ? { snapshotRevision } : {}),
    });
  },
  async assistanceOptions(client: Transport, paper: PaperRef) {
    return client.post<AssistanceOptions>('/api/v2/c06/read-assistance-options', { paper });
  },
  async acceptAssistance(
    client: Transport,
    input: {
      paper: PaperRef;
      contentRevision: string;
      contentHash: string;
      option: AssistanceOption;
      optionsRevision: string;
      glossaryRevision: string;
    },
    operationKey: string,
  ) {
    return client.post<JobReceipt>(
      '/api/v2/c06/accept-assistance',
      {
        paper: input.paper,
        contentRevision: input.contentRevision,
        contentHash: input.contentHash,
        operation: input.option.operation,
        optionId: input.option.optionId,
        optionsRevision: input.optionsRevision,
        glossaryRevision: input.glossaryRevision,
        processingPolicy: PROCESSING_POLICY,
      },
      operationKey,
    );
  },
  async job(client: Transport, jobId: string) {
    return client.get<JobSnapshot>(`/api/v2/jobs/${jobId}`);
  },
  async preparedResult(client: Transport, jobId: string) {
    return client.get<PreparedResult>(`/api/v2/jobs/${jobId}/result`);
  },
  async readGlossary(client: Transport) {
    return client.post<Glossary>('/api/v2/c06/read-glossary', {});
  },
  async replaceGlossary(client: Transport, glossary: Glossary, terms: Glossary['terms']) {
    return client.post<Glossary>('/api/v2/c06/replace-glossary', {
      expectedRevision: glossary.revision,
      normalizationPolicy: GLOSSARY_POLICY,
      terms,
    });
  },
  async savePaper(client: Transport, paper: PaperRef) {
    return client.post('/api/v2/c03/library-save-paper', {
      paper,
      policyRef: { policyId: 'synthetic-local-library', revision: '1' },
    });
  },
};

/** One client operation key per intended submission; retry reuses it. */
export function operationKey(): string {
  return crypto.randomUUID();
}
