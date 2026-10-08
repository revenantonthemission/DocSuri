'use client';

import { useEffect, useRef, type ReactNode } from 'react';

// Shared dialog shell for the job submission surface. Same dialog semantics as
// the result modal: Escape/backdrop close, initial focus inside the panel and a
// labelled `role="dialog"`. Focus moves here deliberately — the shell is only
// mounted on an explicit user action.

export interface JobDialogProps {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
}

export function JobDialog({ open, title, onClose, children }: JobDialogProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKeyDown);
    panelRef.current?.focus();
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        className="w-full max-w-md rounded-lg bg-white p-4 shadow-lg outline-none"
      >
        <h2 className="mb-3 text-lg font-medium">{title}</h2>
        {children}
      </div>
    </div>
  );
}

export default JobDialog;
