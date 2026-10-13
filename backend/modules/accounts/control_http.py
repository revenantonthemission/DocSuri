"""C02 account-control adapters; every principal comes from the protected cookie."""

from __future__ import annotations

import hashlib
from uuid import UUID

from backend.local_browser import (
    ENTRY_COOKIE,
    SESSION_COOKIE,
    BrowserDenied,
    boundary_route,
    optional_authority,
    post_context,
    private_cookie,
    read_payload,
    require_policy,
    require_post_headers,
)
from backend.modules.accounts.control_cursor import ControlCursor
from backend.modules.accounts.control_repository import ControlRepository
from backend.modules.accounts.preauthentication import Preauthentication
from backend.modules.accounts.services.control_identity import (
    ControlIdentityService,
    FixtureIdentityProvider,
)
from backend.modules.accounts.services.control_mfa import ControlMfaService
from backend.transactions import guard
from docsuri_shared.workspace import execution, wire
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

PROFILE_VOCABULARY = "u2-profile-v1"
PROFILE_FIELDS = ("displayName", "affiliation", "biography")
LIFECYCLE_COOKIE = "docsuri_lifecycle"


def control_router(entry, lifecycle) -> APIRouter:
    policy = entry.control_policy
    origin = entry.transactions.profile.origin
    anonymous = Preauthentication(entry)
    repository = ControlRepository(entry.transactions, policy)
    mfa = ControlMfaService(entry)
    cursor = ControlCursor(
        bytes.fromhex(entry.verifier("cursor", "accounts-u2")), lifetime=policy.cursor_seconds
    )
    identities = ControlIdentityService(
        entry, {name: FixtureIdentityProvider(name) for name in ("google", "orcid")}
    )
    router = APIRouter(route_class=boundary_route(origin, missing=(403, "FORBIDDEN")))

    async def context(request, *, guest=False):
        return await post_context(
            request, origin=origin, entry=entry, anonymous=anonymous if guest else None
        )

    def flow(request):
        return anonymous.read(request.cookies.get(ENTRY_COOKIE, "")).flow

    def output(schema, value):
        return schema.model_validate(value).model_dump(mode="json", exclude_none=True)

    def page_records(authority, page, items, kind):
        limit = page.get("limit", 20)
        if type(limit) is not int or not 1 <= limit <= policy.max_page_size:
            raise ValueError("finite page limit required")
        revision = entry.transactions.run(
            "accounts", lambda conn: guard(conn, authority, purpose="account-control")
        )
        snapshot = hashlib.sha256(":".join(v["revision"] for v in items).encode()).hexdigest()
        scope = ":".join((kind, str(revision), str(limit), snapshot))
        position = (
            cursor.decode(authority.account_id, scope, page["cursor"])
            if page.get("cursor")
            else {"index": 0}
        )
        offset = position["index"]
        if type(offset) is not int or not 0 <= offset <= len(items):
            raise ValueError("invalid page position")
        after = offset + limit
        return {
            "items": items[offset:after],
            "page": {
                "nextCursor": cursor.encode(authority.account_id, scope, {"index": after})
                if after < len(items)
                else None,
                "snapshotRevision": snapshot,
            },
            "appliedLimit": limit,
            "policyRef": policy.reference,
        }

    @router.post("/api/v2/c02/access-read-profile")
    async def profile(request: Request):
        _, _, authority = await context(request)
        await read_payload(request, wire.AccessProfileInputHttp)
        value = await run_in_threadpool(repository.profile, authority)
        return present_profile(value)

    def present_profile(value):
        return output(
            wire.AccessProfile,
            {
                "accountId": value["accountId"],
                "revision": value["revision"],
                "lifecycleRevision": value["lifecycleRevision"],
                "email": value["email"],
                "emailVerified": True,
                "fieldVocabularyRevision": PROFILE_VOCABULARY,
                "definitions": [
                    {
                        "fieldId": key,
                        "labelKey": "profile." + key,
                        "valueKind": "single_choice" if key == "role" else "text",
                        "mutable": key != "role",
                        "nullable": False,
                        "choiceIds": ["member", "administrator"] if key == "role" else [],
                        "policyRef": policy.reference,
                    }
                    for key in (*PROFILE_FIELDS, "role")
                ],
                "fields": [
                    {
                        "fieldId": key,
                        "value": value["role"]
                        if key == "role"
                        else value["displayName"]
                        if key == "displayName"
                        else value["profile"].get(key, ""),
                    }
                    for key in (*PROFILE_FIELDS, "role")
                ],
            },
        )

    @router.post("/api/v2/c02/access-update-profile")
    async def update_profile(request: Request):
        operation, _, authority = await context(request)
        value = await read_payload(request, wire.AccessProfileUpdateInputHttp)
        require_policy(value, policy.reference)
        if value["fieldVocabularyRevision"] != PROFILE_VOCABULARY:
            raise BrowserDenied(409, "CONFLICT")
        changes = value["changes"]
        if len(changes) > len(PROFILE_FIELDS) or len({v["fieldId"] for v in changes}) != len(
            changes
        ):
            raise BrowserDenied(422, "INVALID_ARGUMENT")
        result = await run_in_threadpool(
            repository.update_profile,
            authority,
            operation,
            UUID(value["expectedRevision"]),
            {v["fieldId"]: v["value"] for v in changes},
        )
        return present_profile(result)

    @router.post("/api/v2/c02/access-list-consents")
    async def consents(request: Request):
        _, _, authority = await context(request)
        value = await read_payload(request, wire.AccessConsentListInputHttp)
        page = value["page"]
        rows = await run_in_threadpool(repository.consents, authority)
        items = [
            {
                "consentId": row["purpose"],
                "accountId": str(authority.account_id),
                "purposeId": row["purpose"],
                "decision": "granted" if row["granted"] else "revoked",
                "revision": row["revision"],
                "effectiveAt": row["effective_at"],
                "policyRef": policy.reference,
            }
            for row in rows
        ]
        return output(
            wire.AccessConsentPage,
            await run_in_threadpool(page_records, authority, page, items, "consents"),
        )

    @router.post("/api/v2/c02/access-update-consent")
    async def update_consent(request: Request):
        operation, _, authority = await context(request)
        value = await read_payload(request, wire.AccessConsentUpdateInputHttp)
        require_policy(value, policy.reference)
        return output(
            wire.AccessConsentRecord,
            await run_in_threadpool(
                repository.update_consent,
                authority,
                operation,
                UUID(value["expectedRevision"]),
                value["purposeId"],
                value["decision"] == "granted",
            ),
        )

    @router.post("/api/v2/c02/access-request-password-reset")
    async def request_password_reset(request: Request):
        operation, _, _ = await context(request, guest=True)
        value = await read_payload(request, wire.AccessEmailRequestInputHttp)
        require_policy(value, policy.reference)
        return output(
            wire.AccessChallengeDelivery,
            await run_in_threadpool(
                entry.request_password_reset, operation, value["email"], flow(request)
            ),
        )

    @router.post("/api/v2/c02/access-complete-password-reset")
    async def complete_password_reset(request: Request):
        operation, _, _ = await context(request, guest=True)
        value = await read_payload(request, wire.AccessPasswordResetInputHttp)
        proof = value["verification"]
        if proof["flowBinding"] != flow(request):
            raise BrowserDenied(403, "FORBIDDEN")
        result = await run_in_threadpool(
            entry.complete_password_reset,
            operation,
            UUID(proof["challengeId"]),
            proof["proof"],
            proof["flowBinding"],
            value["newPassword"],
        )
        return output(wire.Ack, result)

    @router.post("/api/v2/c02/access-change-password")
    async def change_password(request: Request):
        operation, _, authority = await context(request)
        value = await read_payload(request, wire.AccessPasswordChangeInputHttp)
        result = await run_in_threadpool(
            entry.change_password,
            authority,
            operation,
            value["currentPassword"],
            value["newPassword"],
        )
        response = JSONResponse(output(wire.Ack, result))
        private_cookie(response, SESSION_COOKIE, "", 0)
        return response

    @router.post("/api/v2/c02/access-request-email-change")
    async def request_email_change(request: Request):
        operation, _, authority = await context(request)
        value = await read_payload(request, wire.AccessEmailChangeInputHttp)
        require_policy(value, policy.reference)
        return output(
            wire.AccessChallengeDelivery,
            await run_in_threadpool(
                entry.request_email_change,
                authority,
                operation,
                value["currentProof"],
                value["newEmail"],
                flow(request),
            ),
        )

    @router.post("/api/v2/c02/access-complete-email-change")
    async def complete_email_change(request: Request):
        operation, _, authority = await context(request)
        value = (await read_payload(request, wire.AccessEmailChangeCompleteInputHttp))[
            "verification"
        ]
        if value["flowBinding"] != flow(request):
            raise BrowserDenied(403, "FORBIDDEN")
        result = await run_in_threadpool(
            entry.complete_email_change,
            authority,
            operation,
            UUID(value["challengeId"]),
            value["proof"],
            value["flowBinding"],
        )
        response = JSONResponse(output(wire.Ack, result))
        private_cookie(response, SESSION_COOKIE, "", 0)
        return response

    @router.post("/api/v2/c02/access-begin-mfa-enrollment")
    async def begin_mfa(request: Request):
        operation, _, authority = await context(request)
        value = await read_payload(request, wire.AccessMfaEnrollmentInputHttp)
        require_policy(value, policy.reference)
        return output(
            wire.AccessMfaEnrollment,
            await run_in_threadpool(mfa.begin, authority, value["currentProof"], operation),
        )

    @router.post("/api/v2/c02/access-retrieve-mfa-enrollment-material")
    async def material(request: Request):
        _, _, authority = await context(request)
        value = await read_payload(request, wire.AccessMfaMaterialInputHttp)
        await run_in_threadpool(entry.reauthenticate, authority, value["currentProof"])
        return output(
            wire.AccessMfaMaterial,
            await run_in_threadpool(
                mfa.material, authority, UUID(value["enrollmentId"]), value["deliveryReference"]
            ),
        )

    @router.post("/api/v2/c02/access-confirm-mfa-enrollment")
    async def confirm_mfa(request: Request):
        operation, _, authority = await context(request)
        value = await read_payload(request, wire.AccessMfaConfirmInputHttp)
        proof = value["verification"]
        if proof["challengeId"] != value["enrollmentId"] or proof["flowBinding"] != str(
            authority.session_id
        ):
            raise BrowserDenied(403, "FORBIDDEN")
        return output(
            wire.Ack,
            await run_in_threadpool(
                mfa.confirm, authority, UUID(value["enrollmentId"]), proof["proof"], operation
            ),
        )

    @router.post("/api/v2/c02/access-verify-mfa")
    async def verify_mfa(request: Request):
        require_post_headers(request, origin)
        value = await read_payload(request, wire.AccessMfaVerifyInputHttp)
        if value["factorKind"] != "totp":
            return mfa.recover()
        proof = value["verification"]
        result = await run_in_threadpool(
            mfa.verify,
            request.cookies.get(SESSION_COOKIE, ""),
            request.headers["x-csrf-token"],
            UUID(proof["challengeId"]),
            UUID(proof["flowBinding"]),
            proof["proof"],
        )
        response = JSONResponse(output(wire.AccessLoginResult, result.public))
        private_cookie(response, SESSION_COOKIE, result.token, policy.session_seconds)
        return response

    @router.post("/api/v2/c02/access-recover-mfa")
    async def recover_mfa(request: Request):
        require_post_headers(request, origin)
        await read_payload(request, wire.AccessMfaRecoveryInputHttp)
        return mfa.recover()

    @router.post("/api/v2/c02/access-prepare-lifecycle")
    async def prepare_lifecycle(request: Request):
        operation, _, authority = await context(request)
        value = await read_payload(request, wire.AccessLifecyclePrepareInputHttp)
        require_policy(value, policy.reference)
        return output(
            wire.AccessLifecycleConfirmation,
            await run_in_threadpool(
                lifecycle.prepare_confirmation,
                authority,
                operation,
                UUID(value["expectedRevision"]),
                value["action"],
                value["currentProof"],
            ),
        )

    @router.post("/api/v2/c02/lifecycle-request")
    async def request_lifecycle(request: Request):
        operation = require_post_headers(request, origin)
        value = await read_payload(request, wire.LifecycleRequestInputHttp)
        require_policy(value, policy.reference)
        outcome = await run_in_threadpool(
            lifecycle.request_browser,
            request.cookies.get(SESSION_COOKIE, ""),
            request.headers["x-csrf-token"],
            operation,
            UUID(value["confirmationRef"]),
            value["action"],
        )
        limited = await run_in_threadpool(lifecycle.status_transport, outcome, operation)
        status = await run_in_threadpool(
            lifecycle.inspect_limited, limited.token, limited.csrf, UUID(outcome["requestId"])
        )
        response = JSONResponse(output(wire.LifecycleRequest, status))
        private_cookie(response, LIFECYCLE_COOKIE, limited.token, policy.session_seconds)
        private_cookie(response, SESSION_COOKIE, "", 0)
        return response

    @router.post("/api/v2/c02/lifecycle-inspect")
    async def inspect_lifecycle(request: Request):
        await context(request, guest=True)
        value = await read_payload(request, wire.LifecycleStatusInputHttp)
        token = request.cookies.get(LIFECYCLE_COOKIE, "")
        return output(
            wire.LifecycleRequest,
            await run_in_threadpool(
                lifecycle.inspect_limited,
                token,
                entry.verifier("session-csrf", token),
                UUID(value["lifecycleRequestId"]),
            ),
        )

    @router.post("/api/v2/c02/access-request-reactivation")
    async def request_reactivation(request: Request):
        operation, _, _ = await context(request, guest=True)
        value = await read_payload(request, wire.AccessEmailRequestInputHttp)
        require_policy(value, policy.reference)
        return output(
            wire.AccessChallengeDelivery,
            await run_in_threadpool(
                entry.request_reactivation, operation, value["email"], flow(request)
            ),
        )

    @router.post("/api/v2/c02/lifecycle-reactivate")
    async def reactivate(request: Request):
        operation, _, _ = await context(request, guest=True)
        value = await read_payload(request, wire.LifecycleReactivationInputHttp)
        require_policy(value, policy.reference)
        proof = value["verification"]
        if (
            proof["flowBinding"] != flow(request)
            or value["confirmationRef"] != proof["challengeId"]
        ):
            raise BrowserDenied(403, "FORBIDDEN")
        outcome = await run_in_threadpool(
            lifecycle.reactivate,
            operation,
            UUID(proof["challengeId"]),
            proof["proof"],
            proof["flowBinding"],
        )
        limited = await run_in_threadpool(lifecycle.status_transport, outcome, operation)
        response = JSONResponse(
            output(
                wire.LifecycleReactivationResult,
                {
                    "lifecycleRequestId": outcome["requestId"],
                    "revision": outcome["revision"],
                    "state": "accepted",
                    "access": "reactivation_pending",
                    "policyRef": policy.reference,
                    "requestId": str(operation),
                    "reasonKey": "restoration-evidence-pending",
                },
            )
        )
        private_cookie(response, LIFECYCLE_COOKIE, limited.token, policy.session_seconds)
        return response

    def link_value(item):
        return {
            "identityLinkId": item["linkId"],
            "provider": item["provider"],
            "providerSubject": item["providerSubject"],
            "revision": item["revision"],
            "profileAvailable": item["profileAvailable"],
        }

    @router.post("/api/v2/c02/access-begin-identity-flow")
    async def begin_identity(request: Request):
        _, _, authority = await context(request, guest=True)
        value = await read_payload(request, wire.AccessBeginIdentityInputHttp)
        require_policy(value, policy.reference)
        accepted = await run_in_threadpool(
            identities.begin,
            authority,
            value["provider"],
            value["intent"],
            flow(request),
            value["returnRouteId"],
        )
        url = await run_in_threadpool(identities.fixture_authorization, accepted)
        return output(
            wire.AccessProviderRedirect,
            {
                "flowId": accepted["flowId"],
                "provider": accepted["provider"],
                "authorizationUrl": url,
                "expiresAt": accepted["expiresAt"],
            },
        )

    @router.get("/api/v2/identity/callback/{provider}")
    async def identity_callback(request: Request, provider: str):
        if provider not in identities.providers or len(str(request.url.query).encode()) > 2048:
            raise BrowserDenied(422, "INVALID_ARGUMENT")
        if set(request.query_params) != {"flow", "state", "code"} or any(
            len(request.query_params.getlist(k)) != 1 for k in request.query_params
        ):
            raise BrowserDenied(422, "INVALID_ARGUMENT")
        authority = await optional_authority(request, entry=entry)
        result = await run_in_threadpool(
            identities.complete,
            UUID(request.query_params["flow"]),
            request.query_params["state"],
            flow(request),
            request.query_params["code"],
            identities.providers[provider].callback,
            authority,
        )
        if hasattr(result, "public"):
            if result.public["state"] == "mfa_required":
                body = {"state": "mfa_required", "mfaChallenge": result.public}
            else:
                from backend.transactions import Authority

                session = result.public["session"]
                links = await run_in_threadpool(
                    identities.list_links,
                    Authority(UUID(session["accountId"]), UUID(session["sessionId"])),
                )
                body = {
                    "state": "signed_in",
                    "identityLink": link_value(next(v for v in links if v["provider"] == provider)),
                    "session": session,
                }
            response = JSONResponse(output(execution.AccessIdentityResult, body))
            private_cookie(response, SESSION_COOKIE, result.token, policy.session_seconds)
            return response
        links = await run_in_threadpool(identities.list_links, authority)
        return output(
            execution.AccessIdentityResult,
            {
                "state": "linked",
                "identityLink": link_value(
                    next(v for v in links if v["linkId"] == result["linkId"])
                ),
            },
        )

    @router.post("/api/v2/c02/access-list-identity-links")
    async def list_identity(request: Request):
        _, _, authority = await context(request)
        value = await read_payload(request, wire.AccessIdentityListInputHttp)
        page = value["page"]
        links = await run_in_threadpool(identities.list_links, authority)
        return output(
            wire.AccessIdentityPage,
            await run_in_threadpool(
                page_records, authority, page, [link_value(v) for v in links], "identity-links"
            ),
        )

    @router.post("/api/v2/c02/access-unlink-identity")
    async def unlink_identity(request: Request):
        operation, _, authority = await context(request)
        value = await read_payload(request, wire.AccessUnlinkIdentityInputHttp)
        return output(
            wire.Ack,
            await run_in_threadpool(
                identities.unlink,
                authority,
                UUID(value["identityLinkId"]),
                UUID(value["expectedRevision"]),
                operation,
            ),
        )

    @router.post("/api/v2/c02/access-read-orcid-profile")
    async def orcid_profile(request: Request):
        _, _, authority = await context(request)
        value = await read_payload(request, wire.AccessOrcidProfileInputHttp)
        links = await run_in_threadpool(identities.list_links, authority)
        linked = next(
            (
                v
                for v in links
                if v["provider"] == "orcid" and v["linkId"] == value["identityLinkId"]
            ),
            None,
        )
        if linked is None:
            raise BrowserDenied(403, "FORBIDDEN")
        observed = await run_in_threadpool(identities.orcid_profile, authority)
        return output(
            wire.AccessOrcidProfile,
            {
                "identityLinkId": linked["linkId"],
                "subject": linked["providerSubject"],
                "revision": linked["revision"],
                "provenance": "synthetic-orcid-fixture",
                "works": [],
                "coverage": observed["coverage"],
            },
        )

    return router
