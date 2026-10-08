'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { submitJob } from '@/lib/api/contentJobApi';
import { UserFacingError } from '@/lib/api/errors';
import {
  buildIdempotencyKey,
  readStoredOriginalRequestForOwner,
  storeIdempotencyKey,
  storeOriginalRequest,
} from '@/lib/idempotencyService';
import { useSession } from '@/components/session/SessionContext';
import { emitJobDiagnostic } from '@/lib/jobDiagnostics';

// JobSubmissionForm — the pre-job surface for explicit submission and same-key
// recovery (ADR-013 / Steps 25-26).
//
// Opening the form or changing parameters NEVER submits. The original request
// is captured (and its idempotency key persisted) BEFORE the POST, so an
// uncertain outcome — reload, offline, gateway failure — can be re-checked with
// the exact same key instead of re-executing work or rotating keys. Missing
// originals disable recovery: without the stored key there is no same-parameter
// identity to replay.

export type JobTaskKind = 'summarize' | 'translate';
export type JobPersona = 'expert' | 'beginner';
export type TranslateScope = 'abstract' | 'full';

export interface JobSubmissionIdentity {
  jobId: string;
  taskType: JobTaskKind;
  idempotencyKey: string;
  input: Record<string, unknown>;
}

export interface JobSubmissionFormProps {
  paperId: string;
  version: number;
  task: JobTaskKind;
  onSubmitted: (identity: JobSubmissionIdentity) => void;
  onCancel?: () => void;
}

type SubmitPhase = 'idle' | 'submitting' | 'uncertain' | 'error';

export function JobSubmissionForm({
  paperId,
  version,
  task,
  onSubmitted,
  onCancel,
}: JobSubmissionFormProps) {
  const { user } = useSession();
  const [persona, setPersona] = useState<JobPersona>('expert');
  const [scope, setScope] = useState<TranslateScope>('abstract');
  const [phase, setPhase] = useState<SubmitPhase>('idle');
  const [message, setMessage] = useState<string | null>(null);
  const [recoverable, setRecoverable] = useState(false);
  const attentionRef = useRef<HTMLButtonElement>(null);

  // Reload recovery: a captured original request — captured by THIS owner —
  // means a submission may have reached the backend before the page went away.
  // An absent or other-owner record disables recovery. This effect NEVER submits.
  useEffect(() => {
    const owner = user?.userId;
    setRecoverable(
      owner !== undefined && readStoredOriginalRequestForOwner(paperId, task, owner) !== null,
    );
  }, [paperId, task, user?.userId]);

  const buildInput = useCallback((): Record<string, unknown> => {
    // C1 caller profile: new frontend submissions explicitly supply the
    // supported defaults — `version` from the paper, `targetLang: 'ko'`, the
    // initial summary persona from selection with summary `scope: 'full'`, and
    // the selected translation scope (translation keeps the default persona).
    if (task === 'summarize') {
      return { paperId, version, targetLang: 'ko', persona, scope: 'full' };
    }
    return { paperId, version, targetLang: 'ko', persona: 'expert', scope };
  }, [paperId, persona, scope, task, version]);

  const send = useCallback(
    async (key: string, input: Record<string, unknown>) => {
      setPhase('submitting');
      setMessage(null);
      emitJobDiagnostic({ kind: 'submit', taskType: task, outcome: 'started' });
      try {
        const response = await submitJob({ taskType: task, input, idempotencyKey: key });
        setPhase('idle');
        emitJobDiagnostic({ kind: 'submit', taskType: task, outcome: 'sent' });
        onSubmitted({ jobId: response.jobId, taskType: task, idempotencyKey: key, input });
      } catch (caught) {
        // A raw fetch rejection is a network failure: the request may or may not
        // have reached the backend, so its outcome is UNKNOWN.
        const kind = caught instanceof UserFacingError ? caught.kind : 'network';
        const text =
          caught instanceof UserFacingError
            ? caught.message
            : '요청을 보내지 못했습니다. 잠시 후 다시 시도해 주세요.';
        setMessage(text);
        emitJobDiagnostic({
          kind: 'submit',
          taskType: task,
          outcome: kind === 'network' || kind === 'server' ? 'uncertain' : 'rejected',
        });
        // A network/gateway failure leaves the outcome UNKNOWN — the same key
        // may already have created the job, so recovery must re-check, never
        // re-key. Other failures are definite and keep the draft.
        setPhase(kind === 'network' || kind === 'server' ? 'uncertain' : 'error');
      }
    },
    [onSubmitted, task],
  );

  const submit = useCallback(async () => {
    const userId = user?.userId;
    if (!userId) {
      setPhase('error');
      setMessage('로그인이 필요합니다. 다시 로그인해 주세요.');
      return;
    }
    const input = buildInput();
    const key = await buildIdempotencyKey({ userId, paperId, taskType: task, params: input });
    // Capture BEFORE sending: the key and the exact original input survive a
    // reload that interrupts the POST, so recovery can replay the captured
    // bytes — never a draft rebuilt from the current controls.
    storeIdempotencyKey(paperId, task, key);
    storeOriginalRequest(paperId, task, { key, taskType: task, owner: userId, input });
    setRecoverable(true);
    await send(key, input);
  }, [buildInput, paperId, send, task, user?.userId]);

  const recover = useCallback(async () => {
    // Owner-bound: another session owner's captured request is not a recovery source.
    const original = readStoredOriginalRequestForOwner(paperId, task, user?.userId ?? '');
    if (!original) {
      setRecoverable(false);
      return;
    }
    // Same-key recovery replays the CAPTURED original request. An edited draft
    // is never sent under the original key — a changed draft is a new explicit
    // submission with its own key.
    await send(original.key, original.input);
  }, [paperId, send, task, user?.userId]);

  // Conditional focus: attention moves only when a state actually needs it.
  useEffect(() => {
    if ((phase === 'uncertain' || phase === 'error') && attentionRef.current) {
      attentionRef.current.focus();
    }
  }, [phase]);

  const busy = phase === 'submitting';
  // Same-key re-check is offered while the outcome is unknown (reload recovery
  // on mount, or an uncertain send) — never for a definite rejection, where the
  // draft should be corrected and resubmitted explicitly.
  const canRecover = recoverable && !busy && (phase === 'idle' || phase === 'uncertain');

  return (
    <form
      className="space-y-3"
      onSubmit={(event) => {
        event.preventDefault();
        void submit();
      }}
    >
      {task === 'summarize' ? (
        <label className="block text-sm">
          <span className="mb-1 block font-medium">요약 수준</span>
          <select
            className="w-full rounded border px-2 py-1"
            value={persona}
            disabled={busy}
            onChange={(event) => setPersona(event.target.value as JobPersona)}
          >
            <option value="expert">전문가용</option>
            <option value="beginner">쉬운 설명</option>
          </select>
        </label>
      ) : (
        <label className="block text-sm">
          <span className="mb-1 block font-medium">번역 범위</span>
          <select
            className="w-full rounded border px-2 py-1"
            value={scope}
            disabled={busy}
            onChange={(event) => setScope(event.target.value as TranslateScope)}
          >
            <option value="abstract">초록 번역</option>
            <option value="full">전문 번역</option>
          </select>
        </label>
      )}

      {message && (
        <p
          role={phase === 'error' ? 'alert' : 'status'}
          aria-live="polite"
          className={`text-sm ${phase === 'error' ? 'text-red-600' : 'text-yellow-700'}`}
        >
          {message}
        </p>
      )}

      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={busy}
          className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
        >
          {busy ? '제출 중…' : task === 'summarize' ? '요약 시작' : '번역 시작'}
        </button>

        {canRecover && (
          <button
            ref={attentionRef}
            type="button"
            onClick={() => void recover()}
            className="text-sm text-blue-600 underline"
          >
            이전 요청 확인
          </button>
        )}

        {phase === 'error' && !busy && (
          <button ref={attentionRef} type="button" onClick={() => void submit()} className="text-sm underline">
            다시 시도
          </button>
        )}

        {onCancel && (
          <button type="button" onClick={onCancel} disabled={busy} className="text-sm text-gray-500 underline">
            취소
          </button>
        )}
      </div>

      {phase === 'uncertain' && (
        <p className="text-xs text-gray-500">
          요청이 도달했는지 확인이 필요합니다. 같은 요청으로 결과를 확인합니다 — 새로운 작업을 만들지
          않습니다.
        </p>
      )}
    </form>
  );
}

export default JobSubmissionForm;
