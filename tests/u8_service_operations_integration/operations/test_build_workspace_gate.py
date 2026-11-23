"""The workspace build's gate (U8 plan Steps 95(k) and 97(d); D7 caching and
csp-no-inline-script, P6).

`scripts/u8_build_workspace.py` marks only Vite's content-hashed assets cacheable, writes a
`.gz` copy beside each with a header mtime of 0, and refuses a build that holds an inline
script, leaving no manifest. Every build here is a fixture `dist` in `tmp_path`; no
`vite build` runs.

The planted markup cases of build batch 9a's fix passes (`html.parser` and a browser
reading a page differently) stay in `operations/test_u8_tool.py`, where they were
written, so each runs exactly once.

The lead's check after build batch 9a (cicd-pipeline § 11 `ci/5/write-token`): the
complete-verification workflow grants no job a write permission, and, the clause's own
subject (§ 4), release.yml's workspace build job holds `contents: read` with no stored
credentials, while only its `release` and `attach` jobs hold `contents: write`.
"""

from __future__ import annotations

import gzip
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
INDEX = ('<!doctype html><html lang="ko"><head>'
         '<script type="module" src="/assets/index-D4rcttfr.js"></script>'
         '<link rel="stylesheet" href="/assets/index-wACSqtyO.css"></head>'
         '<body><div id="root"></div></body></html>')
STATIC = '<!doctype html><html lang="ko"><body><main><a href="/">DocSuri</a></main></body></html>'
HASHED = ("assets/index-D4rcttfr.js", "assets/index-wACSqtyO.css")


@pytest.fixture
def gate():
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    import u8_build_workspace

    return u8_build_workspace


def fixture_frontend(tmp_path: Path) -> Path:
    """A frontend whose `dist` holds the shell, its two hashed assets, an unhashed script,
    an image and the three script-free pages."""
    frontend = tmp_path / "frontend"
    dist = frontend / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(INDEX)
    (dist / "assets/index-D4rcttfr.js").write_text("console.log('shell');\n" * 40)
    (dist / "assets/index-wACSqtyO.css").write_text("body { margin: 0; }\n" * 40)
    (dist / "assets/plain.js").write_text("export const plain = 1;\n")
    (dist / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n" + bytes(range(64)))
    for page in ("privacy.html", "terms.html", "maintenance.html"):
        (dist / page).write_text(STATIC)
    return frontend


def test_only_content_hashed_assets_are_marked_cacheable(gate, tmp_path):
    from backend.production_boundary import BuildManifest

    dist = fixture_frontend(tmp_path) / "dist"
    gate.manifest(dist)
    entries = json.loads((dist / gate.MANIFEST).read_text())["files"]
    marked = {entry["path"]: entry["contentHashed"] for entry in entries}
    assert set(marked) == {*HASHED, "assets/plain.js", "index.html", "logo.png",
                           "privacy.html", "terms.html", "maintenance.html"}
    assert sorted(path for path, hashed in marked.items() if hashed) == sorted(HASHED)
    copies = sorted(path.relative_to(dist).as_posix() for path in dist.rglob("*.gz"))
    assert copies == sorted(f"{path}.gz" for path in HASHED)
    for path in HASHED:
        packed = (dist / f"{path}.gz").read_bytes()
        assert gzip.decompress(packed) == (dist / path).read_bytes()
        # The gzip header's MTIME field (bytes 4-7) is zero.
        assert packed[4:8] == b"\x00\x00\x00\x00"
    assert sorted(BuildManifest.load(dist).files) == sorted(f"/{path}" for path in HASHED)


PLANTED = [
    ("index.html", INDEX.replace('<div id="root"></div>',
                                 '<div id="root"></div><script>start()</script>')),
    ("privacy.html", STATIC.replace("<main>", '<main onclick="go()">')),
    ("terms.html", STATIC.replace('href="/"', 'href="javascript:void(0)"')),
    ("maintenance.html", STATIC.replace("</main>", "<script>reload()</script></main>")),
    ("extra/page.html", STATIC.replace("</main>", "<script>nested()</script></main>")),
]


@pytest.mark.parametrize(("page", "markup"), PLANTED,
                         ids=[page for page, _ in PLANTED])
def test_a_build_with_an_inline_script_is_refused(gate, tmp_path, monkeypatch, capsys, page,
                                                  markup):
    clean = fixture_frontend(tmp_path / "clean")
    built = gate.build(clean, run=lambda frontend: None)
    assert built["state"] == "built" and (clean / "dist" / gate.MANIFEST).is_file()

    frontend = fixture_frontend(tmp_path / "planted")
    target = frontend / "dist" / page
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(markup)
    with pytest.raises(gate.BuildRefused, match="the build holds an inline script"):
        gate.build(frontend, run=lambda folder: None)
    assert not (frontend / "dist" / gate.MANIFEST).exists()

    # Through `main`, with the build's child faked to succeed: no `vite build` runs.
    ran = []

    def fake_run(args, **options):
        ran.append(args)
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(gate.subprocess, "run", fake_run)
    capsys.readouterr()
    assert gate.main(["--frontend", str(frontend)]) == 1
    printed = capsys.readouterr().out.splitlines()
    assert [json.loads(line) for line in printed] == [
        {"state": "refused", "reason": "the build holds an inline script"}]
    assert ran == [["corepack", "pnpm@9.15.9", "--dir", str(frontend.resolve()), "exec",
                    "vite", "build"]]
    assert not (frontend / "dist" / gate.MANIFEST).exists()


# --- the lead's check after build batch 9a: no write token (cicd-pipeline § 11 ci/5) -------


WRITE_SCOPES = ("write", "write-all")


def granted_writes(permissions) -> list[str]:
    """The write grants a `permissions` value holds: `write-all`, or any scope at
    `write`."""
    if permissions is None:
        return []
    if isinstance(permissions, str):
        return [permissions] if permissions in WRITE_SCOPES else []
    return [f"{scope}: {level}" for scope, level in permissions.items()
            if level in WRITE_SCOPES]


def verification_problems(workflow: dict) -> list[str]:
    """Why the complete-verification workflow grants a write: its top level is
    `contents: read` and no job, later ones included, holds a write scope."""
    found = [] if workflow.get("permissions") == {"contents": "read"} else ["top level"]
    found += [name for name, job in workflow["jobs"].items()
              if granted_writes(job.get("permissions"))]
    return found


# cicd-pipeline § 4 (:117-121) and C7: only these release jobs may hold `contents: write`;
# the workspace build's job holds `contents: read` and its checkout keeps no credentials.
RELEASE_WRITERS = frozenset({"release", "attach"})


def release_problems(workflow: dict) -> list[str]:
    """Why the release workflow lets a write token reach the workspace build."""
    found = [] if workflow.get("permissions") == {"contents": "read"} else ["top level"]
    jobs = workflow["jobs"]
    build = jobs.get("build")
    if build is None:
        return [*found, "no build job"]
    if build.get("permissions") != {"contents": "read"}:
        found.append("build: permissions")
    for step in build.get("steps", []):
        if str(step.get("uses", "")).startswith("actions/checkout@") and (
                (step.get("with") or {}).get("persist-credentials") is not False):
            found.append("build: checkout keeps credentials")
    found += [name for name, job in jobs.items()
              if name not in RELEASE_WRITERS and granted_writes(job.get("permissions"))]
    return found


def test_the_complete_verification_workflow_grants_no_job_a_write_permission():
    path = ROOT / ".github/workflows/u8-complete-verification.yml"
    workflow = yaml.safe_load(path.read_text())
    assert workflow["permissions"] == {"contents": "read"}
    jobs = workflow["jobs"]
    assert set(jobs) >= {"frontend", "backend", "browser"}
    for name, job in jobs.items():
        assert not granted_writes(job.get("permissions")), name
    assert verification_problems(workflow) == []
    # The clause's own subject (§ 4): release.yml's workspace build holds no write token.
    release = yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text())
    assert set(release["jobs"]) >= {"release", "build", "attach"}
    assert release_problems(release) == [], release_problems(release)
    # A write grant planted in an in-memory copy of each workflow fails.
    for planted in ({"contents": "write"}, "write-all"):
        copy = yaml.safe_load(path.read_text())
        copy["jobs"]["browser"]["permissions"] = planted
        assert verification_problems(copy) == ["browser"]
        copy = yaml.safe_load(path.read_text())
        copy["jobs"]["later"] = {"permissions": planted}
        assert verification_problems(copy) == ["later"]
        copy = yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text())
        copy["jobs"]["build"]["permissions"] = planted
        assert release_problems(copy) == ["build: permissions", "build"]
        copy = yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text())
        copy["jobs"]["later"] = {"permissions": planted}
        assert release_problems(copy) == ["later"]
    copy = yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text())
    copy["permissions"] = {"contents": "write"}
    assert release_problems(copy) == ["top level"]
    copy = yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text())
    copy["jobs"]["build"]["steps"][0]["with"].pop("persist-credentials")
    assert release_problems(copy) == ["build: checkout keeps credentials"]
    # The reader itself catches each form of grant.
    assert granted_writes({"contents": "write"}) == ["contents: write"]
    assert granted_writes({"contents": "read", "pull-requests": "write"}) == [
        "pull-requests: write"]
    assert granted_writes("write-all") == ["write-all"]
    assert granted_writes("read-all") == [] and granted_writes({"contents": "read"}) == []
