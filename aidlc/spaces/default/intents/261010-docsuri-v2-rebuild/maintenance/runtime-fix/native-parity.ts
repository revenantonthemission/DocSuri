// Usage: bun native-parity.ts /path/to/aidlc-upstream-checkout
// Requires generated dist/ outputs and build/binaries/native/aidlc in that
// checkout, plus permission to inspect process ancestry (ps on macOS).
// Every workflow mutation is confined to a fresh temporary fixture.
import assert from "node:assert/strict";
import { copyFileSync, cpSync, readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

const checkoutArg = process.argv[2];
if (!checkoutArg || process.argv.length !== 3) {
  console.error("Usage: bun native-parity.ts /path/to/aidlc-upstream-checkout");
  process.exit(2);
}

const root = resolve(checkoutArg);
const binary = join(root, "build/binaries/native/aidlc");
const {
  createIntent,
  readAllAuditShards,
  setActiveIntentCursor,
  writeSessionBinding,
  writeSessionPidEntry,
} = await import(pathToFileURL(join(root, "dist/codex/.codex/tools/aidlc-lib.ts")).href);
const {
  cleanupTestProject,
  createOrchestrationTestProject,
  FIXTURES_DIR,
} = await import(pathToFileURL(join(root, "tests/harness/fixtures.ts")).href);
const results: Array<Record<string, unknown>> = [];

for (const bareOverride of [false, true]) {
  const project = createOrchestrationTestProject();
  try {
    cpSync(join(root, "dist/codex/.codex"), join(project, ".codex"), { recursive: true });
    const target = createIntent(project, "native-target", "default", "feature");
    const unrelated = createIntent(project, "native-unrelated", "default", "bugfix");
    const targetState = join(target.recordDir, "aidlc-state.md");
    const unrelatedState = join(unrelated.recordDir, "aidlc-state.md");
    copyFileSync(join(FIXTURES_DIR, "state-mid-ideation.md"), targetState);
    copyFileSync(join(FIXTURES_DIR, "state-brownfield-init-done.md"), unrelatedState);
    setActiveIntentCursor(project, unrelated.dirName, "default");
    writeSessionBinding(project, "session-a", "default", target.dirName, "switch");
    writeSessionBinding(project, "session-b", "default", unrelated.dirName, "switch");
    writeSessionPidEntry(project, process.pid, "session-b");
    const targetBefore = readFileSync(targetState, "utf-8");
    const unrelatedBefore = readFileSync(unrelatedState, "utf-8");
    const targetAuditBefore = readAllAuditShards(project, target.dirName, "default");
    const unrelatedAuditBefore = readAllAuditShards(project, unrelated.dirName, "default");
    const env = { ...process.env };
    delete env.AIDLC_SESSION_OVERRIDE;
    delete env.AIDLC_SESSION_OVERRIDE_SOURCE;
    delete env.AIDLC_HARNESS_DIR;
    delete env.AIDLC_HARNESS_NAME;
    env.CODEX_THREAD_ID = "session-a";
    if (bareOverride) env.AIDLC_SESSION_OVERRIDE = "session-a";
    const run = Bun.spawnSync({
      cmd: [binary, "engine", "orchestrate", "park", "--project-dir", project],
      cwd: project,
      env,
      stdout: "pipe",
      stderr: "pipe",
      timeout: 30_000,
    });
    const stdout = run.stdout.toString();
    const stderr = run.stderr.toString();
    if (bareOverride) {
      assert.notEqual(run.exitCode, 0, stdout + stderr);
      assert.match(stderr, /Session override .*session-a.* conflicts with the owning conversation .*session-b/);
      assert.equal(readFileSync(targetState, "utf-8"), targetBefore);
      assert.equal(readAllAuditShards(project, target.dirName, "default"), targetAuditBefore);
    } else {
      assert.equal(run.exitCode, 0, stdout + stderr);
      assert.equal(JSON.parse(stdout).kind, "parked", stdout + stderr);
      assert.match(readFileSync(targetState, "utf-8"), /- \*\*Parked\*\*:/);
      assert.match(readAllAuditShards(project, target.dirName, "default"), /WORKFLOW_PARKED/);
    }
    assert.equal(readFileSync(unrelatedState, "utf-8"), unrelatedBefore);
    assert.equal(readAllAuditShards(project, unrelated.dirName, "default"), unrelatedAuditBefore);
    results.push({
      case: bareOverride ? "bare override still rejected" : "native identity reaches compiled state child",
      passed: true,
      exitCode: run.exitCode,
      unrelatedStateAndAuditUnchanged: true,
    });
  } finally {
    cleanupTestProject(project);
  }
}

console.log(JSON.stringify({
  binary,
  sha256: createHash("sha256").update(readFileSync(binary)).digest("hex"),
  results,
}, null, 2));
