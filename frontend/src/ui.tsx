/** Shared presentation atoms: bounded status, safe error copy and focus helpers. */

import React, { createContext } from 'react';
import {
  ACCOUNT_MAIL_LIMIT_KEY,
  ACCOUNT_MAIL_UNAVAILABLE_KEY,
  ApiError,
  MAIL_HELD_TEXT,
  accountMailLimitText,
  dispositionCopy,
} from './api';

/** The complete shell's `announce`, or `null` where no shell provides it (L1-9): a view
 * that reads it announces through the shell's one live region instead of its own. */
export const ShellAnnounce = createContext<((text: string) => void) | null>(null);

export type Notice = { id: number; tone: 'polite' | 'alert'; text: string; requestId?: string };

let noticeId = 0;

export function notice(tone: Notice['tone'], text: string, requestId?: string): Notice {
  noticeId += 1;
  return { id: noticeId, tone, text, ...(requestId ? { requestId } : {}) };
}

export function describeError(error: unknown): Notice {
  if (error instanceof ApiError) {
    const { messageKey, requestId, retryAfterSeconds } = error.envelope;
    // Account mail at its limit says when email can be sent again (L1-10); while none can
    // be sent at all, one sentence with no time (L1-53). No earlier assembly gets either.
    if (messageKey === ACCOUNT_MAIL_LIMIT_KEY)
      return notice('alert', accountMailLimitText(retryAfterSeconds), requestId);
    if (messageKey === ACCOUNT_MAIL_UNAVAILABLE_KEY)
      return notice('alert', MAIL_HELD_TEXT, requestId);
    return notice('alert', dispositionCopy(error.envelope.code), requestId);
  }
  return notice('alert', '문제가 발생했어요');
}

export function StatusLine({ value }: { value: Notice | null }) {
  if (!value) return null;
  return (
    <p
      className={value.tone === 'alert' ? 'status status-alert' : 'status'}
      role={value.tone === 'alert' ? 'alert' : 'status'}
      data-testid="status-line"
    >
      {value.text}
      {value.requestId ? (
        <span className="status-id"> · 요청 {value.requestId.slice(0, 8)}</span>
      ) : null}
    </p>
  );
}

export function focusHeading(ref: React.RefObject<HTMLElement | null>) {
  window.requestAnimationFrame(() => ref.current?.focus());
}

export function Panel({
  title,
  titleRef,
  testId,
  children,
  as: Tag = 'section',
}: {
  title: string;
  titleRef?: React.RefObject<HTMLHeadingElement | null>;
  testId?: string;
  children: React.ReactNode;
  as?: 'section' | 'div';
}) {
  return (
    <Tag className="panel" {...(testId ? { 'data-testid': testId } : {})}>
      <h2 tabIndex={-1} ref={titleRef}>
        {title}
      </h2>
      {children}
    </Tag>
  );
}
