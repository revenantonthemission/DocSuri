/**
 * U3 discovery and reading surfaces: query/filters/results, reading states and
 * the citation explorer, on the shared shell and C13 Transport.
 *
 * Every state change is announced; committed context survives errors; expired
 * snapshots and degradations are explicit; opened content is served from the
 * exact requested version.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, Transport, dispositionCopy } from '../api';
import { Notice, StatusLine, notice } from '../ui';
import {
  ContentRead,
  CitationResponse,
  QueryFilter,
  QueryContext,
  SearchHit,
  SearchResponse,
  SEARCH_POLICY,
  VOCABULARY,
  api,
} from './api';

type SearchState = 'idle' | 'loading' | 'results' | 'empty' | 'error' | 'invalid';

export function SearchSection({
  client,
  onOpen,
}: {
  client: Transport;
  onOpen: (hit: SearchHit) => void;
}) {
  const [queryText, setQueryText] = useState('');
  const [mode, setMode] = useState<'lexical' | 'semantic'>('lexical');
  const [authorFilter, setAuthorFilter] = useState('');
  const [state, setState] = useState<SearchState>('idle');
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [status, setStatus] = useState<Notice | null>(null);

  const context = (): QueryContext => {
    const filters: QueryFilter[] = [];
    if (authorFilter.trim()) {
      filters.push({ filterId: 'author', operatorId: 'contains', values: [authorFilter.trim()] });
    }
    return {
      query: queryText,
      modeId: mode,
      orderId: 'relevance',
      filters,
      vocabularyRevision: VOCABULARY,
      policyRef: SEARCH_POLICY,
    };
  };

  const run = useCallback(
    async (value?: QueryContext, cursor?: string) => {
      const submitted = value ?? context();
      if (!submitted.query.trim()) {
        setState('invalid');
        setStatus(notice('alert', '검색어를 입력해 주세요'));
        return;
      }
      setState('loading');
      setStatus(notice('polite', '검색하고 있어요'));
      try {
        const result = await api.search(client, submitted, cursor ? { cursor } : {});
        setResponse(result);
        setState(result.hits.length ? 'results' : 'empty');
        setStatus(
          notice(
            result.outcome === 'degraded' ? 'polite' : 'polite',
            result.outcome === 'degraded'
              ? '의미 검색을 사용할 수 없어 어휘 검색으로 대체했어요'
              : `${result.hits.length}건의 결과를 찾았어요`,
          ),
        );
      } catch (error) {
        setState('error');
        setStatus(describe(error));
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [client, queryText, mode, authorFilter],
  );

  return (
    <section className="panel" data-testid="query-workspace">
      <h2 tabIndex={-1}>검색</h2>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void run();
        }}
        aria-label="검색"
      >
        <label htmlFor="u3-query">검색어</label>
        <input
          id="u3-query"
          value={queryText}
          onChange={(event) => setQueryText(event.target.value)}
          maxLength={2048}
          data-testid="search-query"
        />
        <label htmlFor="u3-mode">검색 방식</label>
        <select
          id="u3-mode"
          value={mode}
          onChange={(event) => setMode(event.target.value as 'lexical' | 'semantic')}
          data-testid="search-mode"
        >
          <option value="lexical">어휘</option>
          <option value="semantic">의미</option>
        </select>
        <label htmlFor="u3-author">저자 필터</label>
        <input
          id="u3-author"
          value={authorFilter}
          onChange={(event) => setAuthorFilter(event.target.value)}
          maxLength={100}
          data-testid="search-author"
        />
        <button type="submit" data-testid="search-submit">
          검색
        </button>
      </form>
      <StatusLine value={status} />
      {state === 'loading' ? (
        <p role="status" data-testid="search-status">
          불러오는 중…
        </p>
      ) : null}
      {state === 'invalid' ? (
        <p className="status status-alert" role="alert">
          검색어를 확인해 주세요. 이전 결과는 유지됩니다.
        </p>
      ) : null}
      {state === 'empty' ? (
        <p role="status" data-testid="search-status">
          검색 결과가 없어요
        </p>
      ) : null}
      {state === 'error' ? (
        <p role="alert" data-testid="search-status">
          검색을 완료하지 못했어요
        </p>
      ) : null}
      {response ? (
        <div data-testid="search-results">
          {response.outcome === 'degraded' || response.limitations.length ? (
            <ul className="notice-list" data-testid="snapshot-notice">
              {response.limitations.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          ) : null}
          <p className="subtle" data-testid="snapshot-revision">
            스냅샷 {response.page.snapshotRevision.slice(0, 8)}
          </p>
          <ul className="result-list">
            {response.hits.map((hit) => (
              <li key={hit.paper.versionId} data-testid="result-row">
                <button type="button" onClick={() => onOpen(hit)} data-testid="result-open">
                  <strong>{hit.title}</strong>
                </button>
                <span className="subtle">{hit.authors.join(', ')}</span>
                <span data-testid="result-availability">{hit.availability}</span>
                <p>{hit.snippet}</p>
                <a href={hit.sourceUrl} rel="noreferrer noopener" target="_blank">
                  원문 링크
                </a>
              </li>
            ))}
          </ul>
          {response.page.nextCursor ? (
            <button
              type="button"
              onClick={() => void run(response.query, response.page.nextCursor!)}
              data-testid="search-next"
            >
              다음 페이지
            </button>
          ) : null}
          <button
            type="button"
            onClick={() => void run(response.query)}
            data-testid="search-refine"
          >
            다시 실행
          </button>
        </div>
      ) : null}
    </section>
  );
}

export function ReadingSection({
  client,
  hit,
  signedIn,
}: {
  client: Transport;
  hit: SearchHit;
  signedIn: boolean;
}) {
  const [read, setRead] = useState<ContentRead | null>(null);
  const [status, setStatus] = useState<Notice | null>(null);
  const [direction, setDirection] = useState<'cited' | 'citing'>('cited');
  const [citations, setCitations] = useState<CitationResponse | null>(null);
  const headingRef = useRef<HTMLHeadingElement | null>(null);

  useEffect(() => {
    let active = true;
    setRead(null);
    api
      .readContent(client, hit.paper)
      .then((value) => {
        if (active) {
          setRead(value);
          if (value.availability !== 'ready') {
            setStatus(notice('alert', stateCopy(value.availability)));
          }
        }
      })
      .catch((error) => {
        if (active) setStatus(describe(error));
      });
    return () => {
      active = false;
    };
  }, [client, hit.paper]);

  const explore = async (next: 'cited' | 'citing') => {
    setDirection(next);
    setStatus(notice('polite', '인용 정보를 불러오는 중…'));
    try {
      const value = await api.citations(client, hit.paper, next);
      setCitations(value);
      setStatus(
        notice(
          'polite',
          value.coverage === 'partial'
            ? '일부 인용 정보만 제공됩니다'
            : '인용 정보를 불러왔어요',
        ),
      );
    } catch (error) {
      setStatus(describe(error));
    }
  };

  const saveNode = async (nodeId: string, paper: SearchHit['paper'] | null) => {
    if (!paper) return;
    try {
      await api.savePaper(client, paper);
      setStatus(notice('polite', '내 서재에 저장했어요'));
    } catch (error) {
      setStatus(describe(error));
    }
  };

  return (
    <section className="panel" data-testid="paper-workspace">
      <h2 tabIndex={-1} ref={headingRef} data-testid="paper-identity">
        {hit.title}
      </h2>
      <p className="subtle">
        {hit.authors.join(', ')} · 버전 {hit.paper.versionId}
      </p>
      <StatusLine value={status} />
      {read === null ? (
        <p role="status">불러오는 중…</p>
      ) : read.availability === 'ready' ? (
        <article data-testid="reading-surface">
          {read.content.sections.map((section) => (
            <section key={section.sectionId} id={section.anchor}>
              <h3 data-testid="section-anchor">{section.heading}</h3>
              <p>{section.text}</p>
            </section>
          ))}
          {read.content.assets.map((asset) => (
            <figure key={asset.assetId} data-testid="figure-view">
              <figcaption>{asset.altText}</figcaption>
            </figure>
          ))}
          {read.content.limitations.map((item) => (
            <p key={item} className="subtle">
              {item}
            </p>
          ))}
        </article>
      ) : (
        <div data-testid="content-state" role="status">
          <p>{stateCopy(read.availability)}</p>
          {read.availability === 'absent' ? (
            <button type="button" onClick={() => void explore('cited')}>
              다시 검색하기
            </button>
          ) : null}
          {read.retryable ? (
            <button
              type="button"
              onClick={() => {
                void api.readContent(client, hit.paper).then(setRead);
              }}
            >
              다시 시도
            </button>
          ) : null}
        </div>
      )}
      {signedIn && read?.availability === 'ready' ? (
        <section data-testid="citation-explorer">
          <h3>인용 탐색</h3>
          <div role="group" aria-label="인용 방향">
            <button
              type="button"
              aria-pressed={direction === 'cited'}
              onClick={() => void explore('cited')}
              data-testid="citation-cited"
            >
              이 논문이 인용한
            </button>
            <button
              type="button"
              aria-pressed={direction === 'citing'}
              onClick={() => void explore('citing')}
              data-testid="citation-citing"
            >
              이 논문을 인용한
            </button>
          </div>
          {citations ? (
            <>
              <p data-testid="citation-freshness">
                최신성 {citations.freshness} · 범위 {citations.coverage}
              </p>
              <ul>
                {citations.nodes.map((node) => (
                  <li key={node.nodeId} data-testid="citation-node">
                    <span>{node.title ?? node.nodeId}</span>
                    <span className="subtle">{node.disposition}</span>
                    {node.disposition === 'eligible' && node.paper ? (
                      <button
                        type="button"
                        onClick={() => void saveNode(node.nodeId, node.paper)}
                        data-testid="citation-save"
                      >
                        저장
                      </button>
                    ) : null}
                  </li>
                ))}
              </ul>
              {citations.limitations.map((item) => (
                <p key={item} className="subtle">
                  {item}
                </p>
              ))}
            </>
          ) : null}
        </section>
      ) : null}
    </section>
  );
}

function stateCopy(availability: string): string {
  switch (availability) {
    case 'absent':
      return '이 자료를 찾을 수 없어요';
    case 'building':
      return '자료를 준비하고 있어요';
    case 'unsupported':
      return '이 형식은 지원되지 않아요';
    case 'failed':
      return '자료를 불러오지 못했어요';
    case 'withdrawn':
      return '게시가 중단된 자료예요';
    case 'restricted':
      return '접근이 제한된 자료예요';
    default:
      return '자료를 표시할 수 없어요';
  }
}

function describe(error: unknown): Notice {
  if (error instanceof ApiError) {
    return notice('alert', dispositionCopy(error.envelope.code), error.envelope.requestId);
  }
  return notice('alert', '요청을 완료하지 못했어요');
}
