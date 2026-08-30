"""Buyer-owned output evidence is bounded before it reaches the ledger."""

import pytest

from mesa.delivery import DeliveryVerification


def test_accepts_replayable_buyer_evidence() -> None:
    verification = DeliveryVerification(
        method="json-schema",
        result="verified",
        evidence={"output_contract_digest": "sha256:abc", "required_paths": ["decision"]},
    )
    assert verification.result == "verified"


def test_rejects_empty_method() -> None:
    with pytest.raises(ValueError, match="method must be nonempty"):
        DeliveryVerification(method=" ", result="failed", evidence={})


def test_rejects_unknown_result() -> None:
    with pytest.raises(ValueError, match="result must be"):
        DeliveryVerification(
            method="json-schema",
            result="passed",  # type: ignore[arg-type]
            evidence={},
        )
