/**
 * The footer's legal links (BR5.3, BR5.6): always available, backed by `public.static`,
 * served as documents that need no script.
 */
import React from 'react';
import styles from './shell.module.css';

export function Footer() {
  return (
    <footer className={styles.footer} data-testid="footer">
      <nav aria-label="법적 고지">
        <a href="/privacy" data-testid="footer-privacy">
          개인정보 처리방침
        </a>{' '}
        <a href="/terms" data-testid="footer-terms">
          이용약관
        </a>
      </nav>
    </footer>
  );
}
