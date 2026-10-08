'use client';

// PaperDetailIsland (P3·P5) — the client island inside the SSR /paper/[id] shell.
// Owns the 요약/초록번역/각주트리 action bar and the paper metadata (title/authors/abstract).
// 본문(doc-model rich view) and 본문 번역 open as full-screen IN-APP routes (Link / router.push,
// same tab — each has its own ← back arrow), not a browser tab or inline. Choosing a summary
// source anchor navigates to the 본문 route scrolled to the matching block. real-first.
import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import type { AnchorVM } from '@/types/generated';
import { usePaperMeta } from '@/lib/usePaperMeta';
import { renderInlineMath } from '@/lib/renderMath';
import { SummaryModal, type DetailView } from './SummaryModal';
import { JobDialog } from './JobDialog';
import { JobSubmissionForm, type JobSubmissionIdentity } from './JobSubmissionForm';
import { JobStatus } from './JobStatus';
import { SaveToLibraryButton } from './SaveToLibraryButton';
import { CitationTreePanel } from './CitationTreePanel';
import { DocModelViewer } from './DocModelViewer';
import { recordPaperOpened, recordSummaryRequest } from '@/lib/personalization';
import styles from './PaperDetailIsland.module.css';

interface PaperDetailIslandProps {
  paperId: string;
  version: number;
  arxivUrl?: string;
}

// ResultCardVM.abstractSnippet is a SNIPPET, never the full abstract (BR-U5-4;
// u5-frontend/functional-design/domain-entities.md §1.3 — the 7-field card contract). The
// detail page only has the full abstract on hand, so it must be truncated before being saved
// into a bookmark's card snapshot — otherwise every detail-page bookmark drifts from that
// contract by carrying the entire text. Cuts on the last whitespace at/before the limit so a
// word isn't sliced mid-way.
const ABSTRACT_SNIPPET_MAX_CHARS = 300;
function truncateSnippet(text: string, max = ABSTRACT_SNIPPET_MAX_CHARS): string {
  if (text.length <= max) return text;
  const cut = text.slice(0, max);
  const lastSpace = cut.lastIndexOf(' ');
  return `${(lastSpace > 0 ? cut.slice(0, lastSpace) : cut).trimEnd()}…`;
}

// Top action bar (modal openers). 본문 / 본문 번역 live below the metadata instead.
const ACTIONS: { view: DetailView; label: string }[] = [
  { view: 'summary', label: '요약' },
  { view: 'abstractTrans', label: '초록 번역' },
];

// The job journey state machine: action → explicit submission form → live
// tracking → query-only result. Nothing happens until the human chooses an
// action, and the parent mounts tracking only for an ACTUAL returned identity
// (ADR-013) — never for a guessed or stale one.
type JobFlow =
  | { phase: 'closed' }
  | { phase: 'form'; view: DetailView }
  | { phase: 'tracking'; view: DetailView; identity: JobSubmissionIdentity }
  | { phase: 'result'; view: DetailView; jobId: string };

export function PaperDetailIsland({ paperId, version, arxivUrl }: PaperDetailIslandProps) {
  const [flow, setFlow] = useState<JobFlow>({ phase: 'closed' });
  const [citationOpen, setCitationOpen] = useState(false);
  // Desktop shows the full body inline (the doc-model is pre-stored); phones keep the 전문
  // button that opens the separate full-screen route. Resolved client-side after mount.
  const [isDesktop, setIsDesktop] = useState(false);
  // On desktop, a summary "source anchor" scrolls the inline body to the matching block
  // instead of navigating to the doc-model route.
  const [inlineAnchor, setInlineAnchor] = useState<AnchorVM | null>(null);
  const meta = usePaperMeta(paperId);
  // Source-neutral header (FR-4/FR-5, Phase 2 Q2): the detail header agrees with the search card
  // on the discovery source. arXiv keeps "arXiv:<id>"; a non-arXiv paper shows its source name
  // and links out to that source. http(s)-guarded (external-link safety).
  const m = meta.status === 'done' ? meta.meta : undefined;
  const sourceName = m?.sourceName ?? 'arXiv';
  const isArxiv = sourceName.toLowerCase() === 'arxiv';
  const sourceUrlRaw = m?.sourceUrl ?? m?.arxivUrl ?? arxivUrl;
  const sourceUrl = sourceUrlRaw && /^https?:\/\//i.test(sourceUrlRaw) ? sourceUrlRaw : undefined;
  const router = useRouter();
  const openedRef = useRef<string | null>(null);

  useEffect(() => {
    const key = `${paperId}:${version}`;
    if (openedRef.current === key) return;
    openedRef.current = key;
    recordPaperOpened(paperId, version);
  }, [paperId, version]);

  useEffect(() => {
    const mq = window.matchMedia('(min-width: 768px)');
    const update = () => setIsDesktop(mq.matches);
    update();
    // Safari <14 only has the deprecated addListener/removeListener on MediaQueryList.
    if (typeof mq.addEventListener === 'function') {
      mq.addEventListener('change', update);
      return () => mq.removeEventListener('change', update);
    }
    mq.addListener(update);
    return () => mq.removeListener(update);
  }, []);

  // 본문 / 본문 번역 are in-app routes (Link). A summary source anchor navigates to the 본문
  // route scrolled to the matching block (label carried via the query).
  const bodyHref = `/paper/${encodeURIComponent(paperId)}/doc-model?version=${version}`;
  const translateHref = `/paper/${encodeURIComponent(paperId)}/translate?version=${version}`;
  const openBody = (anchor?: AnchorVM | null) => {
    // Desktop: the body is already on the page — scroll the inline viewer to the anchor.
    if (isDesktop) {
      setInlineAnchor(anchor ?? null);
      return;
    }
    // Phone: open the full-screen doc-model route scrolled to the matching block.
    const sp = new URLSearchParams({ version: String(version) });
    if (anchor?.label) {
      sp.set('anchorLabel', anchor.label);
      if (anchor.span) sp.set('anchorSpan', anchor.span);
    }
    router.push(`/paper/${encodeURIComponent(paperId)}/doc-model?${sp.toString()}`);
  };

  return (
    <div className={styles.root}>
      {/* Sticky action bar directly under the DocSuri header — each button opens the
          summary/translation modal at its tab. */}
      <div className={styles.actionsBar} role="group" aria-label="논문 상세 액션">
        {ACTIONS.map((a) => (
          <button
            key={a.view}
            type="button"
            className={styles.action}
            onClick={() => setFlow({ phase: 'form', view: a.view })}
            data-testid={`open-${a.view}`}
          >
            {a.label}
          </button>
        ))}
        <button
          type="button"
          className={styles.action}
          onClick={() => setCitationOpen((v) => !v)}
          data-testid="open-citation-tree"
        >
          각주 트리
        </button>
        {/* Desktop shows the body inline below, so 전문 번역 joins the top toolbar (no bottom
            body row). On phones it stays in the bottom row next to 전문. */}
        {isDesktop ? (
          <Link className={styles.action} href={translateHref} data-testid="open-full-translation">
            전문 번역
          </Link>
        ) : null}
      </div>

      {citationOpen ? (
        <CitationTreePanel paperId={paperId} onClose={() => setCitationOpen(false)} />
      ) : null}

      {meta.status === 'done' && meta.meta ? (
        <header className={styles.meta} data-testid="paper-meta">
          <div className={styles.titleRow}>
            <h1 className={styles.title} data-testid="paper-title">
              {renderInlineMath(meta.meta.title)}
            </h1>
            <SaveToLibraryButton
              card={{
                arxivId: paperId,
                title: meta.meta.title,
                authors: meta.meta.authors,
                year: meta.meta.year,
                abstractSnippet: truncateSnippet(meta.meta.abstract),
                arxivUrl: meta.meta.arxivUrl ?? arxivUrl,
              }}
            />
          </div>
          <p className={styles.authors} data-testid="paper-authors">
            {meta.meta.authors.join(', ')}
            {meta.meta.year ? <span className={styles.year}> · {meta.meta.year}</span> : null}
          </p>
          <p className={styles.abstract} data-testid="paper-abstract">
            {renderInlineMath(meta.meta.abstract)}
          </p>
          <p className={styles.idline}>
            <span data-testid="paper-source">{isArxiv ? `arXiv:${paperId}` : sourceName}</span>
            {sourceUrl ? (
              <a
                className={styles.link}
                href={sourceUrl}
                target="_blank"
                rel="noopener noreferrer"
                data-testid="paper-source-link"
              >
                {isArxiv ? 'arXiv에서 원문 보기' : `${sourceName}에서 원문 보기`}
              </a>
            ) : null}
          </p>
        </header>
      ) : meta.status === 'loading' ? (
        <p className={styles.metaLoading} data-testid="paper-meta-loading">
          논문 정보를 불러오는 중…
        </p>
      ) : null}

      {/* Phone: body access as buttons below the metadata — each opens a full-screen route
          (본문 = doc-model rich view, 본문 번역 = full-text translation). */}
      {!isDesktop ? (
        <div className={styles.bodyActions} role="group" aria-label="전문">
          <Link className={styles.action} href={bodyHref} data-testid="open-doc-model">
            전문
          </Link>
          <Link className={styles.action} href={translateHref} data-testid="open-full-translation">
            전문 번역
          </Link>
        </div>
      ) : null}

      {/* Desktop: the full body is shown inline (the doc-model is pre-stored), so there is no
          separate 전문 navigation. The title is hidden — the metadata header above carries it. */}
      {isDesktop ? (
        <div className={styles.inlineBody} data-testid="detail-inline-body">
          <DocModelViewer
            paperId={paperId}
            version={version}
            anchor={inlineAnchor}
            arxivUrl={arxivUrl}
            hideTitle
          />
        </div>
      ) : null}

      {flow.phase === 'form' ? (
        <JobDialog
          open
          title={flow.view === 'summary' ? '요약' : '번역'}
          onClose={() => setFlow({ phase: 'closed' })}
        >
          <JobSubmissionForm
            paperId={paperId}
            version={version}
            task={flow.view === 'summary' ? 'summarize' : 'translate'}
            onSubmitted={(identity) => {
              recordSummaryRequest(
                paperId,
                identity.taskType === 'summarize' ? 'summary' : 'translation',
                {},
              );
              setFlow({ phase: 'tracking', view: flow.view, identity });
            }}
            onCancel={() => setFlow({ phase: 'closed' })}
          />
        </JobDialog>
      ) : null}

      {flow.phase === 'tracking' ? (
        <JobDialog open title="작업 진행" onClose={() => setFlow({ phase: 'closed' })}>
          <JobStatus
            jobId={flow.identity.jobId}
            paperId={paperId}
            onComplete={(terminal) => {
              // COMPLETED → read the exact prepared result (query-only).
              // FAILED/ABSTAINED stay shown in the status panel until closed.
              if (terminal === 'COMPLETED') {
                setFlow({ phase: 'result', view: flow.view, jobId: flow.identity.jobId });
              } else {
                setFlow({ phase: 'closed' });
              }
            }}
          />
        </JobDialog>
      ) : null}

      {flow.phase === 'result' ? (
        <SummaryModal
          paperId={paperId}
          jobId={flow.jobId}
          view={flow.view}
          onClose={() => setFlow({ phase: 'closed' })}
          onAnchor={openBody}
        />
      ) : null}
    </div>
  );
}
