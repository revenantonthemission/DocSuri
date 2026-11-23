/** U5's views add no UI stack (tech-stack decision: no new stack). Every module in
 * src/u5-topics imports only React, SWR, the shared `ui` and `api` modules, its sibling
 * U5 modules and topics.css: a plain per-view stylesheet, like U4's research.css and
 * U6's export.css, that imports nothing. The imports are read from the parsed source, so
 * a type-only import, a re-export, a side-effect import, a dynamic import or a require
 * counts as well, and the two packages are ones the workspace already depends on. */

import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import ts from 'typescript';
import { describe, expect, it } from 'vitest';

// The lane runs from the frontend root (vitest.u5-topics.config.ts sits there).
const FRONTEND = process.cwd();
const SOURCE = join(FRONTEND, 'src', 'u5-topics');
const PACKAGE = join(FRONTEND, 'package.json');
const VIEWS = ['api.ts', 'digest-settings.tsx', 'owner-preferences.tsx', 'topics-view.tsx'];
const PACKAGES = ['react', 'swr'];
const SHARED = ['../ui', '../api'];
const SIBLINGS = ['./api', './digest-settings', './owner-preferences', './topics-view'];
const STYLESHEET = 'topics.css';
const ALLOWED = new Set([...PACKAGES, ...SHARED, ...SIBLINGS, `./${STYLESHEET}`]);

/** Every module specifier one source file names, in source order. */
function moduleSpecifiers(name: string, text: string): string[] {
  const kind = name.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS;
  const source = ts.createSourceFile(name, text, ts.ScriptTarget.Latest, true, kind);
  const found: string[] = [];
  const visit = (node: ts.Node): void => {
    if (
      (ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) &&
      node.moduleSpecifier &&
      ts.isStringLiteral(node.moduleSpecifier)
    ) {
      found.push(node.moduleSpecifier.text);
    } else if (
      ts.isImportEqualsDeclaration(node) &&
      ts.isExternalModuleReference(node.moduleReference) &&
      ts.isStringLiteral(node.moduleReference.expression)
    ) {
      found.push(node.moduleReference.expression.text);
    } else if (ts.isCallExpression(node)) {
      const callee = node.expression;
      const loads =
        callee.kind === ts.SyntaxKind.ImportKeyword ||
        (ts.isIdentifier(callee) && callee.text === 'require');
      const [first] = node.arguments;
      if (loads) found.push(first && ts.isStringLiteralLike(first) ? first.text : '<computed>');
    } else if (ts.isImportTypeNode(node)) {
      const argument = node.argument;
      if (ts.isLiteralTypeNode(argument) && ts.isStringLiteral(argument.literal)) {
        found.push(argument.literal.text);
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
  return found;
}

const sourceFiles = () => readdirSync(SOURCE).filter((name) => /\.(ts|tsx)$/.test(name));
const read = (name: string) => readFileSync(join(SOURCE, name), 'utf8');

describe('U5 stack boundary', () => {
  it('imports only React, SWR, the shared ui and api modules, its siblings and topics.css', () => {
    expect(existsSync(join(FRONTEND, 'vitest.u5-topics.config.ts'))).toBe(true);
    const files = sourceFiles();
    expect(files).toEqual(expect.arrayContaining(VIEWS));
    const outside = files.flatMap((name) =>
      moduleSpecifiers(name, read(name))
        .filter((specifier) => !ALLOWED.has(specifier))
        .map((specifier) => `${name} imports ${specifier}`),
    );
    expect(outside).toEqual([]);
    // The two packages come from the workspace's established dependencies.
    const manifest = JSON.parse(readFileSync(PACKAGE, 'utf8')) as {
      dependencies: Record<string, string>;
    };
    expect(Object.keys(manifest.dependencies)).toEqual(expect.arrayContaining(PACKAGES));
  });

  it('keeps one plain stylesheet, topics.css, which imports nothing', () => {
    const stylesheets = readdirSync(SOURCE).filter((name) =>
      /\.(css|scss|sass|less|styl)$/.test(name),
    );
    expect(stylesheets).toEqual([STYLESHEET]);
    const styles = read(STYLESHEET);
    expect(styles).not.toMatch(/@import|@use|@tailwind|url\(/);
    // The view that renders the topics surface loads it; no module loads another sheet.
    const loads = sourceFiles().filter((name) =>
      moduleSpecifiers(name, read(name)).some((specifier) =>
        /\.(css|scss|sass|less|styl)$/.test(specifier),
      ),
    );
    expect(loads).toEqual(['topics-view.tsx']);
    expect(moduleSpecifiers('topics-view.tsx', read('topics-view.tsx'))).toContain(
      `./${STYLESHEET}`,
    );
  });

  it('reads every import form, so no new module can enter unseen', () => {
    const planted = [
      "import React from 'react';",
      "import type { Store } from 'zustand';",
      "export { styled } from 'styled-components';",
      "import 'tailwindcss/tailwind.css';",
      "const motion = await import('framer-motion');",
      "const legacy = require('jquery');",
      "type Theme = import('@emotion/react').Theme;",
      'const dynamic = await import(`./${name}`);',
    ].join('\n');
    expect(moduleSpecifiers('planted.tsx', planted)).toEqual([
      'react',
      'zustand',
      'styled-components',
      'tailwindcss/tailwind.css',
      'framer-motion',
      'jquery',
      '@emotion/react',
      '<computed>',
    ]);
    const outside = moduleSpecifiers('planted.tsx', planted).filter(
      (specifier) => !ALLOWED.has(specifier),
    );
    expect(outside).toHaveLength(7);
  });

  it('names exactly the shared modules and siblings that exist in the workspace', () => {
    for (const shared of SHARED) {
      const base = join(SOURCE, shared);
      const present = ['ts', 'tsx'].some((extension) => existsSync(`${base}.${extension}`));
      expect(present, `${shared} is a shared workspace module`).toBe(true);
    }
    const files = new Set(sourceFiles().map((name) => `./${name.replace(/\.(ts|tsx)$/, '')}`));
    for (const sibling of SIBLINGS) expect(files.has(sibling), sibling).toBe(true);
  });
});
