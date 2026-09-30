/** JobStatus — SSE 기반 작업 상태 표시 */

'use client';

import { useEffect, useRef, useState } from 'react';
import { subscribeJobEvents, JobState } from '@/lib/api/contentJobApi';

type JobStatusProps = {
  jobId: string;
  onComplete?: (state: 'COMPLETED' | 'FAILED' | 'ABSTAINED', assetId?: string, error?: unknown) => void;
};

const STATE_LABELS: Record<string, string> = {
  SUBMITTED: '접수됨',
  ACCEPTED: '대기중',
  QUEUED: '대기중',
  RUNNING: '처리중',
  COMPLETED: '완료',
  FAILED: '실패',
  ABSTAINED: '기권',
};

const STATE_COLORS: Record<string, string> = {
  SUBMITTED: 'text-blue-600',
  ACCEPTED: 'text-yellow-600',
  QUEUED: 'text-yellow-600',
  RUNNING: 'text-blue-600',
  COMPLETED: 'text-green-600',
  FAILED: 'text-red-600',
  ABSTAINED: 'text-gray-600',
};

const TERMINAL_STATES = ['COMPLETED', 'FAILED', 'ABSTAINED'] as const;

const JOB_STATES: readonly string[] = [
  'SUBMITTED',
  'ACCEPTED',
  'QUEUED',
  'RUNNING',
  ...TERMINAL_STATES,
];

function isJobStateName(value: string): value is JobState['state'] {
  return JOB_STATES.includes(value);
}

type JobStatusState = JobState | null;

export function JobStatus({ jobId, onComplete }: JobStatusProps) {
  const [state, setState] = useState<JobStatusState>(null);
  const [eventHistory, setEventHistory] = useState<string[]>([]);
  const jobIdRef = useRef(jobId);

  // Keep jobIdRef updated
  useEffect(() => {
    jobIdRef.current = jobId;
  }, [jobId]);

  useEffect(() => {
    const unsubscribe = subscribeJobEvents(
      jobIdRef.current,
      (event) => {
        if (!isJobStateName(event.state)) return;
        const stateName = event.state;

        setState(() => {
          const next: JobState = { jobId: event.jobId, state: stateName };
          const { assetId, error, abstainReason } = event.payload ?? {};
          if (assetId !== undefined) next.assetId = assetId;
          if (error !== undefined) next.error = error;
          if (abstainReason !== undefined) next.abstainReason = abstainReason;
          return next;
        });
        setEventHistory(prev => [...prev, `${event.state} @ ${new Date(event.timestampUs / 1000).toLocaleTimeString()}`]);
      },
    );

    return unsubscribe;
  }, []);

  if (!state) return <div className="text-sm text-gray-500">작업 상태 로딩 중...</div>;

  const terminalState = TERMINAL_STATES.find(s => s === state.state);

  return (
    <div className="space-y-2 p-4 border rounded-lg bg-white">
      <div className="flex items-center justify-between">
        <span className="font-medium">작업 상태</span>
        <span className={`font-medium ${STATE_COLORS[state.state] || 'text-gray-600'}`}>{STATE_LABELS[state.state] || state.state}</span>
      </div>

      {state.assetId && (
        <div className="text-sm text-green-600">
          자산 ID: <code className="break-all">{state.assetId}</code>
        </div>
      )}

      {state.error && (
        <div className="text-sm text-red-600">
          오류: {state.error.message} ({state.error.errorType})
          {state.error.retryable && <span className="ml-2 text-yellow-600">(재시도 가능)</span>}
        </div>
      )}

      {state.abstainReason && (
        <div className="text-sm text-gray-600">
          기권 사유: {state.abstainReason}
        </div>
      )}

      <details className="mt-2">
        <summary className="text-sm text-gray-500 cursor-pointer">이벤트 히스토리</summary>
        <ul className="mt-1 text-xs text-gray-500 space-y-1">
          {eventHistory.map((e, i) => (
            <li key={i}>{e}</li>
          ))}
        </ul>
      </details>

      {terminalState && onComplete && (
        <div className="mt-2 pt-2 border-t">
          <button
            onClick={() => onComplete(terminalState, state.assetId, state.error)}
            className="text-sm text-blue-600 hover:underline"
          >
            계속하기
          </button>
        </div>
      )}
    </div>
  );
}

export default JobStatus;
