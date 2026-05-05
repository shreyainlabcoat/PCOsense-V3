"""
FastAPI application — exposes the multi-agent PCOS assessment pipeline.
"""

from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware

# Project root on path for `src.*` imports
_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

load_dotenv(_ROOT + "/.env")

from src.api.schemas import PatientAssessmentRequest, patient_dict_from_request
from src.database import SupabaseClient
from src.quality_control import QualityController
if TYPE_CHECKING:
    from src.agents import PCOSOrchestrator

log = logging.getLogger(__name__)

_orchestrator: PCOSOrchestrator | None = None
_qc: QualityController | None = None
_startup_error: str | None = None


def get_orchestrator() -> PCOSOrchestrator:
    """Return singleton orchestrator; safe to call after startup."""
    if _orchestrator is None:
        raise RuntimeError("Orchestrator not initialized — call during startup")
    return _orchestrator


def get_qc() -> QualityController:
    """Return singleton QC controller; safe to call after startup."""
    if _qc is None:
        raise RuntimeError("QualityController not initialized — call during startup")
    return _qc


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _orchestrator, _qc, _startup_error
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    # Initialize heavy resources once at startup, not on first request
    try:
        from src.agents import PCOSOrchestrator

        db = SupabaseClient()
        _orchestrator = PCOSOrchestrator(db=db if db.is_configured() else None)
        _qc = QualityController()
        _startup_error = None
        log.info("PCOSense pipeline initialized")
    except Exception as exc:
        _orchestrator = None
        _qc = QualityController()
        _startup_error = str(exc)
        log.exception("PCOSense pipeline failed to initialize")
    yield
    _orchestrator = None
    _qc = None
    _startup_error = None


def _cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "").strip()
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    # Default to localhost only; set CORS_ORIGINS env var for production
    return ["http://127.0.0.1:3838", "http://localhost:3838"]


app = FastAPI(
    title="PCOSense API",
    description="REST API for the PCOSense multi-agent screening pipeline.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health")
def health() -> dict:
    status = "ok" if _startup_error is None else "degraded"
    return {"status": status, "service": "pcosense-api", "startup_error": _startup_error}


@app.get("/api/v1/readiness")
def readiness() -> dict:
    """Operational readiness checks for deployments and demos."""
    checks: dict[str, bool] = {
        "startup_ok": _startup_error is None,
        "orchestrator_initialized": _orchestrator is not None,
    }
    llm_available = False
    if _orchestrator is not None:
        try:
            llm_available = _orchestrator.ollama.is_available()
        except Exception:
            llm_available = False
    checks["llm_available"] = llm_available
    checks["model_file_present"] = (Path(_ROOT) / "models" / "pcos_model.json").exists()
    checks["metadata_file_present"] = (Path(_ROOT) / "models" / "model_metadata.json").exists()

    failed = [name for name, ok in checks.items() if not ok]
    status = "ready" if not failed else "degraded"
    return {"status": status, "checks": checks, "failed_checks": failed}


@app.post("/api/v1/assess")
def assess_patient(body: PatientAssessmentRequest) -> dict:
    """
    Run Data Validator → Evidence Retriever → Risk Assessor.

    Returns ``validation``, ``evidence``, ``assessment``, ``quality_control``, and ``metadata``.
    If Supabase is configured, results are persisted automatically.
    """
    patient = patient_dict_from_request(body)
    if not patient:
        raise HTTPException(
            status_code=400,
            detail="No patient fields provided. Send at least one clinical feature.",
        )

    try:
        if _startup_error:
            raise RuntimeError(_startup_error)
        result = get_orchestrator().run(patient)
        
        # Generate quality control metrics
        qc_metrics = get_qc().create_metrics_report(
            patient_data=patient,
            prediction_result=result.get("assessment", {}),
            rag_results=result.get("evidence", {}),
        )
        
        result["quality_control"] = qc_metrics.to_dict()
        
    except FileNotFoundError as exc:
        log.exception("Model or artifact missing")
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        log.exception("Pipeline failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return jsonable_encoder(result)


@app.get("/api/v1/feature-info")
def feature_info() -> dict:
    """Expose model feature metadata for clients (optional)."""
    from src.ml_model import PCOSPredictor

    try:
        return PCOSPredictor.get_instance().feature_info()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/v1/quality-summary")
def quality_summary() -> dict:
    """
    Get system-wide quality control performance metrics.
    
    Shows aggregate statistics about assessment quality across all predictions,
    useful for stakeholder dashboards and compliance reporting.
    """
    return get_qc().get_performance_summary()


# ── Mount Shiny frontend so everything runs as a single service ──────────
try:
    from src.app.app import app as shiny_app  # noqa: E402
except Exception as exc:  # pragma: no cover - depends on optional UI deps
    log.warning("Shiny app failed to import: %s", exc)
else:
    app.mount("/", shiny_app)
