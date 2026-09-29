"""Protected receipt issuance and verification against independent release policy."""

import os
import stat
import tempfile
from pathlib import Path

from ..adapters.receipt_signer import KeychainReceiptSigner, require_signer_role
from ..contracts.codec import canonical, decode
from ..contracts.models import ValidityWindow
from ..deployment import receipt_policy as policy_module
from ..deployment.receipt import Capability, Receipt, verify_capability
from ..deployment.receipt_policy import ReceiptOperation, output_directory


def requested_capabilities(policy, requested=None):
    values = tuple(requested) if requested is not None else tuple(policy.artifacts())
    if (not values or len(set(values)) != len(values)
        or not set(values) <= set(policy.artifacts())):
        raise PermissionError("receipt capability is outside release policy")
    return values


def publish_receipts(snapshot, envelopes):
    """Stage every envelope before replacement; only a validated signer-owned public directory."""
    policy = snapshot.policy
    directory = output_directory(policy.profile, policy.release)
    info = directory.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != policy.signer.uid
        or stat.S_IMODE(info.st_mode) != 0o755):
        raise PermissionError("receipt output directory is unprotected")
    # Every ancestor above the signer-owned directory must be root-owned and unwritable by
    # anyone else, so no other identity can rename or replace the public directory.
    policy_module.protected_chain(directory.parent)
    staged = []
    try:
        for capability, envelope in envelopes.items():
            target = directory / (capability.value + ".receipt.json")
            if target.exists() or target.is_symlink():
                info = target.lstat()
                if (not stat.S_ISREG(info.st_mode) or info.st_uid != policy.signer.uid
                    or info.st_nlink != 1 or info.st_mode & 0o022):
                    raise PermissionError("existing receipt is unprotected")
            fd, temporary = tempfile.mkstemp(prefix=".receipt-", dir=directory)
            staged.append((Path(temporary), target))
            with os.fdopen(fd, "wb") as stream:
                stream.write(canonical(envelope))
                stream.flush()
                os.fchmod(stream.fileno(), 0o444)
                os.fsync(stream.fileno())
        snapshot.check_current()
        for temporary, target in staged:
            os.replace(temporary, target)
        descriptor = os.open(directory, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        for temporary, _ in staged:
            temporary.unlink(missing_ok=True)


def issue_protected(snapshot, probe, *, requested=None, seconds=86400, clock=None,
                    signer=None, publish=publish_receipts):
    policy = snapshot.policy
    require_signer_role(policy)
    requested = requested_capabilities(policy, requested)
    if type(seconds) is not int or not 1 <= seconds <= policy.max_receipt_seconds:
        raise ValueError("receipt duration exceeds release policy")
    operation = ReceiptOperation(snapshot, clock)
    key = policy.trust()[policy.signer.key_id]
    if key.revoked or not key.validity.contains(*operation.initial):
        raise PermissionError("signing key is not currently authorized")
    outcomes = probe(operation.initial)
    for capability in requested:
        outcome = outcomes.get(capability)
        if (outcome is None or outcome.proven is not True
            or outcome.capability != capability
            or outcome.artifact != policy.artifacts()[capability] or outcome.evidence is None):
            raise PermissionError("requested capability is not proven for this release")
    lower, upper = operation.check()
    lower = min(lower, operation.initial[0])
    expires = lower + seconds * 1_000_000
    if (key.revoked or not key.validity.contains(lower, upper)
        or expires > int(key.validity.valid_until) or expires >= 2**64):
        raise PermissionError("signing key validity cannot cover receipt")
    validity = ValidityWindow(valid_from=str(lower), valid_until=str(expires))
    signer = signer if signer is not None else KeychainReceiptSigner(policy)
    envelopes = {}
    for capability in requested:
        receipt = Receipt(capability=capability, host=policy.host, release=policy.release,
                          validity=validity, artifact=outcomes[capability].artifact,
                          evidence=outcomes[capability].evidence)
        current = operation.check()
        envelope = signer.sign(receipt, lower=current[0], upper=current[1])
        lower_now, upper_now = operation.check()
        proven, _ = verify_capability(envelope, capability=capability, host=policy.host,
                                     release=policy.release, trust=policy.trust(),
                                     lower=lower_now, upper=upper_now)
        if not proven:
            raise PermissionError("new receipt is not currently verifiable")
        envelopes[capability] = envelope
    operation.check()
    publish(snapshot, envelopes)
    operation.check()
    return envelopes


def verify_evidence(snapshot, evidence, *, clock=None):
    """Evidence supplies receipts; keys, release authority and time come from protected policy."""
    policy = snapshot.policy
    if (not isinstance(evidence, dict) or set(evidence) != {"release", "receipts"}
        or evidence["release"] != policy.release or not isinstance(evidence["receipts"], dict)):
        raise ValueError("evidence may contain only matching release and receipts")
    if not set(evidence["receipts"]) <= {cap.value for cap in Capability}:
        raise ValueError("unknown receipt capability")
    operation = ReceiptOperation(snapshot, clock)
    result = {}
    # Include elapsed time so a key/receipt must be valid across the complete verification cut.
    ending = operation.check()
    lower, upper = min(operation.initial[0], ending[0]), max(operation.initial[1], ending[1])
    for capability in Capability:
        envelope = evidence["receipts"].get(capability.value)
        if capability not in policy.artifacts():
            result[capability.value] = "not_configured"
            continue
        ok, reason = verify_capability(envelope, capability=capability, host=policy.host,
                                       release=policy.release, trust=policy.trust(),
                                       lower=lower, upper=upper)
        if ok:
            receipt = Receipt.model_validate_json(canonical(decode(canonical(envelope["payload"]))))
            if receipt.artifact != policy.artifacts()[capability]:
                ok, reason = False, "artifact_mismatch"
        result[capability.value] = "verified" if ok else reason
    # Re-evaluate validity at the return boundary, not only before signature work.
    lower, upper = operation.check()
    for capability in Capability:
        if result[capability.value] == "verified":
            ok, reason = verify_capability(evidence["receipts"][capability.value],
                                           capability=capability, host=policy.host,
                                           release=policy.release, trust=policy.trust(),
                                           lower=lower, upper=upper)
            if not ok:
                result[capability.value] = reason
    return (frozenset(name for name, reason in result.items() if reason == "verified"),
            {name: reason for name, reason in result.items() if reason != "verified"})
