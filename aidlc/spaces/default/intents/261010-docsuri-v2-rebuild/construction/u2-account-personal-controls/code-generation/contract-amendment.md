# U2 canonical amendment and compatibility

The approved implementation plan requires canonical coordination before reset
persistence and accounting. C03 and the C13 application boundary now declare
3.0.0. Other protocols retain 2.0.0; existing dispatch version stays unchanged.
Required `SettingsResetResult.resetId` is explicitly breaking for strict older
consumers. It is not described as automatically additive compatibility.

The canonical shared registry and OpenAPI definitions add read-only
`settings.listResets` and `settings.inspectReset`, owner/authority-bound paging,
immutable acceptance and separate monotonic live status. They add internal
accepting-owner allocate/inspect/accept/close admission contracts and terminal
closure evidence. Accept and close compete on the same owner record. Usage
must obtain closure through a trusted owner port, never a caller proof or
negative lookup. C02 specifies the existing local transaction guard seam,
current scope/admin/MFA checks and revocation serialization.

Bounded consumer inventory: literal references to SettingsResetResult,
SettingsResetInput, UsageReserveInput and UsageSettleInput in backend,
frontend/src, tests/u1_integrated_paper_journey and shared/python/tests returned
no matches. This is evidence for the inspected v2 consumers only. It does not
establish absence of external consumers. Public activation still requires their
inventory; old strict reset consumers must negotiate C03 v3 or remain on their
prior artifact. Existing U1 routes, DispatchCommand and U7 protocols retain
their wire shapes. Generated schema/type consumers are regenerated together.

Current mounted owners: AccountAccess entry, CorpusContent read, Discovery,
Library, Personalization defaults/onboarding, UsageEntitlements inspection and
PaperAssistance. The only mounted chargeable owner is PaperAssistance. Its
existing admission/rejection proof is the integration base, not permission to
create a second ledger. Future ResearchWorkspace/TopicsDigests/ApprovedExport
must register their actual accepting-owner port before chargeable activation.
No future participant is represented by a successful placeholder.

Before U2 changes, usage-inspect invokes ensure_entitlement and allocates on a
read. U2 will remove that behavior in its profile and exercise nonallocating
absence. Current settings defaults/skip also overwrite established choices;
the approved regression obligations remain open until executable proof.

Canonical validation: the existing /tmp/docsuri-contract-validation interpreter
validated 14 contracts, 450 definitions, 159 typed operations, 119 HTTP
operations, 19 dependency edges, all 70 functional IDs, 16 positive and 39
negative schema cases. This is schema/design evidence only. Generated binding
drift and actual owner integration evidence follow implementation.

Planned owner migration boundary: accounts/u2_controls.sql,
personalization/u2_controls.sql, library/u2_controls.sql and plans/u2_controls.sql
under backend/modules. They apply only after the existing U1 local schema
sequence to the owned synthetic U2 realm. Existing-service data is untouched;
rollback is compatible code/config or forward repair, not destructive down SQL.
