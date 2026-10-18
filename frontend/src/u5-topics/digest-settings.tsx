/** Per-topic digest settings form (dialog): revision-checked save, inline
 * validation on blur, acknowledged save states, and a stale-revision reload
 * offer — never an overwriting blind retry (BR1.3). */

import React, { useEffect, useRef, useState } from 'react';
import { ApiError } from '../api';
import type { Transport } from '../api';
import { describeError, notice, StatusLine, type Notice } from '../ui';
import {
  CADENCE_LABELS,
  DELIVERY_DAYS,
  isValidTime,
  readTopic,
  saveSettings,
  type Cadence,
  type ContentWindow,
  type DeliveryDay,
  type Topic,
} from './api';
import { ConfirmationDialog } from './topics-view';
import { OwnerPreferences } from './owner-preferences';

type SaveState = 'idle' | 'saving' | 'saved' | 'failed';

type Draft = {
  cadence: Cadence;
  deliveryTimeLocal: string;
  deliveryDay: DeliveryDay | null;
  contentWindowDays: ContentWindow;
  revision: number;
};

export function DigestSettingsForm({
  client,
  topic,
  busy,
  onClose,
  onSaved,
  onUnsubscribe,
  onError,
}: {
  client: Transport;
  topic: Topic;
  busy: boolean;
  onClose: () => void;
  onSaved: (message: string) => void;
  onUnsubscribe: () => void;
  onError: (value: Notice | null) => void;
}) {
  const [draft, setDraft] = useState<Draft | null>(null);
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [saveState, setSaveState] = useState<SaveState>('idle');
  const [stale, setStale] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [localNotice, setLocalNotice] = useState<Notice | null>(null);
  const [view, setView] = useState<Topic>(topic);
  const [editPreferences, setEditPreferences] = useState(false);
  const mounted = useRef(false);
  const generation = client.generation;
  const current = () => mounted.current && generation === client.generation;
  const container = useRef<HTMLDivElement>(null);
  const restore = useRef<Element | null>(null);

  useEffect(() => {
    restore.current = document.activeElement;
    mounted.current = true;
    let alive = true;
    readTopic(client, topic.topicId)
      .then((view) => {
        if (!alive || !current() || !view.settings) return;
        setView(view);
        setDraft({
          cadence: view.settings.cadence,
          deliveryTimeLocal: view.settings.deliveryTimeLocal ?? '08:00',
          deliveryDay: view.settings.deliveryDay,
          contentWindowDays: view.settings.contentWindowDays,
          revision: view.settings.revision,
        });
      })
      .catch((failure) => {
        if (alive && current()) onError(describeError(failure));
      });
    const focusable = container.current?.querySelector<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
    );
    focusable?.focus();
    return () => {
      alive = false;
      mounted.current = false;
      if (restore.current instanceof HTMLElement) restore.current.focus();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client, topic.topicId, generation]);

  const loaded = draft !== null;
  useEffect(() => {
    if (loaded) container.current?.querySelector<HTMLElement>('select, input, button')?.focus();
  }, [loaded]);

  if (!draft) {
    return (
      <div className="dialog-backdrop">
        <div
          className="dialog"
          role="dialog"
          aria-modal="true"
          aria-label="발송 설정"
          data-testid="settings-form"
        >
          <p data-testid="settings-loading">설정을 불러오는 중…</p>
        </div>
      </div>
    );
  }

  const timeInvalid = !isValidTime(draft.deliveryTimeLocal);
  const dayMissing = draft.cadence === 'weekly' && draft.deliveryDay === null;
  const canSave = !timeInvalid && !dayMissing && saveState !== 'saving' && !busy;

  const reload = async () => {
    setStale(false);
    try {
      const view = await readTopic(client, topic.topicId);
      if (!current() || !view.settings) return;
      setView(view);
      setDraft({
        cadence: view.settings.cadence,
        deliveryTimeLocal: view.settings.deliveryTimeLocal ?? '08:00',
        deliveryDay: view.settings.deliveryDay,
        contentWindowDays: view.settings.contentWindowDays,
        revision: view.settings.revision,
      });
      setLocalNotice(notice('polite', '최신 설정을 다시 불러왔어요'));
    } catch (failure) {
      if (current()) setLocalNotice(describeError(failure));
    }
  };

  const submit = async () => {
    if (!canSave) return;
    setSaveState('saving');
    setLocalNotice(null);
    try {
      const result = await saveSettings(client, topic.topicId, {
        revision: draft.revision,
        cadence: draft.cadence,
        deliveryTimeLocal: draft.deliveryTimeLocal,
        deliveryDay: draft.cadence === 'weekly' ? draft.deliveryDay : null,
        contentWindowDays: draft.contentWindowDays,
      });
      if (!current()) return;
      setSaveState('saved');
      onSaved(
        result.unchanged
          ? '변경된 내용이 없어요'
          : `'${topic.displayName}' 주제의 발송 설정을 저장했어요`,
      );
    } catch (failure) {
      if (!current()) return;
      setSaveState('failed');
      if (failure instanceof ApiError && failure.envelope.code === 'STALE_REVISION') {
        // The settings changed elsewhere: reload and re-offer, never overwrite.
        setStale(true);
        setLocalNotice(notice('alert', '설정이 다른 곳에서 변경되었어요'));
      } else {
        setLocalNotice(describeError(failure));
      }
    }
  };

  const blur = (field: string) => setTouched((current) => ({ ...current, [field]: true }));

  return (
    <div className="dialog-backdrop">
      <div
        className="dialog"
        role="dialog"
        aria-modal="true"
        aria-label={`'${topic.displayName}' 발송 설정`}
        ref={container}
        data-testid="settings-form"
        onKeyDown={(event) => {
          if (event.key === 'Escape') {
            event.stopPropagation();
            onClose();
          }
          if (event.key !== 'Tab') return;
          const items = Array.from(
            container.current?.querySelectorAll<HTMLElement>(
              'button:not(:disabled), input:not(:disabled), select:not(:disabled), [href]',
            ) ?? [],
          );
          const first = items[0],
            last = items[items.length - 1];
          if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last?.focus();
          } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first?.focus();
          }
        }}
      >
        <h3>'{topic.displayName}' 발송 설정</h3>
        <div className="field">
          <label htmlFor="u5-cadence">발송 주기</label>
          <select
            id="u5-cadence"
            value={draft.cadence}
            onChange={(event) => setDraft({ ...draft, cadence: event.target.value as Cadence })}
            data-testid="cadence-select"
          >
            {(Object.keys(CADENCE_LABELS) as Cadence[]).map((value) => (
              <option key={value} value={value}>
                {CADENCE_LABELS[value]}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="u5-delivery-time">
            발송 시각 ({view.effectivePreferences?.timeZone ?? '계정 시간대 미설정'} 기준)
          </label>
          <input
            id="u5-delivery-time"
            type="time"
            value={draft.deliveryTimeLocal}
            onBlur={() => blur('deliveryTimeLocal')}
            onChange={(event) => setDraft({ ...draft, deliveryTimeLocal: event.target.value })}
            data-testid="delivery-time"
          />
          {touched.deliveryTimeLocal && timeInvalid ? (
            <p className="field-error" data-testid="delivery-time-error" role="alert">
              시각은 HH:MM 형식으로 입력해 주세요
            </p>
          ) : null}
        </div>
        {draft.cadence === 'weekly' ? (
          <div className="field">
            <label htmlFor="u5-delivery-day">발송 요일</label>
            <select
              id="u5-delivery-day"
              value={draft.deliveryDay ?? ''}
              onBlur={() => blur('deliveryDay')}
              onChange={(event) =>
                setDraft({
                  ...draft,
                  deliveryDay: (event.target.value || null) as DeliveryDay | null,
                })
              }
              data-testid="delivery-day"
            >
              <option value="">요일을 선택해 주세요</option>
              {DELIVERY_DAYS.map((day) => (
                <option key={day.value} value={day.value}>
                  {day.label}
                </option>
              ))}
            </select>
            {touched.deliveryDay && dayMissing ? (
              <p className="field-error" data-testid="delivery-day-error" role="alert">
                매주 발송에는 요일이 필요해요
              </p>
            ) : null}
          </div>
        ) : null}
        <div className="field">
          <label htmlFor="u5-content-window">불러올 기간</label>
          <select
            id="u5-content-window"
            value={draft.contentWindowDays}
            onChange={(event) =>
              setDraft({ ...draft, contentWindowDays: Number(event.target.value) as ContentWindow })
            }
            data-testid="window-select"
          >
            <option value={7}>최근 7일</option>
            <option value={30}>최근 30일</option>
          </select>
        </div>
        <p className="inherited-note" data-testid="inherited-note">
          {view.effectivePreferences
            ? `계정에서 적용: ${view.effectivePreferences.languageId === 'ko' ? '한국어' : 'English'} · 표준 (standard) · ${view.effectivePreferences.timeZone ?? '시간대 미설정'}${view.effectivePreferences.usesDefaults ? ' (언어·수준 기본값)' : ''}`
            : '계정 환경설정을 확인할 수 없어요. 환경설정을 다시 확인해 주세요.'}
        </p>
        {!view.effectivePreferences?.timeZone ? (
          <p role="status">시간대를 확인하고 저장해야 예약 발송이 시작돼요.</p>
        ) : null}
        <button
          type="button"
          data-testid="preferences-toggle"
          onClick={() => setEditPreferences(!editPreferences)}
          aria-expanded={editPreferences}
        >
          {editPreferences ? '환경설정 접기' : '계정 환경설정 변경'}
        </button>
        {editPreferences ? (
          <OwnerPreferences
            client={client}
            onSaved={() => {
              void readTopic(client, topic.topicId)
                .then((next) => {
                  if (current()) setView(next);
                })
                .catch((failure) => {
                  if (current()) setLocalNotice(describeError(failure));
                });
            }}
          />
        ) : null}
        {view.runs?.[0] ? (
          <section aria-label="최근 다이제스트" data-testid="digest-preview">
            <h4>최근 다이제스트</h4>
            {view.runs[0].state === 'empty' ? (
              <p data-testid="digest-empty">
                {view.runs[0].presentation?.emptyLabel ?? '새 소식 없음'} · 메일을 보내지 않았어요.
              </p>
            ) : (
              <p className="digest-text">
                {view.runs[0].presentation?.text ?? '저장된 표시 내용을 확인할 수 없어요.'}
              </p>
            )}
            <p>
              {view.runs[0].sendLog?.pathKind === 'local-sink'
                ? '로컬 시험 저장소'
                : view.runs[0].sendLog?.pathKind === 'real'
                  ? '이메일 전송 경로'
                  : '발송 기록 없음'}
            </p>
          </section>
        ) : null}
        <StatusLine value={localNotice} />
        {stale ? (
          <div className="stale-offer" data-testid="stale-offer">
            <p>다른 곳에서 설정이 변경되었어요. 최신 설정을 다시 불러올까요?</p>
            <button type="button" onClick={reload} data-testid="stale-reload">
              다시 불러오기
            </button>
          </div>
        ) : null}
        <div className="dialog-actions">
          <button
            type="button"
            onClick={onClose}
            disabled={saveState === 'saving'}
            data-testid="settings-close"
          >
            닫기
          </button>
          <button
            type="button"
            className="danger"
            onClick={() => setConfirming(true)}
            disabled={saveState === 'saving' || busy}
            data-testid="settings-unsubscribe"
          >
            구독 해지
          </button>
          <button type="button" onClick={submit} disabled={!canSave} data-testid="save-button">
            {saveState === 'saving' ? '저장 중…' : '저장'}
          </button>
        </div>
      </div>
      {confirming ? (
        <ConfirmationDialog
          title="구독 해지 확인"
          body={
            <>
              <p>
                <strong>'{topic.displayName}'</strong> 주제 구독을 해지할까요?
              </p>
              <p className="dialog-note">
                구독 해지 즉시 발송이 멈춰요. 대기 중인 발송 준비물은 폐기돼요.
              </p>
            </>
          }
          confirmLabel="구독 해지"
          busy={busy}
          onConfirm={() => {
            setConfirming(false);
            onUnsubscribe();
          }}
          onClose={() => setConfirming(false)}
          testId="settings-confirm-dialog"
        />
      ) : null}
    </div>
  );
}
