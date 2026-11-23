/**
 * JobsView 작업 (frontend-components.md; A2, BR5.4): the owner's research and novelty jobs,
 * newest first, read through the shared transport with stale-while-revalidate caching.
 * While any visible job is unfinished the list refreshes every 5 s (with a pause toggle,
 * WCAG 2.2.2). Reading it never starts, repeats or cancels work: there is no start,
 * cancel or retry control here.
 */
import React, { useRef, useState } from 'react';
import useSWRInfinite from 'swr/infinite';
import type { Transport } from '../api';
import { Panel } from '../ui';
import {
  finished,
  KIND_COPY,
  LIST_REFRESH_MS,
  listJobs,
  STATE_COPY,
  updatedText,
  type JobKind,
  type JobListItem,
  type JobListPage,
} from './api';
import { JobLiveStatus, type SourceFactory } from './job-live-status';

type Filter = 'all' | JobKind;
const FILTERS: readonly { value: Filter; label: string }[] = [
  { value: 'all', label: '전체' },
  { value: 'research', label: '연구' },
  { value: 'novelty', label: '참신성 분석' },
];

export function JobsView({
  client,
  onOpenResearch,
  onOpenView,
  createSource,
}: {
  client: Transport;
  onOpenResearch: () => void;
  onOpenView: (kind: JobKind) => void;
  createSource?: SourceFactory;
}) {
  const heading = useRef<HTMLHeadingElement | null>(null);
  const [filter, setFilter] = useState<Filter>('all');
  const [paused, setPaused] = useState(false);
  const [selected, setSelected] = useState<JobListItem | null>(null);
  const kind = filter === 'all' ? null : filter;
  const pages = useSWRInfinite<JobListPage>(
    (index, previous: JobListPage | null) =>
      previous && !previous.nextCursor
        ? null
        : ['u8-jobs', client.generation, kind, index === 0 ? null : (previous?.nextCursor ?? null)],
    (key: readonly unknown[]) => listJobs(client, kind, key[3] as string | null),
    {
      revalidateOnFocus: false,
      shouldRetryOnError: false,
      refreshInterval: (latest) =>
        !paused && (latest ?? []).some((page) => page.items.some((item) => !finished(item.state)))
          ? LIST_REFRESH_MS
          : 0,
    },
  );
  const items = (pages.data ?? []).flatMap((page) => page.items);
  const last = pages.data?.[pages.data.length - 1];
  const loading = pages.isLoading;
  const live = items.some((item) => !finished(item.state));

  return (
    <Panel title="작업" titleRef={heading} testId="jobs-view">
      <div className="row" role="group" aria-label="작업 종류">
        {FILTERS.map((option) => (
          <button
            key={option.value}
            type="button"
            aria-pressed={filter === option.value}
            onClick={() => {
              setFilter(option.value);
              setSelected(null);
            }}
            data-testid={`jobs-filter-${option.value}`}
          >
            {option.label}
          </button>
        ))}
        <button
          type="button"
          aria-pressed={paused}
          onClick={() => setPaused((value) => !value)}
          data-testid="jobs-pause"
        >
          {paused ? '자동 새로 고침 다시 시작' : '자동 새로 고침 일시 중지'}
        </button>
      </div>
      {loading ? (
        <ul aria-hidden="true" data-testid="jobs-loading">
          {[0, 1, 2].map((index) => (
            <li key={index} className="skeleton">
              &nbsp;
            </li>
          ))}
        </ul>
      ) : null}
      {pages.error && !loading ? (
        <div role="alert" data-testid="jobs-error">
          <p>작업 목록을 불러오지 못했습니다.</p>
          <button
            type="button"
            onClick={() => {
              // The retry's read hides this block (SWR's isLoading when nothing is cached,
              // the answer otherwise): focus moves to the heading, which stays mounted.
              heading.current?.focus();
              void pages.mutate();
            }}
            data-testid="jobs-retry"
          >
            다시 시도
          </button>
        </div>
      ) : null}
      {!loading && !pages.error && items.length === 0 ? (
        <div data-testid="jobs-empty">
          <p>아직 작업이 없습니다</p>
          <button
            type="button"
            className="link"
            onClick={onOpenResearch}
            data-testid="jobs-empty-research"
          >
            연구
          </button>
        </div>
      ) : null}
      {items.length ? (
        <ul data-testid="jobs-list">
          {items.map((item) => (
            <li key={item.jobId} data-testid="jobs-item">
              <p>
                <strong>{item.label}</strong> · {KIND_COPY[item.kind]} ·{' '}
                <span data-testid="jobs-item-state">{STATE_COPY[item.state] ?? item.state}</span>
              </p>
              <p className="muted">마지막 변경 {updatedText(item.updatedAt)}</p>
              <button
                type="button"
                className="link"
                onClick={() => setSelected(item)}
                data-testid="jobs-item-open"
              >
                {item.resultAvailable ? '결과 보기' : '진행 상황 보기'}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      {last?.nextCursor ? (
        <button
          type="button"
          onClick={() => void pages.setSize(pages.size + 1)}
          disabled={pages.isValidating}
          data-testid="jobs-more"
        >
          더 보기
        </button>
      ) : null}
      {live && !paused ? (
        <p className="muted" data-testid="jobs-refreshing">
          진행 중인 작업이 있어 목록을 자동으로 새로 고칩니다
        </p>
      ) : null}
      {selected ? (
        <section aria-label={`${selected.label} 상태`} data-testid="jobs-selected">
          <JobLiveStatus
            client={client}
            jobId={selected.jobId}
            {...(createSource ? { createSource } : {})}
          />
          <button
            type="button"
            onClick={() => onOpenView(selected.kind)}
            data-testid="jobs-open-view"
          >
            {KIND_COPY[selected.kind]} 화면에서 열기
          </button>
        </section>
      ) : null}
    </Panel>
  );
}
