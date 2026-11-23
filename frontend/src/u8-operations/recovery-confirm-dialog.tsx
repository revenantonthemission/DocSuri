/**
 * RecoveryConfirmDialog (M16; BR4.7, BR4.9): names the target, its current state and the
 * effect, and states that the operator performs the effect. A production restore also
 * needs its acknowledgement ticked. Opening the dialog makes a new submission id for this
 * deliberate submission; its retries reuse it. It reuses the workspace dialog shell, with
 * its focus containment and Escape.
 */
import React, { useState } from 'react';
import { DialogShell } from '../u6-export/dialogs';
import { OPERATION_COPY, type RecoveryOperation } from './api';

export const ACKNOWLEDGEMENT = '이 백업으로 운영 데이터를 되돌리는 요청임을 이해했습니다';
export const ACKNOWLEDGEMENT_REQUIRED = '내용을 확인했다는 항목을 선택하세요';

export function RecoveryConfirmDialog({
  operation,
  target,
  currentState,
  busy,
  newSubmission = () => crypto.randomUUID(),
  onConfirm,
  onCancel,
}: {
  operation: RecoveryOperation;
  target: string;
  currentState: string;
  busy: boolean;
  newSubmission?: () => string;
  onConfirm: (submissionId: string) => void;
  onCancel: () => void;
}) {
  const [submissionId] = useState(newSubmission);
  const [acknowledged, setAcknowledged] = useState(false);
  const [missing, setMissing] = useState(false);
  const production = operation === 'restore.production';
  return (
    <DialogShell title={OPERATION_COPY[operation]} testId="recovery-confirm" onClose={onCancel}>
      <p>대상: {target}</p>
      <p>현재 상태: {currentState}</p>
      <p>
        {production
          ? '운영 데이터를 이 백업으로 되돌리는 요청을 남깁니다. 관리자의 결정과 운영자가 직접 실행해야 하며, 서비스가 쓰기를 멈춘 뒤 운영자가 먼저 새 백업을 만듭니다. 운영자가 실행하기 전에는 아무것도 바뀌지 않습니다.'
          : '요청을 남기면 운영자가 실행합니다.'}
      </p>
      {production ? (
        <label>
          <input
            type="checkbox"
            checked={acknowledged}
            onChange={(event) => {
              setAcknowledged(event.target.checked);
              setMissing(false);
            }}
            aria-invalid={missing || undefined}
            data-testid="recovery-acknowledge"
          />{' '}
          {ACKNOWLEDGEMENT}
        </label>
      ) : null}
      {missing ? (
        <p role="alert" data-testid="recovery-acknowledge-error">
          {ACKNOWLEDGEMENT_REQUIRED}
        </p>
      ) : null}
      <div className="row">
        <button type="button" onClick={onCancel} data-testid="recovery-cancel">
          취소
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => {
            if (production && !acknowledged) {
              setMissing(true);
              return;
            }
            onConfirm(submissionId);
          }}
          data-testid="recovery-submit"
        >
          요청 남기기
        </button>
      </div>
    </DialogShell>
  );
}
