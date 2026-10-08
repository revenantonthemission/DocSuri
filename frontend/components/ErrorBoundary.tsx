'use client';

import { Component, type ReactNode } from 'react';

// ErrorBoundary — render containment for an SSE-consuming job surface (US7.1).
//
// Catches render errors below it, reports a SCRUBBED bounded message (never a
// stack, never payload content) through `onError`, and offers a tracking-only
// reset. Async/network failures are owned by the components that made the call;
// this boundary handles render crashes only.

export interface ErrorBoundaryProps {
  children: ReactNode;
  /** Custom fallback renderer; receives the reset action. */
  fallback?: (args: { reset: () => void }) => ReactNode;
  /** Scrubbed reporting seam (diagnostics are wired separately). */
  onError?: (message: string) => void;
  /** Tracking-only reset hook — must never re-submit work. */
  onReset?: () => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

const MAX_REPORTED_MESSAGE = 200;

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error): void {
    const raw = typeof error.message === 'string' ? error.message : 'render error';
    this.props.onError?.(raw.slice(0, MAX_REPORTED_MESSAGE));
  }

  private reset = (): void => {
    this.props.onReset?.();
    this.setState({ hasError: false });
  };

  render(): ReactNode {
    if (!this.state.hasError) return this.props.children;
    if (this.props.fallback) return this.props.fallback({ reset: this.reset });
    return (
      <div
        role="alert"
        className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700"
      >
        <p>작업 화면을 표시하지 못했습니다. 입력은 제출되지 않았습니다.</p>
        <button type="button" onClick={this.reset} className="mt-1 underline">
          다시 시도
        </button>
      </div>
    );
  }
}

export default ErrorBoundary;
