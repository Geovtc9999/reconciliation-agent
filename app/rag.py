"""Accès au RAG Hermes (règles de rapprochement CEGID) via son hostname interne stable."""
from __future__ import annotations

import httpx

from .config import settings


def hermes_health() -> bool:
    """Sonde légère de disponibilité du RAG (Hermes /health) — sans coût LLM.
    À utiliser pour /ready (vs query_hermes qui déclenche une vraie requête RAG)."""
    if not settings.rag_configured:
        return False
    try:
        r = httpx.get(f"{settings.hermes_url}/health", timeout=5.0)
        return r.status_code == 200
    except Exception:
        return False


def query_hermes(question: str, *, top_k: int | None = None) -> dict:
    """Interroge Hermes /query. Renvoie {answer, citations, ...} ou {} si indisponible."""
    if not settings.rag_configured:
        return {}
    payload = {"question": question, "top_k": top_k or settings.rag_top_k}
    try:
        r = httpx.post(f"{settings.hermes_url}/query", json=payload,
                       timeout=settings.hermes_timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:  # dégradé : la réconciliation continue sans contexte CEGID
        return {"error": str(e)[:200]}


def regles_reassort_rapprochement(periode: str, magasin: str | None) -> dict:
    """Récupère les règles métier de rapprochement caisse/compta pertinentes."""
    mag = f" pour le magasin {magasin}" if magasin else ""
    q = ("Quelles sont les règles de rapprochement / réconciliation entre les "
         "ventes et règlements Retail (caisse, Z de caisse, modes de règlement) et "
         f"les écritures comptables (journaux de caisse/banque, comptes 5112/531/707, TVA){mag} "
         "dans CEGID ? Détaille le traitement des écarts de règlement et des décalages de date.")
    return query_hermes(q)
