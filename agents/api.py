"""FastAPI service for the ISARIC 4C Mortality Score and legacy audit endpoints."""

from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from covid_4c_score import FourCMortalityEngine, ValidationError
from .base import AuditLogger
from .models import SystemTaskPayload
from .supervisor import SystemSupervisor

supervisor = SystemSupervisor(model_provider="mock")

app = FastAPI(
    title="ISARIC 4C Mortality Score API",
    description=(
        "Calculates the 4C Mortality Score for adults admitted to hospital with COVID-19. "
        "Historical validation-cohort estimates are prognostic support, not standalone "
        "treatment or disposition rules."
    ),
    version="1.1.0",
)


class FourCScoreRequest(BaseModel):
    """Complete input required to calculate the original 4C score."""

    model_config = ConfigDict(allow_inf_nan=False)

    patient_id: str = Field(default="PT-001", max_length=128)
    age_years: int = Field(ge=18, le=150)
    sex: str = Field(min_length=1, max_length=16)
    comorbidities_count: int = Field(ge=0)
    respiratory_rate: int = Field(ge=1, le=100)
    spo2_percent: float = Field(gt=0, le=100)
    gcs_score: int = Field(ge=3, le=15)
    urea_mmol_l: Optional[float] = Field(default=None, ge=0)
    bun_mg_dl: Optional[float] = Field(default=None, ge=0)
    crp_mg_l: float = Field(ge=0)

    @model_validator(mode="after")
    def validate_urea_source(self):
        if (self.urea_mmol_l is None) == (self.bun_mg_dl is None):
            raise ValueError("Provide exactly one of urea_mmol_l or bun_mg_dl")
        return self


class ChatRequest(BaseModel):
    query: str


@app.get("/health")
def health():
    return {
        "status": "HEALTHY",
        "service": "covid19-4c-mortality-score",
        "version": app.version,
    }


@app.get("/metrics")
def metrics():
    """Return lightweight process counters as JSON."""
    return {
        "dossiers_processed_total": len(supervisor.dossier_registry),
        "audit_blocks_total": len(AuditLogger.get_trail()),
    }


@app.post("/api/score")
def api_score(payload: FourCScoreRequest):
    """Calculate the ISARIC 4C Mortality Score."""
    try:
        result = FourCMortalityEngine.evaluate(**payload.model_dump())
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return result.to_dict()


# The endpoints below are retained for compatibility with earlier releases.
@app.post("/api/audit")
def api_audit(payload: SystemTaskPayload):
    dossier = supervisor.process_task(payload)
    return dossier.to_dict()


@app.post("/api/chat")
def api_chat(req: ChatRequest):
    try:
        answer = supervisor.query_supervisory_chat(req.query)
        return {"response": answer}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/audit/logs")
def api_audit_logs():
    return {"audit_trail": AuditLogger.get_trail(), "verified": AuditLogger.verify_integrity()}
