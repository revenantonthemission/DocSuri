/**
 * The research composer's limit and novelty without scores (U8 plan Step 42; your
 * decision of 2026-10-24, "Build the research executor").
 *
 * 1. The composer allows 2,048 bytes under the production policy and 32,768 under the
 *    synthetic one; the server stays authoritative.
 * 2. A scoreless assessment with only eligible evidence shows the new text, and an
 *    assessment that carries an invalid score keeps U4's text.
 * 3. By your decision of 2026-10-25 ("A new sentence for it"), an assessment with no
 *    confirmed evidence shows the no-evidence sentence and its limitation, never the
 *    confirmed-evidence sentence, and an abstained result shows it once per criterion.
 */
import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import {
  PRODUCTION_RESEARCH_POLICY_ID,
  PRODUCTION_TEXT_BYTES,
  RESEARCH_LIMITS,
  researchLimits,
} from '../../src/u4-research/api';
import { NoveltyDiscussion, ResearchComposer } from '../../src/u4-research/composer';
import { EvidenceResult } from '../../src/u4-research/evidence';
import {
  artifact,
  Double,
  policy as syntheticPolicy,
  ready,
  receipt,
  scope,
  session,
} from '../u4-research-novelty/fixtures';

const productionPolicy = { policyId: PRODUCTION_RESEARCH_POLICY_ID, revision: '1' };
const SCORELESS = '점수 없이, 확인된 근거로만 비교했어요';
const NO_EVIDENCE = '확인된 근거가 없어 이 기준은 비교하지 않았어요';
const U4_INVALID = '척도 또는 근거를 확인할 수 없어 점수를 표시하지 않아요';

describe('the research composer limit', () => {
  it('is 2,048 bytes for the production policy and U4s 32,768 otherwise', () => {
    expect(researchLimits(productionPolicy).textBytes).toBe(2_048);
    expect(PRODUCTION_TEXT_BYTES).toBe(2_048);
    expect(researchLimits(syntheticPolicy).textBytes).toBe(32_768);
    expect(researchLimits({ policyId: 'another-policy', revision: '1' })).toEqual(RESEARCH_LIMITS);
    // The other limits never change with the policy.
    expect({ ...researchLimits(productionPolicy), textBytes: 0 }).toEqual({
      ...RESEARCH_LIMITS,
      textBytes: 0,
    });
  });

  it('allows a 2,048-byte question under the production policy and refuses one more byte', async () => {
    const server = new Double().on('accept-research-turn', () => receipt);
    const onAccepted = vi.fn();
    render(
      <ResearchComposer
        client={server.client()}
        purpose="research"
        scope={{ ...scope, scopePolicy: productionPolicy }}
        session={session}
        policy={productionPolicy}
        onAccepted={onAccepted}
      />,
    );
    const input = screen.getByRole('textbox', { name: '연구 질문' });
    const button = screen.getByRole('button', { name: '질문 보내기' });
    fireEvent.change(input, { target: { value: '한'.repeat(682) + 'aaa' } });
    expect(input).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByRole('alert')).toHaveTextContent('2049 / 2048 UTF-8');
    expect(button).toBeDisabled();
    fireEvent.submit(input.closest('form')!);
    expect(server.calls).toHaveLength(0);
    const exact = '한'.repeat(682) + 'aa';
    fireEvent.change(input, { target: { value: exact } });
    expect(input).toHaveAttribute('aria-invalid', 'false');
    expect(screen.getByText(/2048 \/ 2048 UTF-8/)).toBeVisible();
    await userEvent.click(button);
    await waitFor(() => expect(onAccepted).toHaveBeenCalledOnce());
    expect(server.calls[0]!.body).toMatchObject({ text: exact, policy: productionPolicy });
  });

  it('keeps 32,768 bytes under the synthetic policy, for the composer and the discussion', () => {
    render(
      <>
        <ResearchComposer
          client={new Double().client()}
          purpose="novelty"
          scope={scope}
          session={session}
          policy={syntheticPolicy}
          onAccepted={vi.fn()}
        />
        <NoveltyDiscussion
          client={new Double().client()}
          source={artifact}
          policy={syntheticPolicy}
          onAccepted={vi.fn()}
        />
      </>,
    );
    const topic = screen.getByRole('textbox', { name: '분석할 주제 또는 원고 설명' });
    fireEvent.change(topic, { target: { value: 'a'.repeat(4_000) } });
    expect(topic).toHaveAttribute('aria-invalid', 'false');
    expect(screen.getByText(/4000 \/ 32768 UTF-8/)).toBeVisible();
    expect(screen.getByText(/^입력 용량 0 \/ 32768 UTF-8/)).toBeVisible();
  });

  it('bounds the novelty discussion by the production policy too', () => {
    render(
      <NoveltyDiscussion
        client={new Double().client()}
        source={artifact}
        policy={productionPolicy}
        onAccepted={vi.fn()}
      />,
    );
    const input = screen.getByRole('textbox', { name: '결과에 대한 질문' });
    fireEvent.change(input, { target: { value: 'b'.repeat(2_049) } });
    expect(screen.getByRole('alert')).toHaveTextContent('2049 / 2048 UTF-8');
    expect(screen.getByRole('button', { name: '결과에 대해 질문 보내기' })).toBeDisabled();
  });
});

describe('novelty without scores', () => {
  it('shows the new text for a scoreless assessment with only eligible evidence', () => {
    const value = structuredClone(artifact);
    value.output.assessments = [
      { criterionId: 'method', label: '방법의 차이', evidenceIds: ['e1'], limitations: [] },
      {
        criterionId: 'contribution',
        label: '기여의 차이',
        evidenceIds: [],
        limitations: ['근거 구간을 찾지 못했습니다'],
      },
    ];
    render(<EvidenceResult value={ready(value)} />);
    // Only the criterion with evidence was compared on confirmed evidence.
    const method = screen.getByRole('region', { name: '방법의 차이' });
    expect(within(method).getByText(SCORELESS)).toBeVisible();
    expect(within(method).queryByText(NO_EVIDENCE)).toBeNull();
    const contribution = screen.getByRole('region', { name: '기여의 차이' });
    expect(within(contribution).getByText(NO_EVIDENCE)).toBeVisible();
    expect(within(contribution).queryByText(SCORELESS)).toBeNull();
    // Its limitation is shown with it.
    expect(within(contribution).getByText('근거 구간을 찾지 못했습니다')).toBeVisible();
    expect(screen.getAllByText(SCORELESS)).toHaveLength(1);
    expect(screen.queryByText(U4_INVALID)).toBeNull();
    // The disclaimer that no assessment proves novelty stays.
    expect(screen.getAllByText(/과학적 참신성의 증명이/)).toHaveLength(2);
  });

  it('shows the no-evidence sentence once per criterion of an abstained result', () => {
    const value = structuredClone(artifact);
    const limitation = '근거 구간을 찾지 못했습니다';
    value.output.assessments = [
      {
        criterionId: 'research-question',
        label: '연구 질문의 차이',
        evidenceIds: [],
        limitations: [limitation],
      },
      { criterionId: 'method', label: '방법의 차이', evidenceIds: [], limitations: [limitation] },
      {
        criterionId: 'contribution',
        label: '기여의 차이',
        evidenceIds: [],
        limitations: [limitation],
      },
    ];
    render(<EvidenceResult value={ready(value)} />);
    expect(screen.getAllByText(NO_EVIDENCE)).toHaveLength(3);
    expect(screen.queryByText(SCORELESS)).toBeNull();
    expect(screen.queryByText(U4_INVALID)).toBeNull();
    expect(screen.getAllByText(limitation)).toHaveLength(3);
    for (const label of ['연구 질문의 차이', '방법의 차이', '기여의 차이']) {
      expect(
        within(screen.getByRole('region', { name: label })).getByText(NO_EVIDENCE),
      ).toBeVisible();
    }
  });

  it('keeps U4s text for an invalid score and for scoreless evidence only partly eligible', () => {
    const value = structuredClone(artifact);
    value.output.assessments = [
      { criterionId: 'a', label: '척도 없음', score: 9, evidenceIds: ['e1'], limitations: [] },
      { criterionId: 'b', label: '근거 일부', evidenceIds: ['e1', 'missing'], limitations: [] },
    ];
    render(<EvidenceResult value={ready(value)} />);
    expect(screen.getAllByText(U4_INVALID)).toHaveLength(2);
    expect(screen.queryByText(SCORELESS)).toBeNull();
    expect(screen.queryByText(NO_EVIDENCE)).toBeNull();
  });

  it('shows the no-evidence sentence when no evidence of a scoreless criterion is confirmed', () => {
    const value = structuredClone(artifact);
    value.output.assessments = [
      {
        criterionId: 'b',
        label: '근거 없음',
        evidenceIds: ['missing'],
        limitations: ['근거를 확인하지 못했습니다'],
      },
    ];
    render(<EvidenceResult value={ready(value)} />);
    const section = screen.getByRole('region', { name: '근거 없음' });
    expect(within(section).getByText(NO_EVIDENCE)).toBeVisible();
    expect(within(section).getByText('근거를 확인하지 못했습니다')).toBeVisible();
    expect(screen.queryByText(SCORELESS)).toBeNull();
    expect(screen.queryByText(U4_INVALID)).toBeNull();
  });
});
