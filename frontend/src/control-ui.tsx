import React, { useEffect, useRef, useState } from 'react';
import { ApiError, Transport, retryTransient } from './api';
import { Notice, StatusLine, describeError, notice } from './ui';

/** A lost acknowledgement retains one transient operation, never an automatic replay. */
export function useOperation() {
  const [message, setMessage] = useState<Notice | null>(null);
  const [busy, setBusy] = useState(false);
  const [unknown, setUnknown] = useState(false);
  const mounted = useRef(true);
  const pending = useRef<{ key: string; work: (key: string) => Promise<void> } | null>(null);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      pending.current = null;
    };
  }, []);
  const execute = async (item: { key: string; work: (key: string) => Promise<void> }) => {
    if (busy) return;
    setBusy(true);
    setUnknown(false);
    setMessage(notice('polite', '처리 중이에요'));
    try {
      await item.work(item.key);
      if (mounted.current) {
        pending.current = null;
        setMessage(notice('polite', '요청 결과를 확인했어요'));
      }
    } catch (error) {
      if (mounted.current) {
        const uncertain = error instanceof ApiError && error.envelope.code === 'UNKNOWN_OUTCOME';
        setUnknown(uncertain);
        if (!uncertain) pending.current = null;
        setMessage(describeError(error));
      }
    } finally {
      if (mounted.current) setBusy(false);
    }
  };
  return {
    busy,
    unknown,
    message,
    setMessage,
    run: async (work: (key: string) => Promise<void>) => {
      if (pending.current || busy) return;
      const item = { key: crypto.randomUUID(), work };
      pending.current = item;
      await execute(item);
    },
    retry: async () => {
      if (pending.current) await execute(pending.current);
    },
  };
}
export function OperationStatus({ operation }: { operation: ReturnType<typeof useOperation> }) {
  return (
    <>
      <StatusLine value={operation.message} />
      {operation.unknown ? (
        <button type="button" disabled={operation.busy} onClick={() => void operation.retry()}>
          같은 요청의 결과 확인
        </button>
      ) : null}
    </>
  );
}
export function Field({
  label,
  id,
  value,
  onChange,
  secret = false,
  type,
  autoComplete,
}: {
  label: string;
  id: string;
  value: string;
  onChange: (value: string) => void;
  secret?: boolean;
  type?: string;
  autoComplete?: string;
}) {
  return (
    <label className="control-field" htmlFor={id}>
      {label}
      <input
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        type={secret ? 'password' : (type ?? 'text')}
        autoComplete={autoComplete}
        maxLength={secret ? 1024 : 4096}
      />
    </label>
  );
}
export function Disclosure({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <details className="control-group">
      <summary>{title}</summary>
      <div className="control-body">{children}</div>
    </details>
  );
}
export function useRead<T>(client: Transport, path: string, body: unknown = {}) {
  const [value, setValue] = useState<T | null>(null);
  const [error, setError] = useState<Notice | null>(null);
  const [loading, setLoading] = useState(true);
  const alive = useRef(true);
  const bodyText = JSON.stringify(body);
  const load = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Reads are idempotent, so a bounded retry absorbs transient dependency
      // or rate pressure; admission refusals (NOT_READY) surface for the
      // explicit manual recovery, and a replaced generation still reports stale.
      const result = await retryTransient(() => client.read<T>(path, JSON.parse(bodyText)));
      if (alive.current) setValue(result);
      if (alive.current) setLoading(false);
      return result;
    } catch (failure) {
      if (alive.current) {
        setError(describeError(failure));
        setLoading(false);
      }
      return undefined;
    }
  }, [client, path, bodyText]);
  useEffect(() => {
    alive.current = true;
    void load();
    return () => {
      alive.current = false;
    };
  }, [load]);
  return { value, error, loading, load, setValue };
}
