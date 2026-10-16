import React, { useEffect, useRef, useState } from 'react';
import { ApiError, type Transport } from '../api';
import { describeError, notice, StatusLine, type Notice } from '../ui';

/** An uncertain write keeps its original key and immutable submitted closure. */
export function useResearchAction(client: Transport) {
  const [message, setMessage] = useState<Notice | null>(null);
  const [busy, setBusy] = useState(false);
  const [unknown, setUnknown] = useState(false);
  const pending = useRef<{ key: string; work: (key: string) => Promise<void> } | null>(null);
  const active = useRef(true);
  const locked = useRef(false);
  useEffect(() => {
    active.current = true;
    return () => {
      active.current = false;
      pending.current = null;
    };
  }, []);
  const execute = async (request: NonNullable<typeof pending.current>) => {
    if (locked.current) return;
    const epoch = client.generation;
    locked.current = true;
    setBusy(true);
    setUnknown(false);
    setMessage(notice('polite', '처리 중이에요'));
    try {
      await request.work(request.key);
      if (active.current && client.generation === epoch) {
        pending.current = null;
        setMessage(notice('polite', '요청 결과를 확인했어요'));
      }
    } catch (error) {
      if (active.current && client.generation === epoch) {
        const uncertain =
          error instanceof ApiError &&
          ['UNKNOWN_OUTCOME', 'OUTCOME_UNKNOWN'].includes(error.envelope.code);
        setUnknown(uncertain);
        if (!uncertain) pending.current = null;
        setMessage(
          uncertain
            ? notice(
                'alert',
                '요청 결과를 아직 확인할 수 없어요. 입력은 유지되며 같은 요청만 다시 확인해요',
              )
            : describeError(error),
        );
      }
    } finally {
      locked.current = false;
      if (active.current && client.generation === epoch) setBusy(false);
    }
  };
  return {
    busy,
    unknown,
    message,
    run: (work: (key: string) => Promise<void>) => {
      if (pending.current || locked.current) return Promise.resolve();
      const request = { key: crypto.randomUUID(), work };
      pending.current = request;
      return execute(request);
    },
    retry: () => (pending.current ? execute(pending.current) : Promise.resolve()),
  };
}

export function ActionStatus({ action }: { action: ReturnType<typeof useResearchAction> }) {
  return (
    <>
      <StatusLine value={action.message} />
      {action.unknown ? (
        <button type="button" disabled={action.busy} onClick={() => void action.retry()}>
          같은 요청의 결과 확인
        </button>
      ) : null}
    </>
  );
}
