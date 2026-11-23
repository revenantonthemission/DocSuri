/**
 * The maintenance notice while admission is maintainer-only (BR6.4): every page but the
 * legal pages shows it, with a small 관리자 로그인 link; only administrators can sign in.
 */
import React from 'react';
import styles from './shell.module.css';
import type { CapabilityStateMap } from './provider-notice';

export const MAINTAINER_ONLY = 'admission-maintainer-only';
export const MAINTENANCE_TEXT = 'DocSuri를 점검하고 있습니다. 잠시 후 다시 접속해 주세요.';

export function maintainerOnly(states: CapabilityStateMap): boolean {
  return states['account.entry']?.reasonKey === MAINTAINER_ONLY;
}

export function MaintenanceBanner({
  states,
  onAdministratorSignIn,
}: {
  states: CapabilityStateMap;
  onAdministratorSignIn: () => void;
}) {
  if (!maintainerOnly(states)) return null;
  // No role of its own: capability changes are announced only through the shell's region
  // (L1-26).
  return (
    <aside className={styles.notice} data-testid="maintenance-banner">
      <p>{MAINTENANCE_TEXT}</p>
      <button
        type="button"
        className="link"
        onClick={onAdministratorSignIn}
        data-testid="maintenance-admin-sign-in"
      >
        관리자 로그인
      </button>
    </aside>
  );
}
