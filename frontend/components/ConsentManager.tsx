/** ConsentManager — 동의 부여/철회 관리 UI */

'use client';

import { useState, useEffect } from 'react';

type ConsentScope = 'email_digest' | 'follow_notify' | 'marketing' | 'personalization';

type ConsentUI = {
  scope: ConsentScope;
  label: string;
  description: string;
  status: 'GRANTED' | 'REVOKED' | 'EXPIRED';
  grantedAt?: string;
  revokedAt?: string;
  expiresAt?: string;
};

const SCOPE_LABELS: Record<ConsentScope, { label: string; description: string }> = {
  email_digest: { label: '이메일 다이제스트', description: '주간 논문 요약 이메일 수신' },
  follow_notify: { label: '팔로우 알림', description: '관심 논문/작가 업데이트 알림' },
  marketing: { label: '마케팅 알림', description: '신기능/이벤트 홍보 이메일' },
  personalization: { label: '개인화 추천', description: '관심사 기반 논문 추천' },
};

type ConsentDTO = {
  scope: string;
  status: ConsentUI['status'];
  granted_at?: string;
  revoked_at?: string;
  expires_at?: string;
};

function isConsentScope(value: string): value is ConsentScope {
  return Object.prototype.hasOwnProperty.call(SCOPE_LABELS, value);
}

export function ConsentManager() {
  const [consents, setConsents] = useState<ConsentUI[]>([]);
  const [loading, setLoading] = useState(true);
  const [revoking, setRevoking] = useState<string | null>(null);

  useEffect(() => {
    loadConsents();
  }, []);

  async function loadConsents() {
    try {
      const res = await fetch('/api/consents');
      if (!res.ok) throw new Error(`consents request failed: ${res.status}`);
      const data = (await res.json()) as ConsentDTO[];
      setConsents(
        data
          .filter((c): c is ConsentDTO & { scope: ConsentScope } => isConsentScope(c.scope))
          .map(c => ({
            scope: c.scope,
            label: SCOPE_LABELS[c.scope].label,
            description: SCOPE_LABELS[c.scope].description,
            status: c.status,
            grantedAt: c.granted_at,
            revokedAt: c.revoked_at,
            expiresAt: c.expires_at,
          })),
      );
    } catch (err) {
      console.error('Failed to load consents:', err);
    } finally {
      setLoading(false);
    }
  }

  async function toggleConsent(scope: ConsentScope, currentlyGranted: boolean) {
    if (currentlyGranted) {
      // 철회
      if (!confirm(`정말로 ${SCOPE_LABELS[scope].label} 동의를 철회하시겠습니까?`)) return;
      setRevoking(scope);
      try {
        await fetch('/api/consents/revoke', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ scope }),
        });
        setConsents(c => c.map(c => c.scope === scope ? { ...c, status: 'REVOKED' } : c));
      } catch {
        alert('철회에 실패했습니다.');
      } finally {
        setRevoking(null);
      }
    } else {
      // 동의
      try {
        await fetch('/api/consents/grant', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ scope }),
        });
        setConsents(c => c.map(c => c.scope === scope ? { ...c, status: 'GRANTED' } : c));
      } catch {
        alert('동의에 실패했습니다.');
      }
    }
  }

  if (loading) {
    return <div className="flex items-center justify-center h-64">로딩 중...</div>;
  }

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold mb-4">동의 관리</h2>
      <div className="space-y-3">
        {consents.map(consent => (
          <div key={consent.scope} className="p-4 border rounded-lg bg-white">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-medium">{consent.label}</h3>
                <p className="text-sm text-gray-500">{consent.description}</p>
              </div>
              <div className="flex items-center gap-3">
                <span className={`px-2 py-1 text-xs rounded-full ${
                  consent.status === 'GRANTED' ? 'bg-green-100 text-green-700' :
                  consent.status === 'REVOKED' ? 'bg-red-100 text-red-700' :
                  'bg-yellow-100 text-yellow-700'
                }`}>
                  {consent.status === 'GRANTED' ? '동의됨' : 
                   consent.status === 'REVOKED' ? '철회됨' : '만료됨'}
                </span>
                {consent.status === 'GRANTED' && (
                  <button
                    onClick={() => toggleConsent(consent.scope, true)}
                    disabled={revoking === consent.scope}
                    className="px-3 py-1 text-sm bg-red-100 text-red-700 rounded hover:bg-red-200 disabled:opacity-50"
                  >
                    철회
                  </button>
                )}
                {consent.status !== 'GRANTED' && (
                  <button
                    onClick={() => toggleConsent(consent.scope, false)}
                    disabled={revoking === consent.scope}
                    className="px-3 py-1 text-sm bg-blue-100 text-blue-700 rounded hover:bg-blue-200 disabled:opacity-50"
                  >
                    {consent.status === 'REVOKED' ? '재동의' : '동의'}
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default ConsentManager;
