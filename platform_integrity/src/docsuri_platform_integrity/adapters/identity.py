"""Client Identity Service — Cloudflare → BFF → FastAPI identity 체인."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from fastapi import Request


@dataclass(frozen=True)
class ClientIdentity:
    identity: str
    authenticated: bool
    source: str  # "CLOUDFLARE", "BFF", "FASTAPI"
    verified_at: int


class ClientIdentityService:
    """Client identity 추출 및 검증."""

    @staticmethod
    def extract_identity(request: Request) -> ClientIdentity:
        # Cloudflare에서 전달된 identity 헤더 읽기
        client_identity = request.headers.get("X-Client-Identity")

        if client_identity:
            # Cloudflare에서 검증된 identity
            if client_identity.startswith("user:"):
                return ClientIdentity(
                    identity=client_identity,
                    authenticated=True,
                    source="CLOUDFLARE",
                    verified_at=int(__import__("time").time() * 1_000_000)
                )
            elif client_identity.startswith("ip:"):
                return ClientIdentity(
                    identity=client_identity,
                    authenticated=False,
                    source="CLOUDFLARE",
                    verified_at=int(__import__("time").time() * 1_000_000)
                )

        # Fallback: IP 기반 익명 identity
        client_ip = request.client.host if request.client else "unknown"
        identity = f"ip:{hashlib.sha256(client_ip.encode()).hexdigest()[:16]}"
        return ClientIdentity(
            identity=identity,
            authenticated=False,
            source="FASTAPI",
            verified_at=int(__import__("time").time() * 1_000_000)
        )


class IdentityMiddleware:
    """Cloudflare → BFF → FastAPI identity 체인 미들웨어."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)

        # Cloudflare에서 전달된 identity 헤더 읽기
        client_identity = request.headers.get("X-Client-Identity")
        if not client_identity:
            # Fallback: IP 기반 익명 identity
            client_ip = scope.get("client", ("unknown", 0))[0]
            client_identity = (
                f"ip:{hashlib.sha256(client_ip.encode()).hexdigest()[:16]}"
            )

        # request.state에 identity 저장
        scope["state"] = scope.get("state", {})
        scope["state"]["client_identity"] = client_identity

        await self.app(scope, receive, send)
