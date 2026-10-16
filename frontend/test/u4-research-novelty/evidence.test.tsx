import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { EvidenceResult } from '../../src/u4-research/evidence';
import { artifact, ready, conforms } from './fixtures';

describe('grounding and immutable results', () => {
  it('shows supported quotation, exact source version and disclosed partial coverage', () => {
    conforms('ResearchArtifactResponse', ready());
    render(<EvidenceResult value={ready()} />);
    expect(screen.getByText('source quotation').tagName).toBe('BLOCKQUOTE');
    expect(screen.getByText(/paper-a · 버전 v1 · section 1/)).toBeVisible();
    expect(screen.getByText(/일부 근거만/)).toHaveAttribute('role', 'status');
    expect(screen.getByRole('link')).toHaveAttribute('rel', 'noopener noreferrer');
  });
  it('renders contradictory and uncertain evidence distinctly without inventing quotation', () => {
    const value = structuredClone(artifact);
    value.output.evidence[0]!.stance = 'contradicts';
    value.output.evidence[0]!.quote = null;
    value.output.evidence.push({
      ...value.output.evidence[0]!,
      evidenceId: 'e2',
      stance: 'uncertain',
      readCoverage: 'partial',
      sourceUrl: null,
    });
    render(<EvidenceResult value={ready(value)} />);
    expect(screen.getByText('상반되는 근거')).toBeVisible();
    expect(screen.getByText('불확실한 근거')).toBeVisible();
    expect(screen.getByText(/일부만 읽음/)).toBeVisible();
    expect(document.querySelector('blockquote')).toBeNull();
  });
  it('keeps unread links outside evidence and suppresses purported quotations', () => {
    const value = structuredClone(artifact);
    value.output.evidence[0]!.readCoverage = 'not-read';
    value.output.coverage = 'abstained';
    render(<EvidenceResult value={ready(value)} />);
    expect(screen.getByText(/근거에서 제외/)).toBeVisible();
    expect(screen.getByText(/판단을 보류/)).toBeVisible();
    expect(screen.queryByText('source quotation')).toBeNull();
  });
  it('does not turn unsafe or malformed source URLs into executable links', () => {
    const value = structuredClone(artifact);
    value.output.evidence[0]!.sourceUrl = 'javascript:alert(1)';
    value.output.evidence.push({
      ...value.output.evidence[0]!,
      evidenceId: 'e2',
      sourceUrl: 'not a URL',
    });
    value.output.summary = '<script>alert(1)</script>';
    render(<EvidenceResult value={ready(value)} />);
    expect(screen.queryByRole('link')).toBeNull();
    expect(document.querySelector('script')).toBeNull();
    expect(screen.getByText('<script>alert(1)</script>')).toBeVisible();
  });
  it('shows a score only with a bounded scale and actual eligible evidence', () => {
    const value = structuredClone(artifact);
    value.output.assessments = [
      {
        criterionId: 'a',
        label: '차별점',
        score: 3,
        scaleMinimum: 0,
        scaleMaximum: 5,
        evidenceIds: ['e1'],
        limitations: ['비교 자료가 제한됨'],
      },
    ];
    render(<EvidenceResult value={ready(value)} />);
    expect(screen.getByText(/3 \(척도 0–5\)/)).toBeVisible();
    expect(screen.getByText(/과학적 참신성의 증명이/)).toBeVisible();
  });
  it('hides scores without a scale, outside the scale, or referencing missing evidence', () => {
    const value = structuredClone(artifact);
    value.output.assessments = [
      { criterionId: 'a', label: '척도 없음', score: 9, evidenceIds: ['e1'], limitations: [] },
      {
        criterionId: 'b',
        label: '범위 벗어남',
        score: 9,
        scaleMinimum: 0,
        scaleMaximum: 5,
        evidenceIds: ['e1'],
        limitations: [],
      },
      {
        criterionId: 'c',
        label: '출처 없음',
        score: 2,
        scaleMinimum: 0,
        scaleMaximum: 5,
        evidenceIds: ['missing'],
        limitations: [],
      },
    ];
    render(<EvidenceResult value={ready(value)} />);
    expect(screen.getAllByText(/점수를 표시하지/)).toHaveLength(3);
  });
  it.each(['pending', 'failed', 'expired', 'deleted', 'restricted'] as const)(
    'shows unavailable %s without a regeneration action',
    (availability) => {
      const value = { availability, artifactId: 'artifact-a', reasonKey: 'research.unavailable' };
      conforms('ResearchArtifactResponse', value);
      render(<EvidenceResult value={value} />);
      expect(screen.getByRole('status')).toHaveTextContent('새 작업을 시작하지');
      expect(screen.queryByRole('button')).toBeNull();
    },
  );
});
