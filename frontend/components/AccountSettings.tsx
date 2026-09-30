'use client';

import { useState } from 'react';
import { ConsentManager } from './ConsentManager';

export function AccountSettings() {
  const [activeTab, setActiveTab] = useState<'security' | 'consents' | 'social' | 'deletion'>('security');
  const [passwordResetSent, setPasswordResetSent] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState('');

  const handlePasswordReset = async (email: string) => {
    try {
      const res = await fetch('/api/account/password-reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });
      if (res.ok) {
        setPasswordResetSent(true);
      } else {
        alert('이메일 발송에 실패했습니다.');
      }
    } catch {
      alert('오류가 발생했습니다.');
    }
  };

  const handleSocialLogin = (provider: 'google' | 'orcid') => {
    window.location.href = `/auth/${provider}`;
  };

  const handleDeleteAccount = async () => {
    if (deleteConfirm !== 'DELETE') {
      alert('정확히 "DELETE"를 입력해주세요.');
      return;
    }
    if (!confirm('정말로 계정을 삭제하시겠습니까? 이 작업은 30일 유예 기간 후 영구적으로 파기되며, 복구할 수 없습니다.')) return;

    setDeleting(true);
    try {
      const res = await fetch('/api/account/delete', {
        method: 'DELETE',
      });
      if (res.ok) {
        alert('계정 삭제가 요청되었습니다. 30일 유예 기간 후 영구 파기됩니다.');
        window.location.href = '/';
      } else {
        alert('삭제 요청에 실패했습니다.');
      }
    } catch {
      alert('오류가 발생했습니다.');
    } finally {
      setDeleting(false);
    }
  };

  const tabs = ['security', 'consents', 'social', 'deletion'] as const;
  const tabLabels = {
    security: '보안',
    consents: '동의 관리',
    social: '소셜 로그인',
    deletion: '계정 삭제',
  };

  return (
    <div className="max-w-2xl mx-auto space-y-8">
      {/* Tab Navigation */}
      <div className="border-b border-gray-200">
        <nav className="flex space-x-8" aria-label="Account settings tabs">
          {tabs.map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {tabLabels[tab]}
            </button>
          ))}
        </nav>
      </div>

      <div className="py-6 space-y-6">
        {activeTab === 'security' && (
          <div className="space-y-6">
            <div>
              <h3 className="text-lg font-medium mb-4">비밀번호 재설정</h3>
              <p className="text-gray-600 mb-4">비밀번호를 잊으셨나요? 이메일로 재설정 링크를 발송해드립니다.</p>
              <div className="flex gap-3">
                <input
                  type="email"
                  placeholder="이메일 주소"
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  onKeyDown={e => e.key === 'Enter' && handlePasswordReset(e.currentTarget.value)}
                />
                <button
                  onClick={() =>
                    handlePasswordReset(
                      document.querySelector<HTMLInputElement>('input[type=email]')?.value ?? '',
                    )
                  }
                  disabled={passwordResetSent}
                  className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                >
                  {passwordResetSent ? '발송됨' : '재설정 링크 발송'}
                </button>
              </div>
              {passwordResetSent && (
                <p className="text-green-600 text-sm mt-2">재설정 링크가 발송되었습니다. 이메일을 확인해주세요.</p>
              )}
            </div>

            <div className="pt-6 border-t border-gray-200">
              <h3 className="text-lg font-medium mb-4">현재 비밀번호 변경</h3>
              <p className="text-gray-600 mb-4">현재 비밀번호를 알고 있다면 바로 변경할 수 있습니다.</p>
              <form className="space-y-3 max-w-md" onSubmit={e => e.preventDefault()}>
                <input type="password" placeholder="현재 비밀번호" className="w-full px-3 py-2 border border-gray-300 rounded" />
                <input type="password" placeholder="새 비밀번호" className="w-full px-3 py-2 border border-gray-300 rounded" />
                <input type="password" placeholder="새 비밀번호 확인" className="w-full px-3 py-2 border border-gray-300 rounded" />
                <button type="submit" className="w-full px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">
                  비밀번호 변경
                </button>
              </form>
            </div>
          </div>
        )}

        {activeTab === 'consents' && (
          <div className="space-y-6">
            <ConsentManager />
          </div>
        )}

        {activeTab === 'social' && (
          <div className="space-y-4">
            <h3 className="text-lg font-medium mb-4">소셜 로그인 연동</h3>
            <p className="text-gray-600 mb-4">외부 계정으로 간편하게 로그인하세요.</p>
              <button
                onClick={() => handleSocialLogin('google')}
                className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 rounded hover:bg-gray-50"
              >
                <svg className="w-5 h-5" viewBox="0 0 24 24"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.7c-.98.66-2.23 1.06-3.57 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23c5.25 0 9.64-3.31 11.04-7.84z"/><path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.73 1 3.32 4.66 2.2 8.65l2.09 2.09C6.38 8.73 7.9 7.53 10.06 7.53z"/></svg>
                <span>Google</span>
              </button>
              <button
                onClick={() => handleSocialLogin('orcid')}
                className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 rounded hover:bg-gray-50"
              >
                <svg className="w-5 h-5" viewBox="0 0 24 24"><path fill="#A6CE39" d="M12 0C5.373 0 0 5.373 0 12c0 6.627 5.373 12 12 12s12-5.373 12-12S18.627 0 12 0zm0 2.25c5.084 0 9.25 4.167 9.25 9.25s-4.166 9.25-9.25 9.25-9.25-4.167-9.25-9.25 9.25-9.25zm0 3.75c-3.038 0-5.5 2.462-5.5 5.5s2.462 5.5 5.5 5.5 5.5-2.462 5.5-5.5-2.462-5.5-5.5z"/></svg>
                <span>ORCID</span>
              </button>
            </div>
        )}

        {activeTab === 'deletion' && (
          <div className="space-y-6">
            <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
              <h3 className="text-lg font-medium text-red-700 mb-2">계정 삭제</h3>
              <p className="text-gray-600 mb-4">
                계정을 삭제하면 30일 유예 기간 후 모든 데이터가 영구적으로 파기됩니다.
                이 작업은 되돌릴 수 없습니다.
              </p>
              <div className="space-y-3">
                <input
                  type="text"
                  placeholder='"DELETE"를 입력하여 확인'
                  value={deleteConfirm}
                  onChange={e => setDeleteConfirm(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-red-500"
                />
                <button
                  onClick={handleDeleteAccount}
                  disabled={deleting || deleteConfirm !== 'DELETE'}
                  className="w-full px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
                >
                  {deleting ? '삭제 중...' : '계정 삭제 요청'}
                </button>
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}

export default AccountSettings;
