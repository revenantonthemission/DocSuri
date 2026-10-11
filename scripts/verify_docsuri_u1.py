#!/usr/bin/env python3
"""Bounded, manifest-scoped U1 development runner; never a unit approval."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import stat
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
RUN = Path('/tmp/docsuri-u1-run').resolve()
IMAGE = 'postgres@sha256:a3b7f434b2dc57ce85a67e171163eb8ab1a1ebcb39d27484661f26b1dfbe30d6'
GIB = 1024 ** 3
PYTHON = ROOT / 'backend/.venv/bin/python'
SCOPES = ('database', 'repository', 'component', 'contracts', 'model', 'integration', 'operations')
PHASES = ('setup', 'runner-readiness', *SCOPES, 'frontend', 'browser', 'coverage', 'teardown')
LABEL = 'dev.docsuri.u1.run'
LOCKS = ('backend/uv.lock', 'frontend/pnpm-lock.yaml', 'shared/python/uv.lock')


def source_identity() -> dict:
    """Bind evidence to actual tracked and newly authored bytes, not just HEAD."""
    result = require(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard',
                      '--', 'backend', 'frontend', 'shared', 'scripts',
                      'tests/u1_integrated_paper_journey', 'ops'])
    files = {}
    for name in sorted(set(result.stdout.split('\0')) - {''}):
        path = ROOT / name
        if path.is_symlink():
            raise Refused('source inventory contains symlink')
        files[name] = digest(path) if path.is_file() else None
    encoded = json.dumps(files, sort_keys=True).encode()
    return {'head': require(['git', 'rev-parse', 'HEAD']).stdout.strip(),
            'sha256': hashlib.sha256(encoded).hexdigest(), 'files': files}


class Refused(RuntimeError):
    """A bounded precondition failed; no successful behavioral result exists."""


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def private_json(path: Path, value: object) -> None:
    """Publish only in this manifest-owned directory; never follow a symlink."""
    if path.parent.resolve() != RUN or path.is_symlink():
        raise Refused('unsafe private record path')
    temporary = path.with_name(path.name + '.pending')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, sort_keys=True, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def clean_environment() -> dict[str, str]:
    # Do not pass production database, cloud credentials or provider settings.
    allowed = ('PATH', 'LANG', 'LC_ALL', 'TMPDIR', 'SYSTEMROOT')
    return {name: os.environ[name] for name in allowed if name in os.environ}


def command(args: list[str], *, cwd: Path = ROOT, timeout: int = 120,
            extra: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    env = clean_environment()
    env.update(extra or {})
    try:
        return subprocess.run(args, cwd=cwd, env=env, capture_output=True,
                              text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Refused(f'command unavailable or timed out: {args[0]}') from exc


def require(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    result = command(args, **kwargs)
    if result.returncode:
        raise Refused(f'command failed with exit {result.returncode}: {args[0]}')
    return result


def headroom() -> None:
    # Reserve the full remaining mounted/runtime + recovery + build allocation.
    if shutil.disk_usage(ROOT).free < 12 * GIB:
        raise Refused('less than 8 GiB host floor plus 4 GiB allocated headroom')


def load_manifest(path: Path) -> dict:
    if path != RUN / 'environment.json' or path.is_symlink():
        raise Refused('environment-file must be the exact isolated U1 manifest')
    for candidate in (RUN, path, RUN / 'ownership.json'):
        info = candidate.lstat()
        if stat.S_ISLNK(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise Refused('fixture ownership or private permissions do not match')
    value = json.loads(path.read_text())
    marker = json.loads((RUN / 'ownership.json').read_text())
    if marker != {'runId': value.get('runId'), 'manifestSha256': digest(path)}:
        raise Refused('ownership marker does not match exact manifest bytes')
    if value.get('profile') != 'synthetic-local' or value.get('repository') != str(ROOT):
        raise Refused('wrong repository/profile')
    if not re.fullmatch(r'docsuri-u1-[0-9a-f]{16}', value.get('runId', '')):
        raise Refused('invalid resource ownership identity')
    if value.get('databaseImage') != IMAGE:
        raise Refused('database image identity changed')
    return value


def resource_matches(kind: str, name: str, run_id: str) -> bool:
    result = command(['docker', kind, 'inspect', name])
    if result.returncode:
        return False
    items = json.loads(result.stdout)
    labels = items[0].get('Labels') if kind == 'volume' else items[0].get('Config', {}).get('Labels')
    return (labels or {}).get(LABEL) == run_id


def setup(path: Path) -> dict:
    headroom()
    if RUN.exists():
        value = load_manifest(path)
        if not resource_matches('container', value['container'], value['runId']):
            raise Refused('existing manifest has missing or foreign container; recover explicitly')
        # Initial setup-only credential record is separated before an API can
        # consume this public resource manifest. Never hand migration authority
        # to the runtime application profile.
        if 'databaseAdminPassword' in value:
            private_json(RUN / 'migration-credentials.json',
                         {'databaseAdminPassword': value.pop('databaseAdminPassword')})
            private_json(path, value)
            private_json(RUN / 'ownership.json', {'runId': value['runId'], 'manifestSha256': digest(path)})
        current_locks = {name: digest(ROOT / name) for name in LOCKS}
        if value['locks'] != current_locks:
            # An explicit setup invocation adopts an authored dependency change,
            # preserves the old configuration identity, and requires fresh tests.
            value.setdefault('configurationHistory', []).append(
                {'locks': value['locks'], 'replacedAt': time.time()})
            value['locks'] = current_locks
            private_json(path, value)
            private_json(RUN / 'ownership.json', {'runId': value['runId'], 'manifestSha256': digest(path)})
        return value
    require(['docker', 'image', 'inspect', IMAGE])  # Never pull an absent image.
    RUN.mkdir(mode=0o700)
    run_id = 'docsuri-u1-' + secrets.token_hex(8)
    value = {
        'profile': 'synthetic-local', 'repository': str(ROOT), 'runId': run_id,
        'container': run_id, 'volume': run_id + '-pgdata', 'databaseImage': IMAGE,
        'database': 'docsuri_u1', 'databasePort': 15439, 'applicationPort': 18039,
        'modelPort': 11439,
        'createdAt': time.time(), 'expiresAt': time.time() + 86400,
        'sourceSha': require(['git', 'rev-parse', 'HEAD']).stdout.strip(),
        'limits': {'hostFreeBytes': 8 * GIB, 'buildBytes': 2 * GIB,
                   'runtimeBytes': GIB, 'recoveryBytes': GIB, 'postgresMemory': 512 * 1024 ** 2},
        'locks': {p: digest(ROOT / p) for p in LOCKS},
        'fixtureAccounts': [], 'fixturePapers': [],
    }
    private_json(path, value)
    private_json(RUN / 'ownership.json', {'runId': run_id, 'manifestSha256': digest(path)})
    administrator_password = secrets.token_urlsafe(32)
    private_json(RUN / 'migration-credentials.json', {'databaseAdminPassword': administrator_password})
    require(['docker', 'volume', 'create', '--label', f'{LABEL}={run_id}', value['volume']])
    require(['docker', 'run', '-d', '--name', run_id, '--label', f'{LABEL}={run_id}',
             '--memory', '512m', '--cpus', '0.5', '--pids-limit', '64', '--read-only',
             '--tmpfs', '/tmp:rw,noexec,nosuid,size=16m', '--tmpfs', '/var/run/postgresql:rw,noexec,nosuid,size=16m',
             '-p', '127.0.0.1:15439:5432', '--mount', f'type=volume,src={value["volume"]},dst=/var/lib/postgresql/data',
             '-e', 'POSTGRES_PASSWORD', '-e', 'POSTGRES_DB=docsuri_u1',
             '-e', 'POSTGRES_INITDB_ARGS=--data-checksums --auth-host=scram-sha-256',
             IMAGE, '-c', 'shared_buffers=32MB', '-c', 'work_mem=2MB', '-c', 'max_connections=12',
             '-c', 'statement_timeout=5000', '-c', 'lock_timeout=2000',
             '-c', 'idle_in_transaction_session_timeout=5000', '-c', 'max_wal_size=128MB'],
            extra={'POSTGRES_PASSWORD': administrator_password})
    for _ in range(30):
        result = command(['docker', 'exec', run_id, 'pg_isready', '-U', 'postgres', '-d', 'docsuri_u1'], timeout=3)
        if result.returncode == 0:
            return value
        time.sleep(0.5)
    raise Refused('owned PostgreSQL did not become ready; manifest preserved for recovery')


def python_args(phase: str, *, collect: bool = False) -> list[str]:
    directory = ROOT / 'tests/u1_integrated_paper_journey' / phase
    if not directory.is_dir() or directory.is_symlink():
        raise Refused(f'{phase}: required test directory not authored')
    args = [str(PYTHON), '-m', 'pytest', '-c', 'backend/pytest.u1-paper-journey.ini',
            str(directory), '-m', 'u1_' + phase, '-p', 'no:cacheprovider']
    return args + (['--collect-only', '-q'] if collect else
                   ['-q', '--junitxml', str(RUN / f'{phase}-junit.xml')])


def phase_commands(phase: str) -> tuple[list[str], list[str], Path]:
    if phase in SCOPES:
        return python_args(phase, collect=True), python_args(phase), ROOT
    if phase == 'frontend':
        base = ['corepack', 'pnpm@9.15.9', 'exec', 'vitest']
        config = ['--config', 'vitest.u1-paper-journey.config.ts']
        return base + ['list', '--json'] + config, base + ['run'] + config + [
            '--reporter=json', '--outputFile', str(RUN / 'frontend-outcomes.json')], ROOT / 'frontend'
    if phase == 'browser':
        base = ['corepack', 'pnpm@9.15.9', 'exec', 'playwright', 'test', '--config', 'playwright.u1-paper-journey.config.ts']
        return base + ['--list'], base + ['--reporter=json'], ROOT / 'frontend'
    raise Refused('coverage requires a completed explicit source inventory; not yet available')


def run_phase(phase: str, value: dict, path: Path) -> None:
    collect, execute, cwd = phase_commands(phase)
    extra = {'DOCSURI_U1_ENVIRONMENT_FILE': str(path),
             'DOCSURI_U1_ORIGIN': f'http://127.0.0.1:{value["applicationPort"]}'}
    result = command(collect, cwd=cwd, extra=extra)
    if phase in SCOPES:
        match = re.search(r'(\d+) tests? collected', result.stdout)
        count = int(match[1]) if match else 0
    elif phase == 'frontend':
        try:
            count = len(json.loads(result.stdout))
        except ValueError:
            count = 0
    else:
        match = re.search(r'Total: (\d+) tests?', result.stdout)
        count = int(match[1]) if match else 0
    identity = source_identity()
    report = {'phase': phase, 'source': identity,
              'collectionCommand': collect, 'collectionExit': result.returncode,
              'collected': count, 'executedCommand': execute, 'executedExit': None, 'timestamp': time.time()}
    if result.returncode or count < 1:
        private_json(RUN / f'{phase}-result.json', report)
        raise Refused(f'{phase}: collection failed or empty; no behavior passed')
    outcome_path = RUN / (f'{phase}-junit.xml' if phase in SCOPES else f'{phase}-outcomes.json')
    if outcome_path.is_symlink():
        raise Refused('unsafe prior outcome report')
    outcome_path.unlink(missing_ok=True)
    result = command(execute, cwd=cwd, extra=extra, timeout=1800)
    report['executedExit'] = result.returncode
    if phase in SCOPES:
        xml_path = RUN / f'{phase}-junit.xml'
        try:
            suites = ET.parse(xml_path).getroot().iter('testsuite')
            counts = {key: 0 for key in ('tests', 'failures', 'errors', 'skipped')}
            for suite in suites:
                for key in counts:
                    counts[key] += int(suite.get(key, '0'))
            counts['passed'] = counts['tests'] - sum(counts[k] for k in ('failures', 'errors', 'skipped'))
            report['outcomes'] = counts
        except (OSError, ValueError, ET.ParseError):
            report['outcomes'] = {'passed': 0, 'missingReport': True}
    else:
        try:
            outcomes = json.loads(outcome_path.read_text() if phase == 'frontend' else result.stdout)
            if phase == 'frontend':
                report['outcomes'] = {'passed': outcomes['numPassedTests'],
                                      'skipped': outcomes['numPendingTests'] + outcomes.get('numTodoTests', 0),
                                      'failures': outcomes['numFailedTests']}
            else:
                stats = outcomes['stats']
                report['outcomes'] = {'passed': stats['expected'], 'skipped': stats['skipped'],
                                      'failures': stats['unexpected'] + stats['flaky']}
        except (OSError, ValueError, KeyError):
            report['outcomes'] = {'passed': 0, 'missingReport': True}
    report['sourceUnchangedDuringRun'] = source_identity()['sha256'] == identity['sha256']
    private_json(RUN / f'{phase}-result.json', report)
    print(result.stdout)
    print(result.stderr, file=sys.stderr)
    if result.returncode:
        raise Refused(f'{phase}: child failure propagated ({result.returncode})')
    if not report['sourceUnchangedDuringRun']:
        raise Refused(f'{phase}: source changed during execution; repeat with stable bytes')
    if (report['outcomes']['passed'] < 1 or report['outcomes'].get('skipped', 0)
            or report['outcomes'].get('failures', 0) or report['outcomes'].get('errors', 0)):
        raise Refused(f'{phase}: required cases skipped or no passing behavior recorded')


def readiness(value: dict) -> None:
    if time.time() >= value['expiresAt']:
        raise Refused('synthetic environment retention expired')
    if not PYTHON.is_file():
        raise Refused('locked backend environment missing')
    require([str(PYTHON), '-c', 'import pytest, pytest_cov, fastapi, psycopg, psycopg_pool; from docsuri_shared.workspace import wire, execution'])
    for path, expected in value['locks'].items():
        if digest(ROOT / path) != expected:
            raise Refused('dependency lock differs from environment manifest')
    if not resource_matches('container', value['container'], value['runId']):
        raise Refused('required owned database unavailable')
    missing = [phase for phase in SCOPES if not (ROOT / 'tests/u1_integrated_paper_journey' / phase).is_dir()]
    print(json.dumps({'runnerImports': 'ready', 'notAuthored': missing,
                      'behaviorTestsPassed': False, 'requiredModelAndMountedEvidence': 'pending'}))


def teardown(value: dict) -> None:
    # No recursive filesystem removal: retain private records until evidence is extracted.
    for kind, key in (('container', 'container'), ('volume', 'volume')):
        name = value[key]
        if not resource_matches(kind, name, value['runId']):
            raise Refused('unknown or missing resource ownership; teardown refused')
    require(['docker', 'stop', '--time', '10', value['container']])
    require(['docker', 'rm', value['container']])
    require(['docker', 'volume', 'rm', value['volume']])
    print('Owned container and volume removed; private manifest/evidence retained.')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', required=True, choices=PHASES)
    parser.add_argument('--profile', required=True, choices=['synthetic-local'])
    parser.add_argument('--environment-file', required=True, type=Path)
    args = parser.parse_args()
    path = args.environment_file.absolute()
    if path != Path('/tmp/docsuri-u1-run/environment.json'):
        parser.error('only the approved isolated environment-file is accepted')
    path = RUN / 'environment.json'
    try:
        value = setup(path) if args.phase == 'setup' else load_manifest(path)
        if args.phase == 'setup':
            print('Owned persistent PostgreSQL created; owner migrations and behavioral evidence pending.')
        elif args.phase == 'runner-readiness':
            readiness(value)
        elif args.phase == 'teardown':
            teardown(value)
        else:
            readiness(value)
            run_phase(args.phase, value, path)
        return 0
    except (Refused, OSError, ValueError, KeyError) as exc:
        print(f'U1 REFUSED: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
