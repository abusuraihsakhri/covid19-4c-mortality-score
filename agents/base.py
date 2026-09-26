"""Identifier screening and tamper-evident in-process audit helpers."""

import copy
import hashlib
import hmac
import json
import os
import re
import secrets
import time
import warnings
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Best-effort identifier screening only; this is not a de-identification guarantee.
PHI_PATTERNS = [
    re.compile(r"\b(?:MRN|mrn)[:#\s-]*\d{4,10}\b", re.IGNORECASE),
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    re.compile(r"\b(?:DOB|Date of Birth)[:\s]*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", re.IGNORECASE),
    re.compile(
        r"\b(?:Patient\s+Name|Patient)[:\s]+[A-Z][a-z]+\s+[A-Z][a-z]+\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:John\s+Doe|Jane\s+Smith|Alice\s+Johnson)\b", re.IGNORECASE),
]


class SecurityException(Exception):
    """Raised when the best-effort identifier screen detects a configured pattern."""


class ResourceLimitExceededException(Exception):
    """Raised when computational parameters exceed safety bounds."""


def assert_no_phi(text: str) -> None:
    """Reject text matching configured identifier patterns.

    This helper is intentionally conservative and incomplete. It must not be
    treated as formal de-identification or a compliance control by itself.
    """
    if not text:
        return
    for pattern in PHI_PATTERNS:
        if pattern.search(str(text)):
            raise SecurityException(
                "Identifier screening violation: sensitive identifier pattern detected"
            )


class PHIGuard:
    @staticmethod
    def assert_no_phi(text: str) -> None:
        assert_no_phi(text)

    @staticmethod
    def redact_phi(text: str) -> str:
        result = str(text)
        for pattern in PHI_PATTERNS:
            result = pattern.sub("[REDACTED_IDENTIFIER]", result)
        return result


class AuditTrail:
    """Append-only in-process HMAC-SHA256 hash chain."""

    GENESIS_HASH = "GENESIS_BLOCK_0000000000000000"

    def __init__(self, secret_key: Optional[str] = None):
        resolved_key = secret_key or os.getenv("AUDIT_SECRET_KEY")
        if resolved_key:
            self.secret_key = resolved_key.encode("utf-8")
        else:
            warnings.warn(
                "AUDIT_SECRET_KEY not set. Using an ephemeral key for this process; "
                "set AUDIT_SECRET_KEY for persistent audit verification.",
                RuntimeWarning,
                stacklevel=2,
            )
            self.secret_key = secrets.token_bytes(32)
        self.logs: List[Dict[str, Any]] = []

    def _signature_for(self, entry: Dict[str, Any]) -> str:
        sign_string = (
            f"{entry['audit_id']}|{entry['timestamp']}|{entry['actor']}|"
            f"{entry['actor_tier']}|{entry['event_type']}|{entry['payload_hash']}|"
            f"{entry['prev_hash']}"
        )
        return hmac.new(
            self.secret_key, sign_string.encode("utf-8"), hashlib.sha256
        ).hexdigest()

    def log(
        self,
        actor: str,
        actor_tier: str,
        event_type: str,
        details: Dict[str, Any],
    ) -> Dict[str, Any]:
        payload_str = json.dumps(details, sort_keys=True)
        assert_no_phi(payload_str)
        payload_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
        audit_id = f"AUDIT-{int(time.time() * 1000)}-{len(self.logs) + 1}"
        timestamp = datetime.now(timezone.utc).isoformat()
        previous_hash = (
            self.logs[-1]["current_hash"] if self.logs else self.GENESIS_HASH
        )
        entry = {
            "audit_id": audit_id,
            "timestamp": timestamp,
            "actor": actor,
            "actor_tier": actor_tier,
            "event_type": event_type,
            "payload_hash": payload_hash,
            "prev_hash": previous_hash,
        }
        entry["current_hash"] = self._signature_for(entry)
        self.logs.append(entry)
        return copy.deepcopy(entry)

    def verify_integrity(self) -> bool:
        required = {
            "audit_id",
            "timestamp",
            "actor",
            "actor_tier",
            "event_type",
            "payload_hash",
            "prev_hash",
            "current_hash",
        }
        for index, entry in enumerate(self.logs):
            if not required.issubset(entry):
                return False
            expected_previous = (
                self.logs[index - 1]["current_hash"]
                if index > 0
                else self.GENESIS_HASH
            )
            if entry["prev_hash"] != expected_previous:
                return False
            if not hmac.compare_digest(
                entry["current_hash"], self._signature_for(entry)
            ):
                return False
        return True

    def get_trail(self) -> List[Dict[str, Any]]:
        return copy.deepcopy(self.logs)


GLOBAL_AUDIT = AuditTrail()


class AuditLogger:
    @staticmethod
    def log(
        actor: str,
        actor_tier: str,
        event_type: str,
        details: Dict[str, Any],
    ) -> Dict[str, Any]:
        return GLOBAL_AUDIT.log(actor, actor_tier, event_type, details)

    @staticmethod
    def get_trail() -> List[Dict[str, Any]]:
        return GLOBAL_AUDIT.get_trail()

    @staticmethod
    def verify_integrity() -> bool:
        return GLOBAL_AUDIT.verify_integrity()


class ActionExecutor:
    @staticmethod
    def execute_with_audit(
        actor: str,
        actor_tier: str,
        action_type: str,
        fn,
        *args,
        **kwargs,
    ):
        result = fn(*args, **kwargs)
        AuditLogger.log(actor, actor_tier, action_type, {"status": "SUCCESS"})
        return result
