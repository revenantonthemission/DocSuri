/** Export history (A2): one row per approval, newest first, with actions by state.

Continue completes an interrupted press and is never a second approval (BR3.7); it
is offered only while the approving session is current. Cancel acts on an approval
not yet started or an accepted export (BR3.6). Settlement appears only when the
entry says it is offered (BR4.5). Reads never export (BR2.2). */

import React, { useRef, useState } from 'react';
import { ApiError, type Transport } from '../api';
import { exportCall, type HistoryEntry, type HistoryPage, UNTITLED_TITLE } from './api';
import {
  APPROVAL_STATE_COPY,
  displayTitle,
  EFFECT_STATE_COPY,
  formatTime,
  FRESH_PREVIEW_GUIDE,
  INVALIDATION_REASON_COPY,
  IN_FLIGHT,
  OUTCOME_REASON_COPY,
  OUTCOME_UNKNOWN_PAIR,
  OWNER_CONFIRMED,
  REFUSAL_HINTS,
  retryClock,
  STALE_BINDING,
} from './copy';
import { SettleDialog, type SettleChoice } from './dialogs';
import { refusalText, StatusBadge, type Announce } from './status';

/** Execute refusals on a continue (Workflow 7), in plain words. */
function continueRefusal(failure: unknown): string {
  if (!(failure instanceof ApiError)) return refusalText(failure);
  const { code, retryAfterSeconds } = failure.envelope;
  if (code === 'CAPACITY_EXHAUSTED')
    return typeof retryAfterSeconds === 'number'
      ? `${retryClock(retryAfterSeconds)}부터 다시 내보낼 수 있습니다`
      : IN_FLIGHT;
  if (code === 'OUTCOME_UNKNOWN') return OUTCOME_UNKNOWN_PAIR;
  if (code === 'APPROVAL_REQUIRED' || code === 'CONFLICT') return STALE_BINDING;
  return refusalText(failure);
}

const rowStatus = (entry: HistoryEntry) =>
  entry.effect ? EFFECT_STATE_COPY[entry.effect.state] : APPROVAL_STATE_COPY[entry.state];

function rowReason(entry: HistoryEntry): string | null {
  const reason = entry.effect?.outcomeReason;
  if (reason) return OUTCOME_REASON_COPY[reason];
  return entry.invalidationReason ? INVALIDATION_REASON_COPY[entry.invalidationReason] : null;
}

function RowOutcome({ entry }: { entry: HistoryEntry }) {
  const effect = entry.effect;
  if (!effect) return null;
  const ownerSettled = effect.settledBy === 'owner';
  const hint = effect.outcomeReason ? REFUSAL_HINTS[effect.outcomeReason] : undefined;
  return (
    <>
      {effect.state === 'succeeded' && ownerSettled ? (
        <p className="export-note" data-testid="history-owner-confirmed">
          {OWNER_CONFIRMED}
        </p>
      ) : null}
      {effect.state === 'succeeded' && effect.remoteUrl ? (
        <a
          href={effect.remoteUrl}
          target="_blank"
          rel="noopener noreferrer"
          data-testid="history-page-link"
        >
          {entry.sourceTitle}
          {ownerSettled ? ` (${OWNER_CONFIRMED})` : ''} · Notion에서 열기
        </a>
      ) : null}
      {effect.state === 'unknown' && effect.nextCheckAt ? (
        <p className="export-note" data-testid="history-next-check">
          확인 중 · 다음 확인 {formatTime(effect.nextCheckAt)}
        </p>
      ) : null}
      {effect.possibleDuplicates.length > 0 ? (
        <div className="export-duplicates" data-testid="history-duplicates">
          <p>같은 표시가 있는 다른 페이지도 찾았습니다:</p>
          <ul>
            {effect.possibleDuplicates.map((item) => (
              <li key={item.remoteReference}>
                {item.remoteUrl ? (
                  <a href={item.remoteUrl} target="_blank" rel="noopener noreferrer">
                    중복일 수 있는 페이지 · Notion에서 열기
                  </a>
                ) : (
                  '중복일 수 있는 페이지 (링크 없음)'
                )}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {hint ? <p className="export-hint">{hint}</p> : null}
    </>
  );
}

function HistoryRow({
  entry,
  busy,
  onContinue,
  onCancel,
  onSettle,
  onFreshPreview,
}: {
  entry: HistoryEntry;
  busy: boolean;
  onContinue: (entry: HistoryEntry) => void;
  onCancel: (entry: HistoryEntry) => void;
  onSettle: (entry: HistoryEntry) => void;
  onFreshPreview: () => void;
}) {
  const effect = entry.effect;
  const notStarted = entry.state === 'approved' && !effect;
  const canContinue = notStarted && entry.continuable;
  const canCancel = notStarted || effect?.state === 'accepted';
  const canSettle = effect?.state === 'unknown' && effect.settlementOffered;
  const needsFreshPreview = (notStarted && !entry.continuable) || entry.state === 'invalidated';
  const reason = rowReason(entry);
  return (
    <li className="export-history-row" data-testid="history-row">
      <p className="export-history-title">
        <span>{entry.sourceTitle}</span>
        <span aria-hidden="true"> → </span>
        <span className="export-visually-hidden">에서 </span>
        <span>{displayTitle(entry.destinationTitle, UNTITLED_TITLE)}</span>
      </p>
      <p className="export-history-meta">
        <StatusBadge status={rowStatus(entry)} testId="history-status" />
        <span> · 승인 {formatTime(entry.approvedAt)}</span>
        {entry.endedAt ? <span> · 종료 {formatTime(entry.endedAt)}</span> : null}
      </p>
      {reason ? (
        <p className="export-note" data-testid="history-reason">
          {reason}
        </p>
      ) : null}
      <RowOutcome entry={entry} />
      <div className="export-actions">
        {canContinue ? (
          <button
            type="button"
            className="export-primary"
            disabled={busy}
            onClick={() => onContinue(entry)}
            data-testid="history-continue"
          >
            이어서 내보내기
          </button>
        ) : null}
        {canCancel ? (
          <button
            type="button"
            disabled={busy}
            onClick={() => onCancel(entry)}
            data-testid="history-cancel"
          >
            취소
          </button>
        ) : null}
        {canSettle ? (
          <button
            type="button"
            disabled={busy}
            onClick={() => onSettle(entry)}
            data-testid="history-settle"
          >
            직접 확인
          </button>
        ) : null}
        {needsFreshPreview ? (
          <button
            type="button"
            disabled={busy}
            onClick={onFreshPreview}
            data-testid="history-fresh-preview"
          >
            미리보기 다시 만들기
          </button>
        ) : null}
      </div>
    </li>
  );
}

export function ExportHistory({
  client,
  page,
  hasPrevious,
  onNext,
  onPrevious,
  onChanged,
  announce,
}: {
  client: Transport;
  page: HistoryPage;
  hasPrevious: boolean;
  onNext: (cursor: string) => void;
  onPrevious: () => void;
  onChanged: () => void;
  announce: Announce;
}) {
  const [busy, setBusy] = useState(false);
  const [settling, setSettling] = useState<HistoryEntry | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  // One key per continue, kept until it is answered, so a retry is the same request.
  const continueKeys = useRef(new Map<string, string>());
  const settleKeys = useRef(new Map<string, string>());
  const entries: readonly HistoryEntry[] = page.entries;

  const report = (text: string) => {
    setNotice(text);
    announce(text);
  };

  // Each action answers in words for its own refusals; the history is then re-read so
  // a row always shows the server's current state.
  const act = async (work: () => Promise<string>) => {
    if (busy) return;
    setBusy(true);
    try {
      report(await work());
    } finally {
      setBusy(false);
      onChanged();
    }
  };

  const runContinue = (entry: HistoryEntry) =>
    act(async () => {
      const keys = continueKeys.current;
      const key = keys.get(entry.approvalId) ?? crypto.randomUUID();
      keys.set(entry.approvalId, key);
      try {
        const effect = await exportCall(
          client,
          'execute-approved-export',
          { approvalId: entry.approvalId, bindingHash: entry.bindingHash },
          key,
        );
        keys.delete(entry.approvalId);
        return `‘${entry.sourceTitle}’ 내보내기를 이어서 시작했습니다 · ${EFFECT_STATE_COPY[effect.state].text}`;
      } catch (failure) {
        if (!(failure instanceof ApiError && failure.envelope.code === 'UNKNOWN_OUTCOME'))
          keys.delete(entry.approvalId);
        return continueRefusal(failure);
      }
    });

  const requestCancel = (entry: HistoryEntry, expectedRevision: string) =>
    exportCall(client, 'cancel-export-approval', {
      approvalId: entry.approvalId,
      expectedRevision,
    });

  // As in the outcome step: the lane records internal facts on an accepted export,
  // which advances its revision without changing its state. When the export read again
  // is still accepted at a newer revision, the owner's cancel is sent once more at that
  // revision; the compare-and-set still refuses an export that has started. A failed
  // read leaves the original refusal standing.
  const cancelAtLatest = async (entry: HistoryEntry, failure: unknown) => {
    const effect = entry.effect;
    const isConflict = failure instanceof ApiError && failure.envelope.code === 'CONFLICT';
    if (!isConflict || effect?.state !== 'accepted') throw failure;
    const latest = await exportCall(client, 'read-export-effect', {
      effectId: effect.effectId,
    }).catch(() => null);
    if (!latest || latest.state !== 'accepted' || latest.revision === effect.revision)
      throw failure;
    await requestCancel(entry, latest.revision);
  };

  const runCancel = (entry: HistoryEntry) =>
    act(async () => {
      const accepted = entry.effect?.state === 'accepted';
      const expectedRevision = accepted ? entry.effect!.revision : entry.previewRevision;
      try {
        await requestCancel(entry, expectedRevision).catch((failure: unknown) =>
          cancelAtLatest(entry, failure),
        );
        return `‘${entry.sourceTitle}’ 내보내기를 취소했습니다`;
      } catch (failure) {
        if (failure instanceof ApiError && failure.envelope.code === 'CONFLICT')
          return '이미 상태가 바뀌었습니다. 기록을 새로 불러왔습니다';
        return refusalText(failure);
      }
    });

  const runSettle = (entry: HistoryEntry, choice: SettleChoice) =>
    act(async () => {
      const effect = entry.effect!;
      const keys = settleKeys.current;
      const key = keys.get(effect.effectId) ?? crypto.randomUUID();
      keys.set(effect.effectId, key);
      try {
        await exportCall(
          client,
          'settle-export-effect',
          {
            effectId: effect.effectId,
            expectedRevision: effect.revision,
            disposition: choice.disposition,
            assumptionAccepted: true,
            ...(choice.remoteUrl ? { remoteUrl: choice.remoteUrl } : {}),
          },
          key,
        );
        keys.delete(effect.effectId);
        setSettling(null);
        return choice.disposition === 'delivered'
          ? '직접 확인해 내보낸 것으로 기록했습니다'
          : '직접 확인해 내보내지 않은 것으로 기록했습니다';
      } catch (failure) {
        if (!(failure instanceof ApiError && failure.envelope.code === 'UNKNOWN_OUTCOME'))
          keys.delete(effect.effectId);
        if (failure instanceof ApiError && failure.envelope.code === 'CONFLICT') {
          setSettling(null);
          return '이미 상태가 바뀌었습니다. 기록을 새로 불러왔습니다';
        }
        return refusalText(failure);
      }
    });

  return (
    <div className="export-history" data-testid="history">
      {notice ? (
        <p className="export-notice" data-testid="history-notice">
          {notice}
        </p>
      ) : null}
      {entries.length === 0 ? (
        <p data-testid="history-empty">아직 내보낸 기록이 없습니다.</p>
      ) : (
        <ul className="export-history-list" data-testid="history-list">
          {entries.map((entry) => (
            <HistoryRow
              key={entry.approvalId}
              entry={entry}
              busy={busy}
              onContinue={(item) => void runContinue(item)}
              onCancel={(item) => void runCancel(item)}
              onSettle={setSettling}
              onFreshPreview={() => report(FRESH_PREVIEW_GUIDE)}
            />
          ))}
        </ul>
      )}
      <div className="export-actions">
        {hasPrevious ? (
          <button type="button" onClick={onPrevious} data-testid="history-previous">
            이전 기록
          </button>
        ) : null}
        {page.nextCursor ? (
          <button type="button" onClick={() => onNext(page.nextCursor!)} data-testid="history-next">
            다음 기록
          </button>
        ) : null}
      </div>
      {settling ? (
        <SettleDialog
          entry={settling}
          busy={busy}
          onSubmit={(choice) => void runSettle(settling, choice)}
          onClose={() => setSettling(null)}
        />
      ) : null}
    </div>
  );
}
