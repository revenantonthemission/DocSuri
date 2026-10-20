/** The destination step (BR1.5, BR8.2; decision S2).

The pages shared with the connection are listed with a refresh action. The listing
state comes from completeness and entries together; untitled pages get a placeholder
and every page shows its location context, so same-titled pages can be told apart.
A page that cannot be used says why. Creation permission is shown only as far as
Notion has shown it. The last used page is preselected only while listed and
readable; a stale one is dropped with a notice. */

import React, { useId, useState } from 'react';
import useSWR from 'swr';
import type { Transport } from '../api';
import {
  exportCall,
  listingState,
  preselection,
  unusableReason,
  UNTITLED_TITLE,
  type Connection,
  type DestinationEntry,
  type Destinations,
} from './api';
import { CREATION_CAPABILITY_COPY, displayTitle, UNUSABLE_REASON_COPY } from './copy';
import { refusalText } from './status';

const LISTING_NOTICES = {
  partial:
    'Notion이 공유된 페이지를 모두 알려주지 않았습니다. 찾는 페이지가 없으면 새로고침하세요.',
  unavailable: '지금은 공유된 페이지 목록을 불러올 수 없습니다. 잠시 후 새로고침하세요.',
  empty:
    '이 연결과 공유된 페이지가 아직 없습니다. Notion에서 내보낼 페이지를 열고, 오른쪽 위 ··· 메뉴의 ‘연결(Connections)’에서 이 통합을 추가한 뒤 새로고침하세요.',
} as const;

function DestinationOption({
  entry,
  connection,
  checked,
  onSelect,
}: {
  entry: DestinationEntry;
  connection: Connection;
  checked: boolean;
  onSelect: (entry: DestinationEntry) => void;
}) {
  const reason = unusableReason(entry, connection);
  const reasonId = useId();
  const capability = entry.creationCapability ?? 'unknown';
  return (
    <li className="export-destination" data-testid="destination-option">
      <label className="export-radio">
        <input
          type="radio"
          name="export-destination"
          value={entry.destinationId}
          checked={checked}
          disabled={reason !== null}
          onChange={() => onSelect(entry)}
          aria-describedby={reasonId}
          data-testid="destination-radio"
        />
        <span className="export-destination-title">
          {displayTitle(entry.title, UNTITLED_TITLE)}
        </span>
      </label>
      <p id={reasonId} className="export-destination-facts">
        <span>위치: {entry.context ?? '워크스페이스 최상위 또는 알 수 없음'}</span>
        <span> · {CREATION_CAPABILITY_COPY[capability]}</span>
        {reason ? (
          <span className="export-destination-reason" data-testid="destination-reason">
            {' '}
            · 선택할 수 없음: {UNUSABLE_REASON_COPY[reason]}
          </span>
        ) : null}
      </p>
    </li>
  );
}

export function DestinationStep({
  client,
  connection,
  initial,
  onChoose,
}: {
  client: Transport;
  connection: Connection;
  /** The page chosen earlier in this flow, kept when returning to the step. */
  initial: DestinationEntry | null;
  onChoose: (entry: DestinationEntry) => void;
}) {
  const [picked, setPicked] = useState<DestinationEntry | null>(initial);
  const { data, error, isLoading, isValidating, mutate } = useSWR<Destinations>(
    ['u6-export-destinations', client, client.generation, connection.connectionId],
    () => exportCall(client, 'list-export-destinations', {}),
    { revalidateOnFocus: false, shouldRetryOnError: false },
  );
  const state = data ? listingState(data) : null;
  const preselected = data ? preselection(data, connection) : { entry: null, dropped: false };
  const entries: readonly DestinationEntry[] = data?.destinations ?? [];
  // A choice the listing no longer offers as usable is not kept.
  const kept =
    picked &&
    entries.find(
      (item) =>
        item.destinationId === picked.destinationId && unusableReason(item, connection) === null,
    );
  const selected = kept ?? (picked ? null : preselected.entry);
  return (
    <div className="export-step" data-testid="destination-step">
      <div className="export-actions">
        <button
          type="button"
          onClick={() => void mutate()}
          disabled={isLoading || isValidating}
          data-testid="destination-refresh"
        >
          목록 새로고침
        </button>
      </div>
      {isLoading ? <p data-testid="destination-loading">공유된 페이지를 불러오는 중…</p> : null}
      {error ? (
        <p className="export-notice" data-testid="destination-error">
          {refusalText(error)}
        </p>
      ) : null}
      {state && state !== 'complete' ? (
        <p className="export-notice" data-testid={`destination-${state}`}>
          {LISTING_NOTICES[state]}
        </p>
      ) : null}
      {preselected.dropped && !picked ? (
        <p className="export-notice" data-testid="destination-stale">
          지난번에 쓴 페이지는 지금 목록에 없거나 읽을 수 없어 선택하지 않았습니다.
        </p>
      ) : null}
      {entries.length > 0 ? (
        <fieldset className="export-choice">
          <legend>내보낼 위치(상위 페이지)</legend>
          <ul className="export-destination-list" data-testid="destination-list">
            {entries.map((entry) => (
              <DestinationOption
                key={entry.destinationId}
                entry={entry}
                connection={connection}
                checked={selected?.destinationId === entry.destinationId}
                onSelect={setPicked}
              />
            ))}
          </ul>
        </fieldset>
      ) : null}
      <div className="export-actions">
        <button
          type="button"
          className="export-primary"
          disabled={!selected}
          onClick={() => selected && onChoose(selected)}
          data-testid="destination-next"
        >
          이 페이지로 미리보기
        </button>
      </div>
      {!selected && entries.length > 0 ? (
        <p className="export-note">내보낼 위치를 하나 고르면 미리보기를 만들 수 있습니다.</p>
      ) : null}
    </div>
  );
}
