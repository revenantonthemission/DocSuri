'use client';

// SummaryModal — the QUERY-ONLY completed-result surface (Step 33).
//
// The modal no longer initiates work: it reads the exact immutable prepared
// result for one completed job (`GET …/{jobId}/result`) and renders it through
// the existing safe views. Nothing here generates, enqueues or re-runs —
// opening the modal, changing preferences or pressing retry are all reads of
// the same payload. Work is initiated only through JobSubmissionForm's explicit
// submit, and this modal never appears before a real, returned job identity.
//
// Accessibility: role="dialog" aria-modal, Escape + backdrop close, initial
// focus, body-scroll lock. External text is escaped by React.
import { useCallback, useEffect, useRef, useState } from 'react';
import type { AnchorVM } from '@/types/generated';
import {
  getJobResult,
  JobResultError,
  type JobResultFailure,
  type PreparedResultEnvelope,
} from '@/lib/api/contentJobApi';
import { SummaryView } from './SummaryView';
import { TranslationView } from './TranslationView';
import { StateView } from './StateView';
import { emitJobDiagnostic } from '@/lib/jobDiagnostics';
import { recordSourceAnchorClicked } from '@/lib/personalization';
import styles from './SummaryModal.module.css';

/** The detail-page result modes (요약/초록 번역/전문 번역). */
export type DetailView = 'summary' | 'abstractTrans' | 'fullTrans';

interface SummaryModalProps {
  paperId: string;
  /** The completed job whose exact prepared result is READ (never re-run). */
  jobId: string;
  /** Which mode this modal renders (chosen by the action bar / card). Fixed. */
  view: DetailView;
  onClose: () => void;
  /** Anchor chosen inside a summary — parent highlights it in the on-page body.
   * Omitted from the search/library card (no full-text body to highlight): the
   * summary's 출처 chips are then disabled. */
  onAnchor?: (anchor: AnchorVM) => void;
}

const MODAL_TITLE: Record<DetailView, string> = {
  summary: '요약',
  abstractTrans: '초록 번역',
  fullTrans: '전문 번역',
};

type ReadState =
  | { status: 'loading' }
  | { status: 'ready'; envelope: PreparedResultEnvelope }
  | { status: 'failed'; reason: JobResultFailure; message: string };

export function SummaryModal({ paperId, jobId, view, onClose, onAnchor }: SummaryModalProps) {
  const [read, setRead] = useState<ReadState>({ status: 'loading' });
  const [assetCopyState, setAssetCopyState] = useState<'idle' | 'copied'>('idle');
  const panelRef = useRef<HTMLDivElement | null>(null);

  // Authorized asset-ID copy: the identifier is plain text — never a URL or a
  // token — and a clipboard that is unavailable or denied degrades quietly.
  const copyAssetId = useCallback(async (assetId: string) => {
    try {
      await navigator.clipboard.writeText(assetId);
      setAssetCopyState('copied');
    } catch {
      // Clipboard unavailable or denied: no failure surface.
    }
  }, []);

  // Query-only read of the exact prepared payload; retry re-reads, it does not
  // regenerate (zero generation/enqueue on every read outcome).
  const readResult = useCallback(async () => {
    setRead({ status: 'loading' });
    setAssetCopyState('idle');
    try {
      const envelope = await getJobResult(jobId);
      setRead({ status: 'ready', envelope });
      emitJobDiagnostic({ kind: 'result-read', outcome: 'ready' });
    } catch (caught) {
      if (caught instanceof JobResultError) {
        setRead({ status: 'failed', reason: caught.reason, message: caught.message });
        emitJobDiagnostic({ kind: 'result-read', outcome: caught.reason });
      } else {
        setRead({
          status: 'failed',
          reason: 'transient',
          message: '일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.',
        });
        emitJobDiagnostic({ kind: 'result-read', outcome: 'transient' });
      }
    }
  }, [jobId]);

  useEffect(() => {
    void readResult();
  }, [readResult]);

  // Escape to close + body-scroll lock while open.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    panelRef.current?.focus();
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [onClose]);

  const handleAnchor = (anchor: AnchorVM) => {
    recordSourceAnchorClicked(paperId, anchor);
    onAnchor?.(anchor);
    onClose();
  };

  function renderResult() {
    if (read.status === 'loading') {
      return <StateView kind="loading" title="결과 불러오는 중…" message="잠시만 기다려 주세요." />;
    }
    if (read.status === 'failed') {
      switch (read.reason) {
        case 'not-ready':
          return (
            <StateView
              kind="degraded"
              message="아직 결과가 준비되지 않았습니다. 잠시 후 다시 확인해 주세요."
              onRetry={() => void readResult()}
            />
          );
        case 'transient':
          return (
            <StateView kind="error" message={read.message} onRetry={() => void readResult()} />
          );
        case 'expired':
        case 'unavailable':
        case 'auth':
        case 'not-found':
          return <StateView kind="error" message={read.message} />;
      }
    }
    const content = read.envelope.preparedResult.content;
    if (content.task === 'summary') {
      return (
        <SummaryView
          summary={content.summary}
          {...(content.cached !== undefined ? { cached: content.cached } : {})}
          {...(onAnchor ? { onAnchor: handleAnchor } : {})}
        />
      );
    }
    return <TranslationView translation={content.translation} />;
  }

  return (
    <div className={styles.backdrop} onClick={onClose} data-testid="summary-modal-backdrop">
      <div
        ref={panelRef}
        className={styles.panel}
        role="dialog"
        aria-modal="true"
        aria-label="요약 및 번역"
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
        data-testid="summary-modal"
      >
        <div className={styles.head}>
          <h2 className={styles.heading}>{MODAL_TITLE[view]}</h2>
          <button
            type="button"
            className={styles.close}
            onClick={onClose}
            aria-label="닫기"
            data-testid="summary-modal-close"
          >
            ✕
          </button>
        </div>

        <div className={styles.body} data-testid="summary-modal-result">
          {read.status === 'ready' && read.envelope.preparedResult.assetId ? (
            <div className="mb-2 flex items-center justify-end gap-2">
              <button
                type="button"
                data-testid="copy-asset-id"
                className="text-xs text-blue-600 underline"
                onClick={() => {
                  const assetId =
                    read.status === 'ready' ? read.envelope.preparedResult.assetId : undefined;
                  if (assetId) void copyAssetId(assetId);
                }}
              >
                자산 ID 복사
              </button>
              <span role="status" aria-live="polite" className="text-xs text-gray-500">
                {assetCopyState === 'copied' ? '복사됨' : ''}
              </span>
            </div>
          ) : null}
          {renderResult()}
        </div>
      </div>
    </div>
  );
}

export default SummaryModal;
