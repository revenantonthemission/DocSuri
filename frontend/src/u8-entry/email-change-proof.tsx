/**
 * EmailChangeProof (L1-1, Step 91(l)): a signed-in person's email-change link. AccountAccess
 * completes an email change only for a signed-in session in the browser that asked, so the
 * complete app shows this panel above every view while its proof waits. The panel states
 * the binding on arrival and explains in full only after a refused 확인 (L1-54). The route
 * ends the session once the change is done; App then asks for a new sign-in.
 */
import React, { useEffect, useRef, useState } from 'react';
import { ApiError, type Transport } from '../api';
import { describeError, notice, Panel, StatusLine, type Notice } from '../ui';
import { EMAIL_CHANGE_REFUSED, type Proof } from './entry-panel';

export const EMAIL_CHANGE_BINDING_NOTE =
  '이 링크는 요청한 브라우저에서, 요청한 계정으로 로그인한 상태에서만 쓸 수 있습니다.';

export function EmailChangeProof({
  client,
  proof,
  onDone,
  onOpenAccount,
  onLeave,
}: {
  client: Transport;
  proof: Proof;
  /** The change is done and the route has ended the session. */
  onDone: () => void;
  /** Ask again from the 계정 view, dropping this proof. */
  onOpenAccount: () => void;
  /** Close the panel, dropping this proof. */
  onLeave: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const busyNow = useRef(false);
  // One count per refusal, so every 403 moves focus to the ask-again control, as
  // CompleteEntry's `askFocus` does (Step 91(l)).
  const [refusals, setRefusals] = useState(0);
  const refused = refusals > 0;
  const [message, setMessage] = useState<Notice | null>(null);
  const askAgain = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    if (refusals > 0) askAgain.current?.focus();
  }, [refusals]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (busyNow.current) return;
    busyNow.current = true;
    setBusy(true);
    setMessage(null);
    try {
      await client.post('/api/v2/c02/access-complete-email-change', {
        verification: proof.verification,
      });
      onDone();
    } catch (error) {
      if (error instanceof ApiError && error.status === 403) {
        setMessage(notice('alert', EMAIL_CHANGE_REFUSED));
        setRefusals((value) => value + 1);
      } else {
        setMessage(describeError(error));
      }
    } finally {
      busyNow.current = false;
      setBusy(false);
    }
  };

  return (
    // A heading here counts for no route change's landing: the panel sits above every view
    // while its proof waits (Step 91(f)). A focus request naming it still lands here.
    <div data-route-focus="skip">
      <Panel title="이메일 변경 확인" testId="email-change-proof">
        <StatusLine value={message} />
        <form className="stack" onSubmit={submit} data-testid="email-change-proof-form">
          <p>새 이메일 주소를 확인해 주세요</p>
          <p data-testid="proof-binding-note">{EMAIL_CHANGE_BINDING_NOTE}</p>
          <div className="row">
            <button type="submit" aria-disabled={busy} data-testid="proof-submit">
              확인
            </button>
            <button
              type="button"
              aria-disabled={busy}
              onClick={() => {
                if (!busyNow.current) onLeave();
              }}
              data-testid="proof-back"
            >
              닫기
            </button>
          </div>
        </form>
        {refused ? (
          <button
            ref={askAgain}
            type="button"
            aria-disabled={busy}
            onClick={() => {
              if (!busyNow.current) onOpenAccount();
            }}
            data-testid="proof-ask-again"
          >
            계정 화면에서 다시 요청
          </button>
        ) : null}
      </Panel>
    </div>
  );
}
