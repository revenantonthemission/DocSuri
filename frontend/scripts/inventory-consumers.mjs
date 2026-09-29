// Actual TypeScript imports and transport casts, resolved with the same compiler configuration.
import ts from 'typescript';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { readFile, writeFile } from 'node:fs/promises';
import { resolve, relative, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const frontend = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const repository = resolve(frontend, '..');
const slash = (path) => path.replaceAll('\\', '/');

export function inventory(root = frontend) {
  const config = ts.readConfigFile(resolve(root, 'tsconfig.json'), ts.sys.readFile);
  if (config.error) throw new Error('cannot read TypeScript consumer configuration');
  const parsed = ts.parseJsonConfigFileContent(config.config, ts.sys, root);
  if (parsed.errors.length) throw new Error('invalid TypeScript consumer configuration');
  const program = ts.createProgram(parsed.fileNames, { ...parsed.options, noEmit: true });
  const checker = program.getTypeChecker();
  const wire = slash(resolve(root, 'types/wire/dtos.ts'));
  const imports = [], boundaries = [], declarations = [], adapters = [], sourceDigests = [];
  const fileName = (source) => slash(relative(resolve(root, '..'), source.fileName));

  function lineage(symbol, seen = new Set()) {
    if (!symbol || seen.has(symbol)) return new Set();
    seen.add(symbol);
    if (symbol.flags & ts.SymbolFlags.Alias) return lineage(checker.getAliasedSymbol(symbol), seen);
    const result = new Set();
    for (const declaration of symbol.declarations ?? []) {
      const path = slash(declaration.getSourceFile().fileName);
      if (path === wire) { result.add(symbol.getName()); continue; }
      if (!path.startsWith(slash(root) + '/') || path.includes('/node_modules/')) continue;
      if (!ts.isTypeAliasDeclaration(declaration) && !ts.isInterfaceDeclaration(declaration)) continue;
      function visit(node) {
        if (ts.isTypeReferenceNode(node)) {
          for (const name of lineage(checker.getSymbolAtLocation(node.typeName), seen)) result.add(name);
        }
        ts.forEachChild(node, visit);
      }
      visit(declaration);
    }
    return result;
  }

  for (const source of program.getSourceFiles()) {
    const name = fileName(source);
    if (!name.startsWith('frontend/') || /\/(node_modules|\.next|test|mocks|types\/wire)\//u.test(name)) continue;
    if (!/\.(ts|tsx)$/u.test(name) || source.isDeclarationFile) continue;
    const before = imports.length + boundaries.length + declarations.length + adapters.length;
    function visit(node) {
      if (ts.isImportDeclaration(node) && ts.isStringLiteral(node.moduleSpecifier)) {
        const module = node.moduleSpecifier.text;
        const bindings = node.importClause?.namedBindings;
        if (bindings && ts.isNamedImports(bindings)) for (const binding of bindings.elements) {
          const roots = [...lineage(checker.getSymbolAtLocation(binding.name))].sort();
          if (roots.length || module.includes('/types') || module.startsWith('@/types')) {
            imports.push({ file: name, module, symbol: binding.propertyName?.text ?? binding.name.text,
              local: binding.name.text, generated: roots });
          }
        }
      }
      if ((ts.isTypeAliasDeclaration(node) || ts.isInterfaceDeclaration(node)) &&
          (name.startsWith('frontend/types/') || name === 'frontend/lib/api/apiClient.ts')) {
        declarations.push({ file: name, symbol: node.name.text,
          generated: [...lineage(checker.getSymbolAtLocation(node.name))].sort() });
      }
      if (ts.isAsExpression(node) && /\.body(?:\b|\[)/u.test(node.expression.getText(source))) {
        const roots = new Set();
        function types(child) {
          if (ts.isTypeReferenceNode(child)) for (const item of lineage(checker.getSymbolAtLocation(child.typeName))) roots.add(item);
          ts.forEachChild(child, types);
        }
        types(node.type);
        boundaries.push({ file: name, type: node.type.getText(source), generated: [...roots].sort() });
      }
      if (ts.isFunctionDeclaration(node) && node.name && /^(classify|map|cardFromMeta)/u.test(node.name.text)) {
        adapters.push({ file: name, symbol: node.name.text,
          input: node.parameters.map((parameter) => parameter.type?.getText(source) ?? 'inferred'),
          output: node.type?.getText(source) ?? 'inferred' });
      }
      ts.forEachChild(node, visit);
    }
    visit(source);
    if (imports.length + boundaries.length + declarations.length + adapters.length !== before) {
      sourceDigests.push({ file: name, sha256: createHash('sha256').update(readFileSync(source.fileName)).digest('hex') });
    }
  }
  const sort = (items) => items.sort((a, b) => JSON.stringify(a).localeCompare(JSON.stringify(b), 'en'));
  return { version: 1, imports: sort(imports), declarations: sort(declarations),
    boundaries: sort(boundaries), adapters: sort(adapters), sourceDigests: sort(sourceDigests) };
}

export function validateInventory(observed, policy) {
  if (observed.boundaries.some((entry) => entry.file === 'frontend/lib/api/apiClient.ts' && !entry.generated.length)) {
    throw new Error('production response cast has no generated contract');
  }
  const key = (entry) => `${entry.file}:${entry.symbol}`;
  const declared = new Set(policy.adapters.map(key));
  if (declared.size !== policy.adapters.length) throw new Error('duplicate view adapter policy');
  const discovered = new Set(observed.adapters.map(key));
  for (const adapter of discovered) if (!declared.has(adapter)) throw new Error('unregistered view adapter');
  for (const adapter of declared) if (!discovered.has(adapter)) throw new Error('view adapter missing');
}

async function main() {
  const output = resolve(repository, 'shared/typescript-consumers.json');
  const observed = inventory();
  const policy = JSON.parse(await readFile(resolve(repository, 'shared/view-adapters.json'), 'utf8'));
  validateInventory(observed, policy);
  for (const adapter of policy.adapters) {
    if (adapter.schema) await readFile(resolve(repository, 'shared', adapter.schema));
    else if (adapter.kind !== 'view-only') throw new Error('wire adapter has no schema');
    if (!adapter.fixtures.length) throw new Error('view adapter has no fixtures');
    for (const fixture of adapter.fixtures) await readFile(resolve(repository, fixture));
  }
  const result = JSON.stringify(observed, null, 2) + '\n';
  if (process.argv.includes('--write')) await writeFile(output, result, { mode: 0o644 });
  else if (await readFile(output, 'utf8') !== result) throw new Error('actual TypeScript consumer inventory drift');
  console.log('ok: actual TypeScript imports, wire casts and view-adapter inventory');
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch(() => { console.error('consumer inventory incomplete'); process.exitCode = 1; });
}
