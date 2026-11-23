/**
 * JobLiveStatus (frontend-components.md "JobsView"; NFR9.5, project rules): the selected
 * job's native event stream, which resumes from the last event id on its own reconnect;
 * polling every 2 s once the stream fails; inside an error boundary; each change
 * announced in the shell's polite live region, the end exactly once.
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import useSWR from 'swr';
import type { Transport } from '../api';
import { useAnnounce } from '../u8-shell/announcer';
import { finished, POLL_MS, readJob, STATE_COPY, type JobSnapshot } from './api';

export type EventSourceLike = {
  readonly readyState: number;
  addEventListener: (type: string, listener: (event: Event) => void) => void;
  close: () => void;
};
export type SourceFactory = (url: string) => EventSourceLike;

const CLOSED = 2;
const nativeSource: SourceFactory = (url) => new EventSource(url, { withCredentials: true });

class LiveBoundary extends React.Component<{ children: React.ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (this.state.failed) {
      return (
        <p role="alert" data-testid="job-live-failed">
          작업 상태를 표시하지 못했습니다. 화면을 다시 열어 주세요.
        </p>
      );
    }
    return this.props.children;
  }
}

export function JobLiveStatus(props: {
  client: Transport;
  jobId: string;
  createSource?: SourceFactory;
}) {
  return (
    <LiveBoundary>
      <LiveStatus {...props} />
    </LiveBoundary>
  );
}

function isSnapshot(value: unknown): value is JobSnapshot {
  const candidate = value as Partial<JobSnapshot> | null;
  return (
    typeof candidate === 'object' &&
    candidate !== null &&
    typeof candidate.jobId === 'string' &&
    typeof candidate.state === 'string' &&
    typeof candidate.seq === 'number'
  );
}

function LiveStatus({
  client,
  jobId,
  createSource = nativeSource,
}: {
  client: Transport;
  jobId: string;
  createSource?: SourceFactory;
}) {
  const { announce } = useAnnounce();
  const [snapshot, setSnapshot] = useState<JobSnapshot | null>(null);
  const [polling, setPolling] = useState(false);
  const [failed, setFailed] = useState(false);
  const spoken = useRef<string | null>(null);
  const ended = useRef(false);

  const accept = useCallback(
    (value: JobSnapshot) => {
      setSnapshot(value);
      if (spoken.current === value.state) return;
      spoken.current = value.state;
      if (finished(value.state)) {
        if (ended.current) return;
        ended.current = true;
        announce(`작업이 끝났습니다: ${STATE_COPY[value.state]}`);
      } else {
        announce(`작업 상태: ${STATE_COPY[value.state] ?? value.state}`);
      }
    },
    [announce],
  );

  useEffect(() => {
    let source: EventSourceLike;
    try {
      source = createSource(`/api/v2/jobs/${encodeURIComponent(jobId)}/events`);
    } catch {
      setPolling(true);
      return undefined;
    }
    source.addEventListener('snapshot', (event) => {
      let value: unknown;
      try {
        value = JSON.parse(String((event as MessageEvent).data));
      } catch {
        return; // a malformed frame is never shown
      }
      if (!isSnapshot(value)) return;
      accept(value);
      if (finished(value.state)) source.close();
    });
    source.addEventListener('error', (event) => {
      if (typeof (event as MessageEvent).data === 'string') {
        // The server's own error frame: the job is no longer the caller's to follow.
        source.close();
        setFailed(true);
        return;
      }
      if (source.readyState === CLOSED) setPolling(true);
    });
    return () => source.close();
  }, [jobId, createSource, accept]);

  const done = snapshot !== null && finished(snapshot.state);
  const poll = useSWR(
    polling && !done && !failed ? ['u8-job', client.generation, jobId] : null,
    () => readJob(client, jobId),
    { refreshInterval: POLL_MS, shouldRetryOnError: false, revalidateOnFocus: false },
  );
  useEffect(() => {
    if (poll.data && isSnapshot(poll.data)) accept(poll.data);
  }, [poll.data, accept]);

  return (
    <section aria-label="작업 진행 상황" data-testid="job-live-status">
      <p data-testid="job-live-state">
        {snapshot ? (STATE_COPY[snapshot.state] ?? snapshot.state) : '상태를 확인하고 있습니다'}
      </p>
      {polling && !done ? (
        <p className="muted" data-testid="job-live-partial">
          실시간 연결이 끊겨 주기적으로 확인합니다
        </p>
      ) : null}
      {failed || poll.error ? (
        <p role="alert" data-testid="job-live-error">
          작업 상태를 확인하지 못했습니다
        </p>
      ) : null}
    </section>
  );
}
