/** The export view (route "내보내기"): the Notion connection and the export history.

Five view states: loading; error (both reads failed); partial (one read failed while
the other loaded, said plainly); empty (not connected and nothing exported, with the
connect action first); ready. The connection is read without knowing its id (A7); a
record still being checked reads as not connected. Reads go through SWR keyed by the
Transport's authority generation, so another owner's data can never be shown. */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import useSWR from 'swr';
import type { Transport } from '../api';
import {
  connectionKey,
  exportCall,
  HISTORY_PAGE_SIZE,
  readConnection,
  type Capability,
  type Connection,
} from './api';
import { CONNECTION_STATE_COPY, limitationText, NOT_CONNECTED } from './copy';
import { ConnectForm } from './connect-form';
import { DisconnectDialog } from './dialogs';
import { ExportHistory } from './history';
import { LiveRegion, refusalText, StatusBadge, useAnnouncer, type Announce } from './status';
import './export.css';

export type ViewState = 'loading' | 'empty' | 'error' | 'ready' | 'partial';

/** The derivation of the five view states from the two reads. */
export function exportViewState(input: {
  connectionLoading: boolean;
  historyLoading: boolean;
  connectionFailed: boolean;
  historyFailed: boolean;
  connected: boolean;
  historyCount: number;
}): ViewState {
  if (input.connectionLoading || input.historyLoading) return 'loading';
  if (input.connectionFailed && input.historyFailed) return 'error';
  if (input.connectionFailed || input.historyFailed) return 'partial';
  return !input.connected && input.historyCount === 0 ? 'empty' : 'ready';
}

function ConnectionStatus({ connection }: { connection: Connection | null }) {
  const status = connection ? CONNECTION_STATE_COPY[connection.state] : NOT_CONNECTED;
  return (
    <div className="export-connection-status" data-testid="connection-status">
      <StatusBadge status={status} testId="connection-state" />
      {connection?.state === 'connected' && connection.workspaceName ? (
        <p data-testid="connection-workspace">워크스페이스: {connection.workspaceName}</p>
      ) : null}
      {connection && connection.limitations.length > 0 ? (
        <ul className="export-limitations" data-testid="connection-limitations">
          {connection.limitations.map((key) => (
            <li key={key}>{limitationText(key)}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

export function ConnectionPanel({
  client,
  capability,
  connection,
  onChanged,
  announce,
}: {
  client: Transport;
  capability: Capability;
  connection: Connection | null;
  onChanged: (connection?: Connection | null) => void;
  announce: Announce;
}) {
  const [replacing, setReplacing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const state = connection?.state;
  const showForm = !connection || state === 'disconnected' || state === 'revoked' || replacing;
  const canDisconnect = state === 'connected' || state === 'unavailable';

  const disconnect = async () => {
    setBusy(true);
    try {
      const value = await exportCall(client, 'disconnect-notion', {});
      setConfirming(false);
      setReplacing(false);
      setNotice('Notion 연결을 해제했습니다');
      announce('Notion 연결을 해제했습니다');
      onChanged(value);
    } catch (failure) {
      const text = refusalText(failure);
      setNotice(text);
      announce(text);
      onChanged();
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="panel export-panel" aria-labelledby="u6-connection-heading">
      <h2 id="u6-connection-heading">Notion 연결</h2>
      <ConnectionStatus connection={connection} />
      {state === 'unavailable' ? (
        <p className="export-notice" data-testid="connection-unavailable-note">
          보호된 토큰을 지금 열 수 없어 내보내기가 기다리고 있습니다. 다시 연결하려면 먼저 연결을
          해제하세요.
        </p>
      ) : null}
      {notice ? (
        <p className="export-notice" data-testid="connection-notice">
          {notice}
        </p>
      ) : null}
      {showForm ? (
        <ConnectForm
          client={client}
          policy={capability.policy}
          connection={connection}
          announce={announce}
          onSaved={(value) => {
            setReplacing(false);
            setNotice(null);
            onChanged(value);
          }}
          onReload={(value) => {
            setReplacing(false);
            onChanged(value);
          }}
        />
      ) : null}
      <div className="export-actions">
        {state === 'connected' && !replacing ? (
          <button type="button" onClick={() => setReplacing(true)} data-testid="connection-replace">
            토큰 교체
          </button>
        ) : null}
        {replacing ? (
          <button
            type="button"
            onClick={() => setReplacing(false)}
            data-testid="connection-replace-cancel"
          >
            교체 취소
          </button>
        ) : null}
        {canDisconnect ? (
          <button
            type="button"
            className="export-danger"
            onClick={() => setConfirming(true)}
            disabled={busy}
            data-testid="connection-disconnect"
          >
            연결 해제
          </button>
        ) : null}
      </div>
      {replacing ? (
        <p className="export-note">
          토큰을 바꾸면 아직 시작하지 않은 승인은 무효가 됩니다. 결과가 불분명한 내보내기는 이
          토큰을 쓴 통합으로 계속 확인하고, 확인할 수 없으면 직접 확인을 기다립니다.
        </p>
      ) : null}
      {confirming ? (
        <DisconnectDialog
          busy={busy}
          onConfirm={() => void disconnect()}
          onClose={() => setConfirming(false)}
        />
      ) : null}
    </section>
  );
}

export function ExportView({
  client,
  capability,
  active = true,
}: {
  client: Transport;
  capability: Capability;
  active?: boolean;
}) {
  const heading = useRef<HTMLHeadingElement>(null);
  const [cursors, setCursors] = useState<(string | null)[]>([null]);
  const [message, announce] = useAnnouncer();
  const cursor = cursors[cursors.length - 1] ?? null;
  const connection = useSWR(active ? connectionKey(client) : null, () => readConnection(client), {
    revalidateOnFocus: false,
    shouldRetryOnError: false,
  });
  const history = useSWR(
    active ? ['u6-export-history', client, client.generation, cursor] : null,
    () =>
      exportCall(client, 'list-export-history', {
        limit: HISTORY_PAGE_SIZE,
        cursor,
      }),
    { revalidateOnFocus: false, shouldRetryOnError: false },
  );
  const connected = connection.data?.state === 'connected';
  const viewState = exportViewState({
    connectionLoading: connection.isLoading,
    historyLoading: history.isLoading,
    connectionFailed: !!connection.error,
    historyFailed: !!history.error,
    connected,
    historyCount: history.data?.entries.length ?? 0,
  });
  const { mutate: reloadConnection } = connection;
  const { mutate: reloadHistory } = history;
  const connectionChanged = useCallback(
    (value?: Connection | null) => {
      void (value === undefined ? reloadConnection() : reloadConnection(value, false));
      void reloadHistory();
    },
    [reloadConnection, reloadHistory],
  );

  useEffect(() => {
    if (active) heading.current?.focus();
  }, [active]);

  return (
    <section
      className="export-view"
      aria-labelledby="u6-export-heading"
      data-testid="export-view"
      data-view-state={viewState}
    >
      <h1 id="u6-export-heading" tabIndex={-1} ref={heading} data-testid="export-heading">
        내보내기
      </h1>
      <p className="export-intro">
        참신성 분석 결과를 미리 보고 직접 승인한 뒤에만 Notion 페이지로 내보냅니다.
      </p>
      <LiveRegion message={message} testId="export-live" />
      {viewState === 'loading' ? <p data-testid="export-loading">불러오는 중…</p> : null}
      {viewState === 'error' ? (
        <p className="export-notice" data-testid="export-error">
          연결과 기록을 불러오지 못했습니다. {refusalText(connection.error)}
        </p>
      ) : null}
      {viewState === 'partial' ? (
        <p className="export-notice" data-testid="export-partial">
          {connection.error
            ? 'Notion 연결 상태를 불러오지 못했습니다. 기록만 표시합니다.'
            : '내보내기 기록을 불러오지 못했습니다. 연결만 표시합니다.'}
        </p>
      ) : null}
      {viewState === 'empty' ? (
        <p data-testid="export-empty">
          아직 Notion에 연결하지 않았고 내보낸 기록도 없습니다. 먼저 Notion을 연결하세요.
        </p>
      ) : null}
      {viewState !== 'loading' && !connection.error ? (
        <ConnectionPanel
          client={client}
          capability={capability}
          connection={connection.data ?? null}
          onChanged={connectionChanged}
          announce={announce}
        />
      ) : null}
      {viewState !== 'loading' && viewState !== 'empty' && history.data ? (
        <section className="panel export-panel" aria-labelledby="u6-history-heading">
          <h2 id="u6-history-heading">내보내기 기록</h2>
          <ExportHistory
            client={client}
            page={history.data}
            hasPrevious={cursors.length > 1}
            onNext={(next) => setCursors((items) => [...items, next])}
            onPrevious={() => setCursors((items) => items.slice(0, -1))}
            onChanged={() => void reloadHistory()}
            announce={announce}
          />
        </section>
      ) : null}
    </section>
  );
}
