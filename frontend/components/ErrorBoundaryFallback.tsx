'use client';

// ErrorBoundaryFallback — the stable-parent full-page fallback (US7.2/US7.3 slice).
//
// Used when containment must happen at the page level: it offers a safe return
// to the paper and a tracking-only reset. It never submits, never polls and
// never touches job state — recovery from a crashed surface is for the human.

export interface ErrorBoundaryFallbackProps {
  paperId?: string;
  onReset?: () => void;
}

export function ErrorBoundaryFallback({ paperId, onReset }: ErrorBoundaryFallbackProps) {
  const returnHref = paperId ? `/paper/${encodeURIComponent(paperId)}` : '/';

  return (
    <div role="alert" className="mx-auto max-w-lg p-6 text-center">
      <h2 className="text-lg font-medium">작업 화면을 표시하지 못했습니다</h2>
      <p className="mt-2 text-sm text-gray-600">
        입력은 제출되지 않았습니다. 논문으로 돌아가거나 다시 시도할 수 있습니다.
      </p>
      <div className="mt-4 flex items-center justify-center gap-4">
        <a href={returnHref} className="text-sm text-blue-600 underline">
          논문으로 돌아가기
        </a>
        {onReset && (
          <button type="button" onClick={onReset} className="text-sm underline">
            다시 시도
          </button>
        )}
      </div>
    </div>
  );
}

export default ErrorBoundaryFallback;
