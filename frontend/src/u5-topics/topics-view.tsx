/** U5 topics view: followed topics, per-topic actions and the settings dialog.

One h1 per page, sections as h2 (Panel), every action keyboard-reachable,
status changes announced through the polite status line, and the destructive
unsubscribe confirmed through a dialog that names the topic. Reads go through
SWR (stale-while-revalidate); every mutation is acknowledged before the list
reflects it. */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import useSWR from 'swr';
import { ApiError } from '../api';
import type { Transport } from '../api';
import { describeError, notice, Panel, StatusLine, type Notice } from '../ui';
import {
  followTopic,
  isUnresolvedUnknown,
  listTopics,
  resolveRun,
  unsubscribeTopic,
  type ResolveDecision,
  type Topic,
} from './api';
import { DigestSettingsForm } from './digest-settings';
import './topics.css';

type ViewState = 'loading' | 'empty' | 'error' | 'ready' | 'partial';

const LAST_DIGEST_COPY: Record<string, { icon: string; text: string }> = {
  sent: { icon: '✓', text: '마지막 발송 완료' },
  empty: { icon: '◦', text: '최근 발송 없음(새 소식 없음)' },
  failed: { icon: '⚠', text: '마지막 발송 실패' },
  unknown: { icon: '?', text: '발송 결과 확인 필요' },
  prepared: { icon: '…', text: '발송 준비 중' },
  sending: { icon: '…', text: '발송 진행 중' },
};

export function lastDigestView(topic: Topic): { icon: string; text: string } | null {
  const state = topic.lastRun?.state;
  if (!state) return null;
  if (state === 'unknown' && !isUnresolvedUnknown(topic)) {
    // A reconciled unknown resolves to sent or failed: report the outcome.
    const observed = topic.lastRun?.observedState;
    return observed && LAST_DIGEST_COPY[observed] ? LAST_DIGEST_COPY[observed] : null;
  }
  return LAST_DIGEST_COPY[state] ?? null;
}

export function ConfirmationDialog({
  title,
  body,
  confirmLabel,
  onConfirm,
  onClose,
  busy = false,
  testId,
}: {
  title: string;
  body: React.ReactNode;
  confirmLabel: string;
  onConfirm: () => void;
  onClose: () => void;
  busy?: boolean;
  testId: string;
}) {
  const container = useRef<HTMLDivElement>(null);
  const restore = useRef<Element | null>(null);
  useEffect(() => {
    restore.current = document.activeElement;
    const node = container.current;
    const focusable = node?.querySelector<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
    );
    focusable?.focus();
    return () => {
      if (restore.current instanceof HTMLElement) restore.current.focus();
    };
  }, []);
  const onKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'Escape') {
      event.stopPropagation();
      onClose();
      return;
    }
    if (event.key !== 'Tab') return;
    const node = container.current;
    const items = Array.from(
      node?.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      ) ?? [],
    );
    if (items.length === 0) return;
    const first = items[0]!;
    const last = items[items.length - 1]!;
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };
  return (
    <div className="dialog-backdrop" onKeyDown={onKeyDown}>
      <div
        className="dialog"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        ref={container}
        data-testid={testId}
      >
        <h3>{title}</h3>
        {body}
        <div className="dialog-actions">
          <button type="button" onClick={onClose} disabled={busy} data-testid={`${testId}-cancel`}>
            취소
          </button>
          <button
            type="button"
            className="danger"
            onClick={onConfirm}
            disabled={busy}
            data-testid={`${testId}-confirm`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

function TopicSummary({ topic }: { topic: Topic }) {
  const digest = lastDigestView(topic);
  return (
    <div className="topic-summary" data-testid="topic-summary">
      <span className="topic-name" data-testid="topic-name">
        {topic.displayName}
      </span>
      <span className="topic-status">
        {topic.status === 'active' ? '구독 중' : '구독 해지'}
      </span>
      {digest ? (
        <span className="topic-digest" data-testid="last-digest">
          <span aria-hidden="true">{digest.icon}</span> {digest.text}
        </span>
      ) : (
        <span className="topic-digest" data-testid="last-digest">
          <span aria-hidden="true">·</span> 아직 발송 전
        </span>
      )}
    </div>
  );
}

function ResolveUnknownControl({
  client,
  topic,
  busy,
  onResolved,
  onError,
}: {
  client: Transport;
  topic: Topic;
  busy: boolean;
  onResolved: (decision: ResolveDecision) => void;
  onError: (failure: unknown) => void;
}) {
  const [working, setWorking] = useState<ResolveDecision | null>(null);
  const runId = topic.lastRun?.runId ?? '';
  const resolve = async (decision: ResolveDecision) => {
    setWorking(decision);
    try {
      // The control owns the single POST; the parent only acknowledges.
      await resolveRun(client, topic.topicId, runId, decision);
      onResolved(decision);
    } catch (failure) {
      onError(failure);
    } finally {
      setWorking(null);
    }
  };
  return (
    <div className="resolve-control" data-testid="resolve-control">
      <span className="resolve-label">마지막 발송 결과를 확인할 수 없어요. 어느 쪽인지 알려주세요:</span>
      <button
        type="button"
        onClick={() => resolve('delivered')}
        disabled={busy || working !== null}
        data-testid="resolve-delivered"
      >
        배달됨으로 해결
      </button>
      <button
        type="button"
        onClick={() => resolve('not-delivered')}
        disabled={busy || working !== null}
        data-testid="resolve-not-delivered"
      >
        미전달로 해결
      </button>
    </div>
  );
}

function TopicRow({
  client,
  topic,
  busy,
  onOpenSettings,
  onUnsubscribe,
  onResolved,
  onError,
}: {
  client: Transport;
  topic: Topic;
  busy: boolean;
  onOpenSettings: (topic: Topic) => void;
  onUnsubscribe: (topic: Topic) => void;
  onResolved: (decision: ResolveDecision) => void;
  onError: (failure: unknown) => void;
}) {
  return (
    <li className="topic-row" data-testid="topic-row">
      <TopicSummary topic={topic} />
      <div className="topic-actions">
        <button
          type="button"
          onClick={() => onOpenSettings(topic)}
          disabled={busy}
          data-testid="settings-link"
        >
          발송 설정
        </button>
        <button
          type="button"
          className="danger"
          onClick={() => onUnsubscribe(topic)}
          disabled={busy}
          data-testid="unsubscribe-button"
        >
          구독 해지
        </button>
      </div>
      {isUnresolvedUnknown(topic) ? (
        <ResolveUnknownControl
          client={client}
          topic={topic}
          busy={busy}
          onResolved={onResolved}
          onError={onError}
        />
      ) : null}
    </li>
  );
}

function FollowTopicAction({
  client,
  busy,
  onFollowed,
}: {
  client: Transport;
  busy: boolean;
  onFollowed: (result: { reactivated: boolean; displayName: string }) => void;
}) {
  const [topicKey, setTopicKey] = useState('');
  const [pending, setPending] = useState(false);
  const [localNotice, setLocalNotice] = useState<Notice | null>(null);
  const trimmed = topicKey.trim();
  const submit = async () => {
    if (!trimmed || pending) return;
    setPending(true);
    setLocalNotice(null);
    try {
      const result = await followTopic(client, trimmed, trimmed);
      onFollowed({ reactivated: result.reactivated, displayName: trimmed });
      setTopicKey('');
    } catch (failure) {
      if (failure instanceof ApiError && failure.envelope.code === 'CONFLICT') {
        setLocalNotice(notice('alert', `'${trimmed}' 주제는 이미 구독 중이에요`));
      } else {
        setLocalNotice(describeError(failure));
      }
    } finally {
      setPending(false);
    }
  };
  return (
    <div className="follow-action" data-testid="follow-action">
      <label htmlFor="u5-follow-key">새 주제</label>
      <input
        id="u5-follow-key"
        value={topicKey}
        onChange={(event) => setTopicKey(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Enter') submit();
        }}
        placeholder="예: 양자 오류 정정"
        data-testid="follow-input"
      />
      <button
        type="button"
        onClick={submit}
        disabled={busy || pending || !trimmed}
        data-testid="follow-button"
      >
        주제 팔로우
      </button>
      <StatusLine value={localNotice} />
    </div>
  );
}

export function TopicsView({
  client,
  active = true,
  degraded = false,
  synthetic = false,
}: {
  client: Transport;
  active?: boolean;
  degraded?: boolean;
  synthetic?: boolean;
}) {
  const heading = useRef<HTMLHeadingElement>(null);
  const [settingsTopic, setSettingsTopic] = useState<Topic | null>(null);
  const [confirmTopic, setConfirmTopic] = useState<Topic | null>(null);
  const [rowBusy, setRowBusy] = useState(false);
  const [status, setStatus] = useState<Notice | null>(null);
  const { data, error, isLoading, mutate } = useSWR(
    active ? 'u5-topics' : null,
    () => listTopics(client),
    {
      revalidateOnFocus: false,
      shouldRetryOnError: false,
      // The digest pipeline moves between passes (preparation, sending,
      // reconciliation): the list polls so the last-digest indicator and the
      // resolve control reflect server state without a manual reload.
      refreshInterval: 4_000,
    },
  );
  const topics = data?.topics ?? [];
  const viewState: ViewState = isLoading
    ? 'loading'
    : error
      ? 'error'
      : topics.length === 0
        ? 'empty'
        : degraded
          ? 'partial'
          : 'ready';
  const refresh = useCallback(() => {
    void mutate();
  }, [mutate]);

  useEffect(() => {
    if (active) heading.current?.focus();
  }, [active]);

  const unsubscribe = async (topic: Topic) => {
    setRowBusy(true);
    try {
      await unsubscribeTopic(client, topic.topicId);
      setStatus(notice('polite', `'${topic.displayName}' 주제 구독을 해지했어요`));
      setConfirmTopic(null);
      refresh();
    } catch (failure) {
      setStatus(describeError(failure));
    } finally {
      setRowBusy(false);
    }
  };

  const resolved = (decision: ResolveDecision) => {
    // The control already posted the single resolve; acknowledge the outcome.
    setStatus(
      notice(
        'polite',
        decision === 'delivered'
          ? '마지막 발송을 배달됨으로 표시했어요'
          : '마지막 발송을 미전달로 표시했어요',
      ),
    );
    refresh();
  };

  return (
    <section className="topics-view" aria-labelledby="u5-topics-heading">
      <h1 id="u5-topics-heading" tabIndex={-1} ref={heading} data-testid="topics-heading">
        주제 구독
      </h1>
      <p className="topics-intro">
        구독한 주제의 새 논문을 정해진 시간에 이메일로 받아봅니다.
        {synthetic ? ' (현재 로컬 시험 환경에서는 메일이 로컬 저장소로만 전달돼요)' : ''}
      </p>
      <StatusLine value={status} />
      <Panel title="팔로우한 주제">
        {viewState === 'loading' ? (
          <p data-testid="topics-loading">불러오는 중…</p>
        ) : viewState === 'error' ? (
          <p data-testid="topics-error" role="alert">
            {describeError(error).text}
          </p>
        ) : viewState === 'empty' ? (
          <p data-testid="topics-empty">아직 팔로우한 주제가 없어요. 아래에서 첫 주제를 팔로우해 보세요.</p>
        ) : (
          <>
            {viewState === 'partial' ? (
              <p className="degraded" data-testid="topics-partial">
                일부 발송 기능이 제한된 상태예요.
              </p>
            ) : null}
            <ul className="topic-list" data-testid="topic-list">
              {topics.map((topic) => (
                <TopicRow
                  key={topic.topicId}
                  client={client}
                  topic={topic}
                  busy={rowBusy}
                  onOpenSettings={setSettingsTopic}
                  onUnsubscribe={setConfirmTopic}
                  onResolved={resolved}
                  onError={(failure) => setStatus(describeError(failure))}
                />
              ))}
            </ul>
          </>
        )}
        <FollowTopicAction
          client={client}
          busy={rowBusy}
          onFollowed={({ reactivated, displayName }) => {
            setStatus(
              notice(
                'polite',
                reactivated
                  ? `'${displayName}' 주제를 다시 구독했어요. 기존 기록과 발송 이력이 이어져요`
                  : `'${displayName}' 주제를 팔로우했어요`,
              ),
            );
            refresh();
          }}
        />
      </Panel>
      {settingsTopic ? (
        <DigestSettingsForm
          client={client}
          topic={settingsTopic}
          busy={rowBusy}
          onClose={() => setSettingsTopic(null)}
          onUnsubscribe={() => {
            setConfirmTopic(settingsTopic);
            setSettingsTopic(null);
          }}
          onSaved={(message) => {
            setStatus(notice('polite', message));
            setSettingsTopic(null);
            refresh();
          }}
          onError={setStatus}
        />
      ) : null}
      {confirmTopic ? (
        <ConfirmationDialog
          title="구독 해지 확인"
          body={
            <>
              <p>
                <strong>'{confirmTopic.displayName}'</strong> 주제 구독을 해지할까요?
              </p>
              <p className="dialog-note">
                구독 해지 즉시 발송이 멈춰요. 이 주제의 대기 중인 발송 준비물은 폐기되고, 이미
                진행 중인 발송은 결과만 기록돼요. 지금까지의 기록은 남아 있어요.
              </p>
            </>
          }
          confirmLabel="구독 해지"
          busy={rowBusy}
          onConfirm={() => unsubscribe(confirmTopic)}
          onClose={() => setConfirmTopic(null)}
          testId="confirm-dialog"
        />
      ) : null}
    </section>
  );
}
