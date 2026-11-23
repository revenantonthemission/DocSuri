/**
 * MovedNotice (BR9.6): shown on the entry and sign-in screens after the switch. Once
 * dismissed it stays dismissed on that device; storage that refuses keeps it shown.
 */
import React, { useRef, useState } from 'react';
import styles from './shell.module.css';

export const DISMISSED_KEY = 'docsuri.moved-notice.dismissed';

function readDismissed(): boolean {
  try {
    return window.localStorage.getItem(DISMISSED_KEY) === '1';
  } catch {
    return false;
  }
}

function writeDismissed(): void {
  try {
    window.localStorage.setItem(DISMISSED_KEY, '1');
  } catch {
    // Without storage the notice is dismissed for this page only.
  }
}

/** Where focus goes when the notice's dismiss control leaves: the enclosing panel's heading,
 * else `#main`, never the page body (Step 91(g)). */
function landingFor(notice: HTMLElement | null): HTMLElement | null {
  const heading = notice?.closest('.panel')?.querySelector<HTMLElement>('h1, h2') ?? null;
  return heading ?? document.getElementById('main');
}

export function MovedNotice() {
  const [dismissed, setDismissed] = useState(readDismissed);
  const self = useRef<HTMLElement | null>(null);
  if (dismissed) return null;
  return (
    <aside
      ref={self}
      className={styles.notice}
      aria-label="새 버전 안내"
      data-testid="moved-notice"
    >
      <p>
        DocSuri가 새 버전으로 옮겨졌습니다. 한 번만 다시 로그인해 주세요. 저장한 논문과 설정은
        그대로 있습니다.
      </p>
      <details data-testid="moved-notice-details">
        <summary className={styles.summary} data-testid="moved-notice-more">
          자세히
        </summary>
        <p>
          계정, 연결한 Google·ORCID 로그인, 설정과 저장한 논문이 새 버전으로 옮겨졌습니다. 옮기지
          않은 기록은 보관용 사본에만 남아 있으며, 궁금한 점은 이용약관의 문의처로 알려 주세요.
        </p>
      </details>
      <button
        type="button"
        onClick={() => {
          writeDismissed();
          landingFor(self.current)?.focus();
          setDismissed(true);
        }}
        data-testid="moved-notice-dismiss"
      >
        닫기
      </button>
    </aside>
  );
}
