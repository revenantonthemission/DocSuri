/** The Notion connect form (Workflow 1; replace in Workflow 2).

The token lives only in this component's state: it never reaches browser storage,
a URL, a log or any other state, and the field is cleared the moment a submit
starts, whatever the outcome (BR1.1). The field is a plain text field, so password
managers never offer to keep it. A refusal names the problem without echoing the
value. A configure CONFLICT is told apart by re-reading the connection (R-03). */

import React, { useId, useRef, useState } from 'react';
import { ApiError, type Transport } from '../api';
import { exportCall, readConnection, tokenProblem, type Connection, type Policy } from './api';
import {
  CONFLICT_CHANGED,
  CONFLICT_STILL_CHECKING,
  CONFLICT_UNAVAILABLE,
  CONNECT_HELP,
  CONNECT_REFUSAL_COPY,
  TOKEN_PROBLEM_COPY,
} from './copy';
import { refusalText, type Announce } from './status';

export type SubmitState = 'idle' | 'checking' | 'saved' | 'failed';

/** R-03: which CONFLICT this was, from the connection as it is now. */
function conflictMessage(expected: Connection | null, current: Connection | null): string {
  if (current?.state === 'unavailable') return CONFLICT_UNAVAILABLE;
  const changed =
    current !== null &&
    (expected === null ||
      current.connectionId !== expected.connectionId ||
      Number(current.revision) > Number(expected.revision));
  return changed ? CONFLICT_CHANGED : CONFLICT_STILL_CHECKING;
}

export function ConnectForm({
  client,
  policy,
  connection,
  onSaved,
  onReload,
  announce,
  submitLabel,
}: {
  client: Transport;
  policy: Policy;
  /** The connection the form replaces, or null for a first connect. */
  connection: Connection | null;
  onSaved: (connection: Connection) => void;
  /** The connection changed elsewhere: hand the reloaded state to the parent. */
  onReload: (connection: Connection | null) => void;
  announce: Announce;
  submitLabel?: string;
}) {
  const [token, setToken] = useState('');
  const [submitState, setSubmitState] = useState<SubmitState>('idle');
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [refusal, setRefusal] = useState<string | null>(null);
  const running = useRef(false);
  const fieldId = useId();
  const helpId = useId();
  const errorId = useId();
  // Every visible record is changed at its own revision (BR1.3); only a first
  // connect, with no visible record, sends none.
  const expectedRevision = connection ? connection.revision : null;
  const replacing = connection?.state === 'connected';

  const settleConflict = async () => {
    let current: Connection | null = null;
    try {
      current = await readConnection(client);
    } catch (failure) {
      return refusalText(failure);
    }
    const message = conflictMessage(connection, current);
    if (message !== CONFLICT_STILL_CHECKING) onReload(current);
    return message;
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (running.current) return;
    // The value leaves the field before anything else happens (BR1.1).
    const value = token;
    setToken('');
    const problem = tokenProblem(value);
    if (problem) {
      setFieldError(TOKEN_PROBLEM_COPY[problem]);
      setSubmitState('failed');
      return;
    }
    running.current = true;
    setFieldError(null);
    setRefusal(null);
    setSubmitState('checking');
    announce('Notion에서 토큰을 확인하고 있습니다');
    try {
      const saved = await exportCall(client, 'configure-notion-connection', {
        token: value.trim(),
        expectedRevision,
        credentialPolicy: policy,
      });
      setSubmitState('saved');
      announce(
        saved.workspaceName
          ? `Notion 워크스페이스 ‘${saved.workspaceName}’에 연결했습니다`
          : 'Notion에 연결했습니다',
      );
      onSaved(saved);
    } catch (failure) {
      const message =
        failure instanceof ApiError && failure.envelope.code === 'CONFLICT'
          ? await settleConflict()
          : refusalText(failure, CONNECT_REFUSAL_COPY);
      setSubmitState('failed');
      setRefusal(message);
      announce(message);
    } finally {
      running.current = false;
    }
  };

  const checking = submitState === 'checking';
  return (
    <form className="export-connect" onSubmit={submit} data-testid="connect-form" noValidate>
      <div className="export-help" id={helpId} data-testid="connect-help">
        <p>{CONNECT_HELP.intro}</p>
        <ul>
          {CONNECT_HELP.requested.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
        <p>{CONNECT_HELP.rest}</p>
      </div>
      <div className="export-field">
        <label htmlFor={fieldId}>Notion 통합 토큰</label>
        <input
          id={fieldId}
          type="text"
          name="notion-integration-token"
          value={token}
          onChange={(event) => setToken(event.target.value)}
          autoComplete="off"
          autoCorrect="off"
          autoCapitalize="off"
          spellCheck={false}
          disabled={checking}
          aria-invalid={fieldError ? true : undefined}
          aria-describedby={fieldError ? `${helpId} ${errorId}` : helpId}
          data-testid="connect-token"
        />
        {fieldError ? (
          <p id={errorId} className="export-field-error" data-testid="connect-field-error">
            {fieldError}
          </p>
        ) : null}
      </div>
      <button type="submit" disabled={checking} data-testid="connect-submit">
        {checking ? '확인 중' : (submitLabel ?? (replacing ? '토큰 교체' : '연결'))}
      </button>
      {checking ? (
        <p className="export-note" data-testid="connect-checking">
          확인 중 · Notion에서 토큰을 확인하고 있습니다
        </p>
      ) : null}
      {refusal ? (
        <p className="export-notice" data-testid="connect-refusal">
          {refusal}
        </p>
      ) : null}
    </form>
  );
}
