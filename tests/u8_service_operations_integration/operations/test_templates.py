"""The arrangement's rendered templates (U8 plan Step 38; D8, security-design § 5.2–5.3,
§ 6.3, § 6.4, § 6.8, tech-stack-decisions § Configuration).

Rendered under a temporary prefix from one `ArrangementPaths` and one `Accounts`; nothing
here installs anything. The linting by macOS's own tools (`visudo -c -f`, `plutil -lint`,
`pfctl -n -f`) is `arrangement/test_template_lint.py`'s, in the macOS job.
"""

from __future__ import annotations

import inspect
import json
import plistlib
import re
from pathlib import Path

import pytest

from docsuri_ops.arrangement import phases, render
from docsuri_ops.arrangement.keychain import generate
from docsuri_ops.arrangement.paths import Accounts, ArrangementPaths
from docsuri_ops.isolation_check import BOOT_LABELS

OPERATOR = "revenantonthemission"
TUNNEL = "docsuri-v2-a1b2c3d4"
ACCOUNTS = Accounts.standard()
ROOT_JOBS = ("org.docsuri.v2.pf", "org.docsuri.v2.backup-unlock", "org.docsuri.v2.logrotate")
LONG_RUNNING = ("org.docsuri.v2.host", "org.docsuri.v2.workers", "org.docsuri.v2.scheduler",
                "org.docsuri.v2.maintenance", "org.docsuri.v2.standing", "org.docsuri.v2.postgres",
                "org.docsuri.models", "org.docsuri.tunnel")
REPOSITORY = Path(__file__).resolve().parents[3]


@pytest.fixture
def paths(tmp_path) -> ArrangementPaths:
    return ArrangementPaths.under(tmp_path / "Library" / "DocSuri")


@pytest.fixture
def rendered(paths) -> list[render.Rendered]:
    return render.render(paths, ACCOUNTS, operator=OPERATOR, tunnel_name=TUNNEL)


def by_name(rendered, name: str) -> render.Rendered:
    return next(item for item in rendered if item.target.name == name)


def text(item: render.Rendered) -> str:
    return item.content.decode()


# --- 1. no rendered file holds a secret ------------------------------------------------------


def test_no_rendered_file_holds_a_secret(rendered, realm):
    # The renderer takes no secret at all, so none can reach a file.
    assert set(inspect.signature(render.render).parameters) == {
        "paths", "accounts", "operator", "tunnel_name"}
    secrets = [generate().decode() for _ in range(4)]
    for name in ("owner-credentials.json", "standin-credentials.json"):
        value = json.loads((Path(realm.root) / name).read_bytes())
        secrets += [str(item) for item in value["roles"].values()]
    for item in rendered:
        body = text(item)
        assert not any(secret in body for secret in secrets), item.target
        assert "-----BEGIN" not in body and not re.search(r"\b[0-9a-f]{40,}\b", body)
        # Outside the explanatory comments, no line names a credential.
        in_force = "\n".join(line for line in body.lower().splitlines()
                             if not line.lstrip().startswith(("#", "<!--", '"comment"')))
        # The installer's `change-password` word (U8 plan Step 136, L2-7) names a program
        # invocation in the sudo rules, never a credential.
        named = in_force.replace("password_encryption", "").replace(
            "/docsuri-installer change-password", "")
        for word in ("password", "passphrase", "token", "secret"):
            assert word not in named, (item.target, word)
    # The launch jobs hold no environment value beyond the model runtime's addresses.
    models = plistlib.loads(by_name(rendered, "org.docsuri.models.plist").content)
    assert set(models["EnvironmentVariables"]) == {
        "OLLAMA_HOST", "OLLAMA_MODELS", "HOME", "OLLAMA_MAX_LOADED_MODELS", "OLLAMA_NUM_PARALLEL"}


def test_the_rendered_files_have_their_owners_modes_and_places(rendered, paths):
    for item in rendered:
        assert item.kind in ("rule", "config")
        if item.target.suffix == ".plist":
            assert item.target.parent == paths.launch_daemons and item.mode == 0o644
            assert item.owner == "root"
    rules = by_name(rendered, "docsuri-v2")
    assert (rules.owner, rules.mode, rules.kind, rules.target) == (
        "root", 0o440, "rule", paths.sudoers_rules)
    assert by_name(rendered, "org.docsuri.v2").target == paths.pf_anchor
    config = by_name(rendered, "postgresql.conf")
    assert config.owner == "database" and config.mode == 0o600
    assert config.target.parent == paths.postgres_data
    # Your answer of 2026-11-11 ("Map the login, root rules"): the rule files are root's,
    # readable by the server, in the root-owned folder outside `postgres/`.
    for name in ("pg_hba.conf", "pg_ident.conf"):
        item = by_name(rendered, name)
        assert (item.owner, item.mode, item.kind) == ("root", 0o644, "rule")
        assert item.target.parent == paths.postgres_rules
    assert render.arrangement_version() == 1
    with pytest.raises(ValueError):
        render.render(paths, ACCOUNTS, operator="bad name;", tunnel_name=TUNNEL)


# --- 2. the sudo rules ---------------------------------------------------------------------------


def aliases(body: str) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for match in re.finditer(r"Cmnd_Alias (\w+) = \\\n((?:    .*\n)+)", body):
        found[match.group(1)] = [line.strip().rstrip(", \\").rstrip(",")
                                 for line in match.group(2).splitlines()]
    return found


def rules(body: str) -> list[tuple[str, str, str]]:
    found = []
    for line in body.splitlines():
        match = re.fullmatch(r"(\S+) ALL = \((\S+)\) (.+)", line)
        if match:
            found.append(match.groups())
    return found


def test_the_sudo_rules_grant_each_account_exactly_its_set(rendered, paths):
    body = text(by_name(rendered, "docsuri-v2"))
    table = aliases(body)
    granted = rules(body)
    bin_folder = str(paths.release_bin)
    for lines in table.values():
        assert lines and all(line.startswith(bin_folder + "/") for line in lines)
    # The service account is given nothing.
    assert not [rule for rule in granted if rule[0] == ACCOUNTS.service.name]
    # The scheduler: only its unattended set, without a password, never an in-person alias.
    scheduler = [rule for rule in granted if rule[0] == ACCOUNTS.scheduler.name]
    assert {(runas, grant) for _, runas, grant in scheduler} == {
        (ACCOUNTS.backup.name, "NOPASSWD: DOCSURI_STANDING_BACKUP"),
        (ACCOUNTS.service.name, "NOPASSWD: DOCSURI_STANDING_SERVICE"),
        ("root", "NOPASSWD: DOCSURI_STANDING_ROOT")}
    agent = f"{bin_folder}/docsuri-backup-agent"
    assert table["DOCSURI_STANDING_BACKUP"] == [f"{agent} {word}" for word in (
        "status", "backup", "ledger-copy", "verify", "dispose-due")]
    assert table["DOCSURI_STANDING_SERVICE"] == [
        f"{bin_folder}/docsuri-ledger {word}" for word in ("append", "copy", "verify", "read")]
    assert table["DOCSURI_STANDING_ROOT"] == [f'{bin_folder}/docsuri-isolation-check ""']
    # You: every in-person command, each alias at timestamp_timeout=0, never NOPASSWD.
    mine = [rule for rule in granted if rule[0] == OPERATOR]
    assert {(runas, grant) for _, runas, grant in mine} == {
        ("root", "DOCSURI_INPERSON_ROOT"), (ACCOUNTS.service.name, "DOCSURI_INPERSON_SERVICE"),
        (ACCOUNTS.backup.name, "DOCSURI_INPERSON_BACKUP")}
    for alias in ("DOCSURI_INPERSON_ROOT", "DOCSURI_INPERSON_SERVICE", "DOCSURI_INPERSON_BACKUP"):
        assert f"Defaults!{alias} timestamp_timeout=0, umask=077" in body
    in_person = {line for name, lines in table.items() if "INPERSON" in name for line in lines}
    expected = {line for program in (*render.IN_PERSON_ROOT, *render.IN_PERSON_SERVICE,
                                     *render.IN_PERSON_BACKUP)
                for line in render.invocations(paths, program)}
    assert in_person == expected
    assert f"{bin_folder}/docsuri-service-stop org.docsuri.v2.host" in in_person
    assert f"{bin_folder}/docsuri-production-tool replace-verifier-key" in in_person
    # `control-key-start` in person only (your decisions of 2026-10-24 and 2026-10-25): in
    # your service alias, at timestamp_timeout=0, and in no standing set.
    key_start = f"{bin_folder}/docsuri-production-tool control-key-start"
    assert key_start in table["DOCSURI_INPERSON_SERVICE"]
    assert [name for name, lines in table.items() if key_start in lines] == [
        "DOCSURI_INPERSON_SERVICE"]
    # `latency-summaries` in person only, the same way (U8 plan Step 71(i), L1-59).
    latency = f"{bin_folder}/docsuri-production-tool latency-summaries"
    assert latency in table["DOCSURI_INPERSON_SERVICE"]
    assert [name for name, lines in table.items() if latency in lines] == [
        "DOCSURI_INPERSON_SERVICE"]
    # The providers' window words in person only, the same way (U8 plan Step 107(g)).
    for word in ("provider-previews", "provider-decision", "provider-failed"):
        line = f"{bin_folder}/docsuri-production-tool {word}"
        assert line in table["DOCSURI_INPERSON_SERVICE"], word
        assert [name for name, lines in table.items() if line in lines] == [
            "DOCSURI_INPERSON_SERVICE"], word
    # The password change in person only, as root (U8 plan Step 137(d), L2-7): in your root
    # alias, at timestamp_timeout=0, in no other alias, and never without a password.
    change = f"{bin_folder}/docsuri-installer change-password"
    assert change in table["DOCSURI_INPERSON_ROOT"]
    assert [name for name, lines in table.items() if change in lines] == ["DOCSURI_INPERSON_ROOT"]
    assert not [rule for rule in granted if "NOPASSWD" in rule[2] and (
        "DOCSURI_INPERSON_ROOT" in rule[2] or change in rule[2])]
    standing ={line for name, lines in table.items() if "STANDING" in name for line in lines}
    assert not standing & {line for line in in_person if "docsuri-isolation-check" not in line
                           and "docsuri-ledger" not in line and "docsuri-backup-agent" not in line}
    in_force = "\n".join(line for line in body.splitlines() if not line.startswith("#"))
    assert "SETENV" not in in_force and "env_keep" not in in_force
    assert "NOPASSWD" not in "".join(rule[2] for rule in mine)


def test_each_programs_closed_set_is_the_programs_own(paths):
    from backend.modules.operations import ledger_cli
    from backend.modules.operations.migration import phases
    from docsuri_ops import production_tool, release
    from docsuri_ops.arrangement import installer
    from docsuri_ops.backup_agent import cli as agent
    from docsuri_ops.u8_platform import fixed

    assert render.LEDGER_WORDS == ledger_cli.WORDS
    assert render.LEDGER_UNATTENDED == ledger_cli.UNATTENDED_WORDS
    assert render.PRODUCTION_TOOL_WORDS == production_tool.WORDS
    assert render.AGENT_UNATTENDED == agent.UNATTENDED
    assert render.AGENT_UNATTENDED + render.AGENT_IN_PERSON == agent.WORDS
    assert render.PROGRAM_WORDS["docsuri-migration-import"] == phases.WORDS
    assert render.PROGRAM_WORDS["docsuri-release"] == release.WORDS
    assert render.PROGRAM_WORDS["docsuri-installer"] == installer.WORDS
    for program, (words, _) in fixed.PROGRAMS.items():
        assert render.PROGRAM_WORDS[program] == tuple(words)
    # The seventeen programs are exactly the release's ops/bin.
    assert set(render.FIXED_PROGRAMS) == {path.name for path in (REPOSITORY / "ops/bin").iterdir()}
    assert set(render.FIXED_PROGRAMS) == set(release.PROGRAM_ENTRIES)


# --- 3. the launch jobs ------------------------------------------------------------------------


def test_each_long_running_job_keeps_alive_and_the_root_jobs_do_not(rendered, paths):
    jobs = {item.target.stem: plistlib.loads(item.content) for item in rendered
            if item.target.suffix == ".plist"}
    assert set(jobs) == set(BOOT_LABELS) | set(ROOT_JOBS)
    assert set(jobs) == set(LONG_RUNNING) | set(ROOT_JOBS) and len(jobs) == 11
    for label in LONG_RUNNING:
        job = jobs[label]
        assert job["KeepAlive"] is True and job["RunAtLoad"] is True and job["ExitTimeOut"] == 30
        assert job["UserName"] == job["GroupName"] and job["UserName"].startswith("_docsuri")
    for label in ROOT_JOBS:
        job = jobs[label]
        assert job["KeepAlive"] is False and "ExitTimeOut" not in job
        assert (job["UserName"], job["GroupName"]) == ("root", "wheel")
    assert jobs["org.docsuri.v2.backup-unlock"]["StartInterval"] == 60
    assert jobs["org.docsuri.v2.logrotate"]["StartCalendarInterval"] == {"Hour": 3, "Minute": 0}
    assert "StartInterval" not in jobs["org.docsuri.v2.pf"]
    accounts = {label: job["UserName"] for label, job in jobs.items()}
    assert accounts["org.docsuri.v2.host"] == ACCOUNTS.service.name
    assert accounts["org.docsuri.v2.standing"] == ACCOUNTS.scheduler.name
    assert accounts["org.docsuri.v2.postgres"] == ACCOUNTS.database.name
    assert accounts["org.docsuri.models"] == ACCOUNTS.models.name
    assert accounts["org.docsuri.tunnel"] == ACCOUNTS.tunnel.name
    release = str(paths.release)
    assert jobs["org.docsuri.v2.maintenance"]["ProgramArguments"] == [
        f"{release}/.venv/bin/python", "-I", "-m", "backend.maintenance_server", "--build",
        f"{release}/frontend/dist", "--port", "18201", "--public-authority", "docsuri.rvnnt.dev",
        "--log-folder", f"{paths.prefix}/profile/logs"]
    assert jobs["org.docsuri.v2.host"]["ProgramArguments"][-3:] == [
        "host", "--profile", f"{paths.prefix}/profile/environment.json"]
    for job in jobs.values():
        for key in ("StandardOutPath", "StandardErrorPath"):
            assert job[key].startswith(str(paths.prefix) + "/")
        assert job["ProgramArguments"][0].startswith((release + "/", str(paths.runtimes) + "/"))


# --- 4. the packet filter's anchor -------------------------------------------------------------


def test_the_anchor_ties_four_ports_to_their_accounts(rendered):
    lines = [line for line in text(by_name(rendered, "org.docsuri.v2")).splitlines()
             if line and not line.startswith("#")]
    passes = {re.search(r"port (\d+) user (\S+)", line).groups() for line in lines
              if line.startswith("pass")}
    assert passes == {("18200", ACCOUNTS.service.name), ("18201", ACCOUNTS.service.name),
                      ("11434", ACCOUNTS.models.name), ("15432", ACCOUNTS.database.name)}
    assert all("on lo0 proto tcp to 127.0.0.1" in line for line in lines)
    assert lines[-1] == ("block return in quick on lo0 proto tcp to 127.0.0.1 port "
                         "{ 18200 18201 11434 15432 }")


# --- 5. the tunnel's three registered configurations ---------------------------------------------


def test_each_tunnel_configuration_keeps_the_ssh_route(rendered, paths):
    configs = {item.target.stem: text(item) for item in rendered
               if item.target.parent == paths.tunnel_config}
    assert set(configs) == {"v1-web", "v2-host", "maintenance"}
    # NFR3.4: each registered configuration is root's, in root's folder.
    for item in rendered:
        if item.target.parent == paths.tunnel_config:
            assert (item.owner, item.mode, item.kind) == ("root", 0o644, "config"), item.target
    assert ("tunnel/config", "root", 0o755) in phases.FOLDERS
    services = {"v1-web": "http://127.0.0.1:3000", "v2-host": "http://127.0.0.1:18200",
                "maintenance": "http://127.0.0.1:18201"}
    for origin, body in configs.items():
        assert "  - hostname: ssh.rvnnt.dev\n    service: ssh://localhost:22\n" in body
        assert f"tunnel: {TUNNEL}\n" in body
        assert f"credentials-file: {paths.tunnel_credentials}/tunnel.json\n" in body
        assert "no-autoupdate: true\n" in body and "loglevel: warn\n" in body
        assert f"service: {services[origin]}\n" in body
        assert body.rstrip().endswith("- service: http_status:404")
        has_header = "httpHostHeader: docsuri.rvnnt.dev" in body
        assert has_header is (origin != "v1-web")
    with pytest.raises(ValueError):
        render.render_tunnel(paths, tunnel_name="docsuri; rm")


# --- 6. PostgreSQL's configuration ---------------------------------------------------------------


def test_pg_hba_has_its_three_lines_in_order(rendered):
    lines = [line for line in text(by_name(rendered, "pg_hba.conf")).splitlines()
             if line and not line.startswith("#")]
    # Your answer of 2026-11-11 ("Map the login, root rules"): the first line gains the one
    # peer map; the other two stay as they were, in their order.
    assert lines == ["local all postgres peer map=docsuri_superuser",
                     "host all postgres 127.0.0.1/32 reject",
                     "host all all 127.0.0.1/32 scram-sha-256"]
    assert render.SUPERUSER_MAP == "docsuri_superuser"


def test_pg_ident_maps_only_the_database_account_to_the_superuser(rendered, paths):
    """Your answer of 2026-11-11: exactly one map line, the first rule line's map, from the
    database account's operating-system name (read from `Accounts`, never a literal) to
    `render.SUPERUSER`. The postgres role is not mapped from itself, so an account named
    `postgres` gains nothing either."""
    from docsuri_ops.arrangement.paths import Account

    def map_lines(items) -> list[list[str]]:
        body = text(by_name(items, "pg_ident.conf"))
        return [line.split() for line in body.splitlines()
                if line.strip() and not line.lstrip().startswith("#")]

    assert map_lines(rendered) == [[render.SUPERUSER_MAP, ACCOUNTS.database.name,
                                    render.SUPERUSER]]
    assert ACCOUNTS.database.name == "_docsuri_v2_db"
    hba_first = next(line for line in text(by_name(rendered, "pg_hba.conf")).splitlines()
                     if line and not line.startswith("#"))
    assert hba_first.split() == ["local", "all", render.SUPERUSER, "peer",
                                 f"map={render.SUPERUSER_MAP}"]
    other = Accounts(database=Account("_docsuri_other_db", 712))
    assert map_lines(render.render_postgres(paths, other)) == [
        [render.SUPERUSER_MAP, "_docsuri_other_db", render.SUPERUSER]]


def test_the_rule_folder_is_roots_and_outside_the_database_accounts_folders(paths):
    """Your answer of 2026-11-11: the rules folder is a root-owned FOLDERS entry at 0755,
    directly under the root-owned prefix, so the database account, which owns `postgres/`,
    can neither rename it away nor write into it."""
    from docsuri_ops.arrangement import phases

    assert paths.postgres_rules == paths.prefix / "postgres-rules"
    assert paths.postgres_rules.parent == paths.prefix
    assert ("postgres-rules", "root", 0o755) in phases.FOLDERS
    database_folders = [relative for relative, owner, _ in phases.FOLDERS if owner == "database"]
    assert all(not str(paths.postgres_rules).startswith(str(paths.prefix / relative) + "/")
               for relative in database_folders)
    assert ArrangementPaths().postgres_rules == Path("/Library/DocSuri/postgres-rules")


def test_postgresql_conf_holds_the_required_settings(rendered, paths):
    settings = {}
    for line in text(by_name(rendered, "postgresql.conf")).splitlines():
        if "=" in line and not line.startswith("#"):
            key, _, value = line.partition("=")
            settings[key.strip()] = value.strip()
    assert settings["listen_addresses"] == "'127.0.0.1'" and settings["port"] == "15432"
    assert settings["unix_socket_directories"] == f"'{paths.postgres_socket}'"
    assert settings["unix_socket_permissions"] == "0700" and settings["ssl"] == "off"
    assert settings["password_encryption"] == "scram-sha-256"
    assert (settings["shared_buffers"], settings["max_connections"]) == ("512MB", "50")
    assert (settings["max_wal_size"], settings["wal_keep_size"], settings["archive_mode"]) == (
        "1GB", "0", "off")
    assert settings["max_replication_slots"] == settings["max_wal_senders"] == "0"
    for key, value in (("log_min_messages", "log"), ("log_error_verbosity", "terse"),
                       ("log_min_error_statement", "panic"), ("log_statement", "'none'"),
                       ("log_min_duration_statement", "-1"), ("log_parameter_max_length", "0"),
                       ("log_parameter_max_length_on_error", "0"),
                       ("logging_collector", "on"), ("log_rotation_age", "1d")):
        assert settings[key] == value, key
    # U8 plan Step 75(e): the memory settings.
    assert (settings["work_mem"], settings["maintenance_work_mem"]) == ("16MB", "256MB")


def test_the_postgres_job_pins_its_rule_files_and_listen_settings(rendered, paths):
    """Your answer of 2026-11-11 ("Pin them on the command line"): the database account
    owns `postgres/data` and could write `hba_file` into postgresql.auto.conf, which the
    server reads after postgresql.conf. The root-owned job therefore carries each pin as a
    `-c` option, which outranks every configuration file: the rule files are the rendered
    ones (`hba_file` and `ident_file` are the very files the isolation check digests and
    compares the server's `SHOW` answers with), and the listen settings are
    postgresql.conf's own values. The arrangement's version stays 1."""
    from docsuri_ops.isolation_check import DATABASE_PORT

    job = plistlib.loads(by_name(rendered, "org.docsuri.v2.postgres.plist").content)
    arguments = job["ProgramArguments"]
    assert arguments[:3] == [str(paths.runtimes / "postgresql-16.14/bin/postgres"), "-D",
                             str(paths.postgres_data)]
    options = arguments[3:]
    assert options[0::2] == ["-c"] * 7
    pins = dict(option.split("=", 1) for option in options[1::2])
    # Your answer of 2026-11-11 ("Map the login, root rules"): the rule files are the
    # root-owned folder's, and no library is preloaded (postgresql.conf sets none, and a
    # library in the postmaster could answer authentication itself).
    assert pins == {
        "hba_file": str(paths.postgres_rules / "pg_hba.conf"),
        "ident_file": str(paths.postgres_rules / "pg_ident.conf"),
        "listen_addresses": "127.0.0.1", "port": str(DATABASE_PORT),
        "unix_socket_directories": str(paths.postgres_socket),
        "unix_socket_permissions": "0700", "shared_preload_libraries": ""}
    assert options[-1] == "shared_preload_libraries="
    settings, _ = conf_settings(rendered)
    for name in ("listen_addresses", "port", "unix_socket_directories",
                 "unix_socket_permissions"):
        assert settings[name].strip("'") == pins[name], name
    assert "shared_preload_libraries" not in settings
    assert str(by_name(rendered, "pg_hba.conf").target) == pins["hba_file"]
    assert str(by_name(rendered, "pg_ident.conf").target) == pins["ident_file"]
    assert (job["UserName"], job["GroupName"]) == (ACCOUNTS.database.name,) * 2
    assert render.arrangement_version() == 1


def conf_settings(rendered) -> tuple[dict[str, str], list[str]]:
    """postgresql.conf's settings in force, and its lines that are not comments."""
    in_force = [line for line in text(by_name(rendered, "postgresql.conf")).splitlines()
                if line.strip() and not line.lstrip().startswith("#")]
    settings = {}
    for line in in_force:
        key, _, value = line.partition("=")
        settings[key.strip()] = value.strip()
    return settings, in_force


def test_postgresql_writes_daily_dated_files_into_its_data_folders_log(rendered, paths):
    """U8 plan Step 75(e): the server's own log is daily dated files in `postgres/data/log/`,
    the folder the rotation job only deletes from."""
    import datetime as dt

    from docsuri_ops import logrotate

    settings, in_force = conf_settings(rendered)
    assert settings["log_directory"] == "'log'"
    assert settings["log_filename"] == "'postgresql-%Y-%m-%d_%H%M%S.log'"
    assert settings["log_rotation_size"] == "0"
    assert "log_truncate_on_rotation" not in settings
    assert not [line for line in in_force if "log_truncate_on_rotation" in line]
    name = dt.datetime(2026, 10, 23, 0, 0, 0).strftime(settings["log_filename"].strip("'"))
    assert name == "postgresql-2026-10-23_000000.log"
    assert logrotate.DATED.fullmatch(name)
    assert paths.postgres_data / "log" == paths.prefix / "postgres/data/log"
    assert [item for item in logrotate.FOLDERS if item.path == "postgres/data/log"] == [
        logrotate.LogFolder("postgres/data/log", "database", 0, "dated")]


def test_the_rotation_list_is_the_rotation_jobs_own(rendered, paths):
    from docsuri_ops.logrotate import FOLDERS

    folder_list = by_name(rendered, "logrotate-folders.json")
    listed = json.loads(text(folder_list))["folders"]
    assert listed == [{"path": item.path, "account": item.account, "ownedFrom": item.owned_from,
                       "kind": item.kind} for item in FOLDERS]
    # U8 plan Step 75(e): the list is root's, read by the root job that rotates.
    assert (folder_list.owner, folder_list.mode, folder_list.target) == (
        "root", 0o644, paths.control / "logrotate-folders.json")
    job = plistlib.loads(by_name(rendered, "org.docsuri.v2.logrotate.plist").content)
    assert (job["UserName"], job["GroupName"]) == ("root", "wheel")
    assert job["ProgramArguments"] == [f"{paths.release}/ops/bin/docsuri-logrotate"]


# --- 7. U8 plan Step 75: each job's account, schedule and logs, the sudo grantees, the filter
# and the key folders, on production's own paths (nothing is written) -------------------------

PRODUCTION = "/Library/DocSuri"
SERVICE_JOBS = {"org.docsuri.v2.host": "host", "org.docsuri.v2.workers": "workers",
                "org.docsuri.v2.scheduler": "scheduler",
                "org.docsuri.v2.maintenance": "maintenance"}
ROOT_PROGRAMS = {"org.docsuri.v2.pf": "pf-load", "org.docsuri.v2.backup-unlock": "backup-unlock",
                 "org.docsuri.v2.logrotate": "logrotate"}
# label: (account, log folder under the prefix, log name)
LOGS = {
    **{label: ("_docsuri_v2", "profile/logs", name) for label, name in SERVICE_JOBS.items()},
    "org.docsuri.v2.standing": ("_docsuri_v2_sched", "scheduler/logs", "standing"),
    "org.docsuri.v2.postgres": ("_docsuri_v2_db", "postgres/logs", "postmaster"),
    "org.docsuri.models": ("_docsuri_models", "models-state/logs", "ollama"),
    "org.docsuri.tunnel": ("_docsuri_tunnel", "tunnel/logs", "cloudflared"),
    **{label: ("root", "control/logs", name) for label, name in ROOT_PROGRAMS.items()},
}


def production_jobs() -> dict[str, dict]:
    rendered = render.render_launch_jobs(ArrangementPaths(), Accounts.standard())
    assert all(item.target == Path("/Library/LaunchDaemons") / item.target.name
               for item in rendered)
    return {item.target.stem: plistlib.loads(item.content) for item in rendered}


def test_each_launch_job_is_its_account_with_its_schedule_and_logs():
    from docsuri_ops import logrotate
    from docsuri_ops.arrangement import phases

    jobs = production_jobs()
    assert set(jobs) == set(LOGS) and len(jobs) == 11
    keys = {job["label"]: job["account"] for job in render.launch_jobs(ArrangementPaths())}
    folders = {(path, owner) for path, owner, _ in phases.FOLDERS}
    for label, (account, folder, name) in LOGS.items():
        job = jobs[label]
        group = "wheel" if account == "root" else account
        assert (job["UserName"], job["GroupName"]) == (account, group), label
        assert job["StandardOutPath"] == f"{PRODUCTION}/{folder}/{name}.out.log", label
        assert job["StandardErrorPath"] == f"{PRODUCTION}/{folder}/{name}.err.log", label
        assert job["RunAtLoad"] is True and job["Umask"] == 0o077, label
        assert (folder, keys[label]) in folders, label
        for output in (f"{name}.out.log", f"{name}.err.log"):
            assert logrotate.HELD_LOG.fullmatch(output) and not logrotate.OWN_LOG.fullmatch(
                output), output
    for name in ("host.log", "workers.log", "scheduler.log", "maintenance.log", "standing.log"):
        assert logrotate.OWN_LOG.fullmatch(name), name
    for label in LONG_RUNNING:
        assert jobs[label]["KeepAlive"] is True and jobs[label]["ExitTimeOut"] == 30, label
    assert jobs["org.docsuri.v2.maintenance"]["ProgramArguments"] == [
        "/Library/DocSuri/release/.venv/bin/python", "-I", "-m", "backend.maintenance_server",
        "--build", "/Library/DocSuri/release/frontend/dist", "--port", "18201",
        "--public-authority", "docsuri.rvnnt.dev", "--log-folder", "/Library/DocSuri/profile/logs"]
    # PostgreSQL: the rule files and the listen settings are pinned on the command line,
    # which outranks postgresql.conf and postgresql.auto.conf (your answer of 2026-11-11),
    # with an empty shared_preload_libraries (your second answer of that day); nothing
    # else overrides postgresql.conf.
    assert jobs["org.docsuri.v2.postgres"]["ProgramArguments"] == [
        "/Library/DocSuri/runtimes/postgresql-16.14/bin/postgres", "-D",
        "/Library/DocSuri/postgres/data",
        "-c", "hba_file=/Library/DocSuri/postgres-rules/pg_hba.conf",
        "-c", "ident_file=/Library/DocSuri/postgres-rules/pg_ident.conf",
        "-c", "listen_addresses=127.0.0.1", "-c", "port=15432",
        "-c", "unix_socket_directories=/Library/DocSuri/postgres/socket",
        "-c", "unix_socket_permissions=0700", "-c", "shared_preload_libraries="]
    models = jobs["org.docsuri.models"]
    assert models["WorkingDirectory"] == "/Library/DocSuri/models-state"
    assert models["EnvironmentVariables"] == {
        "OLLAMA_HOST": "127.0.0.1:11434", "OLLAMA_MODELS": "/Library/DocSuri/models",
        "HOME": "/Library/DocSuri/models-state", "OLLAMA_MAX_LOADED_MODELS": "2",
        "OLLAMA_NUM_PARALLEL": "1"}
    for label, program in ROOT_PROGRAMS.items():
        job = jobs[label]
        assert job["KeepAlive"] is False, label
        assert "ExitTimeOut" not in job and "EnvironmentVariables" not in job, label
        assert job["ProgramArguments"] == [f"/Library/DocSuri/release/ops/bin/docsuri-{program}"]
    pf, unlock, rotation = (jobs[label] for label in ROOT_PROGRAMS)
    assert "StartInterval" not in pf and "StartCalendarInterval" not in pf
    assert unlock["StartInterval"] == 60 and "StartCalendarInterval" not in unlock
    assert rotation["StartCalendarInterval"] == {"Hour": 3, "Minute": 0}
    assert "StartInterval" not in rotation
    assert Path("/Library/LaunchDaemons/org.docsuri.v2.backup-unlock.plist") in {
        item.target for item in render.render_launch_jobs(ArrangementPaths(), ACCOUNTS)}


def test_the_sudo_rules_grant_only_the_operator_and_the_scheduler():
    paths = ArrangementPaths()
    body = render.render_sudoers(paths, ACCOUNTS, operator=OPERATOR).content.decode()
    in_force = [line for line in body.splitlines() if line and not line.startswith("#")]
    granted = rules(body)
    # Every line granting anything is one the parser read.
    assert len(granted) == len([line for line in in_force if " ALL = " in line]) == 6
    assert {grantee for grantee, _, _ in granted} == {"revenantonthemission", "_docsuri_v2_sched"}
    assert {runas for _, runas, _ in granted} == {"root", "_docsuri_v2", "_docsuri_r1t_backup"}
    table = aliases(body)
    agent = [line for line in in_force if "docsuri-backup-agent" in line]
    assert agent and all(
        line.strip().rstrip(", \\").rstrip(",") in table["DOCSURI_STANDING_BACKUP"]
        + table["DOCSURI_INPERSON_BACKUP"] for line in agent)
    assert {name for name, lines in table.items()
            if any("docsuri-backup-agent" in line for line in lines)} == {
        "DOCSURI_STANDING_BACKUP", "DOCSURI_INPERSON_BACKUP"}
    for alias in ("DOCSURI_STANDING_BACKUP", "DOCSURI_INPERSON_BACKUP"):
        assert {runas for _, runas, grant in granted if alias in grant} == {
            "_docsuri_r1t_backup"}, alias
    assert {key: (getattr(Accounts.standard(), key).name, getattr(Accounts.standard(), key).uid)
            for key in ("service", "scheduler", "database", "models", "tunnel", "backup")} == {
        "service": ("_docsuri_v2", 610), "scheduler": ("_docsuri_v2_sched", 611),
        "database": ("_docsuri_v2_db", 612), "models": ("_docsuri_models", 613),
        "tunnel": ("_docsuri_tunnel", 614), "backup": ("_docsuri_r1t_backup", 607)}
    runs_as = [job["UserName"] for job in production_jobs().values()]
    for name in ("_docsuri_v2_sched", "_docsuri_v2_db", "_docsuri_models", "_docsuri_tunnel"):
        assert runs_as.count(name) == 1, name
    assert runs_as.count("_docsuri_v2") == 4 and "_docsuri_r1t_backup" not in runs_as


def test_the_filter_job_loads_its_anchor_at_boot_and_pf_conf_is_untouched(rendered, paths):
    from docsuri_ops import pf_loader, release

    assert by_name(rendered, "org.docsuri.v2").target == (
        paths.system / "etc" / "pf.anchors" / "org.docsuri.v2")
    for item in rendered:
        assert item.target != paths.system / "etc" / "pf.conf"
        assert item.target.name != "pf.conf"
    assert ArrangementPaths().pf_anchor == pf_loader.ANCHOR_FILE == Path(
        "/etc/pf.anchors/org.docsuri.v2")
    assert release.PROGRAM_ENTRIES["docsuri-pf-load"] == "docsuri_ops.pf_loader"
    job = plistlib.loads(by_name(rendered, "org.docsuri.v2.pf.plist").content)
    assert job["RunAtLoad"] is True


def test_the_sudo_rules_live_at_etc_sudoers_d_docsuri_v2():
    """D6 (security-design § 5.2): production's sudo rules are one file, root's, at mode
    0440, at `/etc/sudoers.d/docsuri-v2`; the installer's production context builds this
    default `ArrangementPaths()` (L3-8)."""
    production = ArrangementPaths()
    assert production.is_production
    assert production.sudoers_rules == Path("/etc/sudoers.d/docsuri-v2")
    files = render.render(production, ACCOUNTS, operator=OPERATOR, tunnel_name=TUNNEL)
    assert [(item.target, item.owner, item.mode, item.kind) for item in files
            if item.target.parent == Path("/etc/sudoers.d")] == [
        (Path("/etc/sudoers.d/docsuri-v2"), "root", 0o440, "rule")]


def test_every_key_folder_lies_under_the_time_machine_exclusion():
    from backend import local_profile, u8_host
    from backend.u8_profile import ProductionProfile
    from docsuri_ops import isolation_check
    from docsuri_ops.arrangement import phases

    assert isolation_check.EXCLUSIONS == (
        "/Library/DocSuri/",
        "/Users/revenantonthemission/Library/Group Containers/HUAQ24HBR6.dev.orbstack/")
    assert local_profile.KEY_FOLDERS == ("export-keys", "control-keys", "verifier-key",
                                         "cursor-key")
    profile_root = ArrangementPaths().profile
    for name in local_profile.KEY_FOLDERS:
        assert str(profile_root / name) == f"/Library/DocSuri/profile/{name}"
        assert (f"profile/{name}", "service", 0o700) in phases.FOLDERS
        assert str(profile_root / name).startswith("/Library/DocSuri/")
    # L1-4: the production code gives the cursor key's place; the test never joins it.
    profile = ProductionProfile(profile_root, "production-run", "https://docsuri.rvnnt.dev",
                                15432, float("inf"), realm="production")
    expected = Path("/Library/DocSuri/profile/cursor-key/search-cursor.key")
    assert u8_host.cursor_key_path(profile) == expected
    assert local_profile.key_folder(profile, "cursor-key") / u8_host.CURSOR_KEY == expected
    assert str(expected).startswith("/Library/DocSuri/")
