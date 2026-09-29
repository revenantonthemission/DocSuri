"""Pure generation-lifecycle decisions. No filesystem, no clock, no authority.

The adapter performs I/O; every safety decision that must be reproducible under audit is made
here so it can be tested without a disk. Nothing in this module mutates or deletes anything.
"""

from ..contracts.models import U64, Digest, GateVerdict, Value

MAX_GENERATIONS = 10_000
MAX_FILES_PER_GENERATION = 10_000


class DurabilityReceipt(Value):
    """Proof that a generation's bytes and its directory entries reached stable storage.

    A receipt is written only after every file and every directory was flushed. Its absence is
    what makes an interrupted seal detectable, so it is never synthesised from a manifest alone.
    """

    generation: Digest
    manifest: Digest
    files: U64
    bytes: U64
    head_revision: U64
    receipt: Digest


class ImportedGeneration(Value):
    """Metadata of a verified foreign generation. Import never publishes or activates it."""

    generation: Digest
    manifest: Digest
    files: U64
    bytes: U64
    verifiable: GateVerdict


def receipt_matches(receipt: DurabilityReceipt, *, generation: str, manifest: str,
                    files: int, total_bytes: int, head_revision: int) -> bool:
    """Exact agreement on every field. A partial receipt never counts as durable."""
    if type(files) is not int or type(total_bytes) is not int or type(head_revision) is not int:
        return False
    if files < 0 or total_bytes < 0 or head_revision < 0:
        return False
    return (
        receipt.generation == generation
        and receipt.manifest == manifest
        and int(receipt.files) == files
        and int(receipt.bytes) == total_bytes
        and int(receipt.head_revision) == head_revision
    )


def collectible(generation: str, *, head: str | None, pins: frozenset[str],
                receipts: frozenset[str]) -> bool:
    """A generation is collectible only when nothing can still observe it.

    The head and every pin are protected. A generation without a durability receipt is
    *retained* rather than collected: it is the evidence of an interrupted seal, and deleting
    it would destroy the only trace that activation never completed.
    """
    if not isinstance(generation, str) or not isinstance(pins, frozenset):
        raise TypeError("invalid collection inputs")
    if generation == head or generation in pins:
        return False
    return generation in receipts
