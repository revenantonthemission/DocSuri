// U8 plan Step 92(h): the colour tokens the U8 screens use meet their WCAG ratios in every
// theme block, the static pages carry the accent's text variant (L1-40), the request id
// takes its line's colour in the complete app only, and U8's styles use tokens alone.
import { readdirSync, readFileSync } from 'node:fs';
import { join, relative } from 'node:path';
import { describe, expect, it } from 'vitest';

// This file's own folder is test/u8-complete under the frontend.
const FRONTEND = join(__dirname, '..', '..');
const read = (path: string) => readFileSync(join(FRONTEND, path), 'utf8');

type Tokens = Record<string, string>;
type Block = 'root' | 'dark' | 'light-theme' | 'dark-theme';
const BLOCKS: Block[] = ['root', 'dark', 'light-theme', 'dark-theme'];

function declarations(body: string): Tokens {
  const tokens: Tokens = {};
  for (const match of body.matchAll(/(--color-[\w-]+)\s*:\s*([^;]+);/g))
    tokens[match[1]!] = match[2]!.trim().toLowerCase();
  return tokens;
}

/** A stylesheet's four token blocks, each on its own (not merged with `:root`). */
function blocksOf(css: string): Record<Block, Tokens> {
  const text = css.replace(/\/\*[\s\S]*?\*\//g, '');
  const result: Record<Block, Tokens> = {
    root: {},
    dark: {},
    'light-theme': {},
    'dark-theme': {},
  };
  const media = /@media\s*\(prefers-color-scheme:\s*dark\)\s*\{\s*:root\s*\{([^}]*)\}\s*\}/g;
  for (const match of text.matchAll(media)) Object.assign(result.dark, declarations(match[1]!));
  const rest = text.replace(media, '');
  for (const match of rest.matchAll(/:root\[data-theme='(light|dark)'\]\s*\{([^}]*)\}/g))
    Object.assign(result[`${match[1] as 'light' | 'dark'}-theme`], declarations(match[2]!));
  for (const match of rest.matchAll(/(?:^|[}\s]):root\s*\{([^}]*)\}/g))
    Object.assign(result.root, declarations(match[1]!));
  return result;
}

/** Merge stylesheets in load order; each block lies over `:root`, as the cascade does. */
function merged(paths: string[]): Record<Block, Tokens> {
  const sheets = paths.map((path) => blocksOf(read(path)));
  const root = Object.assign({}, ...sheets.map((sheet) => sheet.root)) as Tokens;
  const out = { root } as Record<Block, Tokens>;
  for (const block of BLOCKS.slice(1))
    out[block] = Object.assign({ ...root }, ...sheets.map((sheet) => sheet[block])) as Tokens;
  return out;
}

function luminance(hex: string): number {
  const value = hex.replace('#', '');
  const full = value.length === 3 ? [...value].map((c) => c + c).join('') : value;
  const [r, g, b] = [0, 2, 4].map((at) => {
    const channel = parseInt(full.slice(at, at + 2), 16) / 255;
    return channel <= 0.03928 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r! + 0.7152 * g! + 0.0722 * b!;
}

function contrast(a: string, b: string): number {
  const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (light! + 0.05) / (dark! + 0.05);
}

const APP = ['app/globals.css', 'src/workspace.css', 'src/u8-shell/shell.module.css'];
const STATIC = ['app/globals.css', 'src/u8-static/legal.css'];

const TEXT_PAIRS: [string, string][] = [
  ['--color-text', '--color-bg'],
  ['--color-text', '--color-surface'],
  ['--color-text', '--color-accent-soft-bg'],
  ['--color-text-muted', '--color-bg'],
  ['--color-text-muted', '--color-surface'],
  ['--color-accent-text', '--color-bg'],
  ['--color-accent-text', '--color-surface'],
  ['--color-accent-contrast', '--color-accent'],
  ['--color-danger', '--color-danger-bg'],
];
const FOCUS_PAIRS: [string, string][] = [
  ['--color-accent', '--color-bg'],
  ['--color-accent', '--color-surface'],
  ['--color-accent-text', '--color-bg'],
];

function ratio(tokens: Tokens, [fore, back]: [string, string]): number {
  const foreground = tokens[fore];
  const background = tokens[back];
  expect(foreground, `${fore} is defined`).toMatch(/^#[0-9a-f]{3,6}$/);
  expect(background, `${back} is defined`).toMatch(/^#[0-9a-f]{3,6}$/);
  return contrast(foreground!, background!);
}

describe('the colour tokens', () => {
  it('the token pairs the U8 screens use meet their ratios in every theme', () => {
    for (const [name, paths] of [
      ['app', APP],
      ['static pages', STATIC],
    ] as const) {
      const blocks = merged([...paths]);
      for (const block of BLOCKS) {
        const tokens = blocks[block];
        // The static pages' header link is --color-accent-text on --color-bg.
        for (const pair of TEXT_PAIRS)
          expect(
            ratio(tokens, pair),
            `${name} ${block}: ${pair.join(' on ')}`,
          ).toBeGreaterThanOrEqual(4.5);
        for (const pair of FOCUS_PAIRS)
          expect(
            ratio(tokens, pair),
            `${name} ${block}: ${pair.join(' on ')}`,
          ).toBeGreaterThanOrEqual(3);
      }
    }
  });

  it("legal.css's accent text equals workspace.css's in every block", () => {
    const legal = blocksOf(read('src/u8-static/legal.css'));
    const workspace = blocksOf(read('src/workspace.css'));
    for (const block of BLOCKS) {
      expect(legal[block]['--color-accent-text'], block).toBeDefined();
      expect(legal[block]['--color-accent-text']).toBe(workspace[block]['--color-accent-text']);
    }
  });

  it("the request id takes its line's colour in the complete app", () => {
    const shell = read('src/u8-shell/shell.module.css').replace(/\/\*[\s\S]*?\*\//g, '');
    expect(shell).toMatch(/\.completeShell\s*\{\s*display:\s*contents;\s*\}/);
    expect(shell).toMatch(/\.completeShell\s+:global\(\.status-id\)\s*\{\s*color:\s*inherit;\s*\}/);
    // With the id inheriting, it shows its line's own pair: danger on danger-bg for an alert,
    // text on accent-soft-bg for a polite line; both pairs meet 4.5:1 above.
    const workspace = read('src/workspace.css');
    expect(workspace).toMatch(
      /\.status-alert\s*\{[^}]*background:\s*var\(--color-danger-bg\);[^}]*color:\s*var\(--color-danger\);/,
    );
    expect(workspace).toMatch(/\.status\s*\{[^}]*background:\s*var\(--color-accent-soft-bg\);/);
    // U1's own id stays as built for earlier assemblies.
    expect(workspace).toMatch(
      /\.status-id\s*\{\s*color:\s*var\(--color-text-muted\);\s*font-size:\s*0\.85rem;\s*\}/,
    );
  });
});

function sourceFiles(): string[] {
  const src = join(FRONTEND, 'src');
  const roots = readdirSync(src).filter((name) => name.startsWith('u8-'));
  return roots.flatMap((root) =>
    (readdirSync(join(src, root), { recursive: true }) as string[])
      .filter((name) => /\.(ts|tsx|css)$/.test(name))
      .map((name) => join(src, root, name)),
  );
}

describe("U8's styles", () => {
  it("U8's styles use only colour tokens", () => {
    const workspace = blocksOf(read('src/workspace.css'));
    const light = merged(['app/globals.css', 'src/workspace.css']).root;
    const files = sourceFiles();
    expect(files.length).toBeGreaterThan(10);
    const offences: string[] = [];
    for (const file of files) {
      const name = relative(FRONTEND, file);
      const isLegal = name === join('src', 'u8-static', 'legal.css');
      const legalBlocks = isLegal ? blocksOf(readFileSync(file, 'utf8')) : null;
      const lines = readFileSync(file, 'utf8').split('\n');
      lines.forEach((line, index) => {
        const where = `${name}:${index + 1}`;
        for (const match of line.matchAll(/#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(/g)) {
          const literal = match[0].toLowerCase();
          const fallback = /var\((--color-[\w-]+),\s*(#[0-9a-f]{3,8})\)/i.exec(line);
          if (fallback && fallback[2]!.toLowerCase() === literal && light[fallback[1]!] === literal)
            continue;
          const declared = /^\s*(--color-[\w-]+)\s*:\s*(#[0-9a-f]{3,8})\s*;/i.exec(line);
          if (legalBlocks && declared) {
            const token = declared[1]!;
            const ok = BLOCKS.some(
              (block) =>
                legalBlocks[block][token] === literal && workspace[block][token] === literal,
            );
            if (ok) continue;
          }
          offences.push(`${where}: ${match[0]}`);
        }
        if (
          /\b(text|bg|border|ring)-(slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|black|white)\b/.test(
            line,
          )
        )
          offences.push(`${where}: palette class`);
      });
    }
    expect(offences).toEqual([]);
  });
});
