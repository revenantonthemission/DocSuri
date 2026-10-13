/** Paper workspace: exact identity, source reading, save and assistance. */

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ApiError, LIBRARY_POLICY, PROCESSING_POLICY, PaperRef, Transport } from './api';
import { Notice, StatusLine, describeError, focusHeading, notice } from './ui';

export type Section = { sectionId: string; heading: string; text: string; anchor: string };
type ContentRead = {
  availability: string;
  content?: {
    paper: PaperRef;
    contentRevision: string;
    contentHash: string;
    sections: Section[];
    sourceUrls: string[];
    coverage: string;
    limitations: string[];
  };
  paper?: PaperRef;
  reasonKey?: string;
};
export type SavedPaper = {
  savedPaperId: string;
  revision: string;
  savedTitle?: string;
  sourceDisposition: string;
  savedPaper?: PaperRef;
  resolvedPaper?: PaperRef;
};
type Option = {
  optionId: string;
  operation: string;
  sourceLanguageId: string;
  targetLanguageId: string;
  labelKey: string;
};
type AssistanceOptions = {
  revision: string;
  options: Option[];
  limitations: string[];
};
type JobSnapshot = {
  jobId: string;
  state: string;
  revision: string;
  seq: number;
  progress?: { mode: string; current?: number; total?: number };
  error?: { code: string; requestId: string };
  acceptedAt: string;
};
type Prepared = {
  result: { resultId: string; revision: string };
  sections: Section[];
  coverage: string;
  limitations: string[];
  operation: string;
  optionId: string;
  paper: PaperRef;
};
type ResultRead = { availability: string; prepared?: Prepared; jobId: string; reasonKey?: string };
type HistoryRow = {
  jobId: string;
  availability: string;
  operation: string;
  state: string;
  createdAt: string;
};

const SAVE_COPY: Record<string, string> = {
  pending: '저장 중…',
  unknown: '저장 여부 확인 중',
  saved: '저장됨',
  failed: '저장하지 못했어요',
  conflict: '다른 곳에서 변경되었어요',
};

const JOB_COPY: Record<string, string> = {
  accepted: '요청을 접수했어요',
  running: '결과를 만들고 있어요',
  succeeded: '준비된 결과가 있어요',
  failed: '결과를 만들지 못했어요',
};

export function PaperWorkspace({
  transport,
  paper,
  signedIn,
  onBack,
}: {
  transport: Transport;
  paper: PaperRef;
  signedIn: boolean;
  onBack: () => void;
}) {
  const heading = useRef<HTMLHeadingElement | null>(null);
  const [read, setRead] = useState<ContentRead | null>(null);
  const [readError, setReadError] = useState<Notice | null>(null);
  const [saved, setSaved] = useState<SavedPaper | null>(null);
  const [saveState, setSaveState] = useState('idle');
  const [options, setOptions] = useState<AssistanceOptions | null>(null);
  const [job, setJob] = useState<JobSnapshot | null>(null);
  const [transportState, setTransportState] = useState<'live' | 'offline'>('live');
  const [result, setResult] = useState<ResultRead | null>(null);
  const [history, setHistory] = useState<HistoryRow[]>([]);
  const [assistNotice, setAssistNotice] = useState<Notice | null>(null);
  const resultHeading = useRef<HTMLHeadingElement | null>(null);

  useEffect(() => {
    focusHeading(heading);
  }, []);

  const loadSaved = useCallback(async () => {
    try {
      const page = await transport.post<{ items: SavedPaper[] }>(
        '/api/v2/c03/library-list-saved-papers',
        { page: { limit: 100 } },
      );
      setSaved(page.items.find((item) => item.savedPaperId === paper.paperId) ?? null);
    } catch {
      setSaved(null);
    }
  }, [transport, paper.paperId]);

  useEffect(() => {
    let active = true;
    transport
      .post<ContentRead>('/api/v2/c04/read-content', { paper, purpose: 'read' })
      .then((value) => {
        if (!active) return;
        setRead(value);
        setReadError(null);
      })
      .catch((error) => {
        if (!active) return;
        setReadError(describeError(error));
      });
    return () => {
      active = false;
    };
  }, [transport, paper]);

  useEffect(() => {
    if (signedIn) void loadSaved();
  }, [signedIn, loadSaved]);

  useEffect(() => {
    if (!signedIn) {
      setOptions(null);
      return;
    }
    let active = true;
    transport
      .post<AssistanceOptions>('/api/v2/c06/read-assistance-options', { paper })
      .then((value) => {
        if (active) setOptions(value);
      })
      .catch(() => {
        if (active) setOptions(null);
      });
    return () => {
      active = false;
    };
  }, [transport, paper, signedIn]);

  const refreshHistory = useCallback(async () => {
    if (!signedIn) return;
    try {
      const page = await transport.post<{ items: HistoryRow[] }>(
        '/api/v2/c06/read-assistance-history',
        { paper, page: { limit: 10 } },
      );
      setHistory(page.items);
    } catch {
      setHistory([]);
    }
  }, [transport, paper, signedIn]);

  useEffect(() => {
    void refreshHistory();
  }, [refreshHistory]);

  // Ordered owner progress: the stream only updates newer sequences; a closed
  // stream marks the connection stale and polling recovers the same state.
  const activeJobId = job?.jobId;
  const jobTerminal = job !== null && (job.state === 'succeeded' || job.state === 'failed');
  useEffect(() => {
    if (!activeJobId || typeof EventSource === 'undefined' || jobTerminal) return;
    let closed = false;
    let timer: number | undefined;
    const source = new EventSource(`/api/v2/jobs/${activeJobId}/events`);
    const adopt = (payload: JobSnapshot) => {
      setJob((current) => (current && payload.seq <= current.seq ? current : payload));
      setTransportState('live');
    };
    source.addEventListener('snapshot', (event) => {
      try {
        adopt(JSON.parse((event as MessageEvent).data) as JobSnapshot);
      } catch {
        /* discard malformed frames */
      }
    });
    source.addEventListener('progress', (event) => {
      try {
        adopt(JSON.parse((event as MessageEvent).data) as JobSnapshot);
      } catch {
        /* discard malformed frames */
      }
    });
    source.onerror = () => {
      source.close();
      setTransportState('offline');
      // Bounded polling recovers the authoritative state; the stream is stale,
      // not the work.
      let attempts = 0;
      timer = window.setInterval(async () => {
        attempts += 1;
        try {
          const current = await transport.get<JobSnapshot>(`/api/v2/jobs/${activeJobId}`);
          setJob((previous) =>
            previous && current.seq <= previous.seq ? previous : current,
          );
          setTransportState('live');
          if (current.state === 'succeeded' || current.state === 'failed') {
            window.clearInterval(timer);
          }
        } catch {
          /* keep the last confirmed state */
        }
        if (closed || attempts >= 60) window.clearInterval(timer);
      }, 2000);
    };
    return () => {
      closed = true;
      source.close();
      if (timer) window.clearInterval(timer);
    };
  }, [activeJobId, jobTerminal, transport]);

  const savePaper = async () => {
    setSaveState('pending');
    try {
      const record = await transport.post<SavedPaper>('/api/v2/c03/library-save-paper', {
        paper,
        policyRef: LIBRARY_POLICY,
      });
      setSaved(record);
      setSaveState('saved');
    } catch (error) {
      if (error instanceof ApiError && error.envelope.code === 'CONFLICT') {
        setSaveState('conflict');
        await loadSaved();
        return;
      }
      setSaveState(error instanceof ApiError && error.envelope.code === 'UNKNOWN_OUTCOME' ? 'unknown' : 'failed');
    }
  };

  const removePaper = async () => {
    if (!saved) return;
    setSaveState('pending');
    try {
      await transport.post('/api/v2/c03/library-remove-saved-paper', {
        savedPaperId: saved.savedPaperId,
        expectedRevision: saved.revision,
      });
      setSaved(null);
      setSaveState('idle');
    } catch (error) {
      setSaveState(error instanceof ApiError && error.envelope.code === 'CONFLICT' ? 'conflict' : 'failed');
      await loadSaved();
    }
  };

  const startWork = async (option: Option) => {
    setAssistNotice(notice('polite', '요청 접수 여부를 확인 중이에요'));
    try {
      const [glossary, fresh] = await Promise.all([
        transport.post<{ revision: string }>('/api/v2/c06/read-glossary', {}),
        transport.post<ContentRead>('/api/v2/c04/read-content', { paper, purpose: 'assistance' }),
      ]);
      if (!fresh.content) {
        setAssistNotice(notice('alert', '현재 이 작업을 사용할 수 없어요', 'source'));
        return;
      }
      const receipt = await transport.post<{ jobId: string; seq: number }>(
        '/api/v2/c06/accept-assistance',
        {
          paper,
          contentRevision: fresh.content.contentRevision,
          contentHash: fresh.content.contentHash,
          operation: option.operation,
          optionId: option.optionId,
          optionsRevision: options?.revision ?? readingRevision(read),
          glossaryRevision: glossary.revision,
          processingPolicy: PROCESSING_POLICY,
        },
      );
      const snapshot = await transport.get<JobSnapshot>(`/api/v2/jobs/${receipt.jobId}`);
      setJob(snapshot);
      setAssistNotice(notice('polite', '요청을 접수했어요'));
      await refreshHistory();
    } catch (error) {
      setAssistNotice(describeError(error));
    }
  };

  const openResult = async (jobId: string) => {
    try {
      const value = await transport.get<ResultRead>(`/api/v2/jobs/${jobId}/result`);
      setResult(value);
      focusHeading(resultHeading);
    } catch (error) {
      setAssistNotice(describeError(error));
    }
  };

  const title = read?.content?.paper ?? read?.paper ?? paper;
  return (
    <PanelSection title={read?.content ? '논문 읽기' : '논문'} titleRef={heading} testId="paper-workspace">
      <button type="button" className="link" onClick={onBack} data-testid="back-to-search">
        ← 검색으로 돌아가기
      </button>
      <p className="identity" data-testid="paper-identity">
        {title.paperId} · {title.versionId}
      </p>
      <StatusLine value={readError} />
      {read && read.availability !== 'ready' ? (
        <p className="muted" data-testid="paper-disposition">
          현재 원문을 읽을 수 없어요 ({read.availability})
        </p>
      ) : null}
      {!read && !readError ? <p role="status">불러오는 중이에요</p> : null}
      {read?.content ? (
        <>
          <ol className="sections" data-testid="reading-surface">
            {read.content.sections.map((section) => (
              <li key={section.sectionId} id={section.anchor}>
                <h3>{section.heading}</h3>
                <p>{section.text}</p>
              </li>
            ))}
          </ol>
          {read.content.limitations.map((limitation) => (
            <p className="muted" key={limitation}>
              {limitation}
            </p>
          ))}
          <p className="muted">
            <a href={read.content.sourceUrls[0]} rel="noreferrer noopener" target="_blank">
              원문 출처 열기
            </a>
          </p>
          <div className="row" data-testid="save-control">
            {saved ? (
              <>
                <span role="status">{SAVE_COPY.saved}</span>
                <button type="button" onClick={removePaper} data-testid="remove-paper">
                  저장 취소
                </button>
              </>
            ) : (
              <button
                type="button"
                onClick={savePaper}
                disabled={!signedIn || saveState === 'pending'}
                data-testid="save-paper"
              >
                {saveState === 'idle' || saveState === 'saved' ? '논문 저장' : SAVE_COPY[saveState]}
              </button>
            )}
            {saveState !== 'idle' && saveState !== 'saved' ? (
              <span role="status" data-testid="save-state">
                {SAVE_COPY[saveState]}
              </span>
            ) : null}
            {!signedIn ? <span className="muted">로그인하면 저장할 수 있어요</span> : null}
          </div>
          <AssistancePanel
            signedIn={signedIn}
            options={options}
            job={job}
            transportState={transportState}
            result={result}
            history={history}
            noticeValue={assistNotice}
            resultHeading={resultHeading}
            onStart={startWork}
            onOpenResult={openResult}
            onCloseResult={() => setResult(null)}
          />
        </>
      ) : null}
    </PanelSection>
  );
}

function readingRevision(read: ContentRead | null): string {
  return read?.content?.contentRevision ?? 'unavailable';
}

function PanelSection({
  title,
  titleRef,
  testId,
  children,
}: {
  title: string;
  titleRef: React.RefObject<HTMLHeadingElement | null>;
  testId: string;
  children: React.ReactNode;
}) {
  return (
    <section className="panel" data-testid={testId}>
      <h2 tabIndex={-1} ref={titleRef}>
        {title}
      </h2>
      {children}
    </section>
  );
}

function AssistancePanel({
  signedIn,
  options,
  job,
  transportState,
  result,
  history,
  noticeValue,
  resultHeading,
  onStart,
  onOpenResult,
  onCloseResult,
}: {
  signedIn: boolean;
  options: AssistanceOptions | null;
  job: JobSnapshot | null;
  transportState: string;
  result: ResultRead | null;
  history: HistoryRow[];
  noticeValue: Notice | null;
  resultHeading: React.RefObject<HTMLHeadingElement | null>;
  onStart: (option: Option) => void;
  onOpenResult: (jobId: string) => void;
  onCloseResult: () => void;
}) {
  const summary = useMemo(
    () => options?.options.find((option) => option.operation === 'summary'),
    [options],
  );
  const translation = useMemo(
    () => options?.options.find((option) => option.operation === 'translate'),
    [options],
  );
  return (
    <section className="panel assistance" aria-labelledby="assistance-heading" data-testid="assistance-panel">
      <h3 id="assistance-heading">요약과 번역</h3>
      {!signedIn ? <p className="muted">로그인하면 요약과 번역을 요청할 수 있어요</p> : null}
      <StatusLine value={noticeValue} />
      {signedIn && options && options.options.length === 0 ? (
        <p data-testid="assistance-unavailable">
          현재 이 작업을 사용할 수 없어요
          {options.limitations.map((limitation) => (
            <span className="muted block" key={limitation}>
              {limitation}
            </span>
          ))}
        </p>
      ) : null}
      {signedIn && options && options.options.length > 0 ? (
        <div className="row">
          <button type="button" disabled={!summary} onClick={() => summary && onStart(summary)} data-testid="start-summary">
            요약 시작
          </button>
          <button
            type="button"
            disabled={!translation}
            onClick={() => translation && onStart(translation)}
            data-testid="start-translation"
          >
            번역 시작
          </button>
        </div>
      ) : null}
      {job ? (
        <div className="job" data-testid="activity-card">
          <p role="status">
            {JOB_COPY[job.state] ?? job.state}
            {transportState === 'offline'
              ? ' · 연결이 끊겼어요. 마지막으로 확인된 상태를 표시해요'
              : ''}
          </p>
          {job.progress?.mode === 'determinate' &&
          typeof job.progress.current === 'number' &&
          typeof job.progress.total === 'number' &&
          job.progress.total > 1 ? (
            <progress value={job.progress.current} max={job.progress.total}>
              {job.progress.current}/{job.progress.total}
            </progress>
          ) : null}
          {job.error ? <p className="muted">{job.error.code}</p> : null}
          <button type="button" onClick={() => onOpenResult(job.jobId)} data-testid="open-result">
            결과 보기
          </button>
        </div>
      ) : null}
      {result ? (
        <section aria-labelledby="result-heading" className="result" data-testid="prepared-result">
          <h4 id="result-heading" tabIndex={-1} ref={resultHeading}>
            준비된 결과
          </h4>
          {result.availability === 'ready' && result.prepared ? (
            <>
              <p className="muted">
                {result.prepared.operation} · {result.prepared.paper.paperId} ·{' '}
                {result.prepared.paper.versionId}
              </p>
              <ol>
                {result.prepared.sections.map((section) => (
                  <li key={section.sectionId}>{section.text}</li>
                ))}
              </ol>
              <p className="muted">
                {result.prepared.coverage} · {result.prepared.limitations.join(' ')}
              </p>
            </>
          ) : (
            <p data-testid="result-disposition">{resultCopy(result.availability)}</p>
          )}
          <button type="button" onClick={onCloseResult} data-testid="close-result">
            닫기
          </button>
        </section>
      ) : null}
      {history.length > 0 ? (
        <div data-testid="prior-assistance">
          <h4>이전 요청</h4>
          <ul>
            {history.map((row) => (
              <li key={row.jobId}>
                <span>
                  {row.operation} · {resultCopy(row.availability)}
                </span>
                {row.availability === 'ready' ? (
                  <button type="button" onClick={() => onOpenResult(row.jobId)}>
                    결과 다시 읽기
                  </button>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

function resultCopy(availability: string): string {
  switch (availability) {
    case 'ready':
      return '결과가 준비되었어요';
    case 'pending':
      return '아직 결과를 만들고 있어요';
    case 'failed':
      return '결과를 만들지 못했어요';
    case 'expired':
      return '결과 보관 기간이 지났어요';
    case 'withdrawn':
      return '원문이 더 이상 제공되지 않아요';
    case 'restricted':
      return '현재 이 결과를 읽을 수 없어요';
    default:
      return '결과를 확인할 수 없어요';
  }
}
