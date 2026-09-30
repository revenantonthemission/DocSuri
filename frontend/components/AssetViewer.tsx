/** AssetViewer — presigned URL로 이미지/자산 렌더링 */

'use client';

import { useEffect, useState } from 'react';
import { getAssetUrl } from '@/lib/api/contentJobApi';

type AssetViewerProps = {
  assetId: string;
  token: string;
  className?: string;
  onError?: (error: Error) => void;
  onLoad?: () => void;
};

export function AssetViewer({ assetId, token, className = '', onError, onLoad }: AssetViewerProps) {
  const [src, setSrc] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadAsset() {
      try {
        setLoading(true);
        const url = await getAssetUrl(assetId, token);
        if (!cancelled) {
          setSrc(url);
          setLoading(false);
        }
      } catch (err) {
        if (!cancelled) {
          const error = err instanceof Error ? err : new Error(String(err));
          setError(error);
          setLoading(false);
        }
      }
    }

    loadAsset();
    return () => { cancelled = true; };
  }, [assetId, token]);

  if (loading) {
    return (
      <div className={`relative aspect-video bg-gray-100 rounded-lg ${className}`}>
        <div className="absolute inset-0 flex items-center justify-center text-gray-400">
          <div className="animate-spin h-8 w-8 text-blue-600">
            <svg className="animate-spin h-8 w-8 text-blue-600" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`relative aspect-video bg-gray-100 rounded-lg ${className}`}>
        <div className="absolute inset-0 flex items-center justify-center text-red-500">
          <div className="text-center p-4">
            <svg className="w-8 h-8 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <p className="text-sm">자산 로드 실패</p>
            <button
              onClick={() => window.location.reload()}
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
      <img
        src={src!}
        alt="Asset"
        className="w-full h-full object-contain"
        onError={() => { onError?.(new Error('Failed to load image')); }}
        onLoad={() => { onLoad?.(); }}
      />
    </div>
  );
}

export default AssetViewer;
