"""Unit tests for SAMANVAY cryptographic logging and Ed25519 signing (Spec §18)."""

import pytest
from samanvay.core.crypto import (
    DecisionLogger,
    generate_keypair,
    sign_log_digest,
    verify_chain,
    verify_log_digest,
)


def test_decision_logger_hash_chain():
    """Verify that records form a valid SHA-256 hash chain and detect tampering."""
    logger = DecisionLogger()

    # Append 5 decisions
    r1 = logger.append(1, 10.0, "ASSIGN", "FACT", "Assigned scout-1")
    r2 = logger.append(2, 25.0, "SWITCH_PLAN", "FACT", "Dominant repair plan chosen")
    r3 = logger.append(3, 40.0, "ESCALATE", "VALUE", "Trade-off aid vs risk")
    r4 = logger.append(4, 55.0, "SHIELD_OVERRIDE", "SAFETY", "Plume boundary avoided")
    r5 = logger.append(5, 70.0, "LEASE_EXPIRE", "FACT", "Lease expired on scout-2")

    assert len(logger.records) == 5

    # Verify untampered chain
    valid, msg = verify_chain(logger.records)
    assert valid, msg

    # Verify Ed25519 signature
    priv, pub = generate_keypair()
    sig = sign_log_digest(priv, logger.last_hash)
    assert verify_log_digest(pub, logger.last_hash, sig)

    # Tampering test: modify one record's explanation
    tampered_records = list(logger.records)
    tampered_records[2] = tampered_records[2].model_copy(update={"explanation": "Tampered explanation"})

    is_valid_after_tamper, tamper_msg = verify_chain(tampered_records)
    assert not is_valid_after_tamper
    assert "Tampered record 3" in tamper_msg
