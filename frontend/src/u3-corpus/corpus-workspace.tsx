/**
 * U3 corpus workspace: the composed discovery → reading → assistance → glossary
 * flow over the owned corpus realm, mounted by the shell when its capabilities
 * are installed.
 */

import React, { useEffect, useRef, useState } from 'react';
import { Transport } from '../api';
import { Panel } from '../ui';
import { SearchHit, api } from './api';
import { ReadingSection, SearchSection } from './search-reading';
import { AssistanceSection, GlossarySection } from './assistance';

export function CorpusWorkspace({
  client,
  signedIn,
}: {
  client: Transport;
  signedIn: boolean;
}) {
  const [hit, setHit] = useState<SearchHit | null>(null);
  const [content, setContent] = useState<{
    revision: string;
    hash: string;
  } | null>(null);
  const heading = useRef<HTMLHeadingElement | null>(null);

  useEffect(() => {
    if (hit) window.requestAnimationFrame(() => heading.current?.focus());
  }, [hit]);

  return (
    <div className="corpus-workspace" data-testid="corpus-workspace">
      {/* The search surface stays mounted so query, filters and results survive
          opening a paper, exactly as the retained-context contract requires. */}
      <div hidden={hit !== null} data-testid="search-region">
        <SearchSection client={client} onOpen={setHit} />
      </div>
      {hit !== null ? (
        <>
          <button
            type="button"
            onClick={() => setHit(null)}
            data-testid="reading-back"
          >
            검색으로 돌아가기
          </button>
          <ReadingSection client={client} hit={hit} signedIn={signedIn} />
          <ContentBinding client={client} hit={hit} onBound={setContent} />
          {content ? (
            <AssistanceSection
              client={client}
              paper={hit.paper}
              contentRevision={content.revision}
              contentHash={content.hash}
              signedIn={signedIn}
            />
          ) : null}
        </>
      ) : null}
      <GlossarySection client={client} signedIn={signedIn} />
    </div>
  );
}

function ContentBinding({
  client,
  hit,
  onBound,
}: {
  client: Transport;
  hit: SearchHit;
  onBound: (value: { revision: string; hash: string }) => void;
}) {
  useEffect(() => {
    let active = true;
    api
      .readContent(client, hit.paper, 'assistance')
      .then((value) => {
        if (!active || value.availability !== 'ready') return;
        onBound({
          revision: value.content.contentRevision,
          hash: value.content.contentHash,
        });
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client, hit.paper]);
  return null;
}

export function CorpusUnavailable() {
  return (
    <Panel title="코퍼스 작업 공간" testId="corpus-unavailable">
      <p role="status">이 환경에서는 코퍼스 기능을 사용할 수 없어요.</p>
    </Panel>
  );
}
