"""TLS-only R1C serving entry. Peer certificate identity is injected from the TLS transport."""

import hashlib
import ssl
from pathlib import Path


def build_server(app, *, certificate: Path, private_key: Path, ca: Path, port: int = 8101):
    import uvicorn
    from uvicorn.protocols.http.h11_impl import H11Protocol

    class CertificateProtocol(H11Protocol):
        def connection_made(self, transport):
            super().connection_made(transport)
            tls = transport.get_extra_info("ssl_object")
            peer = tls.getpeercert(binary_form=True) if tls else None
            if not peer:
                transport.close()
                return
            fingerprint = hashlib.sha256(peer).hexdigest()
            application = self.app

            async def authenticated(scope, receive, send):
                scope = {**scope, "client_certificate_fingerprint": fingerprint}
                await application(scope, receive, send)

            self.app = authenticated

    for path in (certificate, private_key, ca):
        if path.is_symlink() or not path.is_file():
            raise ValueError("TLS material unavailable")
    if private_key.stat().st_mode & 0o077:
        raise PermissionError("TLS key must be role-private")
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        workers=1,
        http=CertificateProtocol,
        proxy_headers=False,
        ssl_certfile=str(certificate),
        ssl_keyfile=str(private_key),
        ssl_ca_certs=str(ca),
        ssl_cert_reqs=ssl.CERT_REQUIRED,
        ssl_version=ssl.PROTOCOL_TLS_SERVER,
        limit_concurrency=16,
        timeout_keep_alive=5,
        access_log=False,
    )
    config.load()
    config.ssl.minimum_version = ssl.TLSVersion.TLSv1_2
    return uvicorn.Server(config)


def serve(app, *, certificate: Path, private_key: Path, ca: Path, port: int = 8101):
    build_server(app, certificate=certificate, private_key=private_key, ca=ca, port=port).run()
