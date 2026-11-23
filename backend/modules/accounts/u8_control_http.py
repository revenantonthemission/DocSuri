"""AccountAccess's account-control routes under D1 (U8 plan Step 19; decisions of
2026-10-22 and the person's decision of 2026-10-24, "Move, scope tools, test U2").

`d1_control_router(entry, lifecycle)` is U2's `control_router` with U8's parts: the
arrival identity service, the complete second factor, and these routes, matched before
the built ones:

- each session cookie's `Max-Age` is the issued session's remaining length (the second
  factor's and the identity callback's);
- the consent routes serve a consent-pending session, from a password or a provider
  sign-in, for giving consents only;
- the identity callback answers a migrated account's first provider sign-in with
  `AccessIdentityConsentPending`;
- the three enrolment routes serve an administrator's setup-only session for enrolling
  the second factor only;
- reset completion and password change answer a new password the password policy
  refuses with 422 `INVALID_ARGUMENT` and `messageKey` `password.policy` (your answer of
  2026-11-11, "Say the password is too weak").

A cookie that is not one of these limited sessions takes the built route. The router
refuses an entry without a first sign-in, so it never serves U2's realm.
"""

from __future__ import annotations

import hashlib
from uuid import UUID

from backend.local_browser import (
    ENTRY_COOKIE,
    SESSION_COOKIE,
    BrowserDenied,
    boundary_route,
    error_response,
    optional_authority,
    private_cookie,
    read_payload,
    require_policy,
    require_post_headers,
)
from backend.modules.accounts.control_http import control_router
from backend.modules.accounts.preauthentication import Preauthentication
from backend.modules.accounts.services.control_identity import FixtureIdentityProvider
from backend.modules.accounts.u8_control_policy import remaining_seconds
from backend.modules.accounts.u8_entry import PasswordPolicyRefused
from backend.modules.accounts.u8_identity import ArrivalIdentityService
from backend.modules.accounts.u8_mfa import CompleteMfaService
from docsuri_shared.workspace import execution, wire
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

CONSENTS = "/api/v2/c02/access-list-consents"
UPDATE_CONSENT = "/api/v2/c02/access-update-consent"
BEGIN_MFA = "/api/v2/c02/access-begin-mfa-enrollment"
MATERIAL = "/api/v2/c02/access-retrieve-mfa-enrollment-material"
CONFIRM_MFA = "/api/v2/c02/access-confirm-mfa-enrollment"
VERIFY_MFA = "/api/v2/c02/access-verify-mfa"
IDENTITY_CALLBACK = "/api/v2/identity/callback/{provider}"
COMPLETE_RESET = "/api/v2/c02/access-complete-password-reset"
CHANGE_PASSWORD = "/api/v2/c02/access-change-password"
# The routes whose built handler serves every cookie that is not a limited session, and
# the two password routes, whose built handler serves every request.
FALLBACKS = (
    CONSENTS, UPDATE_CONSENT, BEGIN_MFA, MATERIAL, CONFIRM_MFA, COMPLETE_RESET,
    CHANGE_PASSWORD,
)


def _output(schema, value):
    return schema.model_validate(value).model_dump(mode="json", exclude_none=True)


async def answer_weak_password(handler, request: Request):
    """The built handler's answer, or, for a new password the password policy refuses,
    the route's own refusal: 422 `INVALID_ARGUMENT` with `messageKey` `password.policy`
    (your answer of 2026-11-11, "Say the password is too weak"). C02's routes declare a
    422 answer, and the boundary already answers malformed input on them that way."""
    try:
        return await handler(request)
    except PasswordPolicyRefused as refused:
        return error_response(refused.status, refused.code, message_key=refused.message_key)


class D1ControlRoutes:
    """The D1 routes over one entry; `built` holds the built handlers they fall back to,
    filled once U2's router is assembled."""

    def __init__(self, entry, identities, mfa):
        self.entry, self.identities, self.mfa = entry, identities, mfa
        self.first = entry.first_sign_in
        self.policy = entry.control_policy
        self.origin = entry.transactions.profile.origin
        self.anonymous = Preauthentication(entry)
        self.built: dict[str, object] = {}
        self.router = APIRouter(route_class=boundary_route(self.origin, missing=(403, "FORBIDDEN")))
        self._mount()

    def session_seconds(self, public: dict) -> int:
        """The session cookie's `Max-Age`: the issued session's remaining length."""
        session = public.get("session") or public
        return remaining_seconds(session["expiresAt"], self.entry.clock())

    async def limited(self, request, purpose: str):
        """The current limited session of `purpose`, or None for any other cookie, which
        then takes the built route."""
        token = request.cookies.get(SESSION_COOKIE, "")
        if not token:
            return None
        found = await run_in_threadpool(self.first.limited_purpose, token)
        if found != purpose:
            return None
        return token, request.headers.get("x-csrf-token", "")

    async def setup_context(self, request):
        """An administrator's setup-only session, or None for the built route."""
        held = await self.limited(request, "mfa")
        if held is None:
            return None
        operation = require_post_headers(request, self.origin)
        authority = await run_in_threadpool(self.first.setup_authority, *held)
        return operation, authority

    def flow(self, request):
        return self.anonymous.read(request.cookies.get(ENTRY_COOKIE, "")).flow

    def _mount(self) -> None:
        router, first, policy, entry, mfa = (
            self.router, self.first, self.policy, self.entry, self.mfa)

        @router.post(CONSENTS)
        async def consents(request: Request):
            held = await self.limited(request, "consent_pending")
            if held is None:
                return await self.built[CONSENTS](request)
            require_post_headers(request, self.origin)
            value = await read_payload(request, wire.AccessConsentListInputHttp)
            limit = value["page"].get("limit", 20)
            if value["page"].get("cursor") or type(limit) is not int or not (
                1 <= limit <= policy.max_page_size
            ):
                raise BrowserDenied(422, "INVALID_ARGUMENT")
            account_id, rows = await run_in_threadpool(first.consents, *held)
            # v2's consent purposes fit one page: there is never a next one.
            items = [
                {
                    "consentId": row["purpose"],
                    "accountId": str(account_id),
                    "purposeId": row["purpose"],
                    "decision": "granted" if row["granted"] else "revoked",
                    "revision": row["revision"],
                    "effectiveAt": row["effective_at"],
                    "policyRef": policy.reference,
                }
                for row in rows
            ][:limit]
            return _output(wire.AccessConsentPage, {
                "items": items,
                "page": {
                    "nextCursor": None,
                    "snapshotRevision": hashlib.sha256(
                        ":".join(v["revision"] for v in items).encode()
                    ).hexdigest(),
                },
                "appliedLimit": limit,
                "policyRef": policy.reference,
            })

        @router.post(UPDATE_CONSENT)
        async def update_consent(request: Request):
            held = await self.limited(request, "consent_pending")
            if held is None:
                return await self.built[UPDATE_CONSENT](request)
            operation = require_post_headers(request, self.origin)
            value = await read_payload(request, wire.AccessConsentUpdateInputHttp)
            require_policy(value, policy.reference)
            given = await run_in_threadpool(
                first.give_consent, *held, operation, UUID(value["expectedRevision"]),
                value["purposeId"], value["decision"] == "granted",
            )
            response = JSONResponse(_output(wire.AccessConsentRecord, given.record))
            if given.completion == "full_session":
                private_cookie(
                    response, SESSION_COOKIE, held[0],
                    remaining_seconds(given.expires_at, entry.clock()),
                )
            elif given.completion == "sign_in_again":
                private_cookie(response, SESSION_COOKIE, "", 0)
            return response

        @router.post(BEGIN_MFA)
        async def begin_mfa(request: Request):
            setup = await self.setup_context(request)
            if setup is None:
                return await self.built[BEGIN_MFA](request)
            operation, authority = setup
            value = await read_payload(request, wire.AccessMfaEnrollmentInputHttp)
            require_policy(value, policy.reference)
            return _output(
                wire.AccessMfaEnrollment,
                await run_in_threadpool(
                    lambda: mfa.begin(authority, value["currentProof"], operation, setup=True)
                ),
            )

        @router.post(MATERIAL)
        async def material(request: Request):
            setup = await self.setup_context(request)
            if setup is None:
                return await self.built[MATERIAL](request)
            _, authority = setup
            value = await read_payload(request, wire.AccessMfaMaterialInputHttp)
            await run_in_threadpool(first.reauthenticate_setup, authority, value["currentProof"])
            return _output(
                wire.AccessMfaMaterial,
                await run_in_threadpool(
                    lambda: mfa.material(
                        authority, UUID(value["enrollmentId"]), value["deliveryReference"],
                        setup=True,
                    )
                ),
            )

        @router.post(CONFIRM_MFA)
        async def confirm_mfa(request: Request):
            setup = await self.setup_context(request)
            if setup is None:
                return await self.built[CONFIRM_MFA](request)
            operation, authority = setup
            value = await read_payload(request, wire.AccessMfaConfirmInputHttp)
            proof = value["verification"]
            if proof["challengeId"] != value["enrollmentId"] or proof["flowBinding"] != str(
                authority.session_id
            ):
                raise BrowserDenied(403, "FORBIDDEN")
            result = await run_in_threadpool(
                lambda: mfa.confirm(
                    authority, UUID(value["enrollmentId"]), proof["proof"], operation,
                    setup=True,
                )
            )
            response = JSONResponse(_output(wire.Ack, result))
            # The setup-only session ended with the enrolment; the person signs in again.
            private_cookie(response, SESSION_COOKIE, "", 0)
            return response

        @router.post(VERIFY_MFA)
        async def verify_mfa(request: Request):
            require_post_headers(request, self.origin)
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
            response = JSONResponse(_output(wire.AccessLoginResult, result.public))
            private_cookie(response, SESSION_COOKIE, result.token,
                           self.session_seconds(result.public))
            return response

        @router.get(IDENTITY_CALLBACK)
        async def identity_callback(request: Request, provider: str):
            return await self.identity_callback(request, provider)

        @router.post(COMPLETE_RESET)
        async def complete_password_reset(request: Request):
            return await answer_weak_password(self.built[COMPLETE_RESET], request)

        @router.post(CHANGE_PASSWORD)
        async def change_password(request: Request):
            return await answer_weak_password(self.built[CHANGE_PASSWORD], request)

    async def identity_callback(self, request: Request, provider: str):
        identities = self.identities
        if provider not in identities.providers or len(str(request.url.query).encode()) > 2048:
            raise BrowserDenied(422, "INVALID_ARGUMENT")
        if set(request.query_params) != {"flow", "state", "code"} or any(
            len(request.query_params.getlist(k)) != 1 for k in request.query_params
        ):
            raise BrowserDenied(422, "INVALID_ARGUMENT")
        authority = await optional_authority(request, entry=self.entry)
        result = await run_in_threadpool(
            identities.complete,
            UUID(request.query_params["flow"]),
            request.query_params["state"],
            self.flow(request),
            request.query_params["code"],
            identities.providers[provider].callback,
            authority,
        )
        if hasattr(result, "public"):
            if result.public["state"] == "mfa_required":
                body = {"state": "mfa_required", "mfaChallenge": result.public}
            elif result.public["state"] == "consent_pending":
                # A migrated account's first provider sign-in: the answer carries its
                # link already, because a consent-pending session passes no guard.
                body = result.public
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
            response = JSONResponse(_output(execution.AccessIdentityResult, body))
            private_cookie(response, SESSION_COOKIE, result.token,
                           self.session_seconds(result.public))
            return response
        links = await run_in_threadpool(identities.list_links, authority)
        return _output(
            execution.AccessIdentityResult,
            {
                "state": "linked",
                "identityLink": link_value(
                    next(v for v in links if v["linkId"] == result["linkId"])
                ),
            },
        )


def link_value(item):
    return {
        "identityLinkId": item["linkId"],
        "provider": item["provider"],
        "providerSubject": item["providerSubject"],
        "revision": item["revision"],
        "profileAvailable": item["profileAvailable"],
    }


def _flat(routes) -> list:
    """The concrete routes behind `routes`: FastAPI keeps an included router as one entry
    (`original_router`), so each is opened in turn."""
    found = []
    for route in routes:
        inner = getattr(route, "original_router", None)
        found += [route] if inner is None else _flat(inner.routes)
    return found


def d1_control_router(entry, lifecycle) -> APIRouter:
    """U2's account-control router with U8's parts, for the two complete realms."""
    if getattr(entry, "first_sign_in", None) is None:
        raise PermissionError("the D1 routes need the complete entry")
    identities = ArrivalIdentityService(
        entry, {name: FixtureIdentityProvider(name) for name in ("google", "orcid")}
    )
    mfa = CompleteMfaService(entry)
    routes = D1ControlRoutes(entry, identities, mfa)
    router = control_router(entry, lifecycle, identities=identities, mfa=mfa,
                            routes=routes.router)
    own = {route.endpoint for route in routes.router.routes}
    for route in _flat(router.routes):
        if getattr(route, "path", None) in FALLBACKS and route.endpoint not in own:
            routes.built[route.path] = route.endpoint
    if set(routes.built) != set(FALLBACKS):
        raise RuntimeError("U2's control router lacks a route the D1 routes fall back to")
    return router
