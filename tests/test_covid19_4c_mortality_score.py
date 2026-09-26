"""
Automated Pytest Test Suite for Covid19 4C Mortality Score.
Domain: Clinical & Biomedical AI
Standard: CAP / CLSI / ISO Standards
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from agents.base import PHIGuard, AuditLogger, AuditTrail, SecurityException
from agents.models import SystemTaskPayload, UrgencyLevel, SystemIntegrityStatus
from agents.workers import InvariantQCWorker, SafetyEscalationWorker, ProtocolConformanceWorker
from agents.supervisor import SystemSupervisor
from cli import _parse_bool, main


def test_phi_guard_enforcement():
    with pytest.raises(SecurityException):
        PHIGuard.assert_no_phi("Patient MRN-994827 blood culture positive for Staphylococcus")

    # Clean text passes
    PHIGuard.assert_no_phi("Analytical assay specimen KEY-001 optimal")


def test_specialized_workers():
    # Worker 1: QC Invariant
    p1 = SystemTaskPayload(task_id="T1", target_identifier="KEY-01", primary_metric=35.0)
    alerts1 = InvariantQCWorker.evaluate(p1)
    assert len(alerts1) == 1
    assert alerts1[0].urgency == UrgencyLevel.ELEVATED

    # Worker 2: Safety
    p2 = SystemTaskPayload(task_id="T2", target_identifier="KEY-02", primary_metric=10.0, is_critical_flag=True)
    alerts2 = SafetyEscalationWorker.evaluate(p2)
    assert len(alerts2) == 1
    assert alerts2[0].urgency == UrgencyLevel.CRITICAL_STAT

    # Worker 3: Protocol Conformance
    p3 = SystemTaskPayload(task_id="T3", target_identifier="KEY-03", primary_metric=10.0, status_descriptor="DISCORDANT_ANOMALY")
    alerts3 = ProtocolConformanceWorker.evaluate(p3)
    assert len(alerts3) == 1


def test_supervisor_consensus_and_audit():
    supervisor = SystemSupervisor(model_provider="mock")
    payload = SystemTaskPayload(
        task_id="TASK-PROD-01",
        target_identifier="KEY-PROD-01",
        primary_metric=12.0,
        secondary_metric=4.0,
        status_descriptor="NOMINAL"
    )
    dossier = supervisor.process_task(payload)
    assert dossier.overall_urgency == UrgencyLevel.ROUTINE
    assert dossier.integrity_status == SystemIntegrityStatus.VALIDATED
    assert dossier.audit_hash != ""

    # Verify cryptographic audit trail
    assert AuditLogger.verify_integrity() is True

    # CLI tests
    assert main(["audit", "--task-id", "CLI-TEST-01"]) == 0
    assert main(["chat", "Explain", "specifications"]) == 0
    assert main(["verify-audit"]) == 0


def test_audit_trail_detects_tampering_and_returns_copy():
    trail = AuditTrail("test-secret")
    trail.log("worker", "test", "FIRST", {"value": 1})
    trail.log("worker", "test", "SECOND", {"value": 2})
    assert trail.verify_integrity() is True

    exported = trail.get_trail()
    exported[0]["actor"] = "external-mutation"
    assert trail.verify_integrity() is True

    trail.logs[-1]["actor"] = "tampered"
    assert trail.verify_integrity() is False


def test_score_api_calculates_complete_case():
    client = TestClient(app)
    response = client.post(
        "/api/score",
        json={
            "patient_id": "API-01",
            "age_years": 65,
            "sex": "M",
            "comorbidities_count": 1,
            "respiratory_rate": 24,
            "spo2_percent": 90.0,
            "gcs_score": 15,
            "urea_mmol_l": 8.0,
            "crp_mg_l": 120.0,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total_score"] == 12
    assert body["risk_group"] == "High"


def test_score_api_requires_one_urea_source():
    client = TestClient(app)
    payload = {
        "age_years": 65,
        "sex": "M",
        "comorbidities_count": 1,
        "respiratory_rate": 24,
        "spo2_percent": 90.0,
        "gcs_score": 15,
        "crp_mg_l": 120.0,
    }
    assert client.post("/api/score", json=payload).status_code == 422
    payload["urea_mmol_l"] = 8.0
    payload["bun_mg_dl"] = 20.0
    assert client.post("/api/score", json=payload).status_code == 422


def test_legacy_batch_boolean_parser():
    assert _parse_bool("true") is True
    assert _parse_bool("false") is False
    assert _parse_bool("0") is False
    with pytest.raises(ValueError):
        _parse_bool("maybe")
