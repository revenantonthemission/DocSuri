import React, { useEffect, useState } from 'react';
import type {
  WorkspaceSettingsSnapshot as Settings,
  WorkspaceSettingsSuggestionPage as Suggestions,
  WorkspaceSettingsResetPage as ResetPage,
  WorkspaceSettingsResetStatus as ResetStatus,
  WorkspaceSettingsResetResult as ResetResult,
} from '../types/wire/dtos';
import { PolicyRef, SETTINGS_POLICY, Transport } from './api';
import { Panel, StatusLine, describeError } from './ui';
import { Disclosure, Field, OperationStatus, useOperation, useRead } from './control-ui';

export function PersonalControls({
  client,
  policy,
  onAppearance,
}: {
  client: Transport;
  policy: PolicyRef;
  onAppearance: (value: 'light' | 'dark' | 'system') => void;
}) {
  const settings = useRead<Settings>(client, '/api/v2/c03/settings-read');
  const suggestions = useRead<Suggestions>(client, '/api/v2/c03/settings-list-suggestions', {
    page: { limit: 25 },
  });
  const [draft, setDraft] = useState<Settings | null>(null);
  const operation = useOperation();
  useEffect(() => {
    if (settings.value) setDraft(settings.value);
  }, [settings.value]);
  const saveInterests = (action: 'save_interests' | 'complete' | 'skip') =>
    void operation.run(async (key) => {
      if (!draft) return;
      const value = await client.post<Settings>(
        '/api/v2/c03/settings-update-onboarding',
        {
          action,
          interestIds: draft.interestIds,
          expectedRevision: draft.revision,
          policyRef: SETTINGS_POLICY,
        },
        key,
      );
      settings.setValue(value);
    });
  return (
    <Panel title="개인 설정" testId="personal-controls">
      <StatusLine value={settings.error} />
      <OperationStatus operation={operation} />
      <button
        type="button"
        onClick={() =>
          void settings.load().then((value) => {
            if (value) setDraft(value);
          })
        }
      >
        저장된 설정 다시 읽기
      </button>
      {settings.loading ? <p role="status">설정을 읽고 있어요</p> : null}
      {draft ? (
        <>
          <form
            className="stack"
            onSubmit={(event) => {
              event.preventDefault();
              void operation.run(async (key) => {
                const value = await client.post<Settings>(
                  '/api/v2/c03/settings-update',
                  {
                    searchDefaults: draft.searchDefaults,
                    assistanceDefaults: draft.assistanceDefaults,
                    appearance: draft.appearance,
                    expectedRevision: draft.revision,
                    policyRef: SETTINGS_POLICY,
                  },
                  key,
                );
                settings.setValue(value);
                onAppearance(value.appearance);
              });
            }}
          >
            <fieldset disabled={operation.busy || operation.unknown}>
              <label>
                기본 검색 방식
                <select
                  aria-label="기본 검색 방식"
                  value={draft.searchDefaults.modeId}
                  onChange={(event) =>
                    setDraft({
                      ...draft,
                      searchDefaults: { ...draft.searchDefaults, modeId: event.target.value },
                    })
                  }
                >
                  <option value="lexical">어휘 검색</option>
                  <option value="semantic">의미 검색 (현재 제공 범위 확인 필요)</option>
                </select>
              </label>
              <label>
                기본 정렬
                <select
                  aria-label="기본 정렬"
                  value={draft.searchDefaults.orderId}
                  onChange={(event) =>
                    setDraft({
                      ...draft,
                      searchDefaults: { ...draft.searchDefaults, orderId: event.target.value },
                    })
                  }
                >
                  <option value="relevance">관련도</option>
                  <option value="newest">최신순</option>
                </select>
              </label>
              <label>
                기본 도움 기능
                <select
                  aria-label="기본 도움 기능"
                  value={draft.assistanceDefaults.actionId}
                  onChange={(event) =>
                    setDraft({
                      ...draft,
                      assistanceDefaults: {
                        ...draft.assistanceDefaults,
                        actionId: event.target.value,
                      },
                    })
                  }
                >
                  <option value="summary">요약</option>
                  <option value="translate">번역</option>
                </select>
              </label>
              <label>
                기본 언어
                <select
                  aria-label="기본 언어"
                  value={draft.assistanceDefaults.languageId}
                  onChange={(event) =>
                    setDraft({
                      ...draft,
                      assistanceDefaults: {
                        ...draft.assistanceDefaults,
                        languageId: event.target.value,
                      },
                    })
                  }
                >
                  <option value="en">영어</option>
                  <option value="ko">한국어</option>
                </select>
              </label>
              <label>
                저장할 화면 모드
                <select
                  aria-label="저장할 화면 모드"
                  value={draft.appearance}
                  onChange={(event) =>
                    setDraft({ ...draft, appearance: event.target.value as Settings['appearance'] })
                  }
                >
                  <option value="system">시스템 설정</option>
                  <option value="light">밝게</option>
                  <option value="dark">어둡게</option>
                </select>
              </label>
              <button type="submit">기본 설정 저장</button>
            </fieldset>
            <p className="muted">
              저장 전 변경 사항은 아직 적용되지 않아요. 기본값을 저장해도 아직 제공되지 않는 기능이
              활성화되지는 않아요.
            </p>
          </form>
          <Disclosure title="관심 분야와 시작 설정">
            <StatusLine value={suggestions.error} />
            <p>현재 단계: {draft.onboarding}. ORCID 연결 없이 직접 선택하거나 건너뛸 수 있어요.</p>
            <fieldset disabled={operation.busy || operation.unknown}>
              {suggestions.value?.items.map((suggestion) => (
                <label key={suggestion.interestId} className="check-row">
                  <input
                    type="checkbox"
                    checked={draft.interestIds.includes(suggestion.interestId)}
                    onChange={(event) =>
                      setDraft({
                        ...draft,
                        interestIds: event.target.checked
                          ? [...draft.interestIds, suggestion.interestId]
                          : draft.interestIds.filter((id) => id !== suggestion.interestId),
                      })
                    }
                  />
                  {suggestion.interestId === '1706.03762'
                    ? 'Transformer / Attention'
                    : suggestion.interestId === '2005.11401'
                      ? '검색 증강 생성 (RAG)'
                      : suggestion.labelKey}{' '}
                  · 직접 선택 목록
                </label>
              ))}
              <button type="button" onClick={() => saveInterests('save_interests')}>
                관심 분야 저장
              </button>
              <button type="button" onClick={() => saveInterests('complete')}>
                시작 설정 완료
              </button>
              <button type="button" onClick={() => saveInterests('skip')}>
                선택을 유지하고 건너뛰기
              </button>
            </fieldset>
          </Disclosure>
          <ResetControls
            client={client}
            policy={policy}
            settingsRevision={draft.revision}
            onAccepted={settings.load}
          />
        </>
      ) : null}
    </Panel>
  );
}
export function ResetControls({
  client,
  policy,
  settingsRevision,
  onAccepted,
}: {
  client: Transport;
  policy: PolicyRef;
  settingsRevision: string;
  onAccepted: () => Promise<unknown>;
}) {
  const [action, setAction] = useState<'delete_behavior' | 'reset_profile'>('delete_behavior');
  const [proof, setProof] = useState('');
  const [confirmation, setConfirmation] = useState<{
    confirmationRef: string;
    revision: string;
  } | null>(null);
  const [epoch, setEpoch] = useState(0);
  const operation = useOperation();
  return (
    <Disclosure title="활동 삭제와 추천 프로필 초기화">
      <OperationStatus operation={operation} />
      <p>
        활동 삭제와 추천 프로필 초기화는 서로 다른 처리예요. 서재, 검색 기록, 기본 설정, 연구 원고는
        이 요청으로 삭제되지 않아요.
      </p>
      <label>
        초기화 범위
        <select
          aria-label="초기화 범위"
          value={action}
          disabled={!!confirmation}
          onChange={(event) => setAction(event.target.value as typeof action)}
        >
          <option value="delete_behavior">활동 데이터 삭제</option>
          <option value="reset_profile">추천 프로필 초기화</option>
        </select>
      </label>
      <Field
        id="reset-proof"
        label="초기화용 현재 비밀번호"
        secret
        value={proof}
        onChange={setProof}
        autoComplete="current-password"
      />
      {!confirmation ? (
        <button
          type="button"
          disabled={operation.busy || operation.unknown}
          onClick={() =>
            void operation.run(async (key) => {
              setConfirmation(
                await client.post(
                  '/api/v2/c03/settings-prepare-reset',
                  {
                    action,
                    currentProof: proof,
                    expectedRevision: settingsRevision,
                    policyRef: policy,
                  },
                  key,
                ),
              );
              setProof('');
            })
          }
        >
          초기화 범위 확인 준비
        </button>
      ) : (
        <div className="control-confirmation" role="group" aria-label="초기화 최종 확인">
          <p>선택한 범위의 정리를 접수할까요? 모든 정리 범위의 증거가 확인되어야 완료예요.</p>
          <button type="button" onClick={() => setConfirmation(null)}>
            취소
          </button>
          <button
            type="button"
            disabled={operation.busy || operation.unknown}
            onClick={() =>
              void operation.run(async (key) => {
                await client.post<ResetResult>(
                  '/api/v2/c03/settings-reset',
                  {
                    action,
                    confirmationRef: confirmation.confirmationRef,
                    expectedRevision: confirmation.revision,
                    policyRef: policy,
                  },
                  key,
                );
                setConfirmation(null);
                await onAccepted();
                setEpoch((value) => value + 1);
              })
            }
          >
            초기화 접수
          </button>
        </div>
      )}
      <ResetHistory client={client} epoch={epoch} />
    </Disclosure>
  );
}
export function ResetHistory({ client, epoch = 0 }: { client: Transport; epoch?: number }) {
  const [view, setView] = useState<'outstanding' | 'history'>('outstanding');
  const [page, setPage] = useState<ResetPage | null>(null);
  const [status, setStatus] = useState<ResetStatus | null>(null);
  const [error, setError] = useState<ReturnType<typeof describeError> | null>(null);
  const [loading, setLoading] = useState(false);
  const sequence = React.useRef(0);
  const detailSequence = React.useRef(0);
  const load = React.useCallback(
    async (cursor?: string) => {
      const request = ++sequence.current;
      setLoading(true);
      setError(null);
      try {
        const result = await client.get<ResetPage>(
          `/api/v2/c03/settings-resets?view=${view}&limit=25${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`,
        );
        if (request === sequence.current) setPage(result);
      } catch (failure) {
        if (request === sequence.current) setError(describeError(failure));
      } finally {
        if (request === sequence.current) setLoading(false);
      }
    },
    [client, view],
  );
  const invalidateReads = React.useCallback(() => {
    sequence.current++;
    detailSequence.current++;
  }, []);
  useEffect(() => {
    void load();
    return invalidateReads;
  }, [load, epoch, invalidateReads]);
  return (
    <section aria-label="초기화 처리 기록">
      <h3>초기화 처리 기록</h3>
      <p>
        다시 로그인한 뒤에도 접수된 요청을 읽을 수 있어요. 새로 읽기는 작업을 다시 실행하지 않아요.
      </p>
      <StatusLine value={error} />
      <label>
        처리 기록 범위
        <select
          aria-label="처리 기록 범위"
          value={view}
          onChange={(event) => {
            sequence.current++;
            detailSequence.current++;
            setView(event.target.value as typeof view);
            setPage(null);
            setStatus(null);
          }}
        >
          <option value="outstanding">아직 처리 중</option>
          <option value="history">전체 기록</option>
        </select>
      </label>
      <button type="button" onClick={() => void load()}>
        처리 기록 새로 읽기
      </button>
      {loading ? <p role="status">처리 기록을 읽고 있어요</p> : null}
      {page && !loading && !page.items.length ? (
        <p>이 범위에서 확인된 요청이 없어요. 응답을 받지 못한 요청의 실패를 뜻하지는 않아요.</p>
      ) : null}
      <ul>
        {page?.items.map((item) => (
          <li key={item.resetId}>
            <button
              type="button"
              onClick={async () => {
                const request = ++detailSequence.current;
                try {
                  const result = await client.get<ResetStatus>(
                    `/api/v2/c03/settings-resets/${encodeURIComponent(item.resetId)}`,
                  );
                  if (request === detailSequence.current) setStatus(result);
                } catch (failure) {
                  if (request === detailSequence.current) setError(describeError(failure));
                }
              }}
            >
              {item.action === 'delete_behavior' ? '활동 데이터 삭제' : '추천 프로필 초기화'} ·{' '}
              {item.disposition === 'complete'
                ? '전체 정리 완료'
                : item.disposition === 'blocked'
                  ? '추가 확인 필요'
                  : '정리 진행 중'}{' '}
              · {new Date(item.acceptedAt).toLocaleString('ko-KR')}
            </button>
          </li>
        ))}
      </ul>
      {page?.page.nextCursor ? (
        <button type="button" onClick={() => void load(page.page.nextCursor ?? undefined)}>
          다음 처리 기록
        </button>
      ) : null}
      {status ? (
        <div role="status">
          <p>접수된 경계와 정리 완료는 별도예요. 현재 상태: {status.reset.disposition}</p>
          <ul>
            {status.scopes.map((scope, index) => (
              <li key={index}>
                {scope.participantId} / {scope.scopeId}: {scope.disposition}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
