"""Asset Service — 발급, presigned URL, same-origin delivery."""

from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass
from enum import StrEnum

import jwt
from minio import Minio
from minio.error import S3Error

from docsuri_platform_integrity.adapters.authz import AuthorizationService


class LicenseType(StrEnum):
    ARXIV = "ARXIV"
    SEMANTIC_SCHOLAR = "SEMANTIC_SCHOLAR"
    OPENALEX = "OPENALEX"
    USER_UPLOAD = "USER_UPLOAD"
    GENERATED = "GENERATED"


@dataclass(frozen=True)
class AssetMetadata:
    asset_id: str
    content_type: str
    owner: str
    license: str
    object_ref: str
    size_bytes: int
    created_at: int


class AssetService:
    """Asset 발급, presigned URL 생성, 인증."""

    JWT_SECRET: str = "CHANGE_ME_IN_PRODUCTION"
    JWT_ALGORITHM = "HS256"
    TOKEN_TTL_SECONDS = 60
    MINIO_BUCKET = "docsuri"

    def __init__(
        self,
        minio_client: Minio,
        authz_service: AuthorizationService,
        bucket: str = MINIO_BUCKET,
    ):
        self.minio = minio_client
        self.authz = authz_service
        self.bucket = bucket

    def issue(self, content: bytes, owner: str, license: str, object_ref: str) -> str:
        asset_id = f"asset:{hashlib.sha256(content).hexdigest()[:32]}"
        object_name = f"assets/{asset_id}"

        try:
            self.minio.put_object(
                bucket_name=self.bucket,
                object_name=object_name,
                data=content,
                length=len(content),
                content_type="application/octet-stream",
            )
        except S3Error as e:
            raise RuntimeError(f"Failed to store asset: {e}") from e

        return asset_id

    def issue_presigned(self, asset_id: str, caller: str, action: str = "view") -> str:
        if not self.authz.recheck(caller, asset_id, "VIEW"):
            raise PermissionError("Asset access denied")

        presigned_url = self._minio_presigned_get(asset_id)
        token = self._create_token(asset_id, caller, action)

        from urllib.parse import urlencode, urlparse, urlunparse
        parsed = urlparse(presigned_url)
        query = urlencode({"token": token})
        return urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            query,
            parsed.fragment,
        ))

    def _minio_presigned_get(self, asset_id: str) -> str:
        return self.minio.presigned_get_object(
            bucket_name="docsuri",
            object_name=f"assets/{asset_id}",
            expires=60,
            response_headers={"response-content-disposition": "inline"},
        )

    def _create_token(self, asset_id: str, caller: str, action: str) -> str:
        payload = {
            "assetId": asset_id,
            "action": action,
            "nonce": uuid.uuid4().hex,
            "exp": int(time.time()) + self.TOKEN_TTL_SECONDS,
            "sub": caller,
        }
        secret = self._get_jwt_secret()
        return jwt.encode(payload, secret, algorithm="HS256")

    def _get_jwt_secret(self) -> str:
        return self.JWT_SECRET

    def authorize(self, caller: str, asset_id: str, action: str) -> bool:
        return self.authz.recheck(caller, asset_id, "VIEW")


def create_minio_client() -> Minio:
    return Minio(
        endpoint="127.0.0.1:9000",
        access_key="minioadmin",
        secret_key="minioadmin",
        secure=False,
    )
