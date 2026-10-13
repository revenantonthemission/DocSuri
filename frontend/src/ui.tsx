/** Shared presentation atoms: bounded status, safe error copy and focus helpers. */

import React from 'react';
import { ApiError, dispositionCopy } from './api';

export type Notice = { id: number; tone: 'polite' | 'alert'; text: string; requestId?: string };

let noticeId = 0;

export function notice(tone: Notice['tone'], text: string, requestId?: string): Notice {
  noticeId += 1;
  return { id: noticeId, tone, text, ...(requestId ? { requestId } : {}) };
}

export function describeError(error: unknown): Notice {
  if (error instanceof ApiError) {
    return notice('alert', dispositionCopy(error.envelope.code), error.envelope.requestId);
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
