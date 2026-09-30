/** UnsubscribePage — 토큰 검증 후 수신 해지 상태 표시 */

'use client';

import { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { AssetViewer } from './AssetViewer';

type UnsubscribeState = 
  | { status: 'verifying' }
  | { status: 'success'; assetId: string }
  | { status: 'error'; code: 'INVALID' | 'EXPIRED' | 'REVOKED' | 'MALFORMED'; message: string };

export function UnsubscribePage() {
  const searchParams = useSearchParams();
  const token = searchParams.get('token');
  const [state, setState] = useState<UnsubscribeState>({ status: 'verifying' });

  useEffect(() => {
    if (!token) {
      setState({ status: 'error', code: 'MALFORMED', message: '토큰이 없습니다.' });
      return;
    }

    async function verify() {
      try {
        const res = await fetch(`/api/unsubscribe?token=${encodeURIComponent(token)}`);
        const data = await res.json();
        
        if (res.ok && data.status === 'success') {
          setState({ status: 'success', assetId: data.assetId });
        } else if (res.status === 400) {
          setState({ status: 'error', code: 'MALFORMED', message: '잘못된 토큰 형식입니다.' });
        } else if (res.status === 401) {
          setState({ status: 'error', code: 'EXPIRED', message: '토큰이 만료되었습니다.' });
        } else if (res.status === 410) {
          setState({ status: 'error', code: 'REVOKED', message: '이미 처리되었거나 철회되었습니다.' });
        } else {
          setState({ status: 'error', code: 'MALFORMED', message: '알 수 없는 오류입니다.' });
        }
      } catch {
        setState({ status: 'error', code: 'MALFORMED', message: '서버 오류가 발생했습니다.' });
      }
    }

    verify();
  }, [token]);

  if (state.status === 'verifying') {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-blue-600 border-t-transparent"></div>
      </div>
    );
  }

  if (state.status === 'success') {
    return (
      <div className="max-w-md mx-auto p-6 text-center">
        <div className="text-green-600 text-4xl mb-4">✓</div>
        <h1 className="text-2xl font-bold mb-2">수신 해지 완료</h1>
        <p className="text-gray-600 mb-4">이메일 수신이 성공적으로 해지되었습니다.</p>
        {state.assetId && (
          <AssetViewer assetId={state.assetId} token="" className="mt-4" />
        )}
      </div>
    );
  }

  const errorMessages = {
    MALFORMED: '잘못된 토큰입니다.',
    EXPIRED: '토큰이 만료되었습니다.',
    REVOKED: '이미 처리되었거나 철회되었습니다.',
  };

  return (
    <div className="max-w-md mx-auto p-6 text-center">
      <div className="text-red-600 text-4xl mb-4">✗</div>
      <h1 className="text-2xl font-bold mb-2">수신 해지 실패</h1>
      <p className="text-gray-600 mb-4">{errorMessages[state.code] || state.message}</p>
      <Link href="/" className="text-blue-600 hover:underline">홈으로 돌아가기</Link>
    </div>
  );
}

export default UnsubscribePage;
