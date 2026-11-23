/**
 * The shell's one polite live region (BR5.8, NFR9.5). Components announce through
 * `useAnnounce`, and earlier units' views through ui.tsx's `ShellAnnounce` (L1-9). An owner
 * change drops the message in that same render, so a message never outlives its owner and
 * never returns with it (L1-26).
 */
import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { ShellAnnounce } from '../ui';

type Announcer = { announce: (text: string) => void; clear: () => void };

const AnnouncerContext = createContext<Announcer>({
  announce: () => undefined,
  clear: () => undefined,
});

export function AnnouncerProvider({
  owner = '',
  children,
}: {
  /** The session's owner; a change empties the region. */
  owner?: string;
  children: React.ReactNode;
}) {
  const [message, setMessage] = useState<{ id: number; text: string } | null>(null);
  const [shownOwner, setShownOwner] = useState(owner);
  if (shownOwner !== owner) {
    // Adjusting state while rendering: React renders again before committing, so the
    // prior owner's message is never shown for the new one.
    setShownOwner(owner);
    setMessage(null);
  }
  const announce = useCallback((text: string) => {
    setMessage((current) => ({ id: (current?.id ?? 0) + 1, text }));
  }, []);
  const clear = useCallback(() => setMessage(null), []);
  const value = useMemo(() => ({ announce, clear }), [announce, clear]);
  const visible = shownOwner === owner ? message : null;
  return (
    <AnnouncerContext.Provider value={value}>
      <ShellAnnounce.Provider value={announce}>{children}</ShellAnnounce.Provider>
      <div className="visually-hidden" aria-live="polite" role="status" data-testid="announcer">
        {visible ? <span key={visible.id}>{visible.text}</span> : null}
      </div>
    </AnnouncerContext.Provider>
  );
}

export function useAnnounce(): Announcer {
  return useContext(AnnouncerContext);
}
