"""Rendering the arrangement's templates (U8 plan Step 37; D8, security-design § 5.2,
§ 6.3, § 6.4, § 6.8, tech-stack-decisions § Configuration).

`render(paths, accounts, operator=…, tunnel_name=…)` turns `templates/` into the files the
installer puts in place, every one from one `ArrangementPaths` and one `Accounts`, and
none holding a secret (D8): the function takes no secret, and a rendered file names a
secret only by its holder's fixed path.

- the eleven launch job definitions (`launch-jobs.json` → `/Library/LaunchDaemons/
  <label>.plist`), each with its account, `RunAtLoad`, `KeepAlive` for the long-running
  jobs with `ExitTimeOut` 30, or a root job's schedule, and its account's log paths;
- the sudo rules (`sudoers` → `/etc/sudoers.d/docsuri-v2`, 0440): every in-person alias at
  `timestamp_timeout=0`, each allowed invocation listed exactly, the programs under
  `/Library/DocSuri/release/ops/bin/`;
- the packet filter anchor (`pf-anchor` → `/etc/pf.anchors/org.docsuri.v2`);
- the tunnel's three registered configurations (`tunnel.yml` → `tunnel/config/
  <origin>.yml`), naming the tunnel chosen at installation and its fixed credentials
  path, each keeping `ssh.rvnnt.dev`, with `httpHostHeader` for v2's host and the
  maintenance server;
- `postgresql.conf`, the database account's, 0600, in its data folder; `pg_hba.conf` and
  `pg_ident.conf`, root's, 0644, in the root-owned `postgres-rules` folder, which the
  database account can read but neither write nor replace (your answer of 2026-11-11,
  "Map the login, root rules"): the first rule line admits the superuser over the socket
  only through the one peer map, which maps only the database account's name;
- the rotation job's folder list (`logrotate-folders.json`).

`FIXED_PROGRAMS` is the release's seventeen programs in `ops/bin/`, which the installer
and the release command set to mode 0755; `PROGRAM_WORDS` their closed sets, which the
sudo rules list exactly.
"""

from __future__ import annotations

import json
import plistlib
from dataclasses import dataclass
from pathlib import Path
from string import Template

from docsuri_ops.u8_platform.credential_release import LOGINS
from docsuri_ops.u8_platform.platform_profile import PRODUCTION_LABELS, TUNNEL_ORIGINS

from .paths import Accounts, ArrangementPaths

TEMPLATES = Path(__file__).resolve().parent / "templates"
SUPERUSER = "postgres"
# The one peer map (`pg_ident.conf`): the database account's operating-system name to the
# superuser, and nothing else (your answer of 2026-11-11, "Map the login, root rules").
SUPERUSER_MAP = "docsuri_superuser"
TUNNEL_CREDENTIALS = "tunnel.json"
TUNNEL_NAME_PATTERN = r"docsuri-v2-[a-z0-9]{6,24}"
# The release's fixed programs (ops/bin), each root-owned and 0755 when installed.
FIXED_PROGRAMS = (
    "docsuri-backup-agent", "docsuri-backup-unlock", "docsuri-credential-release",
    "docsuri-installer", "docsuri-isolation-check", "docsuri-ledger", "docsuri-logrotate",
    "docsuri-logs", "docsuri-migration-import", "docsuri-pf-load", "docsuri-production-tool",
    "docsuri-profile", "docsuri-release", "docsuri-service-start", "docsuri-service-stop",
    "docsuri-standing", "docsuri-tunnel-route",
)
PROGRAM_MODE = 0o755
AGENT_UNATTENDED = ("status", "backup", "ledger-copy", "verify", "dispose-due")
AGENT_IN_PERSON = ("snapshot", "snapshot-stream", "rollback-copy", "stream-back",
                   "dispose-event", "set-date", "dispose-mismatch", "rebuild-catalogue",
                   "prepare-volume", "configure")
LEDGER_WORDS = ("append", "copy", "verify", "read", "repair")
LEDGER_UNATTENDED = ("append", "copy", "verify", "read")
PRODUCTION_TOOL_WORDS = (
    "migrate", "restore-evaluate", "restore-database", "recreate-database", "remove-database",
    "create-export-key-after-loss", "rotate-export-key", "retire-export-key",
    "export-key-counts", "replace-verifier-key", "control-key-recovery", "readiness-evidence",
    "create-disposable", "restore-import", "prepare-production",
    "export-settings", "provider-environment", "research-review",
    # In person only (your decisions of 2026-10-24 and 2026-10-25): never in a standing set.
    "control-key-start",
    # In person only (U8 plan Step 70(d), L1-59): the soak's latency lines, read only.
    "latency-summaries",
    # In person only, while v2 is stopped (U8 plan Step 72(a), L1-4).
    "replace-cursor-key",
    # In person only: the providers' window words (U8 plan Step 106(e); your request of
    # 2026-11-14, "Add the defect fixes").
    "provider-previews", "provider-decision", "provider-failed",
)
PROFILE_WORDS = ("mode", "admission", "rehearsal-database", "backup-volume")
# `None` stands for a program that takes no argument (written `""` in the rules).
PROGRAM_WORDS: dict[str, tuple[str | None, ...]] = {
    "docsuri-service-start": PRODUCTION_LABELS,
    "docsuri-service-stop": PRODUCTION_LABELS,
    "docsuri-tunnel-route": TUNNEL_ORIGINS,
    "docsuri-credential-release": LOGINS,
    "docsuri-isolation-check": (None,),
    "docsuri-logs": ("filter",),
    "docsuri-release": ("install", "rollback", "verify", "recover"),
    "docsuri-installer": ("plan", "apply", "verify", "change-password"),
    "docsuri-profile": PROFILE_WORDS,
    "docsuri-ledger": LEDGER_WORDS,
    "docsuri-production-tool": PRODUCTION_TOOL_WORDS,
    "docsuri-migration-import": ("import", "idempotency"),
    "docsuri-backup-agent": AGENT_UNATTENDED + AGENT_IN_PERSON,
}
# Who runs each in-person program, by security-design § 5.2's grants.
IN_PERSON_ROOT = ("docsuri-service-start", "docsuri-service-stop", "docsuri-tunnel-route",
                  "docsuri-credential-release", "docsuri-isolation-check", "docsuri-logs",
                  "docsuri-release", "docsuri-installer")
IN_PERSON_SERVICE = ("docsuri-profile", "docsuri-ledger", "docsuri-production-tool",
                     "docsuri-migration-import")
IN_PERSON_BACKUP = ("docsuri-backup-agent",)
STANDING = {"backup": ("docsuri-backup-agent", AGENT_UNATTENDED),
            "service": ("docsuri-ledger", LEDGER_UNATTENDED),
            "root": ("docsuri-isolation-check", (None,))}
TUNNEL_SERVICES = {"v1-web": "http://127.0.0.1:3000", "v2-host": "http://127.0.0.1:18200",
                   "maintenance": "http://127.0.0.1:18201"}
HOST_HEADER = ("    originRequest:\n"
               "      httpHostHeader: docsuri.rvnnt.dev\n")


@dataclass(frozen=True)
class Rendered:
    """One file the installer puts in place: where, its bytes, its mode, the account that
    owns it (`root` or an `Accounts` field) and its manifest kind."""

    target: Path
    content: bytes
    mode: int
    owner: str
    kind: str  # `program`, `rule` or `config`


def arrangement_version() -> int:
    value = int((TEMPLATES / "VERSION").read_text().strip())
    if value < 1:
        raise ValueError("the arrangement version is a positive integer")
    return value


def _template(name: str) -> Template:
    return Template((TEMPLATES / name).read_text(encoding="utf-8"))


def _account(accounts: Accounts, key: str) -> str:
    return "root" if key == "root" else getattr(accounts, key).name


def _group(accounts: Accounts, key: str) -> str:
    return "wheel" if key == "root" else getattr(accounts, key).name


# --- launch jobs ---------------------------------------------------------------------------


def launch_jobs(paths: ArrangementPaths) -> list[dict]:
    """The jobs' table with the paths filled in."""
    values = {"prefix": str(paths.prefix), "release": str(paths.release)}
    raw = Template((TEMPLATES / "launch-jobs.json").read_text(encoding="utf-8"))
    return json.loads(raw.substitute(values))["jobs"]


def plist_of(job: dict, accounts: Accounts) -> dict:
    definition = {
        "Label": job["label"],
        "UserName": _account(accounts, job["account"]),
        "GroupName": _group(accounts, job["account"]),
        "ProgramArguments": list(job["arguments"]),
        "WorkingDirectory": job["workingDirectory"],
        "RunAtLoad": True,
        "KeepAlive": bool(job["keepAlive"]),
        "StandardOutPath": job["logs"] + ".out.log",
        "StandardErrorPath": job["logs"] + ".err.log",
        "Umask": 0o077,
    }
    if job["keepAlive"]:
        definition["ExitTimeOut"] = 30
    if "environment" in job:
        definition["EnvironmentVariables"] = dict(job["environment"])
    if "startInterval" in job:
        definition["StartInterval"] = int(job["startInterval"])
    if "calendar" in job:
        definition["StartCalendarInterval"] = dict(job["calendar"])
    return definition


def render_launch_jobs(paths: ArrangementPaths, accounts: Accounts) -> list[Rendered]:
    return [
        Rendered(paths.launch_daemons / f"{job['label']}.plist",
                 plistlib.dumps(plist_of(job, accounts), fmt=plistlib.FMT_XML, sort_keys=True),
                 0o644, "root", "rule")
        for job in launch_jobs(paths)
    ]


# --- sudo rules ----------------------------------------------------------------------------


def invocations(paths: ArrangementPaths, program: str,
                words: tuple[str | None, ...] | None = None) -> list[str]:
    """Each allowed invocation of one program, exactly."""
    path = paths.release_bin / program
    chosen = PROGRAM_WORDS[program] if words is None else words
    return [f'{path} ""' if word is None else f"{path} {word}" for word in chosen]


def _alias_body(lines: list[str]) -> str:
    return ", \\\n".join("    " + line for line in lines)


def render_sudoers(paths: ArrangementPaths, accounts: Accounts, *, operator: str) -> Rendered:
    def every(programs: tuple[str, ...]) -> list[str]:
        return [line for program in programs for line in invocations(paths, program)]

    standing = {name: invocations(paths, program, words)
                for name, (program, words) in STANDING.items()}
    text = _template("sudoers").substitute(
        version=arrangement_version(), bin=paths.release_bin, operator=operator,
        service=accounts.service.name, scheduler=accounts.scheduler.name,
        backup=accounts.backup.name,
        inperson_root=_alias_body(every(IN_PERSON_ROOT)),
        inperson_service=_alias_body(every(IN_PERSON_SERVICE)),
        inperson_backup=_alias_body(every(IN_PERSON_BACKUP)),
        standing_backup=_alias_body(standing["backup"]),
        standing_service=_alias_body(standing["service"]),
        standing_root=_alias_body(standing["root"]),
    )
    return Rendered(paths.sudoers_rules, text.encode(), 0o440, "root", "rule")


# --- the packet filter, the tunnel, PostgreSQL and rotation ----------------------------------


def render_pf_anchor(paths: ArrangementPaths, accounts: Accounts) -> Rendered:
    text = _template("pf-anchor").substitute(
        version=arrangement_version(), service=accounts.service.name,
        models=accounts.models.name, database=accounts.database.name)
    return Rendered(paths.pf_anchor, text.encode(), 0o644, "root", "rule")


def render_tunnel(paths: ArrangementPaths, *, tunnel_name: str) -> list[Rendered]:
    import re

    if re.fullmatch(TUNNEL_NAME_PATTERN, tunnel_name) is None:
        raise ValueError("the tunnel's name is outside its fixed form")
    credentials = paths.tunnel_credentials / TUNNEL_CREDENTIALS
    rendered = []
    for origin in TUNNEL_ORIGINS:
        text = _template("tunnel.yml").substitute(
            version=arrangement_version(), prefix=paths.prefix, origin_name=origin,
            tunnel=tunnel_name, credentials=credentials, service=TUNNEL_SERVICES[origin],
            origin_request="" if origin == "v1-web" else HOST_HEADER)
        rendered.append(Rendered(paths.tunnel_config / f"{origin}.yml", text.encode(), 0o644,
                                 "root", "config"))
    return rendered


def render_postgres(paths: ArrangementPaths, accounts: Accounts) -> list[Rendered]:
    """`postgresql.conf` in the data folder (the database account's); `pg_hba.conf` and
    `pg_ident.conf` in the root-owned rules folder, root's and readable by the server, so
    the database account cannot write a trust line or a wider map into them, nor replace
    them (the launch job names both with `-c`)."""
    values = {"version": arrangement_version(), "prefix": paths.prefix,
              "rules": paths.postgres_rules, "superuser": SUPERUSER,
              "superuser_map": SUPERUSER_MAP, "database": accounts.database.name}
    return [
        Rendered(paths.postgres_data / "postgresql.conf",
                 _template("postgresql.conf").substitute(values).encode(), 0o600,
                 "database", "config"),
        *(Rendered(paths.postgres_rules / name, _template(name).substitute(values).encode(),
                   0o644, "root", "rule")
          for name in ("pg_hba.conf", "pg_ident.conf")),
    ]


def render_rotation(paths: ArrangementPaths) -> Rendered:
    from docsuri_ops.logrotate import FOLDERS

    folders = json.dumps([{"path": item.path, "account": item.account,
                           "ownedFrom": item.owned_from, "kind": item.kind}
                          for item in FOLDERS], sort_keys=True)
    text = _template("logrotate-folders.json").substitute(version=arrangement_version(),
                                                          folders=folders)
    json.loads(text)  # the rendered list is well-formed JSON
    return Rendered(paths.logrotate_folders, text.encode(), 0o644, "root", "config")


def render(paths: ArrangementPaths, accounts: Accounts, *, operator: str,
           tunnel_name: str) -> list[Rendered]:
    """Every rule and configuration file the arrangement installs."""
    if not operator or not operator.replace("_", "").replace("-", "").isalnum():
        raise ValueError("the operator account's name is outside its form")
    return [
        *render_launch_jobs(paths, accounts),
        render_sudoers(paths, accounts, operator=operator),
        render_pf_anchor(paths, accounts),
        *render_tunnel(paths, tunnel_name=tunnel_name),
        *render_postgres(paths, accounts),
        render_rotation(paths),
    ]
