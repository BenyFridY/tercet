"""Buyer-owned delivery evidence recorded beside transport delivery."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

import psycopg

from mesa import db

DeliveryResult = Literal["verified", "failed", "unknown"]
_DELIVERY_RESULTS = frozenset({"verified", "failed", "unknown"})


@dataclass(frozen=True)
class DeliveryVerification:
    """A caller-owned verdict over the bytes recorded for one request.

    ``method`` names the validator. ``evidence`` carries its bounded contract
    digest, required paths, or other replayable facts. The request row already
    binds the response-body digest, so this record does not copy response bytes.
    """

    method: str
    result: DeliveryResult
    evidence: dict[str, Any]
    expires_at_utc: datetime | None = None

    def __post_init__(self) -> None:
        if not self.method.strip():
            raise ValueError("delivery verification method must be nonempty")
        if self.result not in _DELIVERY_RESULTS:
            raise ValueError("delivery verification result must be verified, failed, or unknown")


def record_delivery_verification(
    conn: psycopg.Connection[Any],
    *,
    request_id: UUID,
    verification: DeliveryVerification,
) -> None:
    """Persist caller evidence without promoting transport success to validity."""
    db.insert_verification(
        conn,
        subject_type="delivery",
        subject_ref=str(request_id),
        method=verification.method,
        result=verification.result,
        evidence=verification.evidence,
        expires_at_utc=verification.expires_at_utc,
    )
