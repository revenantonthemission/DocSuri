"""The installer (U8 plan Step 38; infrastructure-specification § 4, Workflow 20, D8),
under a temporary prefix with fake tools (`arrangement_flows`): no macOS tool, sudo,
keychain, launch job or network call is ever made.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import os
import re
import secrets
import stat
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from docsuri_ops.arrangement import manifest
from docsuri_ops.arrangement.checklist import InstallationLog, NotConfirmed
from docsuri_ops.arrangement.installer import PHASES, Installer, manifest_now
from docsuri_ops.arrangement.phases import PHASE_NAMES, PhaseFailed, RuntimesPhase
from docsuri_ops.isolation_macos import rules_digest
from tests.u8_service_operations_integration import arrangement_flows as af

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def stage(tmp_path, monkeypatch):
    return af.install_stage(tmp_path, monkeypatch)


def applied(stage) -> dict:
    outcome = Installer(stage.ctx).apply()
    assert outcome.failed is None, outcome.as_dict()
    return outcome.as_dict()


@contextlib.contextmanager
def every_logger_at_debug(caplog):
    """U8 plan Step 76(d)'s "every logger captured at DEBUG": every logger in
    `logging.Logger.manager.loggerDict` and the root set to DEBUG, so no propagating
    logger's own level drops a record before it reaches caplog; caplog's handler at DEBUG
    on the root and on every non-propagating logger; each logger's level, handlers and
    `propagate` restored afterwards."""
    handler = caplog.handler
    root = logging.getLogger()
    every = [root] + [logger for logger in list(logging.Logger.manager.loggerDict.values())
                      if isinstance(logger, logging.Logger)]
    attached = [root] + [logger for logger in every[1:] if not logger.propagate]
    saved = [(logger, logger.level, list(logger.handlers), logger.propagate)
             for logger in every]
    level = handler.level
    handler.setLevel(logging.DEBUG)
    try:
        for logger in every:
            logger.setLevel(logging.DEBUG)
        for logger in attached:
            if handler not in logger.handlers:
                logger.addHandler(handler)
        yield handler
    finally:
        for logger, before, handlers, propagate in saved:
            logger.setLevel(before)
            logger.handlers[:] = handlers
            logger.propagate = propagate
        handler.setLevel(level)


def record_text(record: logging.LogRecord) -> str:
    """A captured record as text: its message with any exception and stack it carries."""
    return logging.Formatter().format(record)


HEX64 = re.compile(rb"[0-9a-f]{64}")
ORBSTACK = "/Users/revenantonthemission/Library/Group Containers/HUAQ24HBR6.dev.orbstack/"


# --- 1. plan mode changes nothing and lists every difference ---------------------------------


def test_plan_mode_changes_nothing_and_lists_every_difference(stage):
    before = af.tree(stage.ctx.paths.prefix.parent)
    outcome = Installer(stage.ctx).plan().as_dict()
    assert af.tree(stage.ctx.paths.prefix.parent) == before
    assert stage.tools.mutations() == [] and stage.database.scripts == []
    assert [phase["phase"] for phase in outcome["phases"]] == list(PHASE_NAMES)
    assert all(phase["changes"] > 0 for phase in outcome["phases"])
    changes = outcome["changes"]
    assert {change["phase"] for change in changes} == set(PHASE_NAMES)
    for change in changes:
        assert set(change) == {"phase", "action", "target", "difference"}
        assert change["difference"] and "->" in change["difference"] or (
            change["action"] == "checklist")
    targets = {change["target"] for change in changes}
    assert {"_docsuri_v2", "_docsuri_v2_sched", "_docsuri_v2_db", "_docsuri_models",
            "_docsuri_tunnel"} <= targets
    assert str(stage.ctx.paths.sudoers_rules) in targets
    assert str(stage.ctx.paths.pf_anchor) in targets
    assert "docsuri_v2 and docsuri_v2_platform" in targets
    # D6 and NFR3.4: the plan names the sudo rules' and each configuration's owner.
    assert {"phase": "rule-files", "action": "file", "target": str(stage.ctx.paths.sudoers_rules),
            "difference": "absent -> 0440 root"} in changes
    for origin in ("v1-web", "v2-host", "maintenance"):
        target = str(stage.ctx.paths.tunnel_config / f"{origin}.yml")
        found = [change for change in changes if change["target"] == target]
        assert [(change["phase"], change["difference"]) for change in found] == [
            ("rule-files", "absent -> 0644 root")], target


def test_the_installation_binds_each_store_login_to_its_actor(stage):
    """Your decision of 2026-10-26, "Bind each login to its actor": the installation binds
    the operator's store login to you, the scheduler's to the scheduler account and the
    reader's to the service account; its script makes the reader role and keeps the reader
    login out of the runtime role; the operator's driver configuration names your login
    ("Through your login")."""
    import json

    from docsuri_ops.production_tool import PLATFORM_LOGINS

    applied(stage)
    recorded = json.loads((stage.ctx.paths.control / "platform-authorities.json").read_bytes())
    actors = recorded["actors"]
    assert stage.database.store_.logins == {
        PLATFORM_LOGINS["operator"]: (actors["operator"], "operator"),
        PLATFORM_LOGINS["scheduler"]: (actors["scheduler"], "scheduler"),
        PLATFORM_LOGINS["reader"]: (actors["service"], "reader"),
    }
    script = "\n".join(stage.database.scripts)
    reader = PLATFORM_LOGINS["reader"]
    assert f"REVOKE platform_control_runtime FROM {reader};" in script
    assert f"GRANT platform_control_u8_reader TO {reader} WITH INHERIT TRUE" in script
    assert f"GRANT platform_control_runtime TO {reader}" not in script
    config = json.loads((stage.ctx.paths.effects / "operator" / "driver.json").read_bytes())
    assert config["operatorLogin"] == actors["operator"]
    # A binding is never moved to another actor.
    from docsuri_ops.platform_control.errors import ControlError
    from docsuri_ops.u8_platform.u8_protocols import bind_store_logins

    with pytest.raises(ControlError):
        bind_store_logins(stage.database.store_, {"reader": reader},
                          {**actors, "service": actors["operator"]})


def test_an_existing_install_binds_its_unbound_logins_and_verify_checks_each(stage):
    """Review findings (Minor, R16 and R17): on an existing install (every holder present,
    `platform-authorities.json` recorded) whose store logins are unbound and whose reader
    login still holds the runtime role, phase 3 produces a binding change: each login is
    bound to its recorded actor and the reader taken out of the runtime role; the phase's
    verify refuses a store whose login is unbound, bound otherwise or a runtime reader,
    and a second apply then changes nothing."""
    import json

    from docsuri_ops.arrangement.installer import store_login_drift
    from docsuri_ops.production_tool import PLATFORM_LOGINS

    applied(stage)
    assert store_login_drift(stage.ctx) == []
    store = stage.database.store_
    bound = dict(store.logins)
    reader = PLATFORM_LOGINS["reader"]
    # As an install made before the binding: no login bound, the reader a runtime member.
    store.logins.clear()
    store.runtime_members.add(reader)
    assert store_login_drift(stage.ctx) == ["operator", "scheduler", "reader"]
    outcome = Installer(stage.ctx).plan().as_dict()
    changes = [change for change in outcome["changes"] if change["action"] == "store-logins"]
    assert len(changes) == 1 and changes[0]["phase"] == "folders-and-database"
    assert "operator,scheduler,reader unbound" in changes[0]["difference"]
    assert store.logins == {}  # plan mode binds nothing
    scripts = len(stage.database.scripts)
    outcome = Installer(stage.ctx).apply()
    assert outcome.failed is None, outcome.as_dict()
    assert store.logins == bound and reader not in store.runtime_members
    assert len(stage.database.scripts) == scripts + 1
    assert f"REVOKE platform_control_runtime FROM {reader};" in stage.database.scripts[-1]
    assert store_login_drift(stage.ctx) == []
    second = Installer(stage.ctx).apply()
    assert second.failed is None and not [
        change for change in second.as_dict()["changes"] if change["action"] == "store-logins"]
    # Verify refuses each drift: a runtime reader, a login bound to another actor, and an
    # unbound login (the binding change then runs again on the next apply).
    recorded = json.loads((stage.ctx.paths.control / "platform-authorities.json").read_bytes())
    store.runtime_members.add(reader)
    assert store_login_drift(stage.ctx) == ["reader"]
    assert Installer(stage.ctx).apply().failed is None  # bound again
    assert reader not in store.runtime_members
    store.logins[PLATFORM_LOGINS["scheduler"]] = (recorded["actors"]["operator"], "scheduler")
    assert store_login_drift(stage.ctx) == ["scheduler"]
    failed = Installer(stage.ctx).apply()  # never rebound: the change itself fails
    assert (failed.failed, failed.reason) == ("folders-and-database",
                                              "store-login-bound-elsewhere:scheduler")
    from docsuri_ops.arrangement.installer import FoldersDatabasePhase
    from docsuri_ops.arrangement.phases import PhaseFailed

    with pytest.raises(PhaseFailed, match="store-login-unbound:scheduler"):
        FoldersDatabasePhase().verify(stage.ctx)
    store.logins[PLATFORM_LOGINS["scheduler"]] = bound[PLATFORM_LOGINS["scheduler"]]
    del store.logins[PLATFORM_LOGINS["operator"]]
    assert store_login_drift(stage.ctx) == ["operator"]
    assert Installer(stage.ctx).apply().failed is None and store.logins == bound


def test_verify_refuses_a_store_whose_scheduler_grants_differ(stage):
    """Review finding (Minor, R15): an install provisioned before a grant changed keeps
    its old grants (provisioning returns early once `platform-authorities.json` exists),
    so the phase's verify reads each scheduler grant back and compares it with
    `SCHEDULER_GRANTS`: a routine grant that still holds the restore fails the phase."""
    import json

    from docsuri_ops.arrangement.installer import scheduler_grant_drift

    applied(stage)
    assert scheduler_grant_drift(stage.ctx) == []
    recorded = json.loads((stage.ctx.paths.control / "platform-authorities.json").read_bytes())
    routine = stage.database.store_.authorities[recorded["authorities"]["schedulerRoutine"]]
    original = list(routine["operations"])
    # The grant before the person's decision of 2026-10-26 ("Drop it"), still holding
    # the disposal, fails the verify too.
    routine["operations"] = [*original, "platform.copy.dispose"]
    assert scheduler_grant_drift(stage.ctx) == ["schedulerRoutine"]
    routine["operations"] = [*original, "platform.database.restore"]
    assert scheduler_grant_drift(stage.ctx) == ["schedulerRoutine"]
    outcome = Installer(stage.ctx).apply()
    assert (outcome.failed, outcome.reason) == ("folders-and-database",
                                                "platform-grant-drift:schedulerRoutine")
    del stage.database.store_.authorities[recorded["authorities"]["schedulerRestore"]]
    assert scheduler_grant_drift(stage.ctx) == ["schedulerRoutine", "schedulerRestore"]


# --- 2. a second run changes nothing -------------------------------------------------------------


def test_a_second_run_changes_nothing(stage):
    first = applied(stage)
    assert first["changes"] and len(first["phases"]) == len(PHASES)
    recorded = stage.ctx.paths.arrangement_manifest.read_bytes()
    mutations = len(stage.tools.mutations())
    scripts = len(stage.database.scripts)
    tree = af.tree(stage.ctx.paths.prefix)
    second = applied(stage)
    assert second["changes"] == []
    assert len(stage.tools.mutations()) == mutations and len(stage.database.scripts) == scripts
    assert stage.ctx.paths.arrangement_manifest.read_bytes() == recorded
    log = stage.ctx.paths.installation_log
    assert {k: v for k, v in af.tree(stage.ctx.paths.prefix).items() if k != str(log)} == {
        k: v for k, v in tree.items() if k != str(log)}
    plan = Installer(stage.ctx).plan().as_dict()
    assert plan["changes"] == []


def test_the_installed_arrangement_has_its_owners_secrets_and_jobs(stage):
    applied(stage)
    tools, paths = stage.tools, stage.ctx.paths
    assert set(tools.accounts) == {"_docsuri_r1t_backup", "_docsuri_v2", "_docsuri_v2_sched",
                                   "_docsuri_v2_db", "_docsuri_models", "_docsuri_tunnel"}
    assert tools.owner(paths.profile) == 610 and tools.owner(paths.scheduler) == 611
    assert tools.owner(paths.postgres_data) == 612 and tools.owner(paths.models) == 613
    # U8 plan Step 76(b): each folder's owner and real mode.
    for path, uid, mode in (
        (paths.availability, 611, 0o755),
        (paths.postgres_socket, 612, 0o700), (paths.prefix / "postgres" / "logs", 612, 0o700),
        (paths.postgres_data / "log", 612, 0o700),
        # Your answer of 2026-11-11 ("Map the login, root rules"): root's rule folder.
        (paths.postgres_rules, 0, 0o755),
        (paths.models_state, 613, 0o700),
        (paths.tunnel_credentials, 614, 0o700), (paths.tunnel_logs, 614, 0o700),
        (paths.backup_agent, 607, 0o700),
        # D8 (security-design § 6.1): the scheduler's and the service's own folders.
        (paths.scheduler, 611, 0o700), (paths.profile, 610, 0o700),
    ):
        info = path.lstat()
        assert stat.S_ISDIR(info.st_mode), path
        assert (tools.owner(path), stat.S_IMODE(info.st_mode)) == (uid, mode), path
    assert set(tools.keychain) == {"docsuri-v2-operator", "docsuri-v2-restore",
                                   "docsuri-v2-platform", "DocSuri_Backup"}
    assert tools.exclusions == {"/Library/DocSuri/", (
        "/Users/revenantonthemission/Library/Group Containers/HUAQ24HBR6.dev.orbstack/")}
    assert {"org.docsuri.v2.postgres", "org.docsuri.models", "org.docsuri.tunnel",
            "org.docsuri.v2.pf", "org.docsuri.v2.backup-unlock", "org.docsuri.v2.host",
            "org.docsuri.v2.standing"} <= tools.jobs
    profile = json.loads((paths.profile / "environment.json").read_bytes())
    assert (profile["mode"], profile["admission"]) == ("rehearsal", "maintainer-only")
    assert profile["backupVolume"]["identity"] == af.VOLUME_ID
    scheduler = json.loads(paths.scheduler_credentials.read_bytes())
    assert set(scheduler) == {"database", "platform", "actor", "authorities"}
    assert set(scheduler["authorities"]) == {"schedulerRoutine", "schedulerRestore",
                                             "schedulerRemoval"}
    grants = {value["actor"] for value in stage.database.store_.authorities.values()}
    assert grants == {af.OPERATOR, "_docsuri_v2_sched", "_docsuri_v2"}
    removal = next(value for value in stage.database.store_.authorities.values()
                   if value["operations"] == ["platform.database.remove"])
    assert removal["scope"] == ["database-rehearsal", "database-import", "database-scratch"]
    # The person's decision of 2026-10-26 ("Give restore its own grant"): the scheduler's
    # restore is provisioned as its own grant, over the scratch database alone, and its
    # routine grant holds no restore.
    scheduler_grants = {name: stage.database.store_.authorities[identity]
                        for name, identity in scheduler["authorities"].items()}
    assert {value["actor"] for value in scheduler_grants.values()} == {"_docsuri_v2_sched"}
    assert sum(value["actor"] == "_docsuri_v2_sched"
               for value in stage.database.store_.authorities.values()) == 3
    assert (scheduler_grants["schedulerRestore"]["operations"],
            scheduler_grants["schedulerRestore"]["scope"]) == (
        ["platform.database.restore"], ["database-scratch"])
    assert "platform.database.restore" not in scheduler_grants["schedulerRoutine"]["operations"]
    # The lone ledger copy (L1-5, Step 64(c)): the scheduler's routine grant runs it on its
    # own target, the operator's routine grant takes it from the revision, and the target
    # is provisioned.
    routine = scheduler_grants["schedulerRoutine"]
    assert sorted(routine["operations"]) == sorted([
        "platform.database.backup", "platform.isolation.check", "platform.ledger.copy"])
    assert "ledger-copy" in routine["scope"]
    operator_routine = next(value for value in stage.database.store_.authorities.values()
                            if value["actor"] == af.OPERATOR
                            and "platform.decision.record" in value["operations"])
    assert "platform.ledger.copy" in operator_routine["operations"]
    assert "ledger-copy" in stage.database.store_.targets
    driver = json.loads((paths.effects / "scheduler" / "driver.json").read_bytes())
    assert driver["kind"] == "arrangement" and driver["schedulerCredentials"] == str(
        paths.scheduler_credentials)
    # The models were cloned, verified and the login account's runtime retired.
    assert not (stage.ctx.operator_home / "Library/LaunchAgents/homebrew.mxcl.ollama.plist"
                ).exists()
    assert (paths.tunnel_config / "active.yml").read_bytes() == (
        paths.tunnel_config / "v1-web.yml").read_bytes()
    assert not (paths.control / "tunnel-certificate" / "cert.pem").exists()


# --- 3. a phase that fails stops the next --------------------------------------------------------


def test_a_phase_that_fails_stops_the_next(tmp_path, monkeypatch):
    stage = af.install_stage(tmp_path, monkeypatch, wrong="cloudflared")
    outcome = Installer(stage.ctx).apply()
    assert (outcome.failed, outcome.reason) == ("runtimes", "runtime-checksum-differs:cloudflared")
    assert not stage.ctx.paths.profile.exists() or not (
        stage.ctx.paths.profile / "environment.json").exists()
    assert stage.database.scripts == [] and "org.docsuri.v2.postgres" not in stage.tools.jobs
    lines = InstallationLog(stage.ctx.paths.installation_log, clock=lambda: af.NOW,
                            base=stage.ctx.paths.prefix).lines()
    assert {"phase": "runtimes", "step": "verify", "outcome": "failed",
            "reason": "runtime-checksum-differs:cloudflared"} in [
        {k: v for k, v in line.items() if k != "ts"} for line in lines]
    assert any(line["step"] == "checksum:cloudflared" and line["outcome"] == "failed"
               for line in lines)


def test_a_phase_whose_own_check_fails_stops_there(stage):
    stage.tools.fail_lint = True
    outcome = Installer(stage.ctx).apply()
    assert outcome.failed == "rule-files"
    assert outcome.reason.startswith("launch-job-does-not-lint:")
    assert "org.docsuri.models" not in stage.tools.jobs  # phase 5 never ran


# --- 4. the arrangement manifest's digests -------------------------------------------------------


def test_the_arrangement_manifest_records_every_file_in_place(stage):
    applied(stage)
    recorded = manifest.read_manifest(stage.ctx.paths)
    assert recorded is not None and recorded.version == 1
    paths = stage.ctx.paths
    for entry in recorded.files:
        path = manifest.resolve(paths, entry.path)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry.sha256
    kinds = {entry.kind for entry in recorded.files}
    assert kinds == {"program", "rule", "config"}
    # Your answer of 2026-11-11 ("Map the login, root rules"): both rule files, root's, in
    # the root-owned rules folder, each with its digest; none is left in the data folder.
    from docsuri_ops.arrangement import render

    rendered = {item.target: item.content
                for item in render.render_postgres(paths, stage.ctx.accounts)}
    for name, digest in (("pg_hba.conf", recorded.pg_hba_sha256),
                         ("pg_ident.conf", recorded.pg_ident_sha256)):
        target = paths.postgres_rules / name
        assert digest == hashlib.sha256(target.read_bytes()).hexdigest() == hashlib.sha256(
            rendered[target]).hexdigest(), name
        assert stage.tools.owner(target) == 0 and stat.S_IMODE(target.lstat().st_mode) == 0o644
    assert recorded.as_dict()["pgIdentSha256"] == recorded.pg_ident_sha256
    assert manifest.read_manifest(paths).pg_ident_sha256 == recorded.pg_ident_sha256
    assert recorded.filter_rules_sha256 == rules_digest(af.RULES)
    by_path = {entry.path: entry for entry in recorded.files}
    assert by_path[str(paths.sudoers_rules)].kind == "rule"
    assert by_path["postgres-rules/pg_hba.conf"].owner_uid is None  # root's
    assert by_path["postgres-rules/pg_ident.conf"].owner_uid is None
    assert by_path["postgres/data/postgresql.conf"].owner_uid == 612
    assert "postgres/data/pg_hba.conf" not in by_path
    ollama = by_path["runtimes/ollama-0.40.7/ollama"]
    assert ollama.kind == "program" and ollama.root == "runtimes/ollama-0.40.7"
    # U8 plan Step 111(b) (CP-4): pgvector's library, and by Q1 its control file and
    # install script, written out as literals so the test pins the layout's reading.
    vector = by_path["runtimes/postgresql-16.14/lib/vector.dylib"]
    assert (vector.kind, vector.root, vector.owner_uid) == (
        "program", "runtimes/postgresql-16.14", None)
    for path in ("runtimes/postgresql-16.14/share/extension/vector.control",
                 "runtimes/postgresql-16.14/share/extension/vector--0.8.7.sql"):
        extension = by_path[path]
        assert (extension.kind, extension.root, extension.owner_uid) == ("config", None, None)
    # D6, NFR3.4 and L2-15: the sudo rules, the configurations, their folder and the first
    # active choice are root's; the manifest reads its root files' owner as None.
    root = stage.ctx.root_uid
    assert root == 0
    owned = [(paths.sudoers_rules, 0o440)] + [
        (paths.tunnel_config / f"{origin}.yml", 0o644)
        for origin in ("v1-web", "v2-host", "maintenance")] + [
        (paths.tunnel_config, 0o755), (paths.tunnel_config / "active.yml", 0o644)]
    for path, mode in owned:
        assert (stage.tools.owner(path), stat.S_IMODE(path.lstat().st_mode)) == (
            root, mode), path
    assert (paths.tunnel_config / "active.yml").read_bytes() == (
        paths.tunnel_config / "v1-web.yml").read_bytes()
    assert (by_path[str(paths.sudoers_rules)].kind,
            by_path[str(paths.sudoers_rules)].owner_uid) == ("rule", None)
    for origin in ("v1-web", "v2-host", "maintenance"):
        entry = by_path[f"tunnel/config/{origin}.yml"]
        assert (entry.kind, entry.owner_uid) == ("config", None), origin
    assert "tunnel/config/active.yml" not in by_path
    assert manifest.differences(paths, recorded) == []
    (paths.tunnel_config / "maintenance.yml").write_text("changed")
    assert manifest.differences(paths, recorded) == ["tunnel/config/maintenance.yml"]
    assert manifest_now(stage.ctx).as_dict()["version"] == 1


# --- 4a. pgvector's library and extension files in the runtime checks (Step 111, CP-4) -----------

SYSTEM_LIBRARY = "/usr/lib/libSystem.B.dylib"
HOMEBREW_LIBRARY = "/opt/homebrew/opt/libomp/lib/libomp.dylib"
MACHO_MAGIC = b"\xcf\xfa\xed\xfe"


def test_phase_2_runs_otool_on_pgvectors_library_and_refuses_one_linking_outside(
        stage, tmp_path):
    library = stage.ctx.paths.postgres_runtime / "lib" / "vector.dylib"
    # 1. A library under Homebrew's prefix, the case BR6.11 (0) names, stops phase 2.
    stage.tools.links[str(library)] = [SYSTEM_LIBRARY, HOMEBREW_LIBRARY]
    outcome = Installer(stage.ctx).apply()
    assert (outcome.failed, outcome.reason) == ("runtimes", "runtime-loads-outside:pgvector")
    assert stage.database.scripts == [] and "org.docsuri.v2.postgres" not in stage.tools.jobs
    lines = InstallationLog(stage.ctx.paths.installation_log, clock=lambda: af.NOW,
                            base=stage.ctx.paths.prefix).lines()
    assert {"phase": "runtimes", "step": "verify", "outcome": "failed",
            "reason": "runtime-loads-outside:pgvector"} in [
        {k: v for k, v in line.items() if k != "ts"} for line in lines]
    # 2. A library in the runtime's own folder passes.
    stage.tools.links[str(library)] = [
        SYSTEM_LIBRARY, f"{stage.ctx.paths.postgres_runtime}/lib/libpq.5.dylib"]
    assert Installer(stage.ctx).apply().failed is None
    # 3. A removed library, or a link at its name, is refused before `otool -L` runs.
    content = library.read_bytes()
    library.unlink()
    with pytest.raises(PhaseFailed) as caught:
        RuntimesPhase().verify(stage.ctx)
    assert caught.value.reason == "runtime-program-missing:pgvector"
    elsewhere = tmp_path / "elsewhere.dylib"
    elsewhere.write_bytes(content)
    library.symlink_to(elsewhere)
    with pytest.raises(PhaseFailed) as caught:
        RuntimesPhase().verify(stage.ctx)
    assert caught.value.reason == "runtime-program-missing:pgvector"
    outcome = Installer(stage.ctx).apply()  # returns: nothing escapes the `finally`
    assert (outcome.failed, outcome.reason) == ("runtimes", "runtime-program-missing:pgvector")
    recorded = manifest.read_manifest(stage.ctx.paths)
    assert recorded.entry("runtimes/postgresql-16.14/lib/vector.dylib") == manifest.Entry(
        "runtimes/postgresql-16.14/lib/vector.dylib", "program", manifest.UNREAD_DIGEST,
        "runtimes/postgresql-16.14", None)
    library.unlink()
    library.write_bytes(content)
    RuntimesPhase().verify(stage.ctx)
    # 4. By Q1, a missing control file or install script is refused.
    extension = stage.ctx.paths.postgres_runtime / "share" / "extension"
    for name in ("vector.control", "vector--0.8.7.sql"):
        kept = (extension / name).read_bytes()
        (extension / name).unlink()
        with pytest.raises(PhaseFailed) as caught:
            RuntimesPhase().verify(stage.ctx)
        assert caught.value.reason == "runtime-file-missing:pgvector", name
        (extension / name).write_bytes(kept)
    RuntimesPhase().verify(stage.ctx)


def _otool_runner(calls: list[list[str]], library: Path, outside: dict) -> object:
    """`otool -L` as `isolation_macos.MacTools` runs it: each program loads the system
    library, and the library also loads Homebrew's while `outside["library"]` is set.
    Any other command fails the test."""

    def run(argv, **_options):
        calls.append(list(argv))
        assert argv[:2] == ["/usr/bin/otool", "-L"] and len(argv) == 3, argv
        lines = [f"{argv[2]}:", f"\t{SYSTEM_LIBRARY} (compatibility version 1.0.0, "
                 "current version 1345.0.0)"]
        if argv[2] == str(library) and outside.get("library"):
            lines.append(f"\t{HOMEBREW_LIBRARY} (compatibility version 5.0.0, current "
                         "version 5.0.0)")
        return subprocess.CompletedProcess(argv, 0, stdout=("\n".join(lines) + "\n").encode(),
                                           stderr=b"")

    return run


def _isolation_check(stage, run):
    from docsuri_ops import isolation_macos
    from docsuri_ops.isolation_check import CheckContext, IsolationCheck

    return IsolationCheck(CheckContext(
        paths=stage.ctx.paths, accounts=stage.ctx.accounts,
        tools=isolation_macos.MacTools(run), clock=lambda: af.NOW, owner_uid=os.getuid()))


def test_the_isolation_check_judges_the_pgvector_library_the_installer_recorded(stage):
    from docsuri_ops.arrangement import installer
    from docsuri_ops.isolation_check import ItemFailed

    applied(stage)
    paths = stage.ctx.paths
    for entry in manifest.read_manifest(paths).files:
        if entry.kind == "program":
            program = manifest.resolve(paths, entry.path)
            os.chmod(program, 0o755)
            os.chmod(program.parent, 0o755)
    library = paths.postgres_runtime / "lib" / "vector.dylib"
    calls: list[list[str]] = []
    outside: dict = {}
    run = _otool_runner(calls, library, outside)
    # 1. As installed it passes, and `otool -L` was asked about the library itself.
    _isolation_check(stage, run).programs()
    assert ["/usr/bin/otool", "-L", str(library)] in calls
    # 2. Custody: the library, then its folder, writable by another account.
    library.chmod(0o664)
    with pytest.raises(ItemFailed, match="program-custody"):
        _isolation_check(stage, run).programs()
    library.chmod(0o755)
    library.parent.chmod(0o775)
    with pytest.raises(ItemFailed, match="program-custody"):
        _isolation_check(stage, run).programs()
    library.parent.chmod(0o755)
    # 3. Replaced bytes the manifest does not hold.
    library.write_bytes(MACHO_MAGIC + b" replaced")
    with pytest.raises(ItemFailed, match="program-digest"):
        _isolation_check(stage, run).programs()
    # 4. Recorded again, as an apply records a rebuilt library, loading Homebrew's: the
    # new digest is not in the per-digest cache, so `otool -L` runs again.
    installer.record_manifest(stage.ctx)
    outside["library"] = True
    calls.clear()
    with pytest.raises(ItemFailed, match="program-loads-outside"):
        _isolation_check(stage, run).programs()
    assert ["/usr/bin/otool", "-L", str(library)] in calls


def test_the_isolation_check_judges_pgvectors_control_file_and_install_script(stage):
    from docsuri_ops.isolation_check import ItemFailed

    applied(stage)
    paths = stage.ctx.paths
    # The fake tools keep the rendered files' other owners in memory while the check
    # reads real owners, so the manifest is narrowed to the runtimes' entries.
    recorded = manifest.read_manifest(paths)
    manifest.write_manifest(paths, manifest.Manifest(
        recorded.version, tuple(entry for entry in recorded.files
                                if entry.path.startswith("runtimes/"))),
        clock=lambda: af.NOW, owner_uid=os.getuid())
    assert not (paths.control / "arrangement-in-progress.json").exists()
    extension = paths.postgres_runtime / "share" / "extension"
    control, script = extension / "vector.control", extension / "vector--0.8.7.sql"
    for path in (control, script):
        path.chmod(0o644)
    run = _otool_runner([], paths.postgres_runtime / "lib" / "vector.dylib", {})
    _isolation_check(stage, run).files()
    original = control.read_bytes()
    control.write_bytes(original.replace(
        b"'$libdir/vector'", b"'/opt/homebrew/lib/postgresql@16/vector'"))
    with pytest.raises(ItemFailed, match="file-differs"):
        _isolation_check(stage, run).files()
    control.write_bytes(original)
    _isolation_check(stage, run).files()
    script.chmod(0o664)
    with pytest.raises(ItemFailed, match="file-differs"):
        _isolation_check(stage, run).files()


# --- 5. checklist items wait and record no secret -------------------------------------------------


def test_checklist_items_wait_and_record_only_their_outcome(tmp_path, monkeypatch):
    stage = af.install_stage(tmp_path, monkeypatch, decline="old-certificate-revoked")
    outcome = Installer(stage.ctx).apply()
    assert (outcome.failed, outcome.reason) == ("models-and-tunnel", "old-certificate-revoked")
    lines = stage.ctx.log.lines()
    checklist = [line for line in lines if line["step"].startswith("checklist")]
    for line in checklist:
        assert set(line) <= {"ts", "phase", "step", "outcome", "item"}
    assert {"phase": "models-and-tunnel", "step": "checklist", "outcome": "declined",
            "item": "old-certificate-revoked"} in [
        {k: v for k, v in line.items() if k != "ts"} for line in checklist]
    raw = stage.ctx.paths.installation_log.read_text()
    assert not any(answer in raw for answer in stage.answers)
    # The ping addresses went only to the scheduler's own file.
    addresses = json.loads(stage.ctx.paths.healthchecks.read_bytes())
    assert sorted(addresses.values()) == sorted(stage.answers)
    # An item confirmed earlier is not asked again on the next run.
    asked = list(stage.asked)
    stage.asked.clear()
    with pytest.raises(NotConfirmed):
        stage.ctx.checklist.wait("models-and-tunnel", "old-certificate-revoked")
    assert "other-tunnel-without-certificate" in asked
    stage.ctx.checklist.wait("models-and-tunnel", "other-tunnel-without-certificate")
    assert stage.asked == ["old-certificate-revoked"]


# --- 6. the installation log holds no secret ------------------------------------------------------


def test_the_installation_log_holds_no_secret(stage, tmp_path, caplog):
    with every_logger_at_debug(caplog) as handler:
        applied(stage)
    assert not [record for record in handler.records
                if any(secret.decode() in record_text(record) for secret in stage.secrets)]
    # U8 plan Step 76(g): the log's one place, the profile's evidence folder.
    prefix = stage.ctx.paths.prefix
    expected = prefix / "profile" / "evidence" / "installation-log.jsonl"
    assert stage.ctx.paths.installation_log == expected
    info = expected.lstat()
    assert stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o600
    evidence = prefix / "profile" / "evidence"
    assert stat.S_ISDIR(evidence.lstat().st_mode)
    assert stat.S_IMODE(evidence.lstat().st_mode) == 0o700
    assert stage.tools.owner(evidence) == 610
    assert list(tmp_path.rglob("installation-log*")) == [expected]
    raw = stage.ctx.paths.installation_log.read_bytes()
    assert stage.secrets and not any(secret in raw for secret in stage.secrets)
    for secret in stage.secrets:  # every generated secret reached exactly its holder
        held = [path for path in stage.ctx.paths.prefix.rglob("*") if path.is_file()
                and secret in path.read_bytes()]
        in_keychain = secret in stage.tools.keychain.values()
        assert held or in_keychain
    script = stage.database.scripts[0]
    assert sum(secret.decode() in script for secret in stage.secrets) >= 15
    for line in stage.ctx.log.lines():
        assert set(line) <= {"ts", "phase", "step", "outcome", "target", "version", "count",
                             "sha256", "reason", "item"}
    log = stage.ctx.log
    # The refused password field's value is generated per run (L1-36).
    for bad in ({"password": os.urandom(8).hex()}, {"target": "a password; DROP"},
                {"reason": "free text"}):
        with pytest.raises(ValueError):
            log.write("verify", "step", "passed", **bad)


def test_the_database_script_holds_each_role_and_database(stage):
    applied(stage)
    script = stage.database.scripts[0]
    for statement in ("CREATE ROLE docsuri_disposable", "CREATE ROLE docsuri_scheduler",
                      "CREATE ROLE docsuri_operator", "CREATE ROLE docsuri_restore",
                      "GRANT docsuri_disposable TO docsuri_scheduler WITH INHERIT TRUE, SET FALSE",
                      "CREATE DATABASE docsuri_v2 OWNER docsuri_operator",
                      "CREATE DATABASE docsuri_v2_platform",
                      "CREATE EXTENSION IF NOT EXISTS vector",
                      "CREATE SCHEMA platform_control AUTHORIZATION platform_control_owner",
                      "INSERT INTO platform_control.protocol",
                      "CONNECTION LIMIT 4", "GRANT pg_monitor TO docsuri_operations"):
        assert statement in script, statement
    assert script.count("CREATE SCHEMA ") >= 12
    assert f"'{af.RUN_ID}'" in script and "\\i " in script


# --- the installation's verification and the smaller parts ----------------------------------------


class Nothing:
    """The isolation check's tools on a machine with no arrangement: every answer unknown."""

    def __getattr__(self, name):
        return lambda *args, **kwargs: {} if name == "disabled" else None


def test_the_installations_verification_records_each_check(stage):
    from docsuri_ops.arrangement import verify
    from docsuri_ops.arrangement.macos import ToolFailed

    refused = ("-k", "install", "docsuri-service-stop", "find-generic-password", "-w")

    def run(argv, **options):
        stage.tools.calls.append(("run", *argv[:3]))
        joined = " ".join(argv)
        if "status" in argv and stage.ctx.accounts.scheduler.name in argv:
            return b'{"ok": true}'
        if any(word in joined for word in refused) or "status" in argv:
            raise ToolFailed("tool-failed:sudo")
        return b""

    stage.tools.run = run
    stage.tools.exclusions.update({"/Library/DocSuri/", (
        "/Users/revenantonthemission/Library/Group Containers/HUAQ24HBR6.dev.orbstack/")})
    stage.ctx.isolation_tools = Nothing()
    results = verify.run_checks(stage.ctx)
    by_name = {result["check"]: result["passed"] for result in results}
    assert by_name == {
        "in-person-command-needs-a-password": True, "scheduler-runs-no-in-person-command": True,
        "scheduler-runs-no-service-control": True, "scheduler-runs-its-unattended-set": True,
        "service-account-runs-nothing": True, "login-cannot-read-operator-login": True,
        "superuser-tcp-login-refused": True, "time-machine-exclusions": True,
        "isolation-check": False, "runtime-clients-load-their-own-libpq": False}
    logged = [line for line in stage.ctx.log.lines() if line["phase"] == "verify"]
    assert [line["step"] for line in logged] == [result["check"] for result in results]
    assert list((stage.ctx.paths.isolation_evidence).glob("*.json"))  # the check's evidence


def test_the_superuser_tcp_check_signs_in_as_the_rendered_superuser(stage, monkeypatch):
    from docsuri_ops.arrangement import render, verify
    from docsuri_ops.arrangement.macos import ToolFailed

    seen: list[list[str]] = []

    def run(argv, **options):
        seen.append(list(argv))
        raise ToolFailed("tool-failed:psql")

    stage.tools.run = run
    # A renamed superuser moves the check with it: it never tests a role that is not the
    # superuser, which a missing role's refusal would also pass.
    monkeypatch.setattr(render, "SUPERUSER", "docsuri_renamed_superuser")
    check = dict(verify.checks(stage.ctx))["superuser-tcp-login-refused"]
    assert check() is True
    (argv,) = seen
    assert argv[argv.index("-U") + 1] == "docsuri_renamed_superuser"
    assert argv[argv.index("-h") + 1] == "127.0.0.1"


def test_a_model_clone_that_fails_its_digest_is_deleted(stage, monkeypatch):
    from docsuri_ops.arrangement import models

    monkeypatch.setattr(models, "MODEL_PINS", {**models.MODEL_PINS, "qwen3:8b": "0" * 64})
    target = stage.ctx.paths.models
    target.mkdir(parents=True)
    with pytest.raises(models.ModelsRefused, match="model-file-differs"):
        models.clone_models(stage.tools, stage.ctx.operator_home / ".ollama" / "models", target,
                            uid=613, gid=613)
    assert [path for path in target.rglob("*") if path.is_file()] == []
    assert models.runtime_reports_pins(lambda: {"models": []}) is False
    assert models.runtime_reports_pins(lambda: (_ for _ in ()).throw(OSError())) is False


def test_the_tunnel_move_needs_its_certificate_and_its_name(stage):
    from docsuri_ops.arrangement.phases import write_file
    from docsuri_ops.arrangement.tunnel import TunnelMove, TunnelRefused

    options = dict(paths=stage.ctx.paths, tools=stage.tools, tunnel_uid=614, operator_uid=501,
                   cloudflared=stage.ctx.paths.cloudflared_runtime / "cloudflared",
                   wait=lambda item: None, log=lambda step, outcome: None,
                   place=lambda target, content: write_file(stage.ctx, target, content, 0o644,
                                                            "root"))
    with pytest.raises(TunnelRefused, match="tunnel-name"):
        TunnelMove(tunnel_name="Tunnel One", **options)
    move = TunnelMove(tunnel_name=af.TUNNEL, **options)
    with pytest.raises(TunnelRefused, match="new-certificate-missing"):
        move.run()


def test_the_publishers_checksum_is_read_only_from_its_published_form():
    from docsuri_ops.arrangement import runtimes

    pin = runtimes.POSTGRESQL
    assert runtimes.publisher_checksum(pin, f"{'a' * 64}  {pin.archive}\n".encode()) == "a" * 64
    with pytest.raises(ValueError):
        runtimes.publisher_checksum(pin, f"{'a' * 64}  other.tar.bz2\n".encode())
    github = runtimes.CLOUDFLARED
    answer = {"tag_name": github.version, "assets": [{"name": github.archive,
                                                      "digest": "sha256:" + "b" * 64}]}
    assert runtimes.publisher_checksum(github, json.dumps(answer).encode()) == "b" * 64
    with pytest.raises(ValueError, match="another version"):
        runtimes.publisher_checksum(github, json.dumps({**answer, "tag_name": "1.0"}).encode())
    with pytest.raises(ValueError, match="no digest"):
        runtimes.publisher_checksum(github, json.dumps({**answer, "assets": []}).encode())
    assert runtimes.publisher_checksum(runtimes.PGVECTOR_RUNTIME, b"") == runtimes.PGVECTOR.sha256
    import dataclasses

    with pytest.raises(ValueError):
        runtimes.publisher_checksum(dataclasses.replace(pin, checksum="rumour"), b"")
    with pytest.raises(ValueError):
        runtimes.publisher_checksum(dataclasses.replace(pin, checksum="pinned", sha256=None), b"")


def test_the_in_progress_marker_covers_sixty_minutes_and_every_way_out(tmp_path):
    import datetime as dt

    from docsuri_ops.arrangement.paths import ArrangementPaths

    paths = ArrangementPaths.under(tmp_path / "DocSuri")
    now = af.NOW
    recorded = []
    with pytest.raises(RuntimeError):
        with manifest.changing(paths, "release-install", clock=lambda: now,
                               record=lambda: recorded.append(manifest.marker(paths))):
            assert manifest.marker_valid(paths, now)
            assert not manifest.marker_valid(paths, now + dt.timedelta(minutes=61))
            raise RuntimeError("an apply failed")
    assert recorded and recorded[0]["reason"] == "release-install"
    assert manifest.marker(paths) is None and manifest.end_change(paths) is False
    with pytest.raises(manifest.ManifestRefused):
        manifest.begin_change(paths, "Free Text!", clock=lambda: now)
    with pytest.raises(manifest.ManifestRefused):
        manifest.Entry("../x", "program", "a" * 64)
    with pytest.raises(manifest.ManifestRefused):
        manifest.Entry("x", "binary", "a" * 64)
    assert manifest.read_manifest(paths) is None
    assert manifest.differences(paths, None) == ["manifest-missing"]


def test_the_installer_program_takes_one_word_and_runs_only_as_root(capsys, monkeypatch):
    from docsuri_ops.arrangement import installer

    for name in [name for name in os.environ if name.startswith(("PYTHON", "DYLD_", "LD_"))]:
        monkeypatch.delenv(name)
    assert installer.main(["format-disk"]) == 2
    assert json.loads(capsys.readouterr().out.splitlines()[-1])["reason"] == "word-refused"
    assert installer.main(["plan"]) == 2  # this test never runs as root
    assert json.loads(capsys.readouterr().out)["reason"] == "root-required"
    monkeypatch.setenv("PYTHONHOME", "/x")
    assert installer.main(["plan"]) == 2
    assert json.loads(capsys.readouterr().out)["reason"] == "environment-refused"


# --- your decisions of 2026-10-24: staging, the first manifest, migrate, log files --------------


def test_phase_2_stages_with_no_operator_or_ledger_built(stage):
    from docsuri_ops.production_wiring import staging_platform
    from docsuri_ops.release import Stager

    staged = []

    def stage_release(tag):
        from docsuri_ops.arrangement.render import FIXED_PROGRAMS

        folder = stage.ctx.paths.releases / tag
        (folder / "ops" / "bin").mkdir(parents=True)
        for name in FIXED_PROGRAMS:  # the clone's fixed programs, as the stager leaves them
            program = folder / "ops" / "bin" / name
            program.write_text("#!/usr/bin/false\n")
            stage.tools.chmod(program, 0o755)
            # Root-owned, as the staging clone sets them (the fake tools record an owner
            # by path; phase 2 checks them through the `release` link).
            stage.tools.chown(stage.ctx.paths.release_bin / name, stage.ctx.root_uid, 0)
        staged.append(tag)
        return folder

    stage.ctx.release_tag, stage.ctx.stage_release = "v2.1.0", stage_release
    applied(stage)
    assert staged == ["v2.1.0"]
    assert os.readlink(stage.ctx.paths.release) == str(stage.ctx.paths.releases / "v2.1.0")
    # The installer's staging platform: GitHub, clone and sync, and nothing else.
    stager = staging_platform(paths=stage.ctx.paths, tools=stage.tools)
    assert isinstance(stager, Stager)
    assert {name for name in vars(stager)} == {"paths", "github", "clone", "sync",
                                               "libraries_outside", "owner_uid"}


def test_the_first_manifest_loads_and_names_its_rehearsal_database(stage):
    from docsuri_ops.arrangement.installer import FIRST_REHEARSAL
    from docsuri_ops.arrangement.paths import PRODUCTION_DATABASES

    applied(stage)
    profile = af.manifest_loads(stage.ctx.paths.profile / "environment.json")
    assert profile.mode == "rehearsal" and profile.admission == "maintainer-only"
    assert PRODUCTION_DATABASES.kind_of(profile.database_name) == "rehearsal"
    assert profile.rehearsal_database == profile.database_name
    named = stage.ctx.paths.control / FIRST_REHEARSAL
    assert json.loads(named.read_bytes()) == {"database": profile.database_name}
    assert named.stat().st_mode & 0o777 == 0o644
    assert "first-rehearsal-database" in stage.asked  # `cutover begin`, in person


def test_phase_7_stops_when_the_profile_does_not_load(stage):
    from backend.u8_profile import ProfileRefused

    def refuses(manifest):
        raise ProfileRefused("manifest", "rehearsal mode runs on its rehearsal database")

    stage.ctx.load_profile = refuses
    outcome = Installer(stage.ctx).apply()
    assert (outcome.failed, outcome.reason) == ("restart-and-check",
                                                "profile-does-not-load:manifest")


def test_phase_3_ends_with_migrate_reporting_the_database_absent(stage):
    from docsuri_ops.arrangement.installer import MIGRATED_CHAIN, chain_digest

    calls = []

    def migrate(ctx):
        calls.append(ctx.paths.release)
        return {"state": "absent", "template": {"applied": ["u8_accounts.sql"]},
                "platform": {"applied": []}}

    stage.ctx.migrate = migrate
    applied(stage)
    assert len(calls) == 1
    lines = [{k: v for k, v in line.items() if k != "ts"} for line in stage.ctx.log.lines()]
    assert {"phase": "folders-and-database", "step": "migrate", "outcome": "done",
            "reason": "database-absent"} in lines
    recorded = json.loads((stage.ctx.paths.control / MIGRATED_CHAIN).read_bytes())
    assert recorded == {"chainDigest": chain_digest(stage.ctx.source)}
    # The chain is applied: a second run does not migrate again.
    applied(stage)
    assert len(calls) == 1
    stage.ctx.migrate = lambda ctx: {"failed": {"owner": "accounts"}}
    (stage.ctx.paths.control / MIGRATED_CHAIN).unlink()
    outcome = Installer(stage.ctx).apply()
    assert (outcome.failed, outcome.reason) == ("folders-and-database", "migrate-failed")


def test_a_change_to_the_store_amendment_alone_changes_the_chain_digest(tmp_path):
    """The store amendment is part of the release's chain (the person's decision of
    2026-10-25, "After the move, same build"): in a copy of the source tree where only
    `u8_store.sql` changes, the digest phase 3 compares changes, so it migrates again."""
    from pathlib import Path

    from backend.u8_migrations import U1_AMENDMENTS, migrations
    from docsuri_ops.arrangement.installer import chain_digest
    from docsuri_ops.u8_platform.platform_profile import STORE_AMENDMENT, STORE_FILES

    root = Path(__file__).resolve().parents[3]
    files = [file for _, file in (*U1_AMENDMENTS, *migrations())] + list(STORE_FILES)
    assert STORE_AMENDMENT in files

    def copy(target, suffix: bytes = b""):
        for file in files:
            path = target / file
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((root / file).read_bytes()
                             + (suffix if file == STORE_AMENDMENT else b""))
        return target

    same = copy(tmp_path / "same")
    changed = copy(tmp_path / "changed", b"\n-- a later amendment\n")
    assert chain_digest(same) == chain_digest(root)
    assert chain_digest(changed) != chain_digest(same)


def test_every_jobs_log_files_exist_0600_before_the_jobs(stage):
    import stat

    from docsuri_ops.arrangement.installer import profile_log_files

    outcome = applied(stage)
    paths = profile_log_files(stage.ctx.paths)
    assert paths and all(path.parent == stage.ctx.paths.profile / "logs" for path in paths)
    for path in paths:
        info = path.lstat()
        assert stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o600, path
        assert stage.tools.owner(path) == stage.ctx.uid("service")
    order = [(change["action"], change["target"]) for change in outcome["changes"]
             if change["phase"] == "filter-volume-and-jobs"]
    first_job = next(index for index, (action, target) in enumerate(order)
                     if action == "job" and target != "org.docsuri.v2.pf")
    assert all(index < first_job for index, (action, _) in enumerate(order)
               if action == "log-file")
    path = paths[0]
    path.unlink()
    os.symlink(stage.ctx.paths.prefix, path)
    refused = Installer(stage.ctx).apply()
    assert refused.reason == "log-file-is-a-link"


def test_a_declined_value_and_an_unknown_item_stop_the_checklist(stage):
    from docsuri_ops.arrangement.checklist import Checklist

    checklist = Checklist(stage.ctx.log, lambda item, text: True, lambda item, text: "")
    with pytest.raises(NotConfirmed):
        checklist.value("folders-and-database", "healthchecks-heartbeat", "address")
    with pytest.raises(ValueError):
        checklist.wait("rule-files", "make-coffee")
    without = Checklist(stage.ctx.log, lambda item, text: True)
    with pytest.raises(NotConfirmed):
        without.value("folders-and-database", "healthchecks-heartbeat", "address")


def test_the_checklist_names_the_commands_that_are_installed():
    """The person's decisions of 2026-10-25 ("Its own package's name", "Add an in-person
    stop command"): the two items name real commands of the operator tool under
    `docsuri_ops.u8_platform`, `v2-stopped-in-person` its in-person `service stop`, and no
    item names a `docsuri-ops` command or a made-up receipt identifier."""
    from docsuri_ops.arrangement.checklist import ITEMS

    assert ("echo '{}' | /Library/DocSuri/release/.venv/bin/python -I -m "
            "docsuri_ops.u8_platform cutover begin --production") in ITEMS[
        "first-rehearsal-database"]
    stop = ITEMS["v2-stopped-in-person"]
    assert ("echo '{}' | /Library/DocSuri/release/.venv/bin/python -I -m "
            "docsuri_ops.u8_platform service stop <label> --production") in stop
    assert "once per label" in stop and "binds each stop's receipt" in stop
    assert "docsuri-service-stop" not in stop and "receiptId" not in stop
    assert not any("docsuri-ops" in text for text in ITEMS.values())
    # The command it names is the one the operator tool parses.
    from docsuri_ops.u8_platform import service_words

    assert service_words.WORDS == ("stop", "start")


# --- the keyring start through in-person service control (the person's decision of
# 2026-10-25, "Add an in-person stop command"; Step 44 test item 2) --------------------------


def key_start_context(tmp_path, clock):
    from types import SimpleNamespace

    from docsuri_ops.arrangement.paths import ArrangementPaths

    paths = ArrangementPaths.under(tmp_path / "prefix")
    log = InstallationLog(tmp_path / "installation-log.jsonl", clock=clock, base=tmp_path)
    return SimpleNamespace(paths=paths, log=log, operator="maintainer", tools=None)


def key_start_run(answer: dict, calls: list):
    import subprocess

    def run(argv, *, input, **options):
        calls.append(("word", argv[-1]))
        return subprocess.CompletedProcess(argv, 0, json.dumps(answer).encode() + b"\n", b"")

    return run


def test_the_keyring_start_stops_and_starts_v2_through_service_control(tmp_path, realm, clock):
    """Each of v2's three roles is stopped through the operator tool's in-person service
    control, so the store holds each stop's receipt and each stop record cites it, then
    `control-key-start` runs, then each role starts again the same way."""
    from docsuri_ops.arrangement import installer
    from docsuri_ops.production_tool import V2_ROLES
    from docsuri_ops.u8_platform import fixed
    from docsuri_ops.u8_platform.service_words import run_service
    from tests.u8_service_operations_integration import platform_flows as pf
    from tests.u8_service_operations_integration import service_flows as sf

    ctx = key_start_context(tmp_path, clock)
    services = sf.FixedServices(ctx.paths, clock)
    operator = sf.in_person(pf.journey(tmp_path, realm).operator(clock=clock), services)
    # The realm's store holds the realm's labels: each production role maps to its own.
    realm_label = {role: "dev.docsuri.u8.run." + role.rsplit(".", 1)[-1] for role in V2_ROLES}
    calls, records = [], {}

    def service(action: str, label: str) -> dict:
        calls.append((action, label))
        receipt = run_service(action, realm_label[label], operator)
        if action == "stop":
            path = fixed.stop_record_path(ctx.paths, realm_label[label])
            records[label] = json.loads(path.read_bytes())
        return receipt

    answer = {"ok": True, "result": {"digest": "a" * 64, "generation": 2}}
    result = installer.installer_control_key_start(ctx, run=key_start_run(answer, calls),
                                                   service=service)
    assert result == answer["result"]
    assert calls == [*[("stop", label) for label in V2_ROLES], ("word", "control-key-start"),
                     *[("start", label) for label in V2_ROLES]]
    held = sf.receipt_held(operator)
    for label, record in records.items():
        assert held({**record, "label": realm_label[label]}) is True
    assert all(seen["bound"] for seen in services.seen) and len(services.seen) == 6
    # The installation log names each stop's and start's bound operation, no made-up id.
    logged = [line for line in ctx.log.lines() if line["step"].startswith("service-")]
    assert [line["item"] for line in logged] == [seen["operationId"] for seen in services.seen]
    for label in V2_ROLES:  # v2 runs again: no stop record left
        assert not fixed.stop_record_path(ctx.paths, realm_label[label]).exists()


def test_a_failed_stop_ends_the_keyring_start_and_starts_what_was_stopped(tmp_path, clock):
    from docsuri_ops.arrangement import installer
    from docsuri_ops.production_tool import V2_ROLES

    ctx = key_start_context(tmp_path, clock)
    calls = []

    def service(action: str, label: str) -> dict:
        calls.append((action, label))
        if action == "stop" and label == V2_ROLES[1]:
            raise installer.ServiceControlFailed(action)
        return {"operationId": f"{action}-{label}"}

    result = installer.installer_control_key_start(
        ctx, run=key_start_run({"ok": True, "result": {}}, calls), service=service)
    assert result == {"failed": {"reason": "service-control-failed"}}
    # The word never ran; only the role that was stopped starts again.
    assert calls == [("stop", V2_ROLES[0]), ("stop", V2_ROLES[1]), ("start", V2_ROLES[0])]


def test_a_word_that_succeeded_with_one_restart_failed_fails_and_the_next_apply_starts_it(
        tmp_path, clock):
    """Review finding (Major, R10): the word succeeded but one role did not start again.
    The keyring start answers `service-start-failed:<label>`, the phase fails and its
    `verify` refuses, and the next `apply`'s change starts the role (then verify passes)."""
    from types import SimpleNamespace

    from docsuri_ops.arrangement import installer
    from docsuri_ops.arrangement.phases import PhaseFailed
    from docsuri_ops.production_tool import V2_ROLES

    ctx = key_start_context(tmp_path, clock)
    calls = []
    failing = {V2_ROLES[2]}

    def service(action: str, label: str) -> dict:
        calls.append((action, label))
        if action == "start" and label in failing:
            raise installer.ServiceControlFailed(action)
        return {"operationId": f"{action}-{label}"}

    answer = {"ok": True, "result": {"digest": "a" * 64, "generation": 2}}
    result = installer.installer_control_key_start(ctx, run=key_start_run(answer, calls),
                                                   service=service)
    assert result == {"failed": {"reason": f"service-start-failed:{V2_ROLES[2]}",
                                 "unstarted": [V2_ROLES[2]]}}
    assert calls[-3:] == [("start", label) for label in V2_ROLES]
    assert installer.unstarted_roles(ctx) == [V2_ROLES[2]]
    # The phase: `_start_keyring` fails on that answer, and `verify` refuses while the
    # role is down, even though the snapshot (the word's effect) would be in place.
    phase = installer.RestartCheckPhase()
    (ctx.paths.profile / "verifier-key").mkdir(parents=True)
    from backend.local_profile import VERIFIER_KEY

    # The key, generated per run (L1-36).
    (ctx.paths.profile / "verifier-key" / VERIFIER_KEY).write_bytes(secrets.token_bytes(32))
    ctx.control_key_start = lambda context: result
    with pytest.raises(PhaseFailed, match="control-key-start-failed:service-start-failed"):
        phase._start_keyring(ctx)
    checklist = SimpleNamespace(is_done=lambda item: True, wait=lambda *a: None)
    ctx.checklist = checklist
    ctx.service_control = service
    import unittest.mock as mock

    with mock.patch.object(installer, "keyring_snapshot_present", lambda context: True):
        with pytest.raises(PhaseFailed, match=f"service-start-failed:{V2_ROLES[2]}"):
            phase.verify(ctx)
        changes = phase.changes(ctx)
        assert [change.action for change in changes] == ["service-start"]
        # Still failing: the change fails and the role stays recorded.
        with pytest.raises(PhaseFailed):
            changes[0].apply()
        assert installer.unstarted_roles(ctx) == [V2_ROLES[2]]
        failing.clear()
        phase.changes(ctx)[0].apply()
    assert installer.unstarted_roles(ctx) == []
    assert calls[-1] == ("start", V2_ROLES[2])
    assert not (ctx.paths.control / installer.UNSTARTED).exists()


def test_the_installers_service_control_runs_the_operator_tool_as_you(tmp_path, clock):
    """`operator_service` runs the linked release's operator tool as your login account,
    the command the checklist and the runbook name, with `{}` on standard input."""
    from docsuri_ops.arrangement import installer

    ctx = key_start_context(tmp_path, clock)
    seen = []

    class Tools:
        def run(self, argv, *, input=None, **options):
            seen.append((argv, input))
            return json.dumps({"ok": True, "result": {"operationId": "op-1"}}).encode()

    ctx.tools = Tools()
    assert installer.operator_service(ctx)("stop", "org.docsuri.v2.host") == {
        "operationId": "op-1"}
    ((argv, stdin),) = seen
    assert argv == ["/usr/bin/sudo", "-u", "maintainer",
                    str(ctx.paths.release / ".venv/bin/python"), "-I", "-m",
                    "docsuri_ops.u8_platform", "service", "stop", "org.docsuri.v2.host",
                    "--production"]
    assert stdin == b"{}"

    class Refusing:
        def run(self, argv, *, input=None, **options):
            return json.dumps({"ok": False, "error": {"code": "FORBIDDEN"}}).encode()

    ctx.tools = Refusing()
    with pytest.raises(installer.ServiceControlFailed):
        installer.operator_service(ctx)("start", "org.docsuri.v2.host")


def test_the_installers_service_control_waits_as_long_as_its_password_prompts_need(
        tmp_path, clock):
    """The review's fix of 2026-10-26: the run waits under its own named bound, long
    enough for its three password prompts (the login's release, the ledger copy and the
    fixed program), not the tools' 60 s default; a run that passes it, or answers nothing
    readable, is the control's failure."""
    import subprocess

    from docsuri_ops.arrangement import installer
    from docsuri_ops.arrangement.macos import TOOL_SECONDS, ToolFailed

    ctx = key_start_context(tmp_path, clock)
    bounds = []

    class Tools:
        def run(self, argv, *, input=None, seconds=TOOL_SECONDS, **options):
            bounds.append(seconds)
            return json.dumps({"ok": True, "result": {"operationId": "op-1"}}).encode()

    ctx.tools = Tools()
    installer.operator_service(ctx)("stop", "org.docsuri.v2.host")
    assert bounds == [installer.SERVICE_CONTROL_SECONDS]
    assert installer.PASSWORD_PROMPTS == 3
    assert installer.SERVICE_CONTROL_SECONDS >= installer.PASSWORD_PROMPTS * 120 > TOOL_SECONDS

    class TimedOut:
        def run(self, argv, *, input=None, **options):
            raise ToolFailed("tool-unavailable:sudo") from subprocess.TimeoutExpired(argv, 1)

    class Silent:
        def run(self, argv, *, input=None, **options):
            return b""

    for tools in (TimedOut(), Silent()):
        ctx.tools = tools
        with pytest.raises(installer.ServiceControlFailed):
            installer.operator_service(ctx)("stop", "org.docsuri.v2.host")


def test_the_installation_runbook_names_every_password_prompt_of_the_service_control():
    """The review's fix of 2026-10-26: the installation runbook names each prompt of the
    in-person service control, the ledger copy's included."""
    runbook = (ROOT / "aidlc/spaces/default/intents/261016-finish-v2-rebuild/construction/"
               "u8-service-operations-integration/code-generation/"
               "u8-installation-runbook.md").read_text()
    for program in ("docsuri-credential-release", "docsuri-ledger copy",
                    "docsuri-service-stop", "docsuri-service-start"):
        assert program in runbook, program


MIGRATION_RUNBOOK = (ROOT / "aidlc/spaces/default/intents/261016-finish-v2-rebuild/"
                     "construction/u8-service-operations-integration/code-generation/"
                     "u8-migration-runbook.md")
V1_VOLUME_SECTION = ("### Before the first dry run: v1's stores move to their encrypted volume "
                     "(NFR3.6, D8)")


def test_the_migration_runbook_keeps_v1s_volume_passphrase_with_you():
    """L2-16 (D8, NFR3.6; security-design § 6.1): v1's volume passphrase is yours alone."""
    text = MIGRATION_RUNBOOK.read_text()
    assert text.count(V1_VOLUME_SECTION) == 1
    start = text.index(V1_VOLUME_SECTION)
    second = text.index("\n## 2. ")
    third = text.index("\n## 3. ")
    subsections = [match.start() for match in re.finditer(r"^### ", text, re.MULTILINE)
                   if second < match.start() < third]
    assert subsections and subsections[0] == start
    # Read as one line: the runbook wraps its prose.
    section = " ".join(text[start:subsections[1] if len(subsections) > 1 else third].split())
    for name in ("DocSuri_v1", "NFR3.6", "login keychain", "password manager", "-passprompt"):
        assert name in section, name
    custody = section[section.index("never put in"):]
    for place in ("System keychain", "/Library/DocSuri/", "a launch job's definition",
                  "an environment file", "the installation log"):
        assert place in custody, place
    assert "-passphrase" not in section


# --- U8 plan Step 76: accounts, folders, secrets, the volume's passphrase, Time Machine, the
# installation log's place and the instance's encoding ------------------------------------------

NEW_ACCOUNTS = (("_docsuri_v2", 610), ("_docsuri_v2_sched", 611), ("_docsuri_v2_db", 612),
                ("_docsuri_models", 613), ("_docsuri_tunnel", 614))


def recording_run(recorded: list, *, code=lambda argv: 0):
    """A `subprocess.run` stand-in: records each argv with its options, answers `code`."""

    def run(argv, **options):
        recorded.append((list(argv), options))
        return subprocess.CompletedProcess(argv, code(argv), b"", b"")

    return run


def test_new_accounts_are_created_without_a_login(stage):
    """Step 76(a)."""
    from docsuri_ops.arrangement import macos
    from docsuri_ops.arrangement.phases import AccountsPhase, PhaseFailed

    recorded: list = []
    fake = stage.ctx.tools
    stage.ctx.tools = macos.MacTools(run=recording_run(
        recorded, code=lambda argv: 1 if argv[:3] == ["/usr/bin/dscl", ".", "-read"] else 0))
    changes = AccountsPhase().changes(stage.ctx)
    assert [change.target for change in changes] == [name for name, _ in NEW_ACCOUNTS]
    recorded.clear()
    for change in changes:
        change.apply()
    create = ["/usr/bin/dscl", ".", "-create"]
    expected = []
    for name, uid in NEW_ACCOUNTS:
        expected += [create + [f"/Groups/{name}"],
                     create + [f"/Groups/{name}", "PrimaryGroupID", str(uid)],
                     create + [f"/Users/{name}"],
                     create + [f"/Users/{name}", "UniqueID", str(uid)],
                     create + [f"/Users/{name}", "PrimaryGroupID", str(uid)],
                     create + [f"/Users/{name}", "UserShell", "/usr/bin/false"],
                     create + [f"/Users/{name}", "NFSHomeDirectory", "/var/empty"],
                     create + [f"/Users/{name}", "IsHidden", "1"]]
    assert [argv for argv, _ in recorded] == expected
    assert not any("_docsuri_r1t_backup" in part for argv, _ in recorded for part in argv)
    # The phase's verify, on the fake tools.
    stage.ctx.tools = fake
    for name, uid in NEW_ACCOUNTS:
        fake.create_account(name, uid)
    AccountsPhase().verify(stage.ctx)
    for key in ("service", "backup"):
        name = getattr(stage.ctx.accounts, key).name
        held = dict(fake.accounts[name])
        for broken, reason in ((None, "account-missing"),
                               ({**held, "uid": 999}, "account-uid-differs"),
                               ({**held, "shell": "/bin/zsh"}, "account-can-log-in")):
            if broken is None:
                del fake.accounts[name]
            else:
                fake.accounts[name] = broken
            with pytest.raises(PhaseFailed) as failed:
                AccountsPhase().verify(stage.ctx)
            assert failed.value.reason == f"{reason}:{key}"
            fake.accounts[name] = held
        AccountsPhase().verify(stage.ctx)


def test_the_installation_never_writes_pf_conf(stage):
    """Step 76(c)."""
    from docsuri_ops.arrangement import render
    from docsuri_ops.arrangement.paths import Accounts

    applied(stage)
    paths = stage.ctx.paths
    pf_conf = paths.system / "etc" / "pf.conf"
    assert not pf_conf.exists() and not pf_conf.is_symlink()
    assert list(paths.system.rglob("pf.conf")) == []
    assert not [call for call in stage.tools.calls
                if any("pf.conf" in str(part) for part in call)]
    assert paths.pf_anchor.read_bytes() == render.render_pf_anchor(
        paths, Accounts.standard()).content


LOG_FOLDERS = (
    ("profile/logs", "_docsuri_v2", 610, 0o700),
    ("scheduler/logs", "_docsuri_v2_sched", 611, 0o700),
    ("backup-agent/logs", "_docsuri_r1t_backup", 607, 0o700),
    ("postgres/logs", "_docsuri_v2_db", 612, 0o700),
    ("models-state/logs", "_docsuri_models", 613, 0o700),
    ("tunnel/logs", "_docsuri_tunnel", 614, 0o700),
    ("control/logs", "root", 0, 0o755),
    ("postgres/data/log", "_docsuri_v2_db", 612, 0o700),
)


def test_each_log_folder_is_made_for_its_own_account(stage):
    """Step 76(c)."""
    from docsuri_ops.arrangement.paths import Accounts
    from docsuri_ops.arrangement.phases import FOLDERS

    outcome = applied(stage)
    paths, accounts = stage.ctx.paths, Accounts.standard()

    def named(uid: int) -> str:
        return "root" if uid == stage.ctx.root_uid else accounts.by_uid(uid).name

    for relative, owner, uid, mode in LOG_FOLDERS:
        path = paths.prefix / relative
        info = path.lstat()
        assert stat.S_ISDIR(info.st_mode), relative
        found = stage.tools.owner(path)
        assert (found, named(found), stat.S_IMODE(info.st_mode)) == (uid, owner, mode), relative
    assert "postgres/data/log" not in {relative for relative, _, _ in FOLDERS}
    order = [(change["action"], change["target"]) for change in outcome["changes"]]
    logs = order.index(("folder", str(paths.prefix / "postgres" / "logs")))
    job = order.index(("job", "org.docsuri.v2.postgres"))
    initdb = order.index(("initdb", str(paths.postgres_data)))
    data_log = order.index(("folder", str(paths.postgres_data / "log")))
    assert logs < job
    assert initdb < data_log


def test_each_key_has_its_own_owner_only_folder_under_the_profile_root(stage):
    """Step 76(c)."""
    from docsuri_ops.arrangement.paths import ArrangementPaths

    applied(stage)
    profile = stage.ctx.paths.profile
    folders = [profile / name for name in ("export-keys", "control-keys", "verifier-key",
                                           "cursor-key")]
    assert len({folder.lstat().st_ino for folder in folders}) == 4
    for folder in folders:
        info = folder.lstat()
        assert folder.parent == profile and stat.S_ISDIR(info.st_mode), folder
        assert (stage.tools.owner(folder), stat.S_IMODE(info.st_mode)) == (610, 0o700), folder
    assert ArrangementPaths().profile == Path("/Library/DocSuri/profile")


def test_each_secret_is_32_fresh_bytes_written_only_to_its_holder(
        stage, tmp_path, monkeypatch, capsys, caplog):
    """Step 76(d)."""
    import secrets as real

    from docsuri_ops.arrangement import keychain

    taken: list[tuple[int, bytes]] = []

    def token_bytes(size: int) -> bytes:
        value = real.token_bytes(size)
        taken.append((size, value))
        return value

    monkeypatch.setattr(keychain, "secrets", SimpleNamespace(token_bytes=token_bytes))
    with every_logger_at_debug(caplog) as handler:
        outcome = Installer(stage.ctx).apply()
    assert outcome.failed is None, outcome.as_dict()
    assert taken and all(size == 32 for size, _ in taken)
    assert stage.secrets == [value.hex().encode() for _, value in taken]
    assert all(HEX64.fullmatch(secret) for secret in stage.secrets)
    assert len(set(stage.secrets)) == len(stage.secrets)
    paths, tools = stage.ctx.paths, stage.tools
    files = {paths.profile / "owner-credentials.json": (610, 610),
             paths.backup_agent / "v2-login": (607, 607),
             paths.scheduler_credentials: (611, 611),
             paths.profile / "platform-reader.json": (610, 610),
             paths.control / "platform-provisioner.json": (0, 0)}
    items = {"docsuri-v2-operator", "docsuri-v2-restore", "docsuri-v2-platform",
             "DocSuri_Backup"}
    assert set(tools.keychain) == items
    assert sorted((call[1], call[2]) for call in tools.calls if call[0] == "keychain_add") == (
        sorted((item, "root") for item in items))
    every_file = [path for path in tmp_path.rglob("*")
                  if path.is_file() and not path.is_symlink()]
    for secret in stage.secrets:
        holders = [path for path in every_file if secret in path.read_bytes()] + [
            item for item, value in tools.keychain.items() if value == secret]
        assert len(holders) == 1, holders
        assert holders[0] in files or holders[0] in items, holders
    # Your answer of 2026-11-10 ("Fix both and sweep the rest"): each holder is given
    # through its own descriptor, never chowned by path.
    for path, owner in files.items():
        info = path.lstat()
        assert stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o600, path
        assert ("fchown", info.st_ino, *owner) in tools.calls, path
        assert tools.owner(path) == owner[0], path
        assert not [call for call in tools.calls if call[:2] == ("chown", str(path))], path
    assert sum(secret in paths.scheduler_credentials.read_bytes()
               for secret in stage.secrets) == 2
    checks = paths.healthchecks
    assert ("fchown", checks.lstat().st_ino, 611, 611) in tools.calls
    assert tools.owner(checks) == 611
    assert sorted(json.loads(checks.read_bytes()).values()) == sorted(stage.answers)
    assert not any(secret in checks.read_bytes() for secret in stage.secrets)
    # Every password a holder holds is one of this run's secrets.
    owners = json.loads((paths.profile / "owner-credentials.json").read_bytes())
    scheduler = json.loads(paths.scheduler_credentials.read_bytes())
    held = [value.encode() for value in owners["roles"].values()]
    held.append((paths.backup_agent / "v2-login").read_bytes())
    held += [scheduler["database"]["password"].encode(),
             scheduler["platform"]["password"].encode()]
    held += [json.loads((paths.profile / "platform-reader.json").read_bytes())[
        "password"].encode(), json.loads((paths.control / "platform-provisioner.json")
                                         .read_bytes())["password"].encode()]
    held += [tools.keychain[item] for item in sorted(items)]
    assert held and all(value in stage.secrets for value in held), held
    assert len(held) == len(stage.secrets)
    # No secret in the log, the output or any record of every logger at DEBUG, nor in a
    # tool's call record.
    raw = paths.installation_log.read_bytes()
    captured = capsys.readouterr()
    for secret in stage.secrets:
        assert secret not in raw
        assert secret.decode() not in captured.out and secret.decode() not in captured.err
        assert not [record for record in handler.records
                    if secret.decode() in record_text(record)]
        assert not [call for call in tools.calls if secret.decode() in repr(call)]


def test_a_secret_file_is_created_new_and_given_to_its_holder_as_root(tmp_path, monkeypatch):
    """Step 76(d)."""
    from docsuri_ops.arrangement import keychain

    given: list[tuple[int, int, int]] = []

    class RootOs:
        def __getattr__(self, name):
            return getattr(os, name)

        def geteuid(self) -> int:
            return 0

        def fchown(self, descriptor: int, uid: int, gid: int) -> None:
            given.append((os.fstat(descriptor).st_ino, uid, gid))

    class Refusing:
        calls: list = []

        def chown(self, path, uid, gid):
            self.calls.append(path)
            raise AssertionError("the passed-in tools' chown was called")

    tools = Refusing()
    monkeypatch.setattr(keychain, "os", RootOs())
    path = tmp_path / "holder" / "secret.json"
    written, refused = keychain.generate().decode(), keychain.generate().decode()
    keychain.write_secret_file(path, {"password": written}, uid=610, gid=611, base=tmp_path,
                               tools=tools)
    info = path.lstat()
    assert stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o600
    assert json.loads(path.read_bytes()) == {"password": written}
    assert given == [(info.st_ino, 610, 611)] and tools.calls == []
    # An existing file, a link to another file and a dangling link are each refused.
    other = tmp_path / "other"
    other.write_bytes(b"another file")
    existing = tmp_path / "existing.json"
    existing.write_bytes(b"kept")
    linked, dangling = tmp_path / "linked.json", tmp_path / "dangling.json"
    linked.symlink_to(other)
    dangling.symlink_to(tmp_path / "absent")
    for target in (existing, linked, dangling):
        with pytest.raises(FileExistsError):
            keychain.write_secret_file(target, {"password": refused}, uid=610, gid=610,
                                       base=tmp_path, tools=tools)
    assert existing.read_bytes() == b"kept" and not existing.is_symlink()
    assert other.read_bytes() == b"another file" and os.readlink(linked) == str(other)
    assert os.readlink(dangling) == str(tmp_path / "absent")
    assert not (tmp_path / "absent").exists()
    assert len(given) == 1 and tools.calls == []


def test_the_volume_passphrase_goes_to_the_system_keychain_and_waits_for_your_copies(stage):
    """Step 76(e)."""
    from docsuri_ops.arrangement.checklist import ITEMS

    applied(stage)
    added = [call for call in stage.tools.calls
             if call[0] == "keychain_add" and call[1] == "DocSuri_Backup"]
    assert added == [("keychain_add", "DocSuri_Backup", "root", {})]
    secret = stage.tools.keychain["DocSuri_Backup"]
    assert HEX64.fullmatch(secret) and secret in stage.secrets
    assert not [call for call in stage.tools.calls if secret.decode() in repr(call)]
    wanted = ["volume-passphrase-changed", "volume-passphrase-saved",
              "login-keychain-item-deleted"]
    assert [item for item in stage.asked if item in wanted] == wanted
    assert secret not in stage.ctx.paths.installation_log.read_bytes()
    checklist = [line for line in stage.ctx.log.lines() if line["step"].startswith("checklist")]
    assert checklist and secret.decode() not in json.dumps(checklist)
    assert not any(secret.decode() in text for text in ITEMS.values())
    # L2-16 (D8, NFR3.6): checked by how passphrases are handled, never by names, since the
    # platform configuration legitimately carries your `v1Stores` paths. The apply's only
    # keychain items are the three operator logins and the backup volume's passphrase,
    # each once, and the only passphrase items it asks for are the backup volume's.
    items = sorted(call[1] for call in stage.tools.calls if call[0] == "keychain_add")
    assert items == sorted(["docsuri-v2-operator", "docsuri-v2-restore", "docsuri-v2-platform",
                            "DocSuri_Backup"])
    asking = {key: text for key, text in ITEMS.items()
              if "passphrase" in key.lower() or "passphrase" in text.lower()}
    assert sorted(asking) == ["volume-passphrase-changed", "volume-passphrase-saved"]
    for key, text in asking.items():
        assert "DocSuri_Backup" in text or "backup volume" in text, key


def test_the_keychain_adapter_hands_the_secret_to_the_system_keychain_on_standard_input():
    """Step 76(e)."""
    from docsuri_ops.arrangement import keychain
    from docsuri_ops.arrangement.macos import MacTools, ToolFailed

    recorded: list = []
    secret = keychain.generate()
    MacTools(run=recording_run(recorded)).keychain_add("DocSuri_Backup", "root", secret)
    assert [argv for argv, _ in recorded] == [["/usr/bin/security", "-i"]]
    assert recorded[0][1]["input"] == (
        b'add-generic-password -U -s "DocSuri_Backup" -a "root" -w "' + secret
        + b'" "/Library/Keychains/System.keychain"\n')
    assert not any(secret.decode() in part for argv, _ in recorded for part in argv)
    recorded.clear()
    for outside in (secret.upper(), b"not hexadecimal " * 4, secret[:-1] + b"g"):
        with pytest.raises(ToolFailed, match="^keychain-item-outside-its-form$"):
            MacTools(run=recording_run(recorded)).keychain_add("DocSuri_Backup", "root",
                                                                outside)
    assert recorded == []


def test_a_run_as_an_account_drops_roots_supplementary_groups():
    """Batch 7's follow-up review: CPython calls setgroups() only when `extra_groups` is
    given, so a run as an account passes `extra_groups=[]` with `user` and `group`, and a
    run as root (no account) passes none of the three."""
    from docsuri_ops.arrangement.macos import MacTools

    recorded: list = []
    tools = MacTools(run=recording_run(recorded))
    tools.run(["/usr/bin/true"], user=612)
    tools.run(["/usr/bin/true"], user=612, group=20)
    tools.run(["/usr/bin/true"])
    chosen = [{key: options[key] for key in ("user", "group", "extra_groups") if key in options}
              for _, options in recorded]
    assert chosen == [{"user": 612, "group": 612, "extra_groups": []},
                      {"user": 612, "group": 20, "extra_groups": []}, {}]


def test_the_installation_log_records_both_time_machine_exclusions(stage):
    """Step 76(f)."""
    assert stage.tools.exclusions == set()
    applied(stage)
    lines = [{k: v for k, v in line.items() if k != "ts"} for line in stage.ctx.log.lines()]
    machine = [line for line in lines if line["step"] == "time-machine"]
    assert machine == [
        {"phase": "folders-and-database", "step": "time-machine", "outcome": "applied",
         "target": "/Library/DocSuri/"},
        {"phase": "folders-and-database", "step": "time-machine", "outcome": "applied",
         "target": ORBSTACK}]
    verified = {"phase": "folders-and-database", "step": "verify", "outcome": "passed"}
    assert sum(all(line.get(k) == v for k, v in verified.items()) for line in lines) == 1
    count = len(lines)
    applied(stage)
    later = [{k: v for k, v in line.items() if k != "ts"}
             for line in stage.ctx.log.lines()[count:]]
    assert not [line for line in later if line["step"] == "time-machine"]
    assert sum(all(line.get(k) == v for k, v in verified.items()) for line in later) == 1


def test_each_exclusion_is_a_fixed_path_tmutil_call():
    """Step 76(f)."""
    from docsuri_ops.arrangement import timemachine
    from docsuri_ops.arrangement.macos import MacTools

    for path in ("/Library/DocSuri/", ORBSTACK):
        recorded: list = []
        MacTools(run=recording_run(recorded)).exclude(path)
        assert [argv for argv, _ in recorded] == [["/usr/bin/tmutil", "addexclusion", "-p",
                                                   path]]
    recorded = []
    with pytest.raises(ValueError):
        timemachine.exclude(MacTools(run=recording_run(recorded)),
                            "/Users/revenantonthemission/")
    assert recorded == []


def test_the_production_installer_logs_into_the_profiles_evidence_folder(monkeypatch):
    """Step 76(g)."""
    from docsuri_ops.arrangement import installer, macos

    built: list = []

    class StubTools:
        def __init__(self, *args, **kwargs):
            built.append((args, kwargs))

        def __getattr__(self, name):
            raise AssertionError(f"the stub tools' {name} was used")

    # Your answer of 2026-11-10 ("Fix it now"): the log is given to its holder through
    # its own descriptor (`os.fchown`), never through its path.
    owned: list = []
    followed: list = []
    monkeypatch.setattr(macos, "MacTools", StubTools)
    monkeypatch.setattr(os, "fchown",
                        lambda descriptor, uid, gid: owned.append((descriptor, uid, gid)))
    monkeypatch.setattr(os, "chown", lambda path, uid, gid, **kw: followed.append(path))
    settings = {"operator": af.OPERATOR, "operatorUid": af.OPERATOR_UID,
                "operatorHome": "/Users/revenantonthemission", "tunnelName": af.TUNNEL,
                "maintainerAccount": "00000000-0000-4000-8000-0000000000aa",
                "runId": af.RUN_ID}
    ctx = installer.production_context(settings, clock=lambda: af.NOW)
    expected = Path("/Library/DocSuri/profile/evidence/installation-log.jsonl")
    assert built and ctx.log.path == expected
    assert ctx.log.base == Path("/Library/DocSuri")
    descriptor = 7  # a stand-in number: the recorder never touches it
    ctx.log.owner(descriptor)
    assert owned == [(descriptor, 610, 610)] and followed == []
    assert not Path("/Library/DocSuri").exists()


def log_place(tmp_path):
    """An installation log under a temporary prefix whose owner records the inode of the
    descriptor it is given, as `production_context`'s `os.fchown` would be given it."""
    prefix = tmp_path / "prefix"
    path = prefix / "profile" / "evidence" / "installation-log.jsonl"
    given: list[int] = []
    log = InstallationLog(path, clock=lambda: af.NOW, base=prefix,
                          owner=lambda descriptor: given.append(os.fstat(descriptor).st_ino))
    return prefix, path, log, given


def test_the_installation_log_is_created_new_and_given_through_its_own_descriptor(tmp_path):
    """Your answer of 2026-11-10 ("Fix it now"): the log is created relative to its
    folder's descriptor, 0600, and only the call that created it gives it to its holder,
    through that file's own descriptor."""
    prefix, path, log, given = log_place(tmp_path)
    log.write("accounts", "verify", "passed", count=1)
    info = path.lstat()
    assert stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o600
    assert info.st_nlink == 1 and given == [info.st_ino]
    log.write("accounts", "verify", "passed", count=2)
    assert given == [info.st_ino]  # an existing log is never given again
    assert [line["count"] for line in log.lines()] == [1, 2]
    assert path.parent.is_dir() and not path.parent.is_symlink()


def test_a_link_planted_at_the_installation_logs_name_is_refused(tmp_path):
    """Your answer of 2026-11-10 ("Fix it now"): a symbolic link at the log's name, to
    another file or to nothing, is refused; nothing is given and the target is untouched.
    With the link gone, the same write is accepted."""
    from docsuri_ops.arrangement.checklist import LogRefused

    prefix, path, log, given = log_place(tmp_path)
    path.parent.mkdir(parents=True)
    other = tmp_path / "other"
    other.write_bytes(b"another file")
    before = other.stat()
    absent = tmp_path / "absent"
    for target in (other, absent):
        path.symlink_to(target)
        with pytest.raises(LogRefused, match="^installation-log-is-a-link$"):
            log.write("accounts", "verify", "passed", count=1)
        assert given == [] and os.readlink(path) == str(target)
        path.unlink()
    assert other.read_bytes() == b"another file" and not absent.exists()
    after = other.stat()
    assert (after.st_uid, after.st_mode, after.st_nlink) == (
        before.st_uid, before.st_mode, before.st_nlink)
    log.write("accounts", "verify", "passed", count=1)
    assert given == [path.lstat().st_ino]


def test_a_hard_link_planted_at_the_installation_logs_name_after_deletion_is_refused(tmp_path):
    """Your answer of 2026-11-10 ("Fix it now"): the holder deletes the log and puts a
    second name of another file in its place; the next write refuses it (the file has two
    names), gives nothing and leaves the other file as it was."""
    from docsuri_ops.arrangement.checklist import LogRefused

    prefix, path, log, given = log_place(tmp_path)
    log.write("accounts", "verify", "passed", count=1)
    assert len(given) == 1
    path.unlink()
    other = tmp_path / "other"
    other.write_bytes(b"another file")
    os.link(other, path)
    with pytest.raises(LogRefused, match="^installation-log-not-its-own-file$"):
        log.write("accounts", "verify", "passed", count=2)
    assert len(given) == 1
    assert other.read_bytes() == b"another file" and other.stat().st_nlink == 2
    path.unlink()
    log.write("accounts", "verify", "passed", count=2)
    assert len(given) == 2 and given[1] == path.lstat().st_ino


def test_a_link_in_place_of_the_logs_folders_is_refused(tmp_path):
    """Your answer of 2026-11-10 ("Fix it now"): a symbolic link in place of
    `profile/evidence`, or of `profile`, is never followed; nothing is created, written
    or given at its target. With the link gone, the same write is accepted."""
    from docsuri_ops.arrangement.checklist import LogRefused

    prefix, path, log, given = log_place(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    (elsewhere / "evidence").mkdir(parents=True)
    (prefix / "profile").mkdir(parents=True)
    for planted, target in ((prefix / "profile" / "evidence", elsewhere / "evidence"),
                            (prefix / "profile", elsewhere)):
        if planted.name == "profile":
            planted.rmdir()
        planted.symlink_to(target)
        with pytest.raises(LogRefused, match="^installation-log-folder-is-a-link$"):
            log.write("accounts", "verify", "passed", count=1)
        assert given == [] and os.readlink(planted) == str(target)
        assert list((elsewhere / "evidence").iterdir()) == []
        planted.unlink()
    log.write("accounts", "verify", "passed", count=1)
    assert given == [path.lstat().st_ino]
    assert list((elsewhere / "evidence").iterdir()) == []


PLANTED = b'{"item": "old-tunnel-deleted", "outcome": "confirmed", "step": "checklist"}\n'


def reads_recorded(monkeypatch) -> list[int]:
    """The inode of every file read while the test runs, through `os.read` or through an
    `io.open` / `open` by name (`af.reads_recorded`), so a return to a by-path read is
    caught as well as a read through the walk."""
    return af.reads_recorded(monkeypatch)


def test_reading_the_installation_log_never_follows_a_link(tmp_path, monkeypatch):
    """The root installer reads the log at every start (`Checklist`): a link at the log's
    name, or in place of `profile/evidence` or `profile`, is refused with the write's keys
    and its target is never read, although the target holds a line the reader would
    otherwise take as a confirmed item. With the links gone, the log reads again."""
    from docsuri_ops.arrangement.checklist import Checklist, LogRefused

    prefix, path, log, given = log_place(tmp_path)
    log.write("accounts", "verify", "passed", count=1)
    kept = path.read_bytes()
    elsewhere = tmp_path / "elsewhere"
    (elsewhere / "evidence").mkdir(parents=True)
    planted = elsewhere / "evidence" / path.name
    planted.write_bytes(PLANTED)
    planted_inode = planted.stat().st_ino
    inodes = reads_recorded(monkeypatch)
    path.rename(tmp_path / "log-aside")
    path.symlink_to(planted)
    with pytest.raises(LogRefused, match="^installation-log-is-a-link$"):
        log.lines()
    with pytest.raises(LogRefused, match="^installation-log-is-a-link$"):
        Checklist(log, lambda item, text: True)
    path.unlink()
    evidence = path.parent
    evidence.rename(tmp_path / "evidence-aside")
    for place, target in ((evidence, elsewhere / "evidence"), (evidence.parent, elsewhere)):
        if place == evidence.parent:
            place.rmdir()
        place.symlink_to(target)
        with pytest.raises(LogRefused, match="^installation-log-folder-is-a-link$"):
            log.lines()
        place.unlink()
    assert planted_inode not in inodes and planted.read_bytes() == PLANTED
    evidence.parent.mkdir()
    (tmp_path / "evidence-aside").rename(evidence)
    (tmp_path / "log-aside").rename(path)
    assert path.read_bytes() == kept and [line["count"] for line in log.lines()] == [1]
    assert given == [path.lstat().st_ino]


def test_reading_the_installation_log_refuses_a_fifo_or_a_second_name_at_once(tmp_path):
    """A FIFO at the log's name is refused at once (it would otherwise stall the
    installer's start), and so is a second name of another file; no log reads as none."""
    from docsuri_ops.arrangement.checklist import LogRefused

    prefix, path, log, given = log_place(tmp_path)
    assert log.lines() == []  # neither the folders nor the log exist yet
    assert not (prefix / "profile").exists()  # reading makes nothing
    path.parent.mkdir(parents=True)
    os.mkfifo(path)
    with pytest.raises(LogRefused, match="^installation-log-not-its-own-file$"):
        log.lines()
    path.unlink()
    other = tmp_path / "other"
    other.write_bytes(PLANTED)
    os.link(other, path)
    with pytest.raises(LogRefused, match="^installation-log-not-its-own-file$"):
        log.lines()
    path.unlink()
    assert log.lines() == [] and given == []


def test_a_short_write_still_writes_the_whole_line(tmp_path, monkeypatch):
    """`os.write` may write fewer bytes than asked; every byte is written, so no cut line
    joins the next, and a write that writes nothing is an error, not a silent cut."""
    prefix, path, log, _ = log_place(tmp_path)
    original = os.write
    monkeypatch.setattr(os, "write", lambda descriptor, data: original(descriptor,
                                                                       bytes(data[:5])))
    log.write("accounts", "verify", "passed", count=1)
    log.write("accounts", "verify", "passed", count=2)
    assert [line["count"] for line in log.lines()] == [1, 2]
    monkeypatch.setattr(os, "write", lambda descriptor, data: 0)
    with pytest.raises(OSError, match="installation-log-short-write"):
        log.write("accounts", "verify", "passed", count=3)
    monkeypatch.setattr(os, "write", original)
    assert [line["count"] for line in log.lines()] == [1, 2]


def test_a_socket_at_the_logs_name_gets_the_not_its_own_file_key():
    """A UNIX-domain socket answers open(2) with ENXIO on Linux and EOPNOTSUPP on macOS;
    both give the fixed key, never a plain OSError."""
    import errno

    from docsuri_ops.arrangement.checklist import LogRefused, _refusal

    for number in (errno.ENXIO, errno.EOPNOTSUPP, errno.EISDIR):
        refusal = _refusal(OSError(number, "x"))
        assert isinstance(refusal, LogRefused)
        assert str(refusal) == "installation-log-not-its-own-file"
    assert str(_refusal(OSError(errno.ELOOP, "x"))) == "installation-log-is-a-link"
    other = OSError(errno.EACCES, "x")
    assert _refusal(other) is other


def test_the_installation_log_has_no_default_base(tmp_path):
    """No caller can lose the no-link walk by leaving `base` out."""
    with pytest.raises(TypeError):
        InstallationLog(tmp_path / "installation-log.jsonl", clock=lambda: af.NOW)


def test_the_instance_and_its_databases_are_created_utf8_with_the_c_locale(stage):
    """Step 76(h)."""
    from docsuri_ops.arrangement.installer import ProductionDatabase

    recorded: list = []

    def run(argv, **options):
        recorded.append((list(argv), options.get("user"), options.get("group")))
        return b""

    context = SimpleNamespace(paths=stage.ctx.paths, accounts=stage.ctx.accounts,
                              tools=SimpleNamespace(run=run))
    ProductionDatabase(context).initdb()
    paths = stage.ctx.paths
    assert recorded == [([str(paths.postgres_runtime / "bin" / "initdb"), "-D",
                          str(paths.postgres_data), "-U", "postgres", "--auth-local=peer",
                          "--auth-host=reject", "-E", "UTF8", "--locale=C",
                          "--no-instructions"], 612, 612)]
    applied(stage)
    script = stage.database.scripts[0]
    for statement in (
        "CREATE DATABASE docsuri_v2 OWNER docsuri_operator ENCODING ''UTF8'' LOCALE ''C'' "
        "TEMPLATE template1",
        "CREATE DATABASE docsuri_v2_template OWNER docsuri_operator ENCODING ''UTF8'' "
        "LOCALE ''C'' TEMPLATE template1",
        "CREATE DATABASE docsuri_v2_platform ENCODING ''UTF8'' LOCALE ''C'' TEMPLATE template1",
    ):
        lines = [line for line in script.splitlines() if statement in line]
        assert len(lines) == 1, statement
        assert lines[0].startswith("SELECT '") and lines[0].endswith(" \\gexec"), lines[0]


# --- Your answer of 2026-11-10 ("Fix both and sweep the rest"): root never works by path in
# a folder another account owns ---------------------------------------------------------------


def snapshot(path: Path) -> tuple:
    """A file's bytes, mode, owner, inode and number of names."""
    info = path.lstat()
    return path.read_bytes(), info.st_mode, info.st_uid, info.st_ino, info.st_nlink


def another_file(tmp_path, name: str = "another-accounts-file") -> Path:
    other = tmp_path / name
    other.write_bytes(b"a file the account does not own")
    other.chmod(0o644)
    return other


def never_given(tools, path: Path) -> bool:
    """No owner was given to this file through any descriptor."""
    return af.identity(path.lstat()) not in tools.given


def swap_folder(folder: Path, elsewhere: Path, tmp_path) -> Path:
    """The account's move: its folder renamed away and a link to `elsewhere` put in its
    place; answers where the real folder went."""
    kept = tmp_path / f"kept-{folder.name}"
    folder.rename(kept)
    folder.symlink_to(elsewhere)
    return kept


def test_a_hard_link_at_a_jobs_log_name_is_refused_on_the_next_apply(stage, tmp_path):
    """The review's Critical site: the service account deletes a job's log and puts a
    second name of another file in its place; the next apply refuses it, sets no mode or
    owner on it, and once the name is gone the log is created new, 0600, the service
    account's."""
    from docsuri_ops.arrangement.installer import profile_log_files

    applied(stage)
    path = profile_log_files(stage.ctx.paths)[0]
    other = another_file(tmp_path)
    path.unlink()
    os.link(other, path)
    before = snapshot(other)
    # The other file is root's, then the service account's: both owners the log may have,
    # so only the one-name check can refuse it (the review's finding of 2026-11-10).
    for owner in (stage.ctx.root_uid, 610):
        stage.tools.given[af.identity(other.lstat())] = owner
        outcome = Installer(stage.ctx).apply()
        assert (outcome.failed, outcome.reason) == ("filter-volume-and-jobs",
                                                    "log-file-not-its-own-file"), owner
        assert snapshot(other) == before
        assert stage.tools.given[af.identity(other.lstat())] == owner
        assert not [call for call in stage.tools.calls
                    if call[0] == "fchown" and call[1] == before[3]]
        assert not [call for call in stage.tools.calls
                    if call[0] in ("chmod", "chown") and call[1] in (str(path), str(other))]
    del stage.tools.given[af.identity(other.lstat())]
    path.unlink()
    applied(stage)
    info = path.lstat()
    assert stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o600
    assert info.st_nlink == 1 and info.st_ino != other.lstat().st_ino
    assert stage.tools.owner(path) == 610 and ("fchown", info.st_ino, 610, 610) in stage.tools.calls


def test_a_link_at_a_jobs_log_or_its_folder_is_refused_when_the_log_is_placed(stage, tmp_path):
    """The links the account can put where `place_log_file` meets them: at the log's name,
    and in place of `profile/logs`; and a regular file another account owns. Each is
    refused with its key and nothing it points to changes; a file the service account
    owns has its custody set."""
    from docsuri_ops.arrangement.installer import place_log_file, profile_log_files
    from docsuri_ops.arrangement.phases import PhaseFailed

    applied(stage)
    path = profile_log_files(stage.ctx.paths)[0]
    other = another_file(tmp_path)
    before = snapshot(other)
    path.unlink()
    path.symlink_to(other)
    with pytest.raises(PhaseFailed, match="^log-file-is-a-link$"):
        place_log_file(stage.ctx, path)
    assert snapshot(other) == before and never_given(stage.tools, other)
    path.unlink()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    decoy = another_file(elsewhere, path.name)
    decoy_before = snapshot(decoy)
    kept = swap_folder(path.parent, elsewhere, tmp_path)
    with pytest.raises(PhaseFailed, match="^log-folder-is-a-link$"):
        place_log_file(stage.ctx, path)
    assert snapshot(decoy) == decoy_before and os.listdir(elsewhere) == [path.name]
    assert never_given(stage.tools, decoy)
    path.parent.unlink()
    kept.rename(path.parent)
    path.write_bytes(b"")
    path.chmod(0o644)
    stage.tools.given[af.identity(path.lstat())] = 999
    with pytest.raises(PhaseFailed, match="^log-file-not-its-own-file$"):
        place_log_file(stage.ctx, path)
    assert stat.S_IMODE(path.lstat().st_mode) == 0o644
    stage.tools.given[af.identity(path.lstat())] = 610
    place_log_file(stage.ctx, path)
    assert stat.S_IMODE(path.lstat().st_mode) == 0o600 and stage.tools.owner(path) == 610


def test_the_profile_manifest_is_written_only_through_its_folders_descriptor(stage, tmp_path):
    """The review's Major site: deleting `environment.json` makes phase 3 write it again.
    A second name of another file, or a link, left at the pending name is removed and
    never written, chmodded or given; a hard link swapped in at the very moment the owner
    is given is never what is given; a link in place of the profile folder is refused."""
    from docsuri_ops.arrangement import safe_fs
    from docsuri_ops.arrangement.phases import write_file

    applied(stage)
    paths, tools = stage.ctx.paths, stage.tools
    manifest = paths.profile / "environment.json"
    pending = manifest.with_name("environment.json.docsuri-pending")
    other = another_file(tmp_path)
    content, mode, uid, inode, _ = snapshot(other)
    manifest.unlink()
    os.link(other, pending)
    applied(stage)
    assert snapshot(other) == (content, mode, uid, inode, 1)  # only its second name went
    assert never_given(tools, other) and not pending.exists()
    info = manifest.lstat()
    assert info.st_ino != inode and stat.S_IMODE(info.st_mode) == 0o600
    assert tools.owner(manifest) == 610 and af.manifest_loads(manifest).mode == "rehearsal"
    pending.symlink_to(other)
    write_file(stage.ctx, manifest, b"{}", 0o600, "service")
    assert snapshot(other) == (content, mode, uid, inode, 1) and manifest.read_bytes() == b"{}"
    real, seen = tools.fchown, []

    def swapping(descriptor, uid_, gid_):
        pending.unlink()
        os.link(other, pending)  # the account's swap, at the moment of giving
        seen.append(os.fstat(descriptor).st_ino)
        real(descriptor, uid_, gid_)

    tools.fchown = swapping
    try:
        write_file(stage.ctx, manifest, b"{\"x\": 1}", 0o600, "service")
    finally:
        tools.fchown = real
    assert seen and seen[0] != inode
    assert snapshot(other)[:4] == (content, mode, uid, inode) and never_given(tools, other)
    manifest.unlink()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    kept = swap_folder(paths.profile, elsewhere, tmp_path)
    with pytest.raises(safe_fs.PathRefused, match="^folder-is-a-link$"):
        write_file(stage.ctx, manifest, b"{}", 0o600, "service")
    assert os.listdir(elsewhere) == []
    paths.profile.unlink()
    kept.rename(paths.profile)


def test_the_backup_agents_login_is_given_through_its_own_descriptor(stage, tmp_path):
    """The backup account's `v2-login`: a hard link swapped in at the moment of giving is
    never what is given; a link or a second name already at the name is refused with
    nothing written; a link in place of `backup-agent/` is refused."""
    from docsuri_ops.arrangement import keychain, safe_fs

    applied(stage)
    paths, tools = stage.ctx.paths, stage.tools
    login = paths.backup_agent / "v2-login"
    other = another_file(tmp_path)
    content, mode, uid, inode, _ = snapshot(other)
    login.unlink()
    real, seen = tools.fchown, []

    def swapping(descriptor, uid_, gid_):
        login.unlink()
        os.link(other, login)
        seen.append(os.fstat(descriptor).st_ino)
        real(descriptor, uid_, gid_)

    tools.fchown = swapping
    secret = keychain.generate()
    try:
        keychain.write_secret_bytes(login, secret, uid=607, gid=607, base=paths.prefix,
                                    tools=tools)
    finally:
        tools.fchown = real
    assert seen and seen[0] != inode and never_given(tools, other)
    assert snapshot(other)[:4] == (content, mode, uid, inode)
    login.unlink()
    for plant in (lambda: login.symlink_to(other), lambda: os.link(other, login)):
        plant()
        with pytest.raises(FileExistsError):
            keychain.write_secret_bytes(login, secret, uid=607, gid=607, base=paths.prefix,
                                        tools=tools)
        assert other.read_bytes() == content and never_given(tools, other)
        login.unlink()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    kept = swap_folder(paths.backup_agent, elsewhere, tmp_path)
    with pytest.raises(safe_fs.PathRefused, match="^folder-is-a-link$"):
        keychain.write_secret_bytes(login, secret, uid=607, gid=607, base=paths.prefix,
                                    tools=tools)
    assert os.listdir(elsewhere) == []
    paths.backup_agent.unlink()
    kept.rename(paths.backup_agent)
    keychain.write_secret_bytes(login, secret, uid=607, gid=607, base=paths.prefix, tools=tools)
    assert login.read_bytes() == secret and tools.owner(login) == 607


def test_a_link_in_place_of_an_accounts_folder_or_its_parent_is_refused(stage, tmp_path):
    """`folder_change`: the account swaps the folder (or the folder above it, which it
    owns) for a link after the change is planned and before it applies; the apply refuses
    it and the folder the link points to keeps its mode and owner. (A folder cannot have a
    second name.)"""
    from docsuri_ops.arrangement.phases import PhaseFailed, folder_change

    applied(stage)
    paths, tools = stage.ctx.paths, stage.tools
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    os.chmod(elsewhere, 0o755)
    (elsewhere / "cursor-key").mkdir()
    os.chmod(elsewhere / "cursor-key", 0o755)
    marks = {path: (path.lstat().st_mode, path.lstat().st_ino)
             for path in (elsewhere, elsewhere / "cursor-key")}
    ledger = paths.profile / "ledger"
    os.chmod(ledger, 0o755)
    change = folder_change(stage.ctx, "folders-and-database", ledger, "service", 0o700)
    assert change is not None
    kept = swap_folder(ledger, elsewhere, tmp_path)
    with pytest.raises(PhaseFailed, match="^folder-is-a-link$"):
        change.apply()
    ledger.unlink()
    kept.rename(ledger)
    cursor = paths.profile / "cursor-key"
    os.chmod(cursor, 0o755)
    change = folder_change(stage.ctx, "folders-and-database", cursor, "service", 0o700)
    kept = swap_folder(paths.profile, elsewhere, tmp_path)
    with pytest.raises(PhaseFailed, match="^folder-is-a-link$"):
        change.apply()
    assert {path: (path.lstat().st_mode, path.lstat().st_ino) for path in marks} == marks
    assert all(never_given(tools, path) for path in marks)
    paths.profile.unlink()
    kept.rename(paths.profile)
    change.apply()
    assert stat.S_IMODE(cursor.lstat().st_mode) == 0o700 and tools.owner(cursor) == 610


def tunnel_move(stage):
    from docsuri_ops.arrangement.phases import write_file
    from docsuri_ops.arrangement.tunnel import TunnelMove

    paths = stage.ctx.paths
    certificate = paths.control / "tunnel-certificate" / "cert.pem"
    certificate.parent.mkdir(parents=True, exist_ok=True)
    certificate.write_text("certificate fixture")
    paths.tunnel_credentials.mkdir(parents=True, exist_ok=True)
    return TunnelMove(paths=paths, tools=stage.tools, tunnel_name=af.TUNNEL, tunnel_uid=614,
                      operator_uid=501, cloudflared=paths.cloudflared_runtime / "cloudflared",
                      wait=lambda item: None, log=lambda step, outcome: None,
                      place=lambda target, content: write_file(stage.ctx, target, content,
                                                               0o644, "root"))


def test_the_tunnel_credentials_never_go_through_a_link_or_a_taken_name(stage, tmp_path):
    """`cloudflared` writes into a root-only folder; the fixed file is created new in the
    tunnel account's folder and given through its own descriptor. A second name that
    appears while `cloudflared` runs is refused and never written; a link in place of the
    credentials folder is refused before anything runs; the root-only copy never stays."""
    from docsuri_ops.arrangement.tunnel import TunnelRefused

    move, tools, paths = tunnel_move(stage), stage.tools, stage.ctx.paths
    credentials = paths.tunnel_credentials / "tunnel.json"
    other = another_file(tmp_path)
    before = snapshot(other)
    real_run = tools.run

    def planting(argv, **options):
        answer = real_run(argv, **options)
        if "create" in argv:
            os.link(other, credentials)
        return answer

    tools.run = planting
    try:
        with pytest.raises(TunnelRefused, match="^tunnel-credentials-in-the-way$"):
            move._create_tunnel()
    finally:
        tools.run = real_run
    assert snapshot(other)[:4] == before[:4] and never_given(tools, other)
    assert list(paths.control.glob(".tunnel-credentials-*")) == []
    credentials.unlink()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    runs = len([call for call in tools.calls if call[:2] == ("run", "cloudflared")])
    kept = swap_folder(paths.tunnel_credentials, elsewhere, tmp_path)
    with pytest.raises(TunnelRefused, match="^tunnel-credentials-folder-is-a-link$"):
        move._create_tunnel()
    assert os.listdir(elsewhere) == []
    assert len([call for call in tools.calls if call[:2] == ("run", "cloudflared")]) == runs
    paths.tunnel_credentials.unlink()
    kept.rename(paths.tunnel_credentials)
    move._create_tunnel()
    info = credentials.lstat()
    assert stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o600
    assert info.st_nlink == 1 and tools.owner(credentials) == 614
    assert ("fchown", info.st_ino, 614, 614) in tools.calls
    assert json.loads(credentials.read_bytes()) == {"TunnelID": "fixture"}
    assert list(paths.control.glob(".tunnel-credentials-*")) == []
    move._create_tunnel()  # made: nothing runs again
    assert len([call for call in tools.calls if call[:2] == ("run", "cloudflared")]) == runs + 1


def test_model_clones_reach_the_models_folder_only_through_descriptors(stage, tmp_path,
                                                                      monkeypatch):
    """`clone_models`: a second name of another file at a clone's name is never cloned
    over or given, and verification refuses it unread (it has two names); a name that
    appears between the look and the link is refused and never replaced; whatever your
    home folder's copy held at the clone, only its pinned digest goes on; a link in place
    of a folder in the models folder is refused. No staging folder stays, and a clean run
    gives every clone to the models account."""
    from docsuri_ops.arrangement import models, safe_fs

    tools, paths = stage.tools, stage.ctx.paths
    target, source = paths.models, stage.ctx.operator_home / ".ollama" / "models"
    target.mkdir(parents=True)
    first = sorted(models.MODEL_PINS)[0]
    blob = models.members(source, first)[1][0]
    other = another_file(tmp_path)
    before = snapshot(other)

    def clone(**options):
        return models.clone_models(tools, source, target, uid=613, gid=613,
                                   base=paths.prefix, **options)

    def files() -> list[Path]:
        return sorted(path for path in target.rglob("*") if not path.is_dir())

    (target / blob).parent.mkdir(parents=True)
    os.link(other, target / blob)
    inodes = reads_recorded(monkeypatch)
    with pytest.raises(models.ModelsRefused, match="^model-file-differs$"):
        clone()
    assert before[3] not in inodes  # refused by its two names, never read
    assert snapshot(other) == before[:4] + (2,) and never_given(tools, other)
    assert files() == [target / blob]
    (target / blob).unlink()
    real_clone = tools.clone

    def planting(origin, staged):
        real_clone(origin, staged)
        if Path(origin) == source / blob:
            os.link(other, target / blob)

    tools.clone = planting
    try:
        with pytest.raises(models.ModelsRefused, match="^model-file-in-the-way$"):
            clone()
    finally:
        tools.clone = real_clone
    assert snapshot(other)[:4] == before[:4] and files() == [target / blob]
    (target / blob).unlink()
    secret = tmp_path / "secret"
    secret.write_bytes(b"a file of yours root could read")

    def swapped(origin, staged):  # your copy's name now leads to another file
        real_clone(secret if Path(origin) == source / blob else origin, staged)

    tools.clone = swapped
    try:
        with pytest.raises(models.ModelsRefused, match="^model-file-differs$"):
            clone()
    finally:
        tools.clone = real_clone
    assert files() == []
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    kept = swap_folder(target / "blobs", elsewhere, tmp_path)
    with pytest.raises(safe_fs.PathRefused, match="^folder-is-a-link$"):
        clone()
    assert os.listdir(elsewhere) == []
    (target / "blobs").unlink()
    kept.rename(target / "blobs")
    assert list(paths.prefix.glob(".docsuri-models-*")) == []
    assert clone() == sorted(models.MODEL_PINS)
    for path in files():
        assert path.lstat().st_nlink == 1 and tools.owner(path) == 613, path
        assert ("fchown", path.lstat().st_ino, 613, 613) in tools.calls
    assert list(paths.prefix.glob(".docsuri-models-*")) == []


def test_your_login_runtimes_definition_goes_only_through_your_home_folders_descriptors(
        stage, tmp_path):
    """Phase 5 removes your login account's model job definition only as a regular file
    reached by the no-link walk: with `LaunchAgents` swapped for a link to another folder
    holding a file of that name, nothing is removed there."""
    from docsuri_ops.arrangement.phases import LOGIN_OLLAMA, remove_login_definition

    home = stage.ctx.operator_home
    agents = home / "Library" / "LaunchAgents"
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    decoy = another_file(elsewhere, f"{LOGIN_OLLAMA}.plist")
    before = snapshot(decoy)
    kept = swap_folder(agents, elsewhere, tmp_path)
    assert remove_login_definition(home.parent, agents / f"{LOGIN_OLLAMA}.plist") is False
    assert snapshot(decoy) == before
    agents.unlink()
    kept.rename(agents)
    definition = agents / f"{LOGIN_OLLAMA}.plist"
    assert definition.is_file()
    assert remove_login_definition(home.parent, definition) is True
    assert not definition.exists()


# --- The review of the sweep (2026-11-10): each fix tested where production meets it --------


def test_phase_5_keeps_a_decoy_behind_a_link_in_place_of_your_launch_agents(stage, tmp_path):
    """Phase 5's `_move_models` itself, run by the installer: with your `LaunchAgents`
    swapped for a link to another folder holding a file of the definition's name, the
    phase moves the models and removes nothing there; your real definition is untouched
    too, since the walk never reached it."""
    from docsuri_ops.arrangement.phases import LOGIN_OLLAMA

    agents = stage.ctx.operator_home / "Library" / "LaunchAgents"
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    decoy = another_file(elsewhere, f"{LOGIN_OLLAMA}.plist")
    before = snapshot(decoy)
    kept = swap_folder(agents, elsewhere, tmp_path)
    mine = snapshot(kept / f"{LOGIN_OLLAMA}.plist")
    applied(stage)
    assert ("bootstrap", "org.docsuri.models") in stage.tools.calls  # phase 5 ran its move
    assert snapshot(decoy) == before and os.listdir(elsewhere) == [decoy.name]
    assert snapshot(kept / f"{LOGIN_OLLAMA}.plist") == mine
    agents.unlink()
    kept.rename(agents)


def test_a_rendered_files_current_bytes_are_read_only_through_the_walk(stage, tmp_path,
                                                                       monkeypatch):
    """Sweep fix 3 (`file_change`'s `_read_target`), through phase 3's own planning: a
    second name of another file, then a link to it, at `postgres/data/postgresql.conf` (the
    database account's folder; the rule files moved to root's own folder on 2026-11-11)
    and at `control/effects/operator/driver.json` (your login's), each holding the very
    bytes the plan would accept, stop planning with `rule-file-not-a-regular-file`; so does
    a link in place of `postgres/data` to a folder holding the rendered `postgresql.conf`.
    None of those files is read, and each keeps its bytes, mode, owner, inode and number of
    names."""
    from docsuri_ops.arrangement import render
    from docsuri_ops.arrangement.installer import FoldersDatabasePhase
    from docsuri_ops.arrangement.phases import PhaseFailed, file_change

    applied(stage)
    paths = stage.ctx.paths
    hba = paths.postgres_data / "postgresql.conf"
    item = next(rendered for rendered in render.render_postgres(paths, stage.ctx.accounts)
                if rendered.target == hba)
    targets = (hba, paths.effects / "operator" / "driver.json")
    others = {target: tmp_path / f"other-{target.name}" for target in targets}
    for target, other in others.items():
        other.write_bytes(target.read_bytes())
        other.chmod(0o600)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    decoy = elsewhere / hba.name
    decoy.write_bytes(item.content)
    decoy.chmod(item.mode)
    marks = {path: snapshot(path) for path in (*others.values(), decoy)}
    inodes = reads_recorded(monkeypatch)
    for target, other in others.items():
        kept = tmp_path / f"kept-{target.name}"
        target.rename(kept)
        for plant in (
            lambda other=other, target=target: os.link(other, target),
            lambda other=other, target=target: target.symlink_to(other),
        ):
            plant()
            with pytest.raises(PhaseFailed, match="^rule-file-not-a-regular-file$"):
                FoldersDatabasePhase().changes(stage.ctx)
            target.unlink()
        kept.rename(target)
    kept = swap_folder(paths.postgres_data, elsewhere, tmp_path)
    with pytest.raises(PhaseFailed, match="^rule-file-not-a-regular-file$"):
        file_change(stage.ctx, "folders-and-database", item)
    paths.postgres_data.unlink()
    kept.rename(paths.postgres_data)
    assert not {mark[3] for mark in marks.values()} & set(inodes)
    assert {path: snapshot(path) for path in marks} == marks
    assert all(never_given(stage.tools, path) for path in marks)
    assert file_change(stage.ctx, "folders-and-database", item) is None  # in place again


def test_verifying_the_models_folder_refuses_a_second_name_or_another_owner_unread(
        stage, tmp_path, monkeypatch):
    """`verify_models`, as phase 5's own check calls it: a second name of a file holding
    the manifest's very bytes, owned by the models account, is refused unread (it has two
    names), and so is the models account's manifest given to another owner; a manifest of
    its own that does not decode, or is outside its shape, is refused with a fixed key
    rather than escaping as an uncaught error."""
    from docsuri_ops.arrangement import models
    from docsuri_ops.arrangement.phases import ModelsTunnelPhase

    tools, paths = stage.tools, stage.ctx.paths
    uid = stage.ctx.accounts.models.uid
    source, target = stage.ctx.operator_home / ".ollama" / "models", paths.models
    target.mkdir(parents=True)
    assert models.clone_models(tools, source, target, uid=uid, gid=uid,
                               base=paths.prefix) == sorted(models.MODEL_PINS)
    phase = ModelsTunnelPhase()
    assert phase._models_in_place(stage.ctx) is True

    def verify():
        return models.verify_models(target, base=paths.prefix,
                                    owned_by=lambda d: tools.descriptor_owner(d) == uid)

    path = target / models.members(source, sorted(models.MODEL_PINS)[0])[0][0]
    accepted = path.read_bytes()
    other = tmp_path / "other-manifest"
    other.write_bytes(accepted)
    tools.given[af.identity(other.lstat())] = uid
    kept = tmp_path / "kept-manifest"
    path.rename(kept)
    os.link(other, path)
    inodes = reads_recorded(monkeypatch)
    with pytest.raises(models.ModelsRefused, match="^model-file-differs$"):
        verify()
    assert phase._models_in_place(stage.ctx) is False
    assert other.lstat().st_ino not in inodes
    path.unlink()
    kept.rename(path)
    tools.given[af.identity(path.lstat())] = 999
    with pytest.raises(models.ModelsRefused, match="^model-file-differs$"):
        verify()
    assert path.lstat().st_ino not in inodes
    tools.given[af.identity(path.lstat())] = uid
    nested = b"[" * 100_000 + b"]" * 100_000  # within the size bound, past the decoder's depth
    assert len(nested) <= models.MAX_MODEL_MANIFEST
    for shape in (b"not json", b'{"config": 1, "layers": []}', b'{"config": {}}', b"[]",
                  nested):
        path.write_bytes(shape)
        with pytest.raises(models.ModelsRefused, match="^model-blob-identity$"):
            verify()
        assert phase._models_in_place(stage.ctx) is False  # phase 5's own check, no traceback
    path.write_bytes(accepted)
    assert verify() == sorted(models.MODEL_PINS) and phase._models_in_place(stage.ctx)


def test_a_socket_at_a_log_name_gets_its_not_its_own_file_key(tmp_path, stage, monkeypatch):
    """A real UNIX-domain socket, bound where the code meets one (by a relative name, so
    the path stays within the socket's length limit): at the installation log's name it
    is refused on write and on read with `installation-log-not-its-own-file`; at a job's
    log name with `log-file-not-its-own-file`; and `safe_fs.open_existing`, whose own
    copy of the mapping serves the logs filter and the effects writers, refuses it with
    `not-its-own-file`."""
    import socket

    from docsuri_ops.arrangement import safe_fs
    from docsuri_ops.arrangement.checklist import LogRefused
    from docsuri_ops.arrangement.installer import place_log_file, profile_log_files
    from docsuri_ops.arrangement.phases import PhaseFailed

    def bound(path: Path) -> socket.socket:
        monkeypatch.chdir(path.parent)
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(path.name)
        assert stat.S_ISSOCK(path.lstat().st_mode)
        return listener

    prefix, path, log, given = log_place(tmp_path)
    path.parent.mkdir(parents=True)
    with contextlib.closing(bound(path)):
        with pytest.raises(LogRefused, match="^installation-log-not-its-own-file$"):
            log.write("accounts", "verify", "passed", count=1)
        with pytest.raises(LogRefused, match="^installation-log-not-its-own-file$"):
            log.lines()
        with safe_fs.folder_at(prefix, path.parent) as folder:
            with pytest.raises(safe_fs.PathRefused, match="^not-its-own-file$"):
                safe_fs.open_existing(folder, path.name)
    assert given == []
    applied(stage)
    job_log = profile_log_files(stage.ctx.paths)[0]
    job_log.unlink()
    with contextlib.closing(bound(job_log)):
        with pytest.raises(PhaseFailed, match="^log-file-not-its-own-file$"):
            place_log_file(stage.ctx, job_log)
    job_log.unlink()
    place_log_file(stage.ctx, job_log)
    assert stat.S_ISREG(job_log.lstat().st_mode)


def test_a_second_name_held_while_the_manifest_is_recorded_keeps_the_file_checked(stage):
    """The re-review of 2026-11-10 (Major): the database account gives `postgresql.conf` a
    second name right after phase 3 writes it and keeps it until `apply`'s `finally` has
    written the manifest. The manifest still holds the file, with `UNREAD_DIGEST`; once
    the second name is gone and the file changed, the digest the isolation check's `files`
    item reads through the walk differs from the recorded one, so it answers
    `file-differs`. The next apply, with the file a regular one again, puts the rendered
    bytes back and records their real digest."""
    from docsuri_ops.arrangement import render
    from docsuri_ops.arrangement.installer import FoldersDatabasePhase
    from docsuri_ops.isolation_check import _digest_within

    paths = stage.ctx.paths
    config = paths.postgres_data / "postgresql.conf"
    second = paths.postgres_data / "postgresql.conf.kept"

    class SecondNameAfterPhase3(FoldersDatabasePhase):
        def verify(self, ctx):
            super().verify(ctx)
            os.link(config, second)  # after phase 3's own check: nothing after reads it

    phases = tuple(SecondNameAfterPhase3() if isinstance(phase, FoldersDatabasePhase)
                   else phase for phase in PHASES)
    outcome = Installer(stage.ctx, phases).apply()
    assert outcome.failed is None, outcome.as_dict()
    assert second.lstat().st_nlink == 2
    recorded = manifest.read_manifest(paths).entry("postgres/data/postgresql.conf")
    assert recorded == manifest.Entry("postgres/data/postgresql.conf", "config",
                                      manifest.UNREAD_DIGEST, None, stage.ctx.uid("database"))
    second.unlink()
    config.write_bytes(config.read_bytes() + b"listen_addresses = '*'\n")
    found = _digest_within(paths.prefix, config)
    assert found is not None and found != recorded.sha256  # `files`' own comparison
    applied(stage)
    rendered = next(item for item in render.render_postgres(paths, stage.ctx.accounts)
                    if item.target == config)
    assert manifest.read_manifest(paths).entry("postgres/data/postgresql.conf").sha256 == (
        hashlib.sha256(rendered.content).hexdigest())


def test_bytes_the_database_account_rewrote_after_phase_3_never_become_the_baseline(
        stage, monkeypatch):
    """The batch-7 review (Major): right after phase 3's own check, the database account
    rewrites `postgresql.conf` in place, a regular file with one name (`listen_addresses =
    '*'`). Since your answer of 2026-11-11 ("Map the login, root rules") the rule files
    are root's, in a folder that account cannot write; they are rewritten here in the
    same window all the same (`trust`, a wider map), as a rule file changed between phase
    3 and the record would be. `apply`'s `finally` records the manifest, but no file holds
    the bytes the installer rendered, so `postgresql.conf` keeps `UNREAD_DIGEST` and
    `pgHbaSha256` and `pgIdentSha256` are left empty: the isolation check's `files` item
    answers `file-differs` and its `database` item `database-hba-differs`. The same check
    on a clean apply passes both items, so nothing else fails them; the next apply puts the
    rendered bytes back and records their real digests."""
    from docsuri_ops import isolation_check
    from docsuri_ops.arrangement import render
    from docsuri_ops.arrangement.installer import FoldersDatabasePhase

    paths = stage.ctx.paths
    config = paths.postgres_data / "postgresql.conf"
    hba = paths.postgres_rules / "pg_hba.conf"
    ident = paths.postgres_rules / "pg_ident.conf"

    class Loopback:
        def listeners(self, port):
            return [("database", f"127.0.0.1:{port}")]

        def hba_file(self, psql, socket, uid):
            return str(hba)  # the launch job pins it (your answer of 2026-11-11)

        def ident_file(self, psql, socket, uid):
            return str(ident)

    # Ownership is the test machine's account here, not the arrangement's: the custody
    # half of `_owned` is set aside so only the digest comparison decides `files`.
    monkeypatch.setattr(isolation_check, "_owned",
                        lambda path, owner, *, kind=stat.S_ISREG:
                        path.exists() and kind(path.lstat().st_mode))

    def answers() -> dict:
        check = isolation_check.IsolationCheck(isolation_check.CheckContext(
            paths=paths, accounts=stage.ctx.accounts, tools=Loopback(),
            owner_uid=stage.ctx.root_uid))
        found = {}
        for item in ("files", "database"):
            try:
                getattr(check, item)()
                found[item] = "passed"
            except isolation_check.ItemFailed as failure:
                found[item] = failure.reason
        assert check.change_in_progress is False
        return found

    applied(stage)
    assert answers() == {"files": "passed", "database": "passed"}  # the control

    class RewrittenAfterPhase3(FoldersDatabasePhase):
        def verify(self, ctx):
            super().verify(ctx)
            config.write_bytes(config.read_bytes() + b"listen_addresses = '*'\n")
            hba.write_bytes(b"host all all 0.0.0.0/0 trust\n")
            ident.write_bytes(b"docsuri_superuser /^(.*)$ postgres\n")

    phases = tuple(RewrittenAfterPhase3() if isinstance(phase, FoldersDatabasePhase)
                   else phase for phase in PHASES)
    outcome = Installer(stage.ctx, phases).apply()
    assert outcome.failed is None, outcome.as_dict()
    for path in (config, hba, ident):
        assert path.lstat().st_nlink == 1 and stat.S_ISREG(path.lstat().st_mode)
    recorded = manifest.read_manifest(paths)
    for name in ("postgres/data/postgresql.conf", "postgres-rules/pg_hba.conf",
                 "postgres-rules/pg_ident.conf"):
        assert recorded.entry(name).sha256 == manifest.UNREAD_DIGEST, name
    assert recorded.pg_hba_sha256 is None and recorded.pg_ident_sha256 is None
    assert answers() == {"files": "file-differs", "database": "database-hba-differs"}
    rendered = {item.target: item.content
                for item in render.render_postgres(paths, stage.ctx.accounts)}
    applied(stage)
    again = manifest.read_manifest(paths)
    assert again.entry("postgres/data/postgresql.conf").sha256 == (
        hashlib.sha256(rendered[config]).hexdigest())
    assert again.pg_hba_sha256 == hashlib.sha256(rendered[hba]).hexdigest()
    assert again.pg_ident_sha256 == hashlib.sha256(rendered[ident]).hexdigest()
    assert answers() == {"files": "passed", "database": "passed"}


def test_the_manifest_is_recorded_without_raising_and_keeps_each_refused_file(
        stage, tmp_path, monkeypatch):
    """The re-review of 2026-11-10 (Minor): `Installer.apply` driven to its `finally` with
    a FIFO, then a second name of another file, at `postgresql.conf`, `pg_hba.conf` and
    `pg_ident.conf`, and then with a link in place of `postgres/data`, and of the rules
    folder (root's since your answer of 2026-11-11), to a folder holding copies of its
    files. Each run returns its `Outcome` (phase 3 stops) instead of raising; the other
    files are never read and keep their bytes, mode, owner, inode and number of names; and
    the manifest keeps the refused file with `UNREAD_DIGEST` (`pgHbaSha256` or
    `pgIdentSha256` empty for a rule file, which the `database` item counts as a
    difference)."""
    applied(stage)
    paths = stage.ctx.paths
    targets = {"postgresql.conf": paths.postgres_data / "postgresql.conf",
               "pg_hba.conf": paths.postgres_rules / "pg_hba.conf",
               "pg_ident.conf": paths.postgres_rules / "pg_ident.conf"}
    digests = {"pg_hba.conf": "pg_hba_sha256", "pg_ident.conf": "pg_ident_sha256"}
    others = {}
    for name, target in targets.items():
        others[name] = tmp_path / f"other-{name}"
        others[name].write_bytes(target.read_bytes())  # the very bytes in place
        others[name].chmod(0o600)
    elsewhere = {folder: tmp_path / f"elsewhere-{folder.name}"
                 for folder in (paths.postgres_data, paths.postgres_rules)}
    for name, target in targets.items():
        copy = elsewhere[target.parent] / name
        copy.parent.mkdir(exist_ok=True)
        copy.write_bytes(target.read_bytes())
        copy.chmod(0o600)
    marks = {path: snapshot(path) for path in (
        *others.values(), *(file for folder in elsewhere.values() for file in folder.iterdir()))}
    inodes = reads_recorded(monkeypatch)

    def recorded_after_apply() -> manifest.Manifest:
        outcome = Installer(stage.ctx).apply()  # returns: nothing escapes the `finally`
        assert outcome.failed == "folders-and-database", outcome.as_dict()
        return manifest.read_manifest(paths)

    def unread(recorded: manifest.Manifest, name: str) -> bool:
        entry = recorded.entry(manifest.manifest_path(paths, targets[name]))
        return entry is not None and entry.sha256 == manifest.UNREAD_DIGEST

    def empty_digests(recorded: manifest.Manifest) -> set[str]:
        return {name for name, field in digests.items() if getattr(recorded, field) is None}

    for name, target in targets.items():
        kept = tmp_path / f"kept-{name}"
        target.rename(kept)
        for plant in (
            lambda target=target: os.mkfifo(target, 0o600),
            lambda name=name, target=target: os.link(others[name], target),
        ):
            plant()
            recorded = recorded_after_apply()
            assert unread(recorded, name)
            assert empty_digests(recorded) == ({name} & set(digests))
            target.unlink()
        kept.rename(target)
    for folder, holding in elsewhere.items():
        names = {name for name, target in targets.items() if target.parent == folder}
        kept = swap_folder(folder, holding, tmp_path)
        recorded = recorded_after_apply()
        assert all(unread(recorded, name) for name in names)
        assert empty_digests(recorded) == (names & set(digests))
        folder.unlink()
        kept.rename(folder)
    assert not {mark[3] for mark in marks.values()} & set(inodes)
    assert {path: snapshot(path) for path in marks} == marks
    assert all(never_given(stage.tools, path) for path in marks)
    applied(stage)  # in place again: real digests
    assert not any(unread(manifest.read_manifest(paths), name) for name in targets)


# --- U8 plan Step 137(c): the in-person password change (D8, L2-7) ------------------------------

CHANGE_ACTOR = "fixture-operator"  # an account name in the log's key form, no person's


def password_stage(stage) -> SimpleNamespace:
    """The stage applied with the test's own user as root, every holder in place."""
    stage.ctx.root_uid = os.getuid()
    applied(stage)
    return SimpleNamespace(paths=stage.ctx.paths)


def holder_paths(paths) -> list[Path]:
    from docsuri_ops.arrangement import password_change as pc

    return [holder.location(paths) for holder in pc.HOLDERS.values()
            if holder.kind != "keychain"]


def holder_state(stage) -> dict:
    """Every holder's bytes and mode (a link's target, a missing file's absence) and the
    keychain's items, so a test can tell whether a change touched any of them."""
    found: dict = {"keychain": dict(stage.tools.keychain)}
    for path in holder_paths(stage.ctx.paths):
        if path.is_symlink():
            found[str(path)] = ("link", os.readlink(path))
        elif path.exists():
            found[str(path)] = (stat.S_IMODE(path.lstat().st_mode), path.read_bytes())
        else:
            found[str(path)] = None
    return found


def pending_names(paths) -> list[Path]:
    return [path for path in (holder.with_name(holder.name + ".docsuri-pending")
                              for holder in holder_paths(paths))
            if path.exists() or path.is_symlink()]


def change_lines(paths, log) -> tuple[list[dict], list[dict]]:
    """The `password-change` lines of the root record and of the installation log."""
    from docsuri_ops.arrangement.password_change import AUDIT_RECORD

    root = InstallationLog(paths.control / AUDIT_RECORD, clock=lambda: af.NOW,
                           base=paths.prefix)
    return ([line for line in root.lines() if line["phase"] == "password-change"],
            [line for line in log.lines() if line["phase"] == "password-change"])


def write_stop_records(paths, labels) -> None:
    """v2's stop records as `docsuri-service-stop` writes them, owned by the test's own
    user (the stage's root), each with a generated receipt."""
    import datetime as dt
    import uuid

    paths.control_stops.mkdir(parents=True, exist_ok=True)
    for label in labels:
        record = {"label": label, "receiptId": str(uuid.uuid4()),
                  "stoppedAt": (af.NOW - dt.timedelta(minutes=1)).isoformat(),
                  "expiresAt": (af.NOW + dt.timedelta(days=1)).isoformat()}
        target = paths.control_stops / f"{label}.json"
        target.write_bytes(json.dumps(record, sort_keys=True).encode())
        target.chmod(0o644)


class UnreadableLedger:
    """Raise-only: a ledger view whose every read fails."""

    def records(self, kind):
        raise RuntimeError("the ledger cannot be read")


def test_a_password_change_outside_its_set_or_its_preconditions_changes_nothing(
        stage, tmp_path, clock):
    from uuid import uuid4

    from backend.modules.operations.ledger import utc_text
    from backend.modules.operations.migration_records import MigrationRuns
    from backend.modules.operations.recovery import RecoveryRequests
    from backend.u8_policy import SYNTHETIC_OPERATIONS
    from docsuri_ops.arrangement import password_change as pc
    from docsuri_ops.production_tool import V2_ROLES
    from docsuri_ops.release import run_marker_path
    from tests.u8_service_operations_integration import recovery_flows as rf

    paths = password_stage(stage).paths
    ledger = rf.open_ledger(tmp_path, clock)
    requests = RecoveryRequests(ledger, SYNTHETIC_OPERATIONS, clock=clock,
                                mfa_current=lambda account, at: True)

    def refused(login: str, reason: str, view=ledger) -> None:
        state, scripts = holder_state(stage), list(stage.database.scripts)
        mutations, marker = stage.tools.mutations(), manifest.marker(paths)
        root_before, log_before = (len(lines) for lines in change_lines(paths, stage.ctx.log))
        result = pc.change_password(stage.ctx, login, actor=CHANGE_ACTOR, ledger=view)
        assert (result["ok"], result["outcome"], result["reason"]) == (
            False, "refused", reason), (login, result)
        assert stage.database.scripts == scripts and stage.tools.mutations() == mutations
        assert holder_state(stage) == state and pending_names(paths) == []
        assert manifest.marker(paths) == marker
        for lines, before in zip(change_lines(paths, stage.ctx.log), (root_before, log_before),
                                 strict=True):
            assert [(line["outcome"], line["reason"], line["actor"]) for line in
                    lines[before:]] == [("refused", reason, CHANGE_ACTOR)], login

    refused("unknown", "login-outside-its-set")
    manifest.begin_change(paths, "release-install", clock=stage.ctx.clock,
                          owner_uid=os.getuid())
    refused("owners", "arrangement-change-in-progress")
    manifest.end_change(paths)
    write_stop_records(paths, V2_ROLES[:2])
    refused("owners", "v2-running")
    backup = rf.set_record(ledger, now=clock())
    verify = requests.request(
        origin="schedule", operation="restore.verify", environment="live",
        target_id=backup["backupId"],
        expected_revision=ledger.revision("backup-set", backup["backupId"]),
        submission_id=uuid4())["recoveryRequestId"]
    requests.admit(verify)
    for login in ("scheduler", "backup-agent"):
        refused(login, "scheduled-work-running")
    requests.cancel(verify)
    marker_path = run_marker_path(paths)
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_bytes(json.dumps({"pid": os.getpid()}).encode())
    refused("operator", "release-run-active")
    marker_path.unlink()
    production = requests.request(
        origin="administrator", operation="restore.production", environment="live",
        target_id=backup["backupId"],
        expected_revision=ledger.revision("backup-set", backup["backupId"]),
        submission_id=uuid4(), requested_by=str(uuid4()),
        mfa_verified_at=utc_text(clock()))["recoveryRequestId"]
    approval = rf.approval_record(ledger, "production-restore", production, now=clock())
    requests.admit(production, approval_id=approval["approvalId"])
    refused("operator", "recovery-under-way")
    requests.cancel(production)
    runs = MigrationRuns(ledger, clock=clock)
    go_ahead = rf.approval_record(ledger, "dry-run-go-ahead", str(uuid4()), now=clock())
    run = runs.start("dry", tool_commit="0" * 40, go_ahead=go_ahead["approvalId"])["runId"]
    for state in ("copying", "importing"):
        runs.move(run, state)
    refused("operator", "migration-under-way")
    runs.move(run, "failed")
    refused("operator", "ledger-unreadable", view=UnreadableLedger())
    write_stop_records(paths, V2_ROLES)
    reader = paths.profile / "platform-reader.json"
    owners = paths.profile / "owner-credentials.json"
    owners.chmod(0o644)
    refused("owners", "holder-refused")
    owners.chmod(0o600)
    kept = owners.with_name("kept-owner-credentials.json")
    owners.rename(kept)
    owners.symlink_to(kept)
    refused("owners", "holder-refused")
    owners.unlink()
    kept.rename(owners)
    reader.rename(tmp_path / "reader-elsewhere.json")
    refused("platform-reader", "holder-missing")
    ledger.close()


def test_a_password_change_that_fails_midway_says_where_it_stopped(stage, tmp_path, clock):
    from docsuri_ops.arrangement import password_change as pc
    from docsuri_ops.production_tool import V2_ROLES
    from tests.u8_service_operations_integration import recovery_flows as rf

    paths = password_stage(stage).paths
    write_stop_records(paths, V2_ROLES)
    ledger = rf.open_ledger(tmp_path, clock)
    owners = paths.profile / "owner-credentials.json"
    before = owners.read_bytes()
    held: list[bool] = []

    def refusing_script(script):
        """Raise-only: it records whether the word's marker holds the change, then
        refuses."""
        held.append(manifest.marker_valid(paths, stage.ctx.clock()))
        raise RuntimeError("the instance refused the script")

    stage.database.run_script = refusing_script
    result = pc.change_password(stage.ctx, "owners", actor=CHANGE_ACTOR, ledger=ledger)
    del stage.database.run_script
    assert held == [True]
    assert (result["outcome"], result["reason"]) == ("failed", "verifier-not-set"), result
    assert owners.read_bytes() == before and pending_names(paths) == []
    assert manifest.marker(paths) is None
    scripts = len(stage.database.scripts)
    stored = dict(stage.tools.keychain)

    def storing_nothing(service, account, secret, **options):
        """The keychain write that answers but keeps nothing."""
        stage.tools._record("keychain_add", service, account, dict(options))

    stage.tools.keychain_add = storing_nothing
    result = pc.change_password(stage.ctx, "operator", actor=CHANGE_ACTOR, ledger=ledger)
    del stage.tools.keychain_add
    assert (result["outcome"], result["reason"]) == ("failed", "holder-not-rewritten"), result
    assert stage.tools.keychain == stored
    assert len(stage.database.scripts) == scripts + 1
    assert "ALTER ROLE docsuri_operator PASSWORD 'SCRAM-SHA-256$4096:" in (
        stage.database.scripts[-1])
    root, log = change_lines(paths, stage.ctx.log)
    for lines in (root, log):
        assert [(line["step"], line["outcome"], line["reason"]) for line in lines] == [
            ("owners", "failed", "verifier-not-set"),
            ("operator", "failed", "holder-not-rewritten")]
    assert manifest.marker(paths) is None
    ledger.close()


def test_the_scram_verifier_matches_an_independent_computation():
    import base64
    import hmac

    from docsuri_ops.arrangement import password_change as pc

    password, salt = secrets.token_hex(32), secrets.token_bytes(16)  # per run (L1-36)
    verifier = pc.scram_sha256_verifier(password, salt=salt)
    form = re.fullmatch(r"SCRAM-SHA-256\$4096:([A-Za-z0-9+/=]+)\$([A-Za-z0-9+/=]+):"
                        r"([A-Za-z0-9+/=]+)", verifier)
    assert form is not None
    salted = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 4096)
    client_key = hmac.new(salted, b"Client Key", hashlib.sha256).digest()
    assert base64.b64decode(form[1]) == salt
    assert base64.b64decode(form[2]) == hashlib.sha256(client_key).digest()
    assert base64.b64decode(form[3]) == hmac.new(salted, b"Server Key",
                                                 hashlib.sha256).digest()
    roles = pc.HOLDERS["scheduler"].roles
    passwords = {role: secrets.token_hex(32) for role in roles}
    verifiers = {role: pc.scram_sha256_verifier(value, salt=secrets.token_bytes(16))
                 for role, value in passwords.items()}
    script = pc.alter_roles_script("scheduler", verifiers)
    assert re.findall(r"^ALTER ROLE (\S+) PASSWORD '", script, re.MULTILINE) == list(roles)
    assert script.splitlines()[:3] == ["\\set ON_ERROR_STOP on", "\\connect postgres", "BEGIN;"]
    assert script.splitlines()[-1] == "COMMIT;"
    assert not any(value in script for value in passwords.values())
    for outside in ({**verifiers, "docsuri_operator": verifier},
                    {roles[0]: verifiers[roles[0]]},
                    {**verifiers, roles[0]: "md5" + "0" * 32},
                    {**verifiers, roles[0]: verifier + "'; DROP ROLE docsuri_operator; --"}):
        with pytest.raises(pc.Refused, match="^verifier-outside-its-form$"):
            pc.alter_roles_script("scheduler", outside)
    with pytest.raises(pc.Refused, match="^verifier-outside-its-form$"):
        pc.alter_roles_script("unknown", verifiers)


class UnreadLedger:
    """Raise-only: a ledger view the word builds and never reads in these cases."""

    def records(self, kind):
        raise AssertionError("the word read the ledger")


def test_the_change_password_word_reads_its_input_and_its_actor(stage, monkeypatch, capsys):
    import io
    import pwd
    import sys

    from docsuri_ops.arrangement import installer
    from docsuri_ops.arrangement import password_change as pc
    from docsuri_ops.arrangement.phases import write_file

    paths = password_stage(stage).paths
    scripts, mutations = list(stage.database.scripts), stage.tools.mutations()

    def word(raw: bytes, environ: dict) -> tuple[dict, int]:
        state = holder_state(stage)
        answer = pc.run_change_password(io.BytesIO(raw), environ, paths=paths,
                                        context=stage.ctx, ledger=UnreadLedger())
        assert holder_state(stage) == state
        return answer

    own = {"SUDO_UID": str(os.getuid())}
    for raw, reason in ((b'{"login": "owners", "extra": 1}', "input-field-refused"),
                        (b'{"name": "owners"}', "input-field-refused"),
                        (b'{"login": 7}', "input-field-refused"),
                        (b'["owners"]', "input-not-an-object"),
                        (b"not json", "input-not-json"),
                        # Nesting deep enough to exhaust the parser within 4 KiB.
                        (b"[" * 4000, "input-not-json"),
                        (b'{"login": "' + b"a" * 4096 + b'"}', "input-too-large")):
        result, code = word(raw, own)
        assert (code, result["ok"], result["reason"]) == (1, False, reason), raw[:40]
    for environ, reason in (({}, "in-person-actor-refused"),
                            ({"SUDO_UID": "0"}, "not-the-installed-operator")):
        result, code = word(b'{"login": "owners"}', environ)
        assert (code, result["reason"]) == (1, reason), environ
    assert stage.database.scripts == scripts and stage.tools.mutations() == mutations
    for name in [name for name in os.environ if name.startswith(("PYTHON", "DYLD_", "LD_"))]:
        monkeypatch.delenv(name)
    assert installer.main(["change-password"]) == 2  # this test never runs as root
    assert json.loads(capsys.readouterr().out)["reason"] == "root-required"
    # The routing case: its actor is the test's own account, named as the installed
    # operator in a root-owned (here, the test's own) authorities file.
    authorities = paths.control / "platform-authorities.json"
    value = json.loads(authorities.read_bytes())
    value["actors"]["operator"] = pwd.getpwuid(os.getuid()).pw_name
    write_file(stage.ctx, authorities, json.dumps(value, sort_keys=True).encode(), 0o644, "root")
    assert authorities.stat().st_uid == stage.ctx.root_uid
    assert not authorities.stat().st_mode & 0o022
    (paths.control / "installation.json").write_text("{}")
    monkeypatch.setenv("SUDO_UID", str(os.getuid()))
    monkeypatch.setattr(installer.os, "geteuid", lambda: 0)
    monkeypatch.setattr(installer, "ArrangementPaths", lambda: paths)
    monkeypatch.setattr(installer, "production_context", lambda settings, *, clock: stage.ctx)
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(b'{"login": "unknown"}')))
    assert installer.main(["change-password"]) == 1
    printed = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert (printed["ok"], printed["reason"]) == (False, "login-outside-its-set")
    root, log = change_lines(paths, stage.ctx.log)
    assert root[-1]["actor"] == log[-1]["actor"] == value["actors"]["operator"]


def test_the_work_reader_names_only_work_under_way(tmp_path, clock):
    from uuid import uuid4

    from backend.modules.operations.ledger import utc_text
    from backend.modules.operations.migration_records import MigrationRuns
    from backend.modules.operations.recovery import RecoveryRequests
    from backend.u8_policy import SYNTHETIC_OPERATIONS
    from docsuri_ops.arrangement import password_change as pc
    from tests.u8_service_operations_integration import recovery_flows as rf

    ledger = rf.open_ledger(tmp_path, clock)
    requests = RecoveryRequests(ledger, SYNTHETIC_OPERATIONS, clock=clock,
                                mfa_current=lambda account, at: True)

    def named(*, scheduled: bool, recovery: bool, migration: bool = False) -> None:
        expected = {login: None for login in pc.HOLDERS}
        for login in pc.SCHEDULED:
            expected[login] = "scheduled-work-running" if scheduled else None
        for login in pc.KEYCHAIN_LOGINS:
            expected[login] = ("recovery-under-way" if recovery else
                               "migration-under-way" if migration else None)
        assert {login: pc.work_under_way(ledger, login) for login in pc.HOLDERS} == expected

    def request(operation: str, backup: dict | None) -> str:
        options = {"origin": "schedule"}
        if operation == "restore.production":
            options = {"origin": "administrator", "requested_by": str(uuid4()),
                       "mfa_verified_at": utc_text(clock())}
        target = "docsuri_u8" if backup is None else backup["backupId"]
        expected = (requests.backup_revision("live") if backup is None
                    else ledger.revision("backup-set", target))
        identity = requests.request(operation=operation, environment="live", target_id=target,
                                    expected_revision=expected, submission_id=uuid4(),
                                    **options)["recoveryRequestId"]
        approval = None
        if operation == "restore.production":
            approval = rf.approval_record(ledger, "production-restore", identity,
                                          now=clock())["approvalId"]
        requests.admit(identity, approval_id=approval)
        requests.start(identity)
        return identity

    named(scheduled=False, recovery=False)  # an empty ledger names nothing
    backup = rf.set_record(ledger, now=clock())
    for operation in ("backup.create", "restore.verify"):
        source = None if operation == "backup.create" else backup
        identity = request(operation, source)
        named(scheduled=True, recovery=True)  # running
        requests.advance(identity, "verifying", allowed_from=("running",))
        named(scheduled=True, recovery=True)
        requests.advance(identity, "succeeded", allowed_from=("verifying",))
        named(scheduled=False, recovery=False)
        identity = request(operation, source)
        requests.outcome_unknown(identity, evidence=["pending:fixture"])
        named(scheduled=True, recovery=True)
        requests.settle_unknown(identity, "failed")
        named(scheduled=False, recovery=False)
    identity = request("restore.production", backup)
    named(scheduled=False, recovery=True)
    requests.outcome_unknown(identity, evidence=["pending:fixture"])
    requests.settle_unknown(identity, "failed")
    named(scheduled=False, recovery=False)
    runs = MigrationRuns(ledger, clock=clock)
    go_ahead = rf.approval_record(ledger, "dry-run-go-ahead", str(uuid4()), now=clock())
    run = runs.start("dry", tool_commit="0" * 40, go_ahead=go_ahead["approvalId"])["runId"]
    named(scheduled=False, recovery=False, migration=True)  # preparing
    for state in ("copying", "importing", "verifying"):
        runs.move(run, state)
        named(scheduled=False, recovery=False, migration=True)
    runs.move(run, "reported")
    named(scheduled=False, recovery=False)
    runs.move(run, "failed")
    go_ahead = rf.approval_record(ledger, "dry-run-go-ahead", str(uuid4()), now=clock())
    second = runs.start("dry", tool_commit="0" * 40, go_ahead=go_ahead["approvalId"])["runId"]
    runs.interrupt(second, "preparing")
    named(scheduled=False, recovery=False)
    ledger.close()


def test_the_restart_and_the_keychain_read_run_their_one_command():
    from docsuri_ops.arrangement.macos import MacTools, ToolFailed

    recorded: list = []
    MacTools(run=recording_run(recorded)).restart("system/org.docsuri.v2.standing")
    assert [argv for argv, _ in recorded] == [
        ["/bin/launchctl", "kickstart", "-k", "system/org.docsuri.v2.standing"]]
    recorded.clear()
    value = secrets.token_hex(32).encode()  # generated per run (L1-36)

    def answering(argv, **options):
        recorded.append((list(argv), options))
        return subprocess.CompletedProcess(argv, 0, value + b"\n", b"")

    read = MacTools(run=answering).keychain_read("docsuri-v2-restore")
    assert [argv for argv, _ in recorded] == [
        ["/usr/bin/security", "find-generic-password", "-s", "docsuri-v2-restore", "-w",
         "/Library/Keychains/System.keychain"]]
    assert isinstance(read, bytearray) and read == bytearray(value)
    with pytest.raises(ToolFailed):
        MacTools(run=recording_run(recorded, code=lambda argv: 44)).keychain_read(
            "docsuri-v2-restore")


def test_a_login_check_that_raises_after_the_verifiers_changed_still_leaves_its_evidence(
        stage, tmp_path, clock):
    """The coordinator's fix of Step 136's deviation 2: whatever the login check raises once
    the roles hold their new verifiers is not a login's answer, so the role did not log in
    and the change answers the same failed `login-check-failed` refusal as a False answer
    (Step 136(d), item 9; 136(e)'s one JSON result), writes that outcome to both records,
    and the marker still goes."""
    import psycopg

    from docsuri_ops.arrangement import password_change as pc
    from docsuri_ops.production_tool import V2_ROLES
    from tests.u8_service_operations_integration import recovery_flows as rf

    paths = password_stage(stage).paths
    write_stop_records(paths, V2_ROLES)
    ledger = rf.open_ledger(tmp_path, clock)
    scripts = len(stage.database.scripts)

    def raising_login_check(role, password):
        """Raise-only: the driver fails with an error that is not a refused login."""
        raise psycopg.InterfaceError("the connection broke")

    stage.database.login_check = raising_login_check
    result = pc.change_password(stage.ctx, "owners", actor=CHANGE_ACTOR, ledger=ledger)
    del stage.database.login_check
    assert result == {"ok": False, "login": "owners", "outcome": "failed",
                      "reason": "login-check-failed"}
    assert len(stage.database.scripts) == scripts + 1  # the verifiers were set first
    assert manifest.marker(paths) is None
    for lines in change_lines(paths, stage.ctx.log):
        # Only registered fields: no secret, digest or length field can be among them.
        assert lines == [{"ts": lines[0]["ts"], "phase": "password-change", "step": "owners",
                          "outcome": "failed", "reason": "login-check-failed", "count": 0,
                          "actor": CHANGE_ACTOR}]
        assert not re.search(r"[0-9a-f]{32,}", json.dumps(lines))
    for record in (paths.control / pc.AUDIT_RECORD, paths.installation_log):
        text = record.read_text()
        assert not [value for value in stage.secrets if value.decode() in text], record.name
    ledger.close()


def one_failed_line(paths, log, login: str, reason: str) -> None:
    """Each record holds exactly one `password-change` line, the failed outcome."""
    for lines in change_lines(paths, log):
        assert [(line["step"], line["outcome"], line["reason"], line["actor"])
                for line in lines] == [(login, "failed", reason, CHANGE_ACTOR)]


def test_a_failed_standing_restart_after_the_change_keeps_the_new_verifiers(
        stage, tmp_path, clock):
    """Step 136(d): the scheduler's change holds when the standing job's restart fails; the
    answer is the failed `standing-restart-failed` refusal, so the restart is repeated."""
    from docsuri_ops.arrangement import password_change as pc
    from tests.u8_service_operations_integration import recovery_flows as rf

    paths = password_stage(stage).paths
    ledger = rf.open_ledger(tmp_path, clock)
    holder = paths.scheduler_credentials
    before, scripts = holder.read_bytes(), len(stage.database.scripts)
    checked: list[str] = []

    def answering_login_check(role, password):
        """The fake instance's login: every role logs in with its new value."""
        checked.append(role)
        return True

    def failing_restart(domain_label):
        """Raise-only: `launchctl kickstart -k` fails."""
        stage.tools._record("restart", domain_label)
        raise RuntimeError("the standing job did not restart")

    stage.database.login_check = answering_login_check
    stage.tools.restart = failing_restart
    result = pc.change_password(stage.ctx, "scheduler", actor=CHANGE_ACTOR, ledger=ledger)
    del stage.database.login_check, stage.tools.restart
    assert result == {"ok": False, "login": "scheduler", "outcome": "failed",
                      "reason": "standing-restart-failed"}
    # The change holds: the verifiers were set, the holder rewritten and every role logged in.
    roles = pc.HOLDERS["scheduler"].roles
    assert len(stage.database.scripts) == scripts + 1
    for role in roles:
        assert f"ALTER ROLE {role} PASSWORD 'SCRAM-SHA-256$4096:" in stage.database.scripts[-1]
    assert checked == list(roles)
    assert holder.read_bytes() != before and pending_names(paths) == []
    assert ("restart", pc.STANDING_JOB) in stage.tools.calls
    assert manifest.marker(paths) is None
    one_failed_line(paths, stage.ctx.log, "scheduler", "standing-restart-failed")
    ledger.close()


def test_a_login_check_that_answers_false_is_a_failed_change(stage, tmp_path, clock):
    """Step 136(d), item 9: a role that does not log in with its new value answers the
    failed `login-check-failed` refusal, after the verifiers were set."""
    from docsuri_ops.arrangement import password_change as pc
    from docsuri_ops.production_tool import V2_ROLES
    from tests.u8_service_operations_integration import recovery_flows as rf

    paths = password_stage(stage).paths
    write_stop_records(paths, V2_ROLES)
    ledger = rf.open_ledger(tmp_path, clock)
    scripts = len(stage.database.scripts)

    def refusing_login_check(role, password):
        """The fake instance's refused login, as `ProductionDatabase.login_check` answers."""
        return False

    stage.database.login_check = refusing_login_check
    result = pc.change_password(stage.ctx, "owners", actor=CHANGE_ACTOR, ledger=ledger)
    del stage.database.login_check
    assert result == {"ok": False, "login": "owners", "outcome": "failed",
                      "reason": "login-check-failed"}
    assert len(stage.database.scripts) == scripts + 1  # the verifiers were set first
    assert manifest.marker(paths) is None
    one_failed_line(paths, stage.ctx.log, "owners", "login-check-failed")
    ledger.close()


def test_the_first_active_choice_refuses_a_missing_or_linked_registered_configuration(
        stage, tmp_path):
    """Step 138(d) (NFR3.4, L2-15): with no active choice, a missing `v1-web.yml` or one
    replaced by a link (a refused walk) answers the routing program's own key, writes no
    `active.yml` and starts no tunnel job."""
    from docsuri_ops.arrangement.tunnel import TunnelRefused

    move, tools, paths = tunnel_move(stage), stage.tools, stage.ctx.paths
    paths.tunnel_config.mkdir(parents=True, exist_ok=True)
    active, registered = paths.tunnel_config / "active.yml", paths.tunnel_config / "v1-web.yml"
    calls = len(tools.calls)
    with pytest.raises(TunnelRefused, match="^registered-configuration-refused$"):
        move._start_on_v1_web()
    assert not active.exists() and not active.is_symlink()
    target = tmp_path / "elsewhere.yml"
    target.write_text("ingress: elsewhere\n")
    registered.symlink_to(target)
    with pytest.raises(TunnelRefused, match="^registered-configuration-refused$"):
        move._start_on_v1_web()
    assert not active.exists() and not active.is_symlink()
    assert target.read_text() == "ingress: elsewhere\n"
    assert not [call for call in tools.calls[calls:] if call[0] == "bootstrap"]


# --- Step 164(f): the installer's own connections and the runtime's clients (NFR3.3) --------


def test_the_installers_login_check_and_provisioner_demand_scram(monkeypatch):
    """The login check and the provisioner's store each ask the driver for
    `require_auth=scram-sha-256` at 127.0.0.1:15432 (a raise-only spy in the driver's
    place, which refuses before any connection); and against a listener that asks for a
    cleartext password, for MD5 or for nothing, the login check answers False and the
    provisioner's store is unavailable, with no password sent."""
    import dataclasses
    import secrets

    import psycopg

    from docsuri_ops.arrangement.installer import ProductionDatabase
    from docsuri_ops.platform_control.errors import ControlError
    from tests.u8_service_operations_integration.component.test_transactions_scram import (
        CLEARTEXT,
        MD5,
        STANDIN_PORT,
        TRUST,
        WeakAuthStandin,
    )
    from tests.u8_service_operations_integration.operations.test_scram_sites import (
        Reached,
        demanded,
        refusing_connect,
    )

    database, password = ProductionDatabase(None), secrets.token_hex(16)  # per run (L1-36)
    for request in (CLEARTEXT, MD5, TRUST):
        with WeakAuthStandin(request) as standin:
            assert database.login_check("docsuri_operator", password, port=STANDIN_PORT) is False
        assert standin.passwords_seen == 0, request
        store = database.store(password)
        store.target = dataclasses.replace(store.target, port=STANDIN_PORT)
        with WeakAuthStandin(request) as standin:
            with pytest.raises(ControlError) as refused:
                with store.connection():
                    pass
        assert standin.passwords_seen == 0, request
        assert "scram-sha-256" in str(refused.value.__cause__), request
    monkeypatch.setattr(psycopg, "connect", refusing_connect)
    with pytest.raises(Reached) as checked:
        database.login_check("docsuri_operator", password)
    with pytest.raises(Reached) as provisioned:
        with database.store(password).connection():
            pass
    scram = "scram-sha-256"
    assert demanded(checked.value.options) == (
        "127.0.0.1", 15432, "docsuri_operator", "postgres", scram)
    assert demanded(provisioned.value.options) == (
        "127.0.0.1", 15432, "platform_control_provisioner", "docsuri_v2_platform", scram)


def _runtime_tools(runtime: Path, *, versions: dict | None = None, libpq=None):
    """Stand-in tools for the check of the runtime's clients: each program reports its
    version (16.14 unless `versions` names another) and loads `libpq` (the runtime's own
    unless given; None for a program that loads none)."""
    own = str(runtime / "lib" / "libpq.5.dylib")
    asked: list = []

    def run(argv, **options):
        asked.append(("run", *argv))
        name = Path(argv[0]).name
        assert argv == [str(runtime / "bin" / name), "--version"], argv
        return f"{name} (PostgreSQL) {(versions or {}).get(name, '16.14')}\n".encode()

    def libraries(program):
        asked.append(("libraries", str(program)))
        loaded = [own] if libpq is None else [libpq] if isinstance(libpq, str) else libpq
        return ["/usr/lib/libSystem.B.dylib", *[library for library in loaded if library]]

    return SimpleNamespace(run=run, libraries=libraries), asked


def test_the_installation_checks_the_runtime_clients_and_their_libpq(stage):
    """L4-5 (A): the tenth check passes when the pinned runtime's `pg_dump`, `pg_restore`
    and `psql` each report 16.14 and load the runtime's own libpq, and fails on another
    version, on a libpq outside the runtime's folder, and on a program that loads none.
    It runs here with stand-in tools only: the installed runtime is read at Environment
    Provisioning, not in this stage."""
    from docsuri_ops.arrangement import verify

    runtime = stage.ctx.paths.postgres_runtime
    names = [name for name, _ in verify.checks(stage.ctx)]
    assert len(names) == 10 and names.count("runtime-clients-load-their-own-libpq") == 1

    def decided(**tools) -> tuple[bool, list]:
        stage.ctx.tools, asked = _runtime_tools(runtime, **tools)
        return dict(verify.checks(stage.ctx))["runtime-clients-load-their-own-libpq"](), asked

    passed, asked = decided()
    assert passed is True
    assert asked == [step for name in ("pg_dump", "pg_restore", "psql") for step in (
        ("run", str(runtime / "bin" / name), "--version"),
        ("libraries", str(runtime / "bin" / name)))]
    for name in ("pg_dump", "pg_restore", "psql"):
        for other in ("16.13", "16.140", "17.2", ""):
            assert decided(versions={name: other})[0] is False, (name, other)
    for elsewhere in ("/opt/homebrew/opt/libpq/lib/libpq.5.dylib", "/usr/lib/libpq.5.dylib",
                      "@rpath/libpq.5.dylib", str(runtime) + "-other/lib/libpq.5.dylib", ""):
        assert decided(libpq=elsewhere)[0] is False, elsewhere
    # Two libpq lines for one program, one the runtime's own and one outside it: every
    # one must be the runtime's, so it fails whichever comes first.
    own, outside = str(runtime / "lib" / "libpq.5.dylib"), "/opt/homebrew/lib/libpq.5.dylib"
    assert decided(libpq=[own, outside])[0] is False
    assert decided(libpq=[outside, own])[0] is False
    assert decided(libpq=[own, str(runtime / "lib" / "libpq.5.16.dylib")])[0] is True


# --- the standalone `verify` word (the person's decision of 2026-11-22, "Yes, fix it now") --


def test_the_verify_word_is_not_ok_and_exits_1_when_a_check_fails_or_raises(
        stage, monkeypatch, capsys):
    """`docsuri-installer verify` prints ok true and exits 0 only when every check
    passed; with a check that fails, or one that raises, it prints ok false, names that
    check under `failed`, and exits 1. Every check's outcome is printed either way."""
    from docsuri_ops.arrangement import installer, verify

    paths = stage.ctx.paths
    paths.control.mkdir(parents=True, exist_ok=True)
    (paths.control / "installation.json").write_text("{}")
    for name in [name for name in os.environ if name.startswith(("PYTHON", "DYLD_", "LD_"))]:
        monkeypatch.delenv(name)
    monkeypatch.setattr(installer.os, "geteuid", lambda: 0)
    monkeypatch.setattr(installer, "ArrangementPaths", lambda: paths)
    monkeypatch.setattr(installer, "production_context", lambda settings, *, clock: stage.ctx)

    def broken() -> bool:
        raise RuntimeError("the tool did not answer")

    def word(second) -> tuple[int, dict]:
        monkeypatch.setattr(verify, "checks", lambda ctx: [
            ("first", lambda: True), ("second", second), ("third", lambda: True)])
        code = installer.main(["verify"])
        return code, json.loads(capsys.readouterr().out.splitlines()[-1])

    code, printed = word(lambda: True)
    assert (code, printed["ok"]) == (0, True) and "failed" not in printed
    assert printed["checks"] == [{"check": name, "passed": True}
                                 for name in ("first", "second", "third")]
    for second in (lambda: False, broken):
        code, printed = word(second)
        assert (code, printed["ok"], printed["failed"]) == (1, False, ["second"])
        assert [item["passed"] for item in printed["checks"]] == [True, False, True]
