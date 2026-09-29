import { expect, it } from 'vitest';
import { classifySummarizeResponse } from '../lib/api/classifySummarize';
import { cardFromMeta } from '../lib/library/cardFromMeta';
import type { LibraryItemMeta } from '../types/generated';

it('requires the wire task and payload to agree before refining a summary view', () => {
  expect(classifySummarizeResponse({status:'ok', task:'translate', summary:{tldr:'x'}}).kind).toBe('error');
  expect(classifySummarizeResponse({status:'ok', task:'summary', summary:null}).kind).toBe('error');
  expect(classifySummarizeResponse({status:'ok', task:'summary', summary:{}, translation:{}}).kind).toBe('error');
  const summary = {tldr:'x', contributions:[], method:'m', results:'r', limitations:'l', reproducibility:{}, anchors:[]};
  expect(classifySummarizeResponse({status:'ok', task:'summary', summary}).kind).toBe('summary');
});

it('maps an opaque library snapshot only after its view contract is satisfied', () => {
  const meta: LibraryItemMeta = {title:'Paper',authors:['A'],arxivId:'2401.00001'};
  expect(cardFromMeta(meta)).toMatchObject({title:'Paper', authors:['A'], relevance:null});
  for (const invalid of [null, {}, {...meta, authors:[42]}, {...meta, year:Number.NaN}]) {
    expect(() => cardFromMeta(invalid as LibraryItemMeta)).toThrow('Invalid library snapshot');
  }
});
