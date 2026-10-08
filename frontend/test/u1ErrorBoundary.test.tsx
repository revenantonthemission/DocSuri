import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { useState } from 'react';
import { ErrorBoundary } from '@/components/ErrorBoundary';

function Boom(): React.JSX.Element {
  throw new Error('render failed');
}

function Toggleable({ broken }: { broken: boolean }): React.JSX.Element {
  if (broken) throw new Error('temporary render failure');
  return <p>정상 렌더</p>;
}

function Harness(): React.JSX.Element {
  const [broken, setBroken] = useState(true);
  return (
    <ErrorBoundary
      onReset={() => setBroken(false)}
      fallback={({ reset }) => (
        <div>
          <p>대체 화면</p>
          <button type="button" onClick={reset}>
            복구
          </button>
        </div>
      )}
    >
      <Toggleable broken={broken} />
    </ErrorBoundary>
  );
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('ErrorBoundary', () => {
  it('renders children when nothing throws', () => {
    render(
      <ErrorBoundary>
        <p>내용</p>
      </ErrorBoundary>,
    );
    expect(screen.getByText('내용')).toBeInTheDocument();
  });

  it('contains a render crash and reports only a scrubbed bounded message', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
    const onError = vi.fn();

    render(
      <ErrorBoundary onError={onError}>
        <Boom />
      </ErrorBoundary>,
    );

    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(onError).toHaveBeenCalledTimes(1);
    const reported = onError.mock.calls[0]?.[0] as string;
    expect(reported).toBe('render failed');
    expect(reported.length).toBeLessThanOrEqual(200);
    expect(reported).not.toContain('at ');
    consoleError.mockRestore();
  });

  it('resets and re-renders the children through the fallback action', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(<Harness />);
    expect(screen.getByText('대체 화면')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '복구' }));
    expect(screen.getByText('정상 렌더')).toBeInTheDocument();
    consoleError.mockRestore();
  });

  it('calls the tracking-only reset hook (never a resubmit path)', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
    const onReset = vi.fn();

    render(
      <ErrorBoundary onReset={onReset} fallback={({ reset }) => (
        <button type="button" onClick={reset}>
          리셋
        </button>
      )}>
        <Boom />
      </ErrorBoundary>,
    );

    fireEvent.click(screen.getByRole('button', { name: '리셋' }));
    expect(onReset).toHaveBeenCalledTimes(1);
    consoleError.mockRestore();
  });
});
