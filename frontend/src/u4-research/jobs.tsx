import React, { useEffect, useRef, useState } from 'react';
import { ApiError, type Transport } from '../api';
import { describeError, StatusLine, type Notice } from '../ui';
import { ActionStatus, useResearchAction } from './action';
import {
  checkedJob,
  researchCall,
  type Artifact,
  type ArtifactResponse,
  type Job,
  type JobKind,
} from './api';
import { EvidenceResult } from './evidence';

export type JobLink = { jobId: string; kind: JobKind; contextId: string };
const safeId = /^[a-zA-Z0-9_.:-]{1,128}$/;
export function readJobLink(hash = window.location.hash): JobLink | null {
  if (!hash.startsWith('#research-job?')) return null;
  const query = new URLSearchParams(hash.slice('#research-job?'.length));
  if ([...query.keys()].length !== 3) return null;
  const jobId = query.get('jobId') ?? '',
    kind = query.get('kind') ?? '',
    contextId = query.get('contextId') ?? '';
  if (
    !safeId.test(jobId) ||
    !safeId.test(contextId) ||
    !['research-turn', 'novelty-analysis', 'novelty-discussion'].includes(kind)
  )
    return null;
  return { jobId, kind: kind as JobKind, contextId };
}
export function keepJobLink(value: JobLink) {
  // Opaque references only. Every restore reauthorizes through C07; no browser text storage.
  const hash = `#research-job?${new URLSearchParams(value)}`;
  window.history.replaceState(null, '', `${window.location.pathname}${hash}`);
}
export function forgetJobLink() {
  if (window.location.hash.startsWith('#research-job?'))
    window.history.replaceState(null, '', window.location.pathname);
}

const STATE: Record<Job['state'], string> = {
  accepted: '접수됨 · 실행을 기다리고 있어요',
  running: '실행 중이에요',
  cancel_requested: '취소 요청을 확인했어요 · 아직 취소 완료가 아니에요',
  cancelled: '취소가 완료됐어요',
  succeeded: '완료됐어요 · 준비된 결과를 열 수 있어요',
  failed: '작업이 실패했어요 · 새 작업을 자동으로 시작하지 않아요',
};

export function ResearchJob({
  client,
  reference,
  onNoveltyResult,
}: {
  client: Transport;
  reference: JobLink;
  onNoveltyResult?: (value: Artifact | null) => void;
}) {
  const [job, setJob] = useState<Job | null>(null);
  const [result, setResult] = useState<ArtifactResponse | null>(null);
  const [error, setError] = useState<Notice | null>(null);
  const [loading, setLoading] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const latest = useRef<Job | null>(null);
  const request = useRef(0);
  const alive = useRef(true);
  const action = useResearchAction(client);
  // These controls stay focusable while their read runs (aria-disabled, not disabled): a
  // focused button that becomes disabled drops keyboard focus to the document, and Tab
  // then restarts at the top of the page (WCAG 2.4.3). Their handlers ignore presses.
  const refreshUnavailable = loading || action.busy;
  const openUnavailable = action.busy || action.unknown;
  const update = (next: Job) => {
    checkedJob(next, reference);
    if (latest.current && next.seq < latest.current.seq) return;
    if (
      latest.current &&
      next.seq === latest.current.seq &&
      (next.state !== latest.current.state || next.revision !== latest.current.revision)
    )
      return;
    if (
      latest.current &&
      ['succeeded', 'failed', 'cancelled'].includes(latest.current.state) &&
      next.state !== latest.current.state
    )
      return;
    latest.current = next;
    setJob(next);
  };
  const refresh = async () => {
    const id = ++request.current;
    setLoading(true);
    setError(null);
    try {
      const value = await researchCall(client, 'read-research-job', reference);
      if (alive.current && id === request.current) update(value);
    } catch (failure) {
      if (alive.current && id === request.current) {
        if (
          failure instanceof ApiError &&
          ['UNAUTHENTICATED', 'FORBIDDEN', 'NOT_FOUND', 'SOURCE_INELIGIBLE'].includes(
            failure.envelope.code,
          )
        ) {
          latest.current = null;
          setJob(null);
          setResult(null);
          onNoveltyResult?.(null);
        }
        setError(describeError(failure));
      }
    } finally {
      if (alive.current && id === request.current) setLoading(false);
    }
  };
  useEffect(() => {
    alive.current = true;
    void refresh();
    return () => {
      alive.current = false;
      request.current += 1;
    };
    // Parent keys this view by job identity; opening or refreshing is a pure read.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client, reference.jobId, reference.contextId, reference.kind]);
  return (
    <section className="research-job" aria-label="연구 작업 상태">
      <h3>
        {reference.kind === 'research-turn'
          ? '질문 진행 상태'
          : reference.kind === 'novelty-analysis'
            ? '분석 진행 상태'
            : '결과 토론 진행 상태'}
      </h3>
      <p role="status">
        {loading
          ? '현재 상태를 확인하고 있어요'
          : job
            ? STATE[job.state]
            : '아직 작업 상태를 확인하지 못했어요'}
      </p>
      {job?.progress.mode === 'determinate' ? (
        <progress aria-label="작업 진행" value={job.progress.current} max={job.progress.total} />
      ) : null}
      <button
        type="button"
        aria-disabled={refreshUnavailable}
        onClick={() => {
          if (!refreshUnavailable) void refresh();
        }}
      >
        진행 상태 새로고침
      </button>
      <p className="muted">
        이 페이지 주소로 다시 돌아올 수 있어요. 로그인과 현재 접근 권한을 다시 확인하며, 열람으로
        작업을 재실행하지 않아요.
      </p>
      <StatusLine value={error} />
      {job?.state === 'succeeded' && job.result ? (
        <button
          type="button"
          aria-disabled={openUnavailable}
          onClick={() => {
            if (openUnavailable) return;
            void action.run(async () => {
              const generation = request.current;
              // A new authority check must not leave an earlier private result on screen if refused.
              setResult(null);
              onNoveltyResult?.(null);
              const source = job.result!;
              const value = await researchCall(client, 'read-research-artifact', {
                artifact: {
                  artifactId: source.resultId,
                  revision: source.revision,
                  contentHash: source.contentHash,
                },
              });
              if (!alive.current || generation !== request.current) return;
              if (
                value.availability === 'ready' &&
                (value.prepared.artifact.artifactId !== source.resultId ||
                  value.prepared.artifact.revision !== source.revision ||
                  value.prepared.artifact.contentHash !== source.contentHash ||
                  value.prepared.contextId !== reference.contextId)
              )
                throw new Error('artifact binding mismatch');
              setResult(value);
              if (value.availability === 'ready' && value.prepared.kind === 'novelty-result')
                onNoveltyResult?.(value.prepared);
            });
          }}
        >
          준비된 결과 열기
        </button>
      ) : null}
      {reference.kind === 'novelty-analysis' &&
      job &&
      ['accepted', 'running'].includes(job.state) ? (
        <div className="control-confirmation">
          <label className="check-row">
            <input
              type="checkbox"
              checked={confirm}
              onChange={(event) => setConfirm(event.target.checked)}
            />
            현재 분석의 취소를 요청합니다. 이미 완료된 결과는 유지됩니다.
          </label>
          <button
            type="button"
            disabled={!confirm || action.busy || action.unknown}
            onClick={() =>
              void action.run(async (key) => {
                update(await researchCall(client, 'cancel-novelty-analysis', reference, key));
                setConfirm(false);
              })
            }
          >
            분석 취소 요청
          </button>
        </div>
      ) : null}
      <ActionStatus action={action} />
      {result ? <EvidenceResult value={result} /> : null}
    </section>
  );
}
