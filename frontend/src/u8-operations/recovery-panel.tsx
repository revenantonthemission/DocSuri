/**
 * RecoveryPanel (frontend-components.md "OperationsView"; BR4.1, BR4.2, BR4.4, BR4.7,
 * BR4.9): 백업 만들기, 복원 검증 and 운영 데이터 복원 요청, each confirmed in its dialog and
 * recorded as a request the operator performs. Each request shows its environment, its
 * origin and its state; a conflict says another request came first. A submission's
 * confirmation is a plain line: OperationsView announces it with the refresh it triggers
 * (L1-26).
 */
import React, { useState } from 'react';
import { ApiError, type PolicyRef, type Transport } from '../api';
import { describeError, notice, StatusLine, type Notice } from '../ui';
import {
  OPERATION_COPY,
  operationsTime,
  RECOVERY_STATE_COPY,
  requestRecovery,
  valueOf,
  type DashboardItem,
  type Incident,
  type RecoveryOperation,
  type RecoveryState,
} from './api';
import { RecoveryConfirmDialog } from './recovery-confirm-dialog';

export const CHOOSE_SET = '복원할 백업을 선택하세요';
export const CONFLICT_TEXT = '다른 요청이 먼저 처리되었습니다. 새로 고친 뒤 다시 확인하세요';
export const WAITING_TEXT = '같은 환경의 다른 복구 작업이 끝나면 진행됩니다';
const WAIT_REASONS: Partial<Record<RecoveryState, string>> = {
  'post-restore-pending': '복원된 데이터베이스의 백업이 통과해야 서비스가 다시 시작됩니다',
  held: '다른 백업으로 다시 복원하려면 관리자 도구에서 결정이 필요합니다',
};
const ENVIRONMENT_COPY: Readonly<Record<string, string>> = { rehearsal: '리허설', live: '운영' };
const ORIGIN_COPY: Readonly<Record<string, string>> = { administrator: '관리자', schedule: '예약' };
const RECEIPT_SHOWN = 8;

const OPERATIONS: readonly RecoveryOperation[] = [
  'backup.create',
  'restore.verify',
  'restore.production',
];

export function RecoveryPanel({
  client,
  account,
  policy,
  items,
  incident,
  newSubmission,
  onSubmitted,
}: {
  client: Transport;
  account: string;
  policy: PolicyRef;
  items: readonly DashboardItem[];
  incident: Incident | null;
  newSubmission?: () => string;
  /** The receipt's job id (the request's evidence reference) and the confirmation text. */
  onSubmitted: (jobId: string, text: string) => void;
}) {
  const [confirmation, setConfirmation] = useState<string | null>(null);
  const [operation, setOperation] = useState<RecoveryOperation>('backup.create');
  const [chosen, setChosen] = useState('');
  const [invalid, setInvalid] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<Notice | null>(null);
  const sets = items.filter((item) => item.capability === 'operations.backup-set');
  const passed = sets.filter((item) => item.status === 'available');
  const revision = items.find((item) => item.capability === 'operations.backup-revision');
  const environment = revision?.evidenceRef.split(':')[1] ?? 'live';
  const requests = items.filter((item) => item.capability === 'operations.recovery-request');
  const restore = operation !== 'backup.create';
  const set = passed.find((item) => item.evidenceRef === chosen);

  const open = () => {
    if (restore && !set) {
      setInvalid(true);
      return;
    }
    setInvalid(false);
    setMessage(null);
    setConfirmation(null);
    setConfirming(true);
  };

  const submit = async (submissionId: string) => {
    setBusy(true);
    try {
      const receipt = await requestRecovery(client, account, {
        operation,
        targetId: restore && set ? set.evidenceRef : environment,
        expectedRevision:
          (restore && set
            ? valueOf(set, 'revision')
            : valueOf(revision ?? { limitations: [] }, 'revision')) ?? '0',
        origin: 'administrator',
        submissionId,
        policy,
        ...(incident ? { incidentId: incident.incidentId } : {}),
      });
      setConfirming(false);
      const text = `${OPERATION_COPY[operation]} 요청 상태: ${RECOVERY_STATE_COPY.requested}`;
      setMessage(null);
      setConfirmation(`${text} · 요청 ${receipt.jobId.slice(0, RECEIPT_SHOWN)}`);
      onSubmitted(receipt.jobId, text);
    } catch (error) {
      // The dialog stays open: a retry of this submission reuses its id.
      setMessage(
        error instanceof ApiError && error.envelope.code === 'CONFLICT'
          ? notice('alert', CONFLICT_TEXT)
          : describeError(error),
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <section aria-labelledby="recovery-panel-title" data-testid="recovery-panel">
      <h3 id="recovery-panel-title">복구</h3>
      {incident ? (
        <p data-testid="recovery-incident">
          사고 {incident.capabilities.join(', ')}에 대한 요청입니다
        </p>
      ) : null}
      <fieldset>
        <legend>작업</legend>
        {OPERATIONS.map((value) => (
          <label key={value}>
            <input
              type="radio"
              name="recovery-operation"
              value={value}
              checked={operation === value}
              onChange={() => {
                setOperation(value);
                setInvalid(false);
              }}
              data-testid={`recovery-operation-${value}`}
            />{' '}
            {OPERATION_COPY[value]}
          </label>
        ))}
      </fieldset>
      {operation === 'restore.production' ? (
        <p data-testid="recovery-production-note">
          운영 데이터 복원은 관리자의 결정과 운영자의 직접 실행이 필요합니다. 운영자는 서비스가
          쓰기를 멈춘 뒤 먼저 새 백업을 만들고, 실행하기 전에는 아무것도 바뀌지 않습니다.
        </p>
      ) : null}
      {restore ? (
        <fieldset aria-invalid={invalid || undefined}>
          <legend>백업</legend>
          {passed.length === 0 ? <p>무결성 확인을 통과한 백업이 없습니다</p> : null}
          {passed.map((item) => (
            <label key={item.evidenceRef}>
              <input
                type="radio"
                name="recovery-set"
                value={item.evidenceRef}
                checked={chosen === item.evidenceRef}
                onChange={() => {
                  setChosen(item.evidenceRef);
                  setInvalid(false);
                }}
                data-testid="recovery-set"
              />{' '}
              {item.component} · {operationsTime(item.observedAt)}
            </label>
          ))}
        </fieldset>
      ) : null}
      {invalid ? (
        <p role="alert" data-testid="recovery-set-error">
          {CHOOSE_SET}
        </p>
      ) : null}
      <button type="button" onClick={open} data-testid="recovery-open">
        요청 확인
      </button>
      {confirmation ? <p data-testid="recovery-confirmation">{confirmation}</p> : null}
      <StatusLine value={message} />
      {confirming ? (
        <RecoveryConfirmDialog
          operation={operation}
          target={
            restore && set
              ? `${set.component} (${set.evidenceRef})`
              : (ENVIRONMENT_COPY[environment] ?? environment)
          }
          currentState={
            restore && set
              ? '무결성 확인 통과'
              : `백업 ${valueOf(revision ?? { limitations: [] }, 'revision') ?? '0'}개`
          }
          busy={busy}
          {...(newSubmission ? { newSubmission } : {})}
          onConfirm={(submissionId) => void submit(submissionId)}
          onCancel={() => setConfirming(false)}
        />
      ) : null}
      <h4>복구 요청</h4>
      {requests.length === 0 ? <p>복구 요청이 없습니다</p> : null}
      <ul data-testid="recovery-requests">
        {requests.map((item) => {
          const state = (valueOf(item, 'state') ?? 'unknown') as RecoveryState;
          const reason = WAIT_REASONS[state];
          return (
            <li key={item.evidenceRef} data-testid="recovery-request">
              <span>
                {
                  OPERATION_COPY[
                    (valueOf(item, 'operation') ?? 'backup.create') as RecoveryOperation
                  ]
                }{' '}
                ·{' '}
                {ENVIRONMENT_COPY[valueOf(item, 'environment') ?? ''] ??
                  valueOf(item, 'environment')}{' '}
                · {ORIGIN_COPY[valueOf(item, 'origin') ?? ''] ?? valueOf(item, 'origin')} ·{' '}
                <strong>{RECOVERY_STATE_COPY[state] ?? state}</strong>
              </span>
              {reason ? <p>{reason}</p> : null}
              {state === 'requested' ? <p className="muted">{WAITING_TEXT}</p> : null}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
