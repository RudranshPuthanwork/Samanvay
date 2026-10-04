"""Cryptographic primitives for SAMANVAY decision logging (Spec §5.3.6, §6.6, §18).

Provides:
- Deterministic canonical hashing for SHA-256 hash-chaining of DecisionRecord.
- Ed25519 key generation, mission-end signing, and audit log verification.
"""

import hashlib
import json
from typing import Any
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

from samanvay.core.models import DecisionRecord


GENESIS_HASH = "0000000000000000000000000000000000000000000000000000000000000000"


def canonical_json_bytes(obj: Any) -> bytes:
    """Serialize object to sorted, compact canonical JSON bytes."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def compute_decision_hash(
    record_id: int,
    t: float,
    kind: str,
    classification: str,
    trigger_event: int | None,
    forecast_epoch: int | None,
    chosen: str | None,
    options: list[str],
    operator_choice: dict[str, Any] | None,
    explanation: str,
    prev_hash: str,
) -> str:
    """Compute SHA-256 hash for a DecisionRecord entry including prev_hash."""
    payload = {
        "id": record_id,
        "t": round(t, 4),
        "kind": kind,
        "classification": classification,
        "trigger_event": trigger_event,
        "forecast_epoch": forecast_epoch,
        "chosen": chosen,
        "options": sorted(options),
        "operator_choice": operator_choice,
        "explanation": explanation,
        "prev_hash": prev_hash,
    }
    digest = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    return digest


class DecisionLogger:
    """Hash-chained in-memory and persistent decision logger."""

    def __init__(self, genesis_hash: str = GENESIS_HASH) -> None:
        self._records: list[DecisionRecord] = []
        self._last_hash: str = genesis_hash

    @property
    def last_hash(self) -> str:
        return self._last_hash

    @property
    def records(self) -> list[DecisionRecord]:
        return list(self._records)

    def append(
        self,
        record_id: int,
        t: float,
        kind: str,
        classification: str,
        explanation: str,
        trigger_event: int | None = None,
        forecast_epoch: int | None = None,
        chosen: str | None = None,
        options: list[str] | None = None,
        operator_choice: Any = None,
    ) -> DecisionRecord:
        """Create, hash, chain, and store a DecisionRecord."""
        opts = options or []
        op_dict = operator_choice.model_dump() if hasattr(operator_choice, "model_dump") else operator_choice
        rec_hash = compute_decision_hash(
            record_id=record_id,
            t=t,
            kind=kind,
            classification=classification,
            trigger_event=trigger_event,
            forecast_epoch=forecast_epoch,
            chosen=chosen,
            options=opts,
            operator_choice=op_dict,
            explanation=explanation,
            prev_hash=self._last_hash,
        )

        record = DecisionRecord(
            id=record_id,
            t=t,
            kind=kind,  # type: ignore[arg-type]
            classification=classification,  # type: ignore[arg-type]
            trigger_event=trigger_event,
            forecast_epoch=forecast_epoch,
            chosen=chosen,
            options=opts,
            operator_choice=operator_choice,
            explanation=explanation,
            prev_hash=self._last_hash,
            hash=rec_hash,
        )
        self._records.append(record)
        self._last_hash = rec_hash
        return record


# -----------------------------------------------------------------------------
# Ed25519 Signing and Verification
# -----------------------------------------------------------------------------

def generate_keypair() -> tuple[ed25519.Ed25519PrivateKey, ed25519.Ed25519PublicKey]:
    """Generate Ed25519 private and public key pair."""
    priv_key = ed25519.Ed25519PrivateKey.generate()
    pub_key = priv_key.public_key()
    return priv_key, pub_key


def sign_log_digest(private_key: ed25519.Ed25519PrivateKey, final_hash: str) -> str:
    """Sign the final hash of the decision log with Ed25519."""
    signature = private_key.sign(final_hash.encode("utf-8"))
    return signature.hex()


def verify_log_digest(
    public_key: ed25519.Ed25519PublicKey,
    final_hash: str,
    signature_hex: str,
) -> bool:
    """Verify the signature on the final hash using Ed25519."""
    try:
        sig_bytes = bytes.fromhex(signature_hex)
        public_key.verify(sig_bytes, final_hash.encode("utf-8"))
        return True
    except Exception:
        return False


def verify_chain(records: list[DecisionRecord], genesis_hash: str = GENESIS_HASH) -> tuple[bool, str]:
    """Validate every link in the decision log hash chain.

    Returns:
        (is_valid, error_message_if_invalid)
    """
    expected_prev = genesis_hash
    for idx, rec in enumerate(records):
        if rec.prev_hash != expected_prev:
            return False, f"Broken link at record {rec.id} (index {idx}): expected prev_hash {expected_prev}, got {rec.prev_hash}"

        recomputed = compute_decision_hash(
            record_id=rec.id,
            t=rec.t,
            kind=rec.kind.value if hasattr(rec.kind, "value") else str(rec.kind),
            classification=rec.classification.value if hasattr(rec.classification, "value") else str(rec.classification),
            trigger_event=rec.trigger_event,
            forecast_epoch=rec.forecast_epoch,
            chosen=rec.chosen,
            options=rec.options,
            operator_choice=rec.operator_choice.model_dump() if rec.operator_choice else None,
            explanation=rec.explanation,
            prev_hash=rec.prev_hash,
        )
        if recomputed != rec.hash:
            return False, f"Tampered record {rec.id}: recorded hash {rec.hash} does not match computed {recomputed}"
        expected_prev = rec.hash

    return True, "Chain valid"
