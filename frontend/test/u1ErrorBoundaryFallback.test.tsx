import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { ErrorBoundaryFallback } from '@/components/ErrorBoundaryFallback';

describe('ErrorBoundaryFallback', () => {
  it('announces the failure and offers a safe return to the paper', () => {
    render(<ErrorBoundaryFallback paperId="paper-9" />);

    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText(/입력은 제출되지 않았습니다/)).toBeInTheDocument();
    const link = screen.getByRole('link', { name: '논문으로 돌아가기' });
    expect(link).toHaveAttribute('href', '/paper/paper-9');
  });

  it('falls back to the home route when no paper context exists', () => {
    render(<ErrorBoundaryFallback />);
    expect(screen.getByRole('link', { name: '논문으로 돌아가기' })).toHaveAttribute('href', '/');
    expect(screen.queryByRole('button', { name: '다시 시도' })).not.toBeInTheDocument();
  });

  it('resets through the tracking-only action without submitting anything', () => {
    const onReset = vi.fn();
    render(<ErrorBoundaryFallback paperId="paper-9" onReset={onReset} />);

    fireEvent.click(screen.getByRole('button', { name: '다시 시도' }));
    expect(onReset).toHaveBeenCalledTimes(1);
  });
});
