/** AssetViewer — authorized asset rendering through the same-origin BFF (SECURITY-08) */

'use client';

import { useEffect, useState } from 'react';
import { browserAssetSrc } from '@/lib/api/assetSrc';

// The viewer renders the authorized bytes served by
// `/bff/api/papers/{paperId}/assets/{assetId}` — the hop carries the session
// cookie server-side and the browser never learns a storage URL or a token.
// There is no presigned/token prop anymore: delivery authorization is the
// server's re-check on every request.

type AssetViewerProps = {
  paperId: string;
  assetId: string;
  className?: string;
  onError?: (error: Error) => void;
  onLoad?: () => void;
};

export function AssetViewer({ paperId, assetId, className = '', onError, onLoad }: AssetViewerProps) {
  const [state, setState] = useState<'loading' | 'ready' | 'failed'>('loading');
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    setState('loading');
  }, [paperId, assetId, attempt]);

  const src = browserAssetSrc(
    `/api/papers/${encodeURIComponent(paperId)}/assets/${encodeURIComponent(assetId)}`,
  );

  if (state === 'failed') {
    return (
      <div className={`relative aspect-video bg-gray-100 rounded-lg ${className}`}>
        <div className="absolute inset-0 flex items-center justify-center text-red-500">
          <div className="text-center p-4">
            <svg className="w-8 h-8 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <p className="text-sm">자산 로드 실패</p>
            <button
              type="button"
              onClick={() => setAttempt((n) => n + 1)}
              className="mt-2 text-xs text-blue-600 hover:underline"
            >
              다시 시도
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`relative aspect-video bg-gray-100 rounded-lg overflow-hidden ${className}`}>
      {state === 'loading' && (
        <div className="absolute inset-0 flex items-center justify-center text-gray-400" aria-hidden="true">
          <div className="animate-spin h-8 w-8 text-blue-600">
            <svg className="animate-spin h-8 w-8 text-blue-600" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          </div>
        </div>
      )}
      <img
        key={`${paperId}|${assetId}|${attempt}`}
        src={src}
        alt="자산 이미지"
        className={`w-full h-full object-contain ${state === 'loading' ? 'opacity-0' : ''}`}
        onError={() => {
          setState('failed');
          onError?.(new Error('Failed to load image'));
        }}
        onLoad={() => {
          setState('ready');
          onLoad?.();
        }}
      />
    </div>
  );
}

export default AssetViewer;
