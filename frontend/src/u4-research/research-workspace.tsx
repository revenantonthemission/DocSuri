import React, { useEffect, useId, useRef, useState } from 'react';
import type { Transport } from '../api';
import { describeError, StatusLine, type Notice } from '../ui';
import { ActionStatus, useResearchAction } from './action';
import {
  emptyScope,
  researchCall,
  RESEARCH_LIMITS,
  utf8Bytes,
  type Artifact,
  type Context,
  type Deletion,
  type Policy,
  type Session,
  type Sessions,
} from './api';
import { NoveltyDiscussion, ResearchComposer } from './composer';
import { forgetJobLink, keepJobLink, readJobLink, ResearchJob, type JobLink } from './jobs';
import './research.css';

export function ResearchWorkspace({
  client,
  purpose,
  active = true,
  degraded = false,
  synthetic = false,
  policy,
}: {
  client: Transport;
  purpose: 'research' | 'novelty';
  active?: boolean;
  degraded?: boolean;
  synthetic?: boolean;
  policy: Policy;
}) {
  const [listing, setListing] = useState<Sessions | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [context, setContext] = useState<Context | null>(null);
  const [title, setTitle] = useState('');
  const titleBudgetId = useId();
  const titleBytes = utf8Bytes(title);
  const titleOverLimit = titleBytes > RESEARCH_LIMITS.titleBytes;
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Notice | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [allConfirmed, setAllConfirmed] = useState(false);
  const [deletion, setDeletion] = useState<string | null>(null);
  const [job, setJob] = useState<JobLink | null>(() => {
    const value = readJobLink();
    return value && (purpose === 'research') === (value.kind === 'research-turn') ? value : null;
  });
  const [recoveryNavigation, setRecoveryNavigation] = useState(0);
  const [novelty, setNovelty] = useState<Artifact | null>(null);
  const action = useResearchAction(client);
  const heading = useRef<HTMLHeadingElement>(null);
  const alive = useRef(true);
  const listingRequest = useRef(0);
  const loaded = useRef(false);
  const load = async (cursor?: string) => {
    const request = ++listingRequest.current;
    setLoading(true);
    setError(null);
    setAllConfirmed(false);
    try {
      const value = await researchCall(client, 'list-research-sessions', {
        page: { limit: 10, ...(cursor ? { cursor } : {}) },
      });
      if (alive.current && request === listingRequest.current) setListing(value);
    } catch (failure) {
      if (alive.current && request === listingRequest.current) setError(describeError(failure));
    } finally {
      if (alive.current && request === listingRequest.current) setLoading(false);
    }
  };
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      listingRequest.current += 1;
    };
  }, []);
  useEffect(() => {
    const followLink = () => {
      const target = readJobLink();
      setNovelty(null);
      setJob(
        target && (purpose === 'research') === (target.kind === 'research-turn') ? target : null,
      );
      // Reopening a URL rechecks current authority, including within this same document.
      setRecoveryNavigation((value) => value + 1);
    };
    window.addEventListener('hashchange', followLink);
    return () => window.removeEventListener('hashchange', followLink);
  }, [purpose]);
  useEffect(() => {
    if (active && purpose === 'research' && !loaded.current) {
      loaded.current = true;
      void load();
    }
    // Explicit subsequent refreshes preserve the current editing session.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, purpose]);
  const accepted = (value: JobLink) => {
    setJob(value);
    keepJobLink(value);
  };
  const deleted = (result: Deletion, label: string) => {
    setDeletion(
      result.state === 'complete'
        ? `${label} 정리가 완료됐어요`
        : `${label} 삭제 경계를 확인했어요. 정리 상태: ${result.state}. 남은 작업 ${result.remainingJobIds.length}개. ${result.limitations.join(' ')}`,
    );
    setSession(null);
    setContext(null);
    setJob(null);
    setNovelty(null);
    setConfirmed(false);
    setAllConfirmed(false);
    forgetJobLink();
    void load();
  };
  const open = async (id: string) => {
    const value = await researchCall(client, 'read-research-session', { sessionId: id });
    if (value.lifecycle !== 'active') throw new Error('session unavailable');
    setSession(value);
    setContext(null);
    setJob(null);
    setNovelty(null);
    setConfirmed(false);
    setDeletion(null);
    forgetJobLink();
    heading.current?.focus();
  };
  return (
    <section
      className="panel research-workspace"
      hidden={!active}
      aria-label={purpose === 'research' ? '연구 공간' : '참신성 분석 공간'}
      data-testid={`workspace-${purpose}`}
    >
      <h2 ref={heading} tabIndex={-1}>
        {purpose === 'research' ? '근거로 이어가는 연구' : '참신성 분석'}
      </h2>
      <p>
        {purpose === 'research'
          ? '자료를 읽고 질문하며, 확인된 결과로 다시 돌아오세요.'
          : '주제와 기존 연구의 관계를 검토하세요. 분석은 참신성의 증명이 아니에요.'}
      </p>
      {degraded ? (
        <p role="status">
          일부 연구 기능이 제한되어 있어요. 지원 범위와 결과의 한계를 확인해 주세요.
        </p>
      ) : null}
      {synthetic ? (
        <p>
          현재 합성 자료로 동작을 확인하는 환경이에요. 실제 연구 자료 처리와 전체 기능 제공은 아직
          검증되지 않았어요.
        </p>
      ) : null}
      {purpose === 'research' ? (
        <section aria-label="내 연구 목록">
          <h3>이어서 연구하기</h3>
          <button type="button" disabled={loading || action.busy} onClick={() => void load()}>
            연구 목록 새로고침
          </button>
          {loading ? (
            <p role="status">연구 목록을 확인하고 있어요</p>
          ) : listing?.sessions.length === 0 ? (
            <p>저장된 연구가 없어요. 새 연구를 시작해 보세요.</p>
          ) : null}
          <StatusLine value={error} />
          <ul className="research-session-list">
            {listing?.sessions.map((item, index) => (
              <li key={item.sessionId}>
                <button
                  type="button"
                  disabled={action.busy || action.unknown || item.lifecycle !== 'active'}
                  aria-current={session?.sessionId === item.sessionId ? 'true' : undefined}
                  onClick={() => void action.run(() => open(item.sessionId))}
                >
                  연구 {index + 1} 열기 · 질문 {item.turnIds.length}개
                </button>
              </li>
            ))}
          </ul>
          {listing?.page.nextCursor ? (
            <button
              type="button"
              disabled={loading}
              onClick={() => void load(listing.page.nextCursor!)}
            >
              다음 연구 목록
            </button>
          ) : null}
          <details className="control-group">
            <summary>모든 연구 삭제</summary>
            <div className="control-confirmation">
              <p>
                현재 계정의 모든 연구 세션과 연결된 질문, 작업, 초안, 첨부, 결과가 대상이에요. 실제
                정리와 백업 처리의 남은 제한은 응답에서 확인해요.
              </p>
              <label className="check-row">
                <input
                  type="checkbox"
                  checked={allConfirmed}
                  disabled={!listing || loading || action.busy || action.unknown}
                  onChange={(event) => setAllConfirmed(event.target.checked)}
                />
                현재 계정의 모든 연구 삭제 범위를 확인했습니다
              </label>
              <button
                type="button"
                disabled={!listing || !allConfirmed || loading || action.busy || action.unknown}
                onClick={() =>
                  void action.run(async (key) => {
                    const result = await researchCall(
                      client,
                      'delete-research-sessions',
                      {
                        scope: 'all-sessions',
                        expectedRevision: listing!.page.snapshotRevision,
                        confirmed: true,
                        policy,
                      },
                      key,
                    );
                    deleted(result, '모든 연구');
                  })
                }
              >
                모든 연구 삭제 확인
              </button>
            </div>
          </details>
        </section>
      ) : null}
      <form
        aria-label="새 연구 시작"
        onSubmit={(event) => {
          event.preventDefault();
          if (purpose === 'research' && (!title.trim() || titleOverLimit)) return;
          // Keep both keys stable if context creation succeeded but session acknowledgement was lost.
          let allocated = context;
          const sessionKey = crypto.randomUUID();
          void action.run(async (key) => {
            if (!allocated) {
              allocated = await researchCall(
                client,
                'create-research-context',
                { purpose, policy },
                key,
              );
              setContext(allocated);
            }
            if (purpose === 'research') {
              const value = await researchCall(
                client,
                'create-research-session',
                { title, scope: emptyScope(allocated.contextId, policy) },
                sessionKey,
              );
              setSession(value);
              setContext(null);
              setTitle('');
              void load();
            }
            setJob(null);
            setNovelty(null);
            setDeletion(null);
            setConfirmed(false);
            forgetJobLink();
            heading.current?.focus();
          });
        }}
      >
        <fieldset disabled={action.busy || action.unknown}>
          {purpose === 'research' ? (
            <label>
              새 연구 이름
              <input
                aria-label="새 연구 이름"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                maxLength={RESEARCH_LIMITS.titleBytes}
                aria-invalid={titleOverLimit}
                aria-describedby={titleBudgetId}
                autoComplete="off"
              />
            </label>
          ) : null}
          {purpose === 'research' ? (
            <p id={titleBudgetId} role={titleOverLimit ? 'alert' : undefined}>
              이름 용량 {titleBytes} / {RESEARCH_LIMITS.titleBytes} UTF-8 바이트
              {titleOverLimit ? ' · 한도를 초과했어요. 이름을 줄여 주세요.' : ''}
            </p>
          ) : null}
          <button
            type="submit"
            disabled={purpose === 'research' ? !title.trim() || titleOverLimit : !!context}
          >
            {' '}
            {purpose === 'research' ? '새 연구 시작' : '새 분석 준비'}{' '}
          </button>
        </fieldset>
      </form>
      <ActionStatus action={action} />
      {session ? (
        <section aria-label="현재 연구">
          <ResearchComposer
            key={session.sessionId}
            client={client}
            session={session}
            scope={session.scope}
            purpose="research"
            policy={policy}
            onAccepted={accepted}
          />
          <section className="control-group">
            <h3>전송한 질문 다시 보기</h3>
            {session.turnIds.length === 0 ? (
              <p>목록을 새로 열면 확인된 질문을 볼 수 있어요.</p>
            ) : (
              session.turnIds.map((id, index) => (
                <button
                  key={id}
                  type="button"
                  disabled={action.busy || action.unknown}
                  onClick={() =>
                    void action.run(async () => {
                      const turn = await researchCall(client, 'read-research-turn', {
                        sessionId: session.sessionId,
                        turnId: id,
                      });
                      if (turn.sessionId !== session.sessionId)
                        throw new Error('turn binding mismatch');
                      accepted({
                        jobId: String(turn.job.jobId),
                        kind: 'research-turn',
                        contextId: session.scope.contextId,
                      });
                    })
                  }
                >
                  질문 {index + 1} 진행 및 결과 보기
                </button>
              ))
            )}
          </section>
          <details className="control-group">
            <summary>현재 연구 삭제</summary>
            <div className="control-confirmation">
              <p>
                현재 연구의 질문, 대기 작업, 초안, 첨부와 파생 결과에 삭제 경계를 설정합니다. 실제
                정리 결과와 남은 제한은 응답에서 확인합니다.
              </p>
              <label className="check-row">
                <input
                  type="checkbox"
                  checked={confirmed}
                  onChange={(event) => setConfirmed(event.target.checked)}
                />
                현재 연구 삭제 범위를 확인했습니다
              </label>
              <button
                type="button"
                disabled={!confirmed || action.busy || action.unknown}
                onClick={() =>
                  void action.run(async (key) => {
                    const result = await researchCall(
                      client,
                      'delete-research-sessions',
                      {
                        scope: 'one-session',
                        sessionId: session.sessionId,
                        expectedRevision: session.revision,
                        confirmed: true,
                        policy,
                      },
                      key,
                    );
                    deleted(result, '현재 연구');
                  })
                }
              >
                현재 연구 삭제 확인
              </button>
            </div>
          </details>
        </section>
      ) : null}
      {deletion ? <p role="status">{deletion}</p> : null}
      {purpose === 'novelty' && context ? (
        <ResearchComposer
          key={context.contextId}
          client={client}
          scope={emptyScope(context.contextId, policy)}
          purpose="novelty"
          policy={policy}
          onAccepted={accepted}
        />
      ) : null}
      {job ? (
        <ResearchJob
          key={`${job.jobId}:${recoveryNavigation}`}
          client={client}
          reference={job}
          onNoveltyResult={setNovelty}
        />
      ) : null}
      {novelty ? (
        <NoveltyDiscussion
          key={novelty.artifact.artifactId}
          client={client}
          source={novelty}
          policy={policy}
          onAccepted={accepted}
        />
      ) : null}
    </section>
  );
}
