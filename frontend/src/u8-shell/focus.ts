/**
 * Focus across routes (BR5.8): a destination's heading takes focus on each route change,
 * and a paper opened from a result returns to that result's position and focus.
 */
import { useEffect, useRef } from 'react';

/** App's request to move focus into a part of the page: `testId` names it; without one,
 * the frame answers as it answers a route change. */
export type FocusRequest = { id: number; testId?: string };

/** The route that earlier assemblies pass, which never changes. */
export const EARLIER_ASSEMBLY = 'earlier-assembly';

const CONTENT = '#main .workspace-content';
const SKIPPED = '[hidden], [data-route-focus="skip"]';

let claimed: (() => HTMLElement | null) | null = null;

/** Claim the focus target for the next route change (L1-25), such as the result a closed
 * paper returns to. The claim is used once, by the next route change. */
export function claimRouteFocus(target: () => HTMLElement | null): void {
  claimed = target;
}

function counts(element: Element): boolean {
  return element.closest(SKIPPED) === null;
}

function focusHeadingOf(element: HTMLElement): void {
  if (!element.hasAttribute('tabindex')) element.setAttribute('tabindex', '-1');
  element.focus();
}

function firstContentHeading(): HTMLElement | null {
  const headings = document.querySelectorAll<HTMLElement>(`${CONTENT} h1, ${CONTENT} h2`);
  return [...headings].find(counts) ?? null;
}

function focusMain(): void {
  document.getElementById('main')?.focus();
}

/** A route change's landing: the claimed target, else the destination's own focused
 * heading, else its first heading, else `#main`. */
function landRoute(): void {
  const claim = claimed;
  claimed = null;
  const target = claim?.() ?? null;
  if (target?.isConnected) {
    target.focus();
    return;
  }
  const active = document.activeElement;
  if (
    active instanceof HTMLElement &&
    /^H[12]$/.test(active.tagName) &&
    active.closest(CONTENT) !== null &&
    counts(active)
  )
    return;
  const heading = firstContentHeading();
  if (heading) focusHeadingOf(heading);
  else focusMain();
}

/** A request naming a part of the page focuses that part's first h1 or h2. */
function landRequest(testId: string): void {
  const part = document.querySelector<HTMLElement>(`[data-testid="${CSS.escape(testId)}"]`);
  const heading = part?.querySelector<HTMLElement>('h1, h2') ?? null;
  if (heading) focusHeadingOf(heading);
  else focusMain();
}

/** Focus after a route change or a focus request (L1-25), never on the first render. It
 * runs in App's own effect, after the effects of the views that just mounted, so its frame
 * comes after those views' own heading frames and decides last. */
export function useRouteFocus(route: string, request: FocusRequest | null): void {
  const previousRoute = useRef(route);
  const previousRequest = useRef(request?.id ?? null);
  useEffect(() => {
    const routeChanged = previousRoute.current !== route;
    const requestChanged = previousRequest.current !== (request?.id ?? null);
    // The first answer of the complete assembly is a baseline, not a route change.
    const fromBaseline = previousRoute.current === EARLIER_ASSEMBLY;
    previousRoute.current = route;
    previousRequest.current = request?.id ?? null;
    if (requestChanged && request) {
      const testId = request.testId;
      const frame = window.requestAnimationFrame(() =>
        testId === undefined ? landRoute() : landRequest(testId),
      );
      return () => window.cancelAnimationFrame(frame);
    }
    if (!routeChanged || fromBaseline || route === EARLIER_ASSEMBLY) return;
    const frame = window.requestAnimationFrame(landRoute);
    return () => window.cancelAnimationFrame(frame);
  }, [route, request]);
}

/** The control a return point names, for `claimRouteFocus`. */
export function returnTarget(point: ReturnPoint): () => HTMLElement | null {
  return () => (point.focus ? find(point.focus) : null);
}

/** Where a paper was opened from: the view, the scroll position and the focused control. */
export type ReturnPoint = { view: string; scrollY: number; focus: string | null };

function focusKey(element: Element | null): string | null {
  if (!(element instanceof HTMLElement) || element === document.body) return null;
  return element.dataset.testid ?? (element.id ? `#${element.id}` : null);
}

export function captureReturn(view: string): ReturnPoint {
  return { view, scrollY: window.scrollY, focus: focusKey(document.activeElement) };
}

function find(key: string): HTMLElement | null {
  if (key.startsWith('#')) return document.getElementById(key.slice(1));
  return document.querySelector<HTMLElement>(`[data-testid="${CSS.escape(key)}"]`);
}

/** Restore a return point once its view has rendered again. */
export function restoreReturn(point: ReturnPoint): void {
  window.requestAnimationFrame(() => {
    try {
      window.scrollTo(0, point.scrollY);
    } catch {
      // A document that cannot scroll keeps its place.
    }
    if (point.focus) find(point.focus)?.focus();
  });
}
