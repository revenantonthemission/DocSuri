/** Shared status atoms for the export screens: a status badge that always pairs text
with an icon, the one polite live region each view owns, and plain refusal copy. */

import React, { useCallback, useState } from 'react';
import { ApiError, dispositionCopy } from '../api';
import type { StatusCopy } from './copy';

/** Text plus a decorative icon: the words carry the meaning, never the color. */
export function StatusBadge({ status, testId }: { status: StatusCopy; testId?: string }) {
  return (
    <span className="export-status" {...(testId ? { 'data-testid': testId } : {})}>
      <span className="export-status-icon" aria-hidden="true">
        {status.icon}
      </span>{' '}
      <span className="export-status-text">{status.text}</span>
    </span>
  );
}

export type Announcement = { id: number; text: string };
export type Announce = (text: string) => void;

let announcementId = 0;

/** One announcer per view: every status change goes through the same polite region. */
export function useAnnouncer(): [Announcement | null, Announce] {
  const [message, setMessage] = useState<Announcement | null>(null);
  const announce = useCallback((text: string) => {
    announcementId += 1;
    setMessage({ id: announcementId, text });
  }, []);
  return [message, announce];
}

/** The polite live region. It is always mounted so assistive technology hears changes. */
export function LiveRegion({ message, testId }: { message: Announcement | null; testId: string }) {
  return (
    <p className="export-live" role="status" aria-live="polite" data-testid={testId}>
      {message ? <span key={message.id}>{message.text}</span> : null}
    </p>
  );
}

/** Plain Korean for a refusal: the operation's own copy first, then the shared copy. */
export function refusalText(failure: unknown, table: Record<string, string> = {}): string {
  if (failure instanceof ApiError) {
    return table[failure.envelope.code] ?? dispositionCopy(failure.envelope.code);
  }
  return '문제가 발생했어요';
}

export const refusalCode = (failure: unknown): string | null =>
  failure instanceof ApiError ? failure.envelope.code : null;
