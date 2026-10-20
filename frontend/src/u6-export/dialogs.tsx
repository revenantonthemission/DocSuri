/** Export dialogs over one accessible shell, following U5's ConfirmationDialog:
focus moves into the dialog, Tab is trapped, Escape closes it, and focus returns to
the control that opened it. */

import React, { useEffect, useId, useRef, useState } from 'react';
import { isNotionPageLink, type HistoryEntry, type SettleDisposition } from './api';
import { SETTLE_ASSUMPTION_COPY } from './copy';

const FOCUSABLE =
  'button:not([disabled]), [href], input:not([disabled]), select, textarea, [tabindex]:not([tabindex="-1"])';

function isRadio(element: Element | null): element is HTMLInputElement {
  return element instanceof HTMLInputElement && element.type === 'radio' && element.name !== '';
}

/** The dialog's tab stops in order. A radio group is one stop: its checked radio, or its
first radio while none is checked. */
function tabStops(container: HTMLElement): HTMLElement[] {
  const items = Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE));
  const groups = new Set<string>();
  return items.flatMap((item) => {
    if (!isRadio(item)) return [item];
    if (groups.has(item.name)) return [];
    groups.add(item.name);
    const checked = items.find(
      (other) => isRadio(other) && other.name === item.name && other.checked,
    );
    return [checked ?? item];
  });
}

/** Whether the focused element sits on this stop (any radio of the stop's group does). */
function onStop(stop: HTMLElement, active: Element | null): boolean {
  return stop === active || (isRadio(stop) && isRadio(active) && stop.name === active.name);
}

export function DialogShell({
  title,
  testId,
  onClose,
  children,
}: {
  title: string;
  testId: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  const container = useRef<HTMLDivElement>(null);
  const restore = useRef<Element | null>(null);
  const titleId = useId();
  useEffect(() => {
    const dialog = container.current;
    restore.current = document.activeElement;
    let inside: HTMLElement | null = null;
    // aria-modal: focus that lands outside by any route (taken by the page, dropped with a
    // replaced node) goes back to where it was inside, or to the first stop.
    const contain = (event: FocusEvent) => {
      const target = event.target;
      if (!dialog || !(target instanceof Node)) return;
      if (dialog.contains(target)) {
        if (target instanceof HTMLElement) inside = target;
        return;
      }
      const last = inside;
      (last && last.isConnected && last.matches(FOCUSABLE) ? last : tabStops(dialog)[0])?.focus();
    };
    document.addEventListener('focusin', contain);
    if (dialog) tabStops(dialog)[0]?.focus();
    return () => {
      document.removeEventListener('focusin', contain);
      if (restore.current instanceof HTMLElement) restore.current.focus();
    };
  }, []);
  const onKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'Escape') {
      event.stopPropagation();
      onClose();
      return;
    }
    if (event.key !== 'Tab' || !container.current) return;
    // Every Tab moves between the dialog's own stops, wrapping both ways, rather than
    // leaving the order to the browser: engines differ inside an unchecked radio group.
    const stops = tabStops(container.current);
    if (stops.length === 0) return;
    event.preventDefault();
    const current = stops.findIndex((stop) => onStop(stop, document.activeElement));
    const step = event.shiftKey ? stops.length - 1 : 1;
    const next =
      current === -1 ? (event.shiftKey ? stops.length - 1 : 0) : (current + step) % stops.length;
    stops[next]!.focus();
  };
  return (
    <div className="export-dialog-backdrop" onKeyDown={onKeyDown}>
      <div
        className="export-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        ref={container}
        data-testid={testId}
      >
        <h2 id={titleId}>{title}</h2>
        {children}
      </div>
    </div>
  );
}

/** BR1.4, BR6.4: the consequences are named before the token is deleted. */
export function DisconnectDialog({
  busy,
  onConfirm,
  onClose,
}: {
  busy: boolean;
  onConfirm: () => void;
  onClose: () => void;
}) {
  return (
    <DialogShell title="Notion 연결 해제" testId="disconnect-dialog" onClose={onClose}>
      <p>연결을 해제하면 저장된 토큰을 삭제합니다.</p>
      <ul className="export-dialog-list">
        <li>아직 시작하지 않은 승인은 무효가 됩니다.</li>
        <li>이미 내보낸 페이지는 Notion에 그대로 남습니다.</li>
        <li>결과가 불분명한 내보내기는 이후 직접 확인으로만 정리할 수 있습니다.</li>
      </ul>
      <div className="export-dialog-actions">
        <button type="button" onClick={onClose} disabled={busy} data-testid="disconnect-keep">
          연결 유지
        </button>
        <button
          type="button"
          className="export-danger"
          onClick={onConfirm}
          disabled={busy}
          data-testid="disconnect-confirm"
        >
          연결 해제
        </button>
      </div>
    </DialogShell>
  );
}

export type SettleChoice = { disposition: SettleDisposition; remoteUrl?: string };

/** BR4.5: recorded only with the assumption visible; the link must be a Notion page link. */
export function SettleDialog({
  entry,
  busy,
  onSubmit,
  onClose,
}: {
  entry: HistoryEntry;
  busy: boolean;
  onSubmit: (choice: SettleChoice) => void;
  onClose: () => void;
}) {
  const [choice, setChoice] = useState<SettleDisposition | null>(null);
  const [pageLink, setPageLink] = useState('');
  const [linkError, setLinkError] = useState<string | null>(null);
  const linkId = useId();
  const errorId = useId();
  const assumptionId = useId();
  const submit = () => {
    if (!choice) return;
    const link = pageLink.trim();
    if (choice === 'delivered' && link && !isNotionPageLink(link)) {
      setLinkError(
        'Notion 페이지 링크를 입력해 주세요. 예: https://www.notion.so/페이지-이름-로-끝나는-32자리-식별자',
      );
      return;
    }
    setLinkError(null);
    onSubmit({
      disposition: choice,
      ...(choice === 'delivered' && link ? { remoteUrl: link } : {}),
    });
  };
  return (
    <DialogShell title="Notion에서 직접 확인" testId="settle-dialog" onClose={onClose}>
      <p>
        <strong>{entry.destinationTitle}</strong> 페이지 아래에 <strong>{entry.sourceTitle}</strong>{' '}
        페이지가 있는지 Notion에서 확인해 주세요.
      </p>
      <fieldset className="export-choice" aria-describedby={choice ? assumptionId : undefined}>
        <legend>페이지가 있나요?</legend>
        <label className="export-radio">
          <input
            type="radio"
            name="settle-choice"
            checked={choice === 'delivered'}
            onChange={() => setChoice('delivered')}
            data-testid="settle-delivered"
          />
          있습니다
        </label>
        <label className="export-radio">
          <input
            type="radio"
            name="settle-choice"
            checked={choice === 'not-delivered'}
            onChange={() => setChoice('not-delivered')}
            data-testid="settle-not-delivered"
          />
          없습니다
        </label>
      </fieldset>
      {choice ? (
        <p id={assumptionId} className="export-assumption" data-testid="settle-assumption">
          {SETTLE_ASSUMPTION_COPY[choice]}
        </p>
      ) : null}
      {choice === 'delivered' ? (
        <div className="export-field">
          <label htmlFor={linkId}>Notion 페이지 링크 (선택)</label>
          <input
            id={linkId}
            type="url"
            inputMode="url"
            autoComplete="off"
            value={pageLink}
            onChange={(event) => setPageLink(event.target.value)}
            aria-invalid={linkError ? true : undefined}
            aria-describedby={linkError ? errorId : undefined}
            data-testid="settle-link"
          />
          {linkError ? (
            <p id={errorId} className="export-field-error" data-testid="settle-link-error">
              {linkError}
            </p>
          ) : null}
        </div>
      ) : null}
      <div className="export-dialog-actions">
        <button type="button" onClick={onClose} disabled={busy} data-testid="settle-cancel">
          닫기
        </button>
        <button
          type="button"
          onClick={submit}
          disabled={busy || !choice}
          data-testid="settle-confirm"
        >
          기록하기
        </button>
      </div>
    </DialogShell>
  );
}
