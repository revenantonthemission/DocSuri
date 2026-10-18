/** Edits C03-owned preferences; Topics never stores a second preference copy. */
import React, { useEffect, useRef, useState } from 'react';
import { ApiError, SETTINGS_POLICY, type Transport } from '../api';
import { describeError, notice, StatusLine, type Notice } from '../ui';

type Snapshot = {
  revision: string;
  timeZone?: string | null;
  assistanceDefaults: {
    languageId: 'en' | 'ko';
    presentationLevelId: 'standard';
    actionId: string;
    vocabularyRevision: string;
  };
};

export function OwnerPreferences({ client, onSaved }: { client: Transport; onSaved: () => void }) {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [language, setLanguage] = useState<'en' | 'ko'>('en');
  const [zone, setZone] = useState('');
  const [working, setWorking] = useState(false);
  const [stale, setStale] = useState(false);
  const [status, setStatus] = useState<Notice | null>(null);
  const alive = useRef(false);
  const pending = useRef<{ body: object; key: string } | null>(null);
  const [uncertain, setUncertain] = useState(false);
  const generation = client.generation;
  const current = () => alive.current && generation === client.generation;
  const accept = (value: Snapshot) => {
    setSnapshot(value);
    setLanguage(value.assistanceDefaults.languageId);
    setZone(value.timeZone ?? '');
  };
  const load = async () => {
    setWorking(true);
    try {
      const value = await client.post<Snapshot>('/api/v2/c03/settings-read', {});
      if (!current()) return;
      accept(value);
      setStale(false);
      setStatus(null);
    } catch (failure) {
      if (current()) setStatus(describeError(failure));
    } finally {
      if (current()) setWorking(false);
    }
  };
  useEffect(() => {
    alive.current = true;
    setSnapshot(null);
    pending.current = null;
    setUncertain(false);
    void load();
    return () => {
      alive.current = false;
    };
    // Transport responses also enforce the authority generation.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client, generation]);

  const save = async () => {
    if (!snapshot || !zone.trim() || working || stale) return;
    setWorking(true);
    setStatus(null);
    const request = pending.current ?? {
      body: {
        expectedRevision: snapshot.revision,
        policyRef: SETTINGS_POLICY,
        timeZone: zone.trim(),
        assistanceDefaults: { ...snapshot.assistanceDefaults, languageId: language },
      },
      key: crypto.randomUUID(),
    };
    pending.current = request;
    try {
      const value = await client.post<Snapshot>(
        '/api/v2/c03/settings-update',
        request.body,
        request.key,
      );
      if (!current()) return;
      accept(value);
      pending.current = null;
      setUncertain(false);
      setStatus(notice('polite', '계정 환경설정을 저장했어요'));
      onSaved();
    } catch (failure) {
      if (!current()) return;
      const unknown = failure instanceof ApiError && failure.envelope.code === 'UNKNOWN_OUTCOME';
      setUncertain(unknown);
      if (!unknown) pending.current = null;
      setStale(failure instanceof ApiError && failure.envelope.code === 'STALE_REVISION');
      setStatus(
        unknown
          ? notice('alert', '저장 결과가 확인되지 않았어요. 같은 요청의 결과를 확인해 주세요.')
          : describeError(failure),
      );
    } finally {
      if (current()) setWorking(false);
    }
  };

  return (
    <section aria-label="계정 환경설정" data-testid="owner-preferences">
      <h4>계정 환경설정</h4>
      <p>모든 주제에 적용됩니다. 저장이 확인된 설정으로 다음 발송을 준비해요.</p>
      {!snapshot ? (
        <p>환경설정을 불러오는 중…</p>
      ) : (
        <>
          <div className="field">
            <label htmlFor="digest-language">다이제스트 언어</label>
            <select
              id="digest-language"
              data-testid="digest-language"
              value={language}
              disabled={working || uncertain}
              onChange={(event) => setLanguage(event.target.value as 'en' | 'ko')}
            >
              <option value="en">English</option>
              <option value="ko">한국어</option>
            </select>
          </div>
          <p>설명 수준: 표준 (standard)</p>
          <div className="field">
            <label htmlFor="digest-timezone">계정 시간대 (IANA)</label>
            <input
              id="digest-timezone"
              data-testid="digest-timezone"
              value={zone}
              disabled={working || uncertain}
              placeholder="예: Asia/Seoul"
              onChange={(event) => setZone(event.target.value)}
            />
          </div>
          {!snapshot.timeZone ? (
            <p role="status">시간대를 확인하고 저장해야 예약 발송이 시작돼요.</p>
          ) : null}
          <button
            type="button"
            data-testid="preferences-save"
            onClick={save}
            disabled={working || stale || !zone.trim()}
          >
            {working ? '저장 중…' : uncertain ? '저장 결과 확인' : '계정 환경설정 저장'}
          </button>
        </>
      )}
      <StatusLine value={status} />
      {(!snapshot || stale) && !working ? (
        <button type="button" data-testid="preferences-reload" onClick={load}>
          환경설정 다시 불러오기
        </button>
      ) : null}
    </section>
  );
}
