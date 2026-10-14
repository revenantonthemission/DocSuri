/** Owner-scoped Library views. Reading saved context never submits new research. */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { type PaperRef, type PolicyRef, type QueryContext, Transport } from './api';
import { type Notice, Panel, StatusLine, describeError, notice } from './ui';

type View = 'papers' | 'queries' | 'history' | 'recent';
type RecordItem = {
  savedPaperId?: string;
  savedSearchId?: string;
  historyId?: string;
  revision?: string;
  savedTitle?: string;
  title?: string;
  label?: string;
  savedPaper?: PaperRef;
  resolvedPaper?: PaperRef;
  paper?: PaperRef;
  queryContext?: QueryContext;
  sourceDisposition?: string;
  recordedAt?: string;
  lastActivityAt?: string;
};
type Page = {
  items: RecordItem[];
  page: { nextCursor?: string | null; snapshotRevision: string };
  clearBoundary?: string;
};
type Pending = { path: string; body: unknown; key: string; title: string };
const PATH: Record<View, string> = {
  papers: 'library-list-saved-papers',
  queries: 'library-list-saved-searches',
  history: 'library-list-history',
  recent: 'settings-list-recent-papers',
};
const COPY: Record<View, string> = {
  papers: '저장한 논문',
  queries: '저장한 검색',
  history: '검색 기록',
  recent: '최근 활동',
};
const API = '/api/v2/c03/';

export function LibraryControls({
  client,
  policy,
  onOpenPaper,
  onRunQuery,
}: {
  client: Transport;
  policy: PolicyRef;
  onOpenPaper: (paper: PaperRef) => void;
  onRunQuery: (query: QueryContext) => void;
}) {
  const [view, setView] = useState<View>('papers');
  const [page, setPage] = useState<Page | null>(null);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<Notice | null>(null);
  const [pending, setPending] = useState<Pending | null>(null);
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<QueryContext | null>(null);
  const mounted = useRef(true);
  const sequence = useRef(0);
  const heading = useRef<HTMLHeadingElement>(null);
  const confirmButton = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      sequence.current++;
    };
  }, []);
  useEffect(() => {
    if (pending) confirmButton.current?.focus();
  }, [pending]);

  const load = useCallback(
    async (cursor?: string) => {
      const current = ++sequence.current;
      const epoch = client.generation;
      setLoading(true);
      setStatus(null);
      if (!cursor) setPage(null);
      try {
        const value = await client.read<Page>(API + PATH[view], {
          page: { limit: 20, ...(cursor ? { cursor } : {}) },
        });
        if (!mounted.current || current !== sequence.current || epoch !== client.generation) return;
        setPage((previous) =>
          cursor && previous ? { ...value, items: [...previous.items, ...value.items] } : value,
        );
      } catch (error) {
        if (mounted.current && current === sequence.current && epoch === client.generation)
          setStatus(describeError(error));
      } finally {
        if (mounted.current && current === sequence.current) setLoading(false);
      }
    },
    [client, view],
  );
  useEffect(() => {
    void load();
    setPreview(null);
  }, [load]);

  function requestRemoval(item: RecordItem) {
    const paper = Boolean(item.savedPaperId);
    const id = paper ? item.savedPaperId : item.savedSearchId;
    if (!id || !item.revision) return;
    setPending({
      path: API + (paper ? 'library-remove-saved-paper' : 'library-remove-saved-search'),
      body: { [paper ? 'savedPaperId' : 'savedSearchId']: id, expectedRevision: item.revision },
      key: crypto.randomUUID(),
      title: paper ? '저장한 논문을 서재에서 삭제할까요?' : '저장한 검색을 삭제할까요?',
    });
  }

  async function confirm() {
    if (!pending || busy) return;
    const epoch = client.generation;
    setBusy(true);
    setStatus(null);
    try {
      await client.post(pending.path, pending.body, pending.key);
      if (!mounted.current || epoch !== client.generation) return;
      setPending(null);
      await load();
      if (!mounted.current || epoch !== client.generation) return;
      setStatus(notice('polite', '요청한 변경이 저장되었습니다.'));
      heading.current?.focus();
    } catch (error) {
      if (mounted.current && epoch === client.generation) setStatus(describeError(error));
    } finally {
      if (mounted.current && epoch === client.generation) setBusy(false);
    }
  }

  return (
    <Panel title="내 서재" titleRef={heading} testId="library-controls">
      <div className="button-group" role="group" aria-label="서재 보기">
        {(Object.keys(COPY) as View[]).map((name) => (
          <button
            key={name}
            type="button"
            aria-pressed={view === name}
            disabled={busy || pending !== null}
            data-testid={`library-view-${name}`}
            onClick={() => setView(name)}
          >
            {COPY[name]}
          </button>
        ))}
      </div>
      <p>저장한 논문 참조와 검색 조건을 확인하세요. 최근 활동은 동의한 활동만 표시합니다.</p>
      <button
        type="button"
        onClick={() => void load()}
        disabled={loading || busy}
        data-testid="library-refresh"
      >
        새로고침
      </button>
      {view === 'history' && page?.clearBoundary && (
        <button
          type="button"
          disabled={busy || pending !== null}
          data-testid="library-clear-history"
          onClick={() =>
            setPending({
              path: API + 'library-clear-history',
              body: { expectedRevision: page.clearBoundary, policyRef: policy },
              key: crypto.randomUUID(),
              title: '검색 기록을 지울까요? 저장한 논문과 검색은 유지됩니다.',
            })
          }
        >
          검색 기록 지우기
        </button>
      )}
      <StatusLine value={status} />
      {pending && (
        <section
          className="control-confirmation"
          aria-label="변경 확인"
          data-testid="library-confirmation"
        >
          <h3>{pending.title}</h3>
          <p>
            응답을 받지 못했다면 같은 요청을 다시 확인하세요. 다른 탭에서 변경되었다면 새로고침한 뒤
            다시 선택하세요.
          </p>
          <button
            ref={confirmButton}
            type="button"
            onClick={() => void confirm()}
            disabled={busy}
            data-testid="library-confirm"
          >
            {busy ? '확인 중…' : '변경 확인'}
          </button>
          <button
            type="button"
            disabled={busy}
            data-testid="library-cancel"
            onClick={() => {
              setPending(null);
              heading.current?.focus();
            }}
          >
            닫기
          </button>
        </section>
      )}
      {loading && <p role="status">{COPY[view]} 불러오는 중…</p>}
      {!loading && page?.items.length === 0 && (
        <p data-testid="library-empty">표시할 {COPY[view]}이 없습니다.</p>
      )}
      {page && (
        <ul className="control-list" aria-label={COPY[view]}>
          {page.items.map((item, index) => {
            const paper = item.resolvedPaper ?? (view === 'recent' ? item.paper : undefined);
            const available =
              paper &&
              (item.sourceDisposition === undefined || item.sourceDisposition === 'available');
            const title =
              item.savedTitle ??
              item.title ??
              item.label ??
              item.queryContext?.query ??
              item.paper?.paperId ??
              '논문';
            return (
              <li
                key={
                  item.savedPaperId ??
                  item.savedSearchId ??
                  item.historyId ??
                  `${item.paper?.versionId}-${index}`
                }
              >
                <h3>{title}</h3>
                {item.savedPaper && <p>저장한 버전: {item.savedPaper.versionId}</p>}
                {(item.recordedAt ?? item.lastActivityAt) && (
                  <time dateTime={item.recordedAt ?? item.lastActivityAt}>
                    {new Date((item.recordedAt ?? item.lastActivityAt)!).toLocaleString('ko-KR')}
                  </time>
                )}
                {item.queryContext && (
                  <>
                    <button
                      type="button"
                      data-testid="library-preview-query"
                      onClick={() => setPreview(item.queryContext!)}
                    >
                      검색 조건 보기
                    </button>
                    <button
                      type="button"
                      data-testid="library-rerun-query"
                      onClick={() => onRunQuery(item.queryContext!)}
                    >
                      다시 검색
                    </button>
                  </>
                )}
                {paper && (
                  <button
                    type="button"
                    disabled={!available}
                    data-testid="library-open-paper"
                    onClick={() => available && onOpenPaper(paper)}
                  >
                    논문 열기
                  </button>
                )}
                {item.sourceDisposition && item.sourceDisposition !== 'available' && (
                  <p role="status">원문을 현재 사용할 수 없습니다. 저장한 참조는 유지됩니다.</p>
                )}
                {(item.savedPaperId || item.savedSearchId) && (
                  <button
                    type="button"
                    disabled={busy || pending !== null}
                    data-testid="library-remove"
                    onClick={() => requestRemoval(item)}
                  >
                    서재에서 삭제
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      )}
      {page?.page.nextCursor && (
        <button
          type="button"
          disabled={loading || busy}
          data-testid="library-next-page"
          onClick={() => void load(page.page.nextCursor!)}
        >
          더 보기
        </button>
      )}
      {preview && (
        <section aria-label="저장한 검색 조건" data-testid="library-query-preview">
          <h3>저장한 검색 조건</h3>
          <p>검색어: {preview.query}</p>
          <p>
            검색 방식: {preview.modeId} · 정렬: {preview.orderId}
          </p>
          <ul>
            {preview.filters.map((filter, index) => (
              <li key={index}>
                {filter.filterId}: {filter.values.map(String).join(', ')}
              </li>
            ))}
          </ul>
          <p>조건을 보는 동안 검색을 실행하지 않습니다.</p>
          <button type="button" onClick={() => setPreview(null)}>
            조건 닫기
          </button>
        </section>
      )}
    </Panel>
  );
}
