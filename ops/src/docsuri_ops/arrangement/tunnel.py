"""Moving the tunnel without a gap (U8 plan Step 37; Workflow 20 step 6, NFR3.4,
security-design § 6.4).

The move is a fixed sequence of by-hand checklist items and the installer's own tool
steps, run in order and each recorded without certificate content:

1. confirm your other project's tunnel runs without the certificate (by hand);
2. revoke the account certificate your login account holds (by hand, in the dashboard);
3. as root, issue a new certificate into a root-only folder (by hand: a browser login);
4. create the new tunnel under the name the registered configurations use, its
   credentials written by `cloudflared tunnel create --credentials-file` into a root-only
   folder and put from there at their fixed path in the tunnel account's folder, created
   new and given to the tunnel account through their own descriptor;
5. make v1's web the active configuration, written root-owned through the installer's
   pending-file write, and start the tunnel's job;
6. move the hostnames' routes (by hand);
7. stop and remove your login account's `dev.docsuri.tunnel`, delete the old tunnel and
   confirm it is gone (by hand);
8. revoke the new certificate, confirm a listing with it is refused, then delete it,
   and confirm no certificate token remains (by hand, then the file goes).

From then the tunnel is one of service control's named services.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from . import safe_fs
from .paths import ArrangementPaths
from .render import TUNNEL_CREDENTIALS, TUNNEL_NAME_PATTERN

ROOT_CERTIFICATE_FOLDER = "tunnel-certificate"
# The routing program's own key for a registered configuration it cannot use
# (`u8_platform/fixed.py`'s `tunnel_route`).
REGISTERED_REFUSED = "registered-configuration-refused"
V1_AGENT = "dev.docsuri.tunnel"
SEQUENCE = (
    ("check", "other-tunnel-without-certificate"),
    ("check", "old-certificate-revoked"),
    ("check", "new-certificate-issued"),
    ("tool", "create-tunnel"),
    ("tool", "start-on-v1-web"),
    ("check", "hostnames-routed"),
    ("tool", "retire-login-tunnel"),
    ("check", "old-tunnel-deleted"),
    ("check", "new-certificate-revoked"),
    ("tool", "delete-new-certificate"),
    ("check", "no-certificate-token-left"),
)


class TunnelRefused(RuntimeError):
    """A tunnel step failed; the message is a fixed key."""


@dataclass
class TunnelMove:
    paths: ArrangementPaths
    tools: object
    tunnel_name: str
    tunnel_uid: int
    operator_uid: int
    cloudflared: Path
    wait: Callable[[str], None]
    log: Callable[[str, str], None]
    # The root-owned write the installer gives (`phases.write_file`): a pending file
    # created new beside the target, given its mode and owner on its own descriptor and
    # renamed over the target (NFR3.4).
    place: Callable[[Path, bytes], None]

    def __post_init__(self) -> None:
        if re.fullmatch(TUNNEL_NAME_PATTERN, self.tunnel_name) is None:
            raise TunnelRefused("tunnel-name-outside-its-form")

    @property
    def certificate_folder(self) -> Path:
        return self.paths.control / ROOT_CERTIFICATE_FOLDER

    @property
    def credentials(self) -> Path:
        return self.paths.tunnel_credentials / TUNNEL_CREDENTIALS

    def run(self) -> list[str]:
        """Every step in order; a step already done (its result in place) is skipped."""
        done = []
        for kind, name in SEQUENCE:
            if kind == "check":
                self.wait(name)
            else:
                getattr(self, "_" + name.replace("-", "_"))()
                self.log(name, "done")
            done.append(name)
        return done

    def _create_tunnel(self) -> None:
        """The new tunnel, its credentials put at their fixed path in the tunnel account's
        folder (your answer of 2026-11-10, "Fix both and sweep the rest"): `cloudflared`
        writes them into a fresh root-only folder in `control/`, never into a folder the
        tunnel account could change; the installer reads them back there and creates the
        fixed file new, relative to the credentials folder's descriptor (reached by the
        no-link walk), at 0600 and given to the tunnel account through its own descriptor;
        the root-only copy goes. A name already at the fixed path, a link included, is
        never written through: an existing name means the tunnel was made, and a name
        that appears in between is refused."""
        try:
            with safe_fs.folder_at(self.paths.prefix, self.credentials.parent) as folder:
                if safe_fs.lexists(folder, self.credentials.name):
                    return
        except FileNotFoundError:
            pass
        except safe_fs.PathRefused:
            raise TunnelRefused("tunnel-credentials-folder-is-a-link") from None
        certificate = self.certificate_folder / "cert.pem"
        if not certificate.is_file():
            raise TunnelRefused("new-certificate-missing")
        staging = Path(tempfile.mkdtemp(prefix=".tunnel-credentials-", dir=self.paths.control))
        try:
            staged = staging / self.credentials.name
            self.tools.run([str(self.cloudflared), "--origincert", str(certificate), "tunnel",
                            "create", "--credentials-file", str(staged), self.tunnel_name])
            content = safe_fs.read_regular(staging, staged)
            if content is None:
                raise TunnelRefused("tunnel-credentials-not-written")
            uid = self.tunnel_uid
            safe_fs.create_new(self.paths.prefix, self.credentials, content, mode=0o600,
                               give=lambda descriptor: self.tools.fchown(descriptor, uid, uid))
        except FileExistsError:
            raise TunnelRefused("tunnel-credentials-in-the-way") from None
        except safe_fs.PathRefused:
            raise TunnelRefused("tunnel-credentials-folder-is-a-link") from None
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    def _start_on_v1_web(self) -> None:
        """v1's web made the active choice, then the tunnel's job started (NFR3.4,
        security-design § 6.4): when no active choice exists, `v1-web.yml` is read as a
        regular file through the no-link walk and placed by the root-owned write the move
        is given, so the first active choice is root's; a missing file, a refused walk or
        a refused write answers the routing program's own key."""
        active = self.paths.tunnel_config / "active.yml"
        registered = self.paths.tunnel_config / "v1-web.yml"
        if not active.exists():
            try:
                content = safe_fs.read_regular(self.paths.prefix, registered)
                if content is None:
                    raise TunnelRefused(REGISTERED_REFUSED)
                self.place(active, content)
            except (OSError, safe_fs.PathRefused):
                raise TunnelRefused(REGISTERED_REFUSED) from None
        self.tools.bootstrap(self.paths.launch_daemons / "org.docsuri.tunnel.plist")

    def _retire_login_tunnel(self) -> None:
        """Your login account's `dev.docsuri.tunnel`: stopped and its definition removed
        once the new tunnel serves; another project's jobs stay as they are."""
        self.tools.bootout(f"gui/{self.operator_uid}/{V1_AGENT}")

    def _delete_new_certificate(self) -> None:
        certificate = self.certificate_folder / "cert.pem"
        if certificate.exists():
            os.unlink(certificate)
