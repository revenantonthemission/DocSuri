/**
 * U3 assistance and glossary surfaces: reconciled options, accepted work with
 * ordered progress (EventSource + polling fallback), prepared results and the
 * owner glossary editor with visible compare-and-swap conflicts.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, Transport, dispositionCopy } from '../api';
import { Notice, StatusLine, notice } from '../ui';
import {
  AssistanceOptions,
  Glossary,
  JobSnapshot,
  PaperRef,
  PreparedResult,
  api,
  operationKey,
} from './api';

const KEY_PREFIX = 'docsuri.u3.operation';
const JOB_PREFIX = 'docsuri.u3.job';

function storedKey(paperId: string, operation: string): string | null {
  try {
    return window.localStorage.getItem(`${KEY_PREFIX}.${paperId}.${operation}`);
  } catch {
    return null;
  }
}

function keepKey(paperId: string, operation: string, value: string): void {
  try {
    window.localStorage.setItem(`${KEY_PREFIX}.${paperId}.${operation}`, value);
  } catch {
    /* a restricted storage keeps the in-memory key for this session only */
  }
}

function storedJob(paperId: string): string | null {
  try {
    return window.localStorage.getItem(`${JOB_PREFIX}.${paperId}`);
  } catch {
    return null;
  }
}

function keepJob(paperId: string, jobId: string): void {
  try {
    window.localStorage.setItem(`${JOB_PREFIX}.${paperId}`, jobId);
  } catch {
    /* the in-memory identity still serves this session */
  }
}

export function AssistanceSection({
  client,
  paper,
  contentRevision,
  contentHash,
  signedIn,
}: {
  client: Transport;
  paper: PaperRef;
  contentRevision: string;
  contentHash: string;
  signedIn: boolean;
}) {
  const [options, setOptions] = useState<AssistanceOptions | null>(null);
  const [glossaryRevision, setGlossaryRevision] = useState<string | null>(null);
  const [job, setJob] = useState<JobSnapshot | null>(null);
  const [result, setResult] = useState<PreparedResult | null>(null);
  const [status, setStatus] = useState<Notice | null>(null);
  const [busy, setBusy] = useState(false);
  const eventSource = useRef<EventSource | null>(null);
  const pollTimer = useRef<number | null>(null);

  useEffect(() => {
    if (!signedIn) return;
    let active = true;
    Promise.all([api.assistanceOptions(client, paper), api.readGlossary(client)])
      .then(([optionsValue, glossary]) => {
        if (!active) return;
        setOptions(optionsValue);
        setGlossaryRevision(glossary.revision);
      })
      .catch((error) => {
        if (active) setStatus(describe(error));
      });
    return () => {
      active = false;
    };
  }, [client, paper, signedIn]);

  const stopTransports = useCallback(() => {
    eventSource.current?.close();
    eventSource.current = null;
    if (pollTimer.current !== null) {
      window.clearInterval(pollTimer.current);
      pollTimer.current = null;
    }
  }, []);

  useEffect(() => stopTransports, [stopTransports]);

  const refreshSnapshot = useCallback(
    async (jobId: string) => {
      try {
        const snapshot = await api.job(client, jobId);
        setJob(snapshot);
        if (snapshot.state === 'succeeded' || snapshot.state === 'failed') {
          stopTransports();
          const prepared = await api.preparedResult(client, jobId);
          setResult(prepared);
          setStatus(
            notice(
              snapshot.state === 'succeeded' ? 'polite' : 'alert',
              snapshot.state === 'succeeded' ? '결과가 준비되었어요' : '작업을 완료하지 못했어요',
            ),
          );
        }
        return snapshot;
      } catch (error) {
        stopTransports();
        setStatus(describe(error));
        return null;
      }
    },
    [client, stopTransports],
  );

  const watch = useCallback(
    (jobId: string) => {
      stopTransports();
      if (typeof window.EventSource === 'function') {
        const source = new window.EventSource(`/api/v2/jobs/${jobId}/events`);
        eventSource.current = source;
        source.addEventListener('snapshot', (event) => {
          try {
            const snapshot = JSON.parse((event as MessageEvent).data) as JobSnapshot;
            setJob((current) => (current && current.seq > snapshot.seq ? current : snapshot));
            if (snapshot.state === 'succeeded' || snapshot.state === 'failed') {
              stopTransports();
              void refreshSnapshot(jobId);
            }
          } catch {
            /* a malformed frame is ignored; the poll fallback still recovers */
          }
        });
        source.onerror = () => {
          // Fall back to the same authoritative snapshot; never execute work.
          source.close();
          eventSource.current = null;
          if (pollTimer.current === null) {
            pollTimer.current = window.setInterval(() => void refreshSnapshot(jobId), 2000);
          }
        };
      } else {
        pollTimer.current = window.setInterval(() => void refreshSnapshot(jobId), 2000);
      }
    },
    [refreshSnapshot, stopTransports],
  );

  useEffect(() => {
    if (!signedIn) return;
    // A revisit reads the retained job and result; it never starts new work.
    const jobId = storedJob(paper.paperId);
    if (jobId) void refreshSnapshot(jobId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client, paper.paperId, signedIn]);

  const accept = async (optionId: string) => {
    if (!options || !glossaryRevision) return;
    const option = options.options.find((item) => item.optionId === optionId);
    if (!option) return;
    setBusy(true);
    // One operation key per intended submission; a lost reply retries with it.
    const key = storedKey(paper.paperId, option.operation) ?? operationKey();
    keepKey(paper.paperId, option.operation, key);
    try {
      const receipt = await api.acceptAssistance(
        client,
        { paper, contentRevision, contentHash, option, optionsRevision: options.revision, glossaryRevision },
        key,
      );
      setResult(null);
      keepJob(paper.paperId, receipt.jobId);
      setStatus(notice('polite', '작업을 접수했어요'));
      void refreshSnapshot(receipt.jobId);
      watch(receipt.jobId);
    } catch (error) {
      setStatus(describe(error));
    } finally {
      setBusy(false);
    }
  };

  if (!signedIn) {
    return (
      <section className="panel" data-testid="assistance-unavailable">
        <h3>요약·번역</h3>
        <p>로그인하면 선택한 구간에 대한 요약과 번역을 요청할 수 있어요.</p>
      </section>
    );
  }

  return (
    <section className="panel" data-testid="assistance-panel">
      <h3>요약·번역</h3>
      <StatusLine value={status} />
      {options && options.options.length ? (
        <div data-testid="assistance-options">
          {options.options.map((option) => (
            <button
              key={option.optionId}
              type="button"
              disabled={busy}
              onClick={() => void accept(option.optionId)}
              data-testid={`start-${option.operation}`}
            >
              {option.labelKey}
            </button>
          ))}
          {options.limitations.map((item) => (
            <p key={item} className="subtle">
              {item}
            </p>
          ))}
        </div>
      ) : options ? (
        <p role="status" data-testid="assistance-unavailable">
          현재 사용할 수 있는 요약·번역 옵션이 없어요
        </p>
      ) : (
        <p role="status">옵션을 불러오는 중…</p>
      )}
      {job ? (
        <div data-testid="activity-card" aria-live="polite">
          <p data-testid="job-progress">
            {job.progress.mode === 'determinate'
              ? `진행 ${job.progress.current}/${job.progress.total}`
              : '진행 중'}
            {' · '}
            {job.state}
          </p>
          <p className="subtle">순서 {job.seq}</p>
          {job.error ? <p role="alert">{dispositionCopy(job.error.code)}</p> : null}
        </div>
      ) : null}
      {result?.availability === 'ready' ? (
        <article data-testid="prepared-result">
          <h4>준비된 결과</h4>
          {result.prepared.sections.map((section) => (
            <section key={section.sectionId}>
              <h5>{section.heading}</h5>
              <p>{section.text}</p>
            </section>
          ))}
          <p className="subtle">범위 {result.prepared.coverage}</p>
          {result.prepared.limitations.map((item) => (
            <p key={item} className="subtle">
              {item}
            </p>
          ))}
        </article>
      ) : result ? (
        <div data-testid={result.availability === 'expired' ? 'result-expired' : 'result-state'}>
          <p>
            {result.availability === 'expired'
              ? '보관 기간이 지난 결과예요. 다시 요청하려면 새로 접수해 주세요.'
              : result.availability === 'pending'
                ? '결과를 준비하고 있어요'
                : '결과를 사용할 수 없어요'}
          </p>
        </div>
      ) : null}
    </section>
  );
}

export function GlossarySection({
  client,
  signedIn,
}: {
  client: Transport;
  signedIn: boolean;
}) {
  const [glossary, setGlossary] = useState<Glossary | null>(null);
  const [source, setSource] = useState('');
  const [preferred, setPreferred] = useState('');
  const [conflict, setConflict] = useState<string | null>(null);
  const [status, setStatus] = useState<Notice | null>(null);

  useEffect(() => {
    if (!signedIn) return;
    let active = true;
    api
      .readGlossary(client)
      .then((value) => {
        if (active) setGlossary(value);
      })
      .catch((error) => {
        if (active) setStatus(describe(error));
      });
    return () => {
      active = false;
    };
  }, [client, signedIn]);

  if (!signedIn) {
    return (
      <section className="panel" data-testid="glossary-editor">
        <h3>용어집</h3>
        <p>로그인하면 용어 선호를 관리할 수 있어요.</p>
      </section>
    );
  }

  const save = async () => {
    if (!glossary) return;
    const term = {
      termId: crypto.randomUUID(),
      source: source.trim(),
      preferred: preferred.trim(),
      languageId: 'ko',
    };
    if (!term.source || !term.preferred) {
      setStatus(notice('alert', '원어와 선호 용어를 모두 입력해 주세요'));
      return;
    }
    setStatus(notice('polite', '저장하고 있어요'));
    try {
      const updated = await api.replaceGlossary(client, glossary, [...glossary.terms, term]);
      setGlossary(updated);
      setConflict(null);
      setSource('');
      setPreferred('');
      setStatus(notice('polite', '용어집을 저장했어요'));
    } catch (error) {
      if (error instanceof ApiError && error.envelope.code === 'CONFLICT') {
        setConflict('다른 곳에서 용어집이 변경되었어요. 최신 내용을 확인해 주세요.');
        const latest = await api.readGlossary(client).catch(() => null);
        if (latest) setGlossary(latest);
      }
      setStatus(describe(error));
    }
  };

  return (
    <section className="panel" data-testid="glossary-editor">
      <h3>용어집</h3>
      <StatusLine value={status} />
      {conflict ? (
        <p role="alert" data-testid="glossary-conflict">
          {conflict}
        </p>
      ) : null}
      <ul>
        {(glossary?.terms ?? []).map((term) => (
          <li key={term.termId} data-testid="glossary-term">
            {term.source} → {term.preferred}
          </li>
        ))}
      </ul>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void save();
        }}
      >
        <label htmlFor="glossary-source">원어</label>
        <input
          id="glossary-source"
          value={source}
          onChange={(event) => setSource(event.target.value)}
          maxLength={64}
          data-testid="glossary-source"
        />
        <label htmlFor="glossary-preferred">선호 용어</label>
        <input
          id="glossary-preferred"
          value={preferred}
          onChange={(event) => setPreferred(event.target.value)}
          maxLength={64}
          data-testid="glossary-preferred"
        />
        <button type="submit" data-testid="glossary-save">
          저장
        </button>
      </form>
      {glossary ? (
        <p className="subtle" data-testid="glossary-revision">
          개정 {glossary.revision.slice(0, 8)}
        </p>
      ) : null}
    </section>
  );
}

function describe(error: unknown): Notice {
  if (error instanceof ApiError) {
    return notice('alert', dispositionCopy(error.envelope.code), error.envelope.requestId);
  }
  return notice('alert', '요청을 완료하지 못했어요');
}
