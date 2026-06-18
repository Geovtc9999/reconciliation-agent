"""Agent Réconciliation Retail↔Compta — API FastAPI.

Flux : POST /reconcile → proposition (RAG Hermes + Claude + artefact MinIO + trace
Langfuse), statut `pending_validation`. PORTE HITL : rien n'est finalisé tant que
POST /proposal/{id}/validate (décision humaine) n'a pas été appelé.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from . import obs, reconcile, storage
from .config import settings
from .models import ReconcileRequest, ValidationDecision

logging.basicConfig(level=settings.log_level)
log = logging.getLogger("reconciliation-agent")

app = FastAPI(title=settings.app_name, version=settings.app_version)


@app.get("/health")
def health():
    return {"status": "ok", "service": settings.app_name, "version": settings.app_version}


@app.get("/ready")
def ready():
    checks = {
        "llm_configured": settings.llm_configured,
        "s3_configured": settings.s3_configured,
        "rag": {"url": settings.hermes_url},
        "langfuse": obs.healthcheck(),
        "hitl_required": settings.hitl_required,
        "n8n_webhook": bool(settings.n8n_validation_webhook),
    }
    try:
        if settings.s3_configured:
            checks["bucket"] = settings.s3_bucket
            checks["bucket_ok"] = storage.bucket_ok()
    except Exception as e:
        checks["bucket_ok"] = False
        checks["s3_error"] = str(e)[:200]
    try:
        from .rag import query_hermes
        r = query_hermes("ping", top_k=1)
        checks["rag"]["reachable"] = "error" not in r
    except Exception as e:
        checks["rag"]["reachable"] = False
        checks["rag"]["error"] = str(e)[:160]
    return checks


@app.post("/reconcile")
def post_reconcile(req: ReconcileRequest):
    if not req.retail_lines and not req.compta_lines:
        raise HTTPException(400, "Fournir au moins des lignes retail ou compta.")
    proposal = reconcile.run_reconciliation(req)
    return proposal.model_dump()


@app.get("/proposals")
def get_proposals():
    if not settings.s3_configured:
        raise HTTPException(503, "Stockage objet non configuré")
    return {"proposals": storage.list_proposals()}


@app.get("/proposal/{pid}")
def get_one(pid: str):
    p = reconcile.get_proposal(pid)
    if p is None:
        raise HTTPException(404, "Proposition introuvable")
    return p.model_dump()


@app.post("/proposal/{pid}/validate")
def validate(pid: str, decision: ValidationDecision):
    """PORTE HUMAN-IN-THE-LOOP : décision humaine obligatoire pour finaliser."""
    try:
        p = reconcile.validate_proposal(pid, decision)
    except KeyError:
        raise HTTPException(404, "Proposition introuvable")
    except ValueError as e:
        raise HTTPException(409, str(e))
    return p.model_dump()


@app.on_event("startup")
def _startup():
    log.info("%s %s — démarrage (HITL=%s, RAG=%s)",
             settings.app_name, settings.app_version,
             settings.hitl_required, settings.hermes_url)
