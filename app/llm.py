"""Raisonnement de réconciliation assisté par Claude (sortie structurée)."""
from __future__ import annotations

import datetime
import json

from .config import settings
from .obs import log_generation

SYSTEM = (
    "Tu es l'agent de réconciliation Retail↔Compta de NEXERP, expert CEGID. "
    "On te fournit des lignes RETAIL (caisse/ventes/règlements), des lignes COMPTA "
    "(écritures), des appariements candidats déterministes, et un CONTEXTE de règles "
    "CEGID issu du RAG. Ton rôle : produire une réconciliation fiable et auditable. "
    "Pour chaque rapprochement, indique le statut (apparie, ecart_montant, ecart_date, "
    "retail_seul, compta_seul, anomalie), l'écart, une explication courte citant la "
    "règle CEGID quand pertinent, un niveau de confiance (0..1) et une action "
    "recommandée. N'invente aucune donnée. Tu NE finalises RIEN : ta sortie est une "
    "PROPOSITION soumise à validation humaine."
)

# Outil de sortie structurée imposé au modèle.
TOOL = {
    "name": "proposer_reconciliation",
    "description": "Renvoie la proposition de réconciliation structurée.",
    "input_schema": {
        "type": "object",
        "properties": {
            "matches": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "retail_id": {"type": ["string", "null"]},
                        "compta_id": {"type": ["string", "null"]},
                        "statut": {"type": "string", "enum": [
                            "apparie", "ecart_montant", "ecart_date",
                            "retail_seul", "compta_seul", "anomalie"]},
                        "ecart_montant": {"type": "number"},
                        "ecart_jours": {"type": "integer"},
                        "explication": {"type": "string"},
                        "confiance": {"type": "number"},
                        "action_recommandee": {"type": "string"},
                    },
                    "required": ["statut", "explication", "confiance", "action_recommandee"],
                },
            },
            "synthese": {"type": "string", "description":
                         "Synthèse en français : écart global, points d'attention, "
                         "anomalies, et ce qui requiert l'arbitrage humain."},
        },
        "required": ["matches", "synthese"],
    },
}


def reconcile_llm(req, candidates: list[dict], rag: dict, trace) -> dict:
    """Appelle Claude et renvoie {matches, synthese, usage}. Lève si clé absente."""
    import anthropic
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    rag_answer = (rag or {}).get("answer") or "(contexte CEGID indisponible)"
    rag_citations = (rag or {}).get("citations", [])

    user = (
        f"PÉRIODE: {req.periode}  MAGASIN: {req.magasin or '-'}\n"
        f"TOLÉRANCES: montant ±{req.tolerance_euros}€, date ±{req.tolerance_jours} j\n\n"
        f"=== RÈGLES CEGID (RAG Hermes) ===\n{rag_answer}\n\n"
        f"=== LIGNES RETAIL ({len(req.retail_lines)}) ===\n"
        f"{json.dumps([l.model_dump() for l in req.retail_lines], ensure_ascii=False)}\n\n"
        f"=== LIGNES COMPTA ({len(req.compta_lines)}) ===\n"
        f"{json.dumps([l.model_dump() for l in req.compta_lines], ensure_ascii=False)}\n\n"
        f"=== APPARIEMENTS CANDIDATS (déterministes) ===\n"
        f"{json.dumps(candidates, ensure_ascii=False)}\n\n"
        "Analyse, corrige/complète les appariements, identifie écarts et anomalies, "
        "puis appelle l'outil proposer_reconciliation."
    )

    t0 = datetime.datetime.now(datetime.timezone.utc)
    resp = client.messages.create(
        model=settings.answer_model,
        max_tokens=settings.max_tokens,
        system=SYSTEM,
        tools=[TOOL],
        tool_choice={"type": "tool", "name": "proposer_reconciliation"},
        messages=[{"role": "user", "content": user}],
    )
    t1 = datetime.datetime.now(datetime.timezone.utc)

    out = {"matches": [], "synthese": ""}
    for block in resp.content:
        if getattr(block, "type", "") == "tool_use" and block.name == "proposer_reconciliation":
            out = block.input
            break

    usage = {"input": resp.usage.input_tokens, "output": resp.usage.output_tokens}
    log_generation(trace, name="reconciliation.llm", model=settings.answer_model,
                   input=user, output=json.dumps(out, ensure_ascii=False),
                   usage=usage, start_time=t0, end_time=t1)
    out["usage"] = usage
    out["rag_citations"] = rag_citations
    return out
