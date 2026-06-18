"""Cœur de la réconciliation : pré-appariement déterministe → RAG → LLM →
proposition persistée (MinIO) → notification n8n. Porte HITL à la validation."""
from __future__ import annotations

import datetime
import hashlib

import httpx

from . import obs, rag, storage
from .config import settings
from .models import Proposal, ReconcileRequest, ValidationDecision


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _pid(req: ReconcileRequest) -> str:
    seed = f"{req.periode}|{req.magasin}|{_now()}|{len(req.retail_lines)}|{len(req.compta_lines)}"
    return "rec-" + hashlib.sha1(seed.encode()).hexdigest()[:12]


def _days_between(a: str, b: str) -> int:
    try:
        da = datetime.date.fromisoformat(a[:10])
        db = datetime.date.fromisoformat(b[:10])
        return abs((da - db).days)
    except Exception:
        return 999


def _candidate_matches(req: ReconcileRequest) -> list[dict]:
    """Appariement déterministe : par montant (±tol) et date proche. Greedy."""
    cands, used_c = [], set()
    for r in req.retail_lines:
        best = None
        for c in req.compta_lines:
            if c.id in used_c:
                continue
            dm = round(abs(r.montant - c.montant), 2)
            dj = _days_between(r.date, c.date)
            if dm <= req.tolerance_euros and dj <= req.tolerance_jours:
                score = (dm, dj)
                if best is None or score < best[0]:
                    best = (score, c, dm, dj)
        if best:
            _, c, dm, dj = best
            used_c.add(c.id)
            cands.append({"retail_id": r.id, "compta_id": c.id,
                          "ecart_montant": dm, "ecart_jours": dj,
                          "statut": "apparie" if (dm == 0 and dj == 0) else "ecart_date" if dm == 0 else "ecart_montant"})
    matched_r = {x["retail_id"] for x in cands}
    for r in req.retail_lines:
        if r.id not in matched_r:
            cands.append({"retail_id": r.id, "compta_id": None, "statut": "retail_seul"})
    for c in req.compta_lines:
        if c.id not in used_c:
            cands.append({"retail_id": None, "compta_id": c.id, "statut": "compta_seul"})
    return cands


def _notify_n8n(proposal: Proposal, trace) -> None:
    """Notifie n8n qu'une proposition attend une validation humaine (porte HITL)."""
    if not settings.n8n_validation_webhook:
        return
    payload = {
        "event": "reconciliation.pending_validation",
        "proposal_id": proposal.proposal_id,
        "periode": proposal.periode,
        "magasin": proposal.magasin,
        "ecart_global": proposal.ecart_global,
        "nb_ecarts": proposal.nb_ecarts,
        "nb_non_apparies": proposal.nb_non_apparies,
        "synthese": proposal.synthese,
        "artefact_uri": proposal.artefact_uri,
        "validate_url": f"/proposal/{proposal.proposal_id}/validate",
    }
    try:
        httpx.post(settings.n8n_validation_webhook, json=payload, timeout=15.0)
        obs.log_event(trace, name="n8n.notified", metadata={"proposal_id": proposal.proposal_id})
    except Exception as e:
        obs.log_event(trace, name="n8n.notify_failed", metadata={"error": str(e)[:160]})


def run_reconciliation(req: ReconcileRequest) -> Proposal:
    """Produit une proposition en statut pending_validation (jamais finalisée)."""
    pid = _pid(req)
    with obs.observe(name="reconciliation.run",
                     input={"periode": req.periode, "magasin": req.magasin,
                            "n_retail": len(req.retail_lines), "n_compta": len(req.compta_lines)},
                     metadata={"proposal_id": pid, "hitl_required": settings.hitl_required}) as trace:
        candidates = _candidate_matches(req)
        rag_ctx = rag.regles_reassort_rapprochement(req.periode, req.magasin)

        matches, synthese, sources = candidates, "", []
        if settings.llm_configured:
            from .llm import reconcile_llm
            try:
                res = reconcile_llm(req, candidates, rag_ctx, trace)
                matches = res.get("matches", candidates)
                synthese = res.get("synthese", "")
                sources = res.get("rag_citations", [])
            except Exception as e:
                synthese = f"(LLM indisponible : {str(e)[:160]} — appariements déterministes seuls)"
        else:
            synthese = "Réponse LLM désactivée (ANTHROPIC_API_KEY absente) — appariements déterministes seuls."
            sources = (rag_ctx or {}).get("citations", [])

        total_r = round(sum(l.montant for l in req.retail_lines), 2)
        total_c = round(sum(l.montant for l in req.compta_lines), 2)
        nb_app = sum(1 for m in matches if m.get("statut") == "apparie")
        nb_ec = sum(1 for m in matches if m.get("statut") in ("ecart_montant", "ecart_date", "anomalie"))
        nb_non = sum(1 for m in matches if m.get("statut") in ("retail_seul", "compta_seul"))

        proposal = Proposal(
            proposal_id=pid, periode=req.periode, magasin=req.magasin,
            statut="pending_validation", cree_le=_now(),
            total_retail=total_r, total_compta=total_c,
            ecart_global=round(total_r - total_c, 2),
            nb_apparies=nb_app, nb_ecarts=nb_ec, nb_non_apparies=nb_non,
            matches=matches, synthese=synthese, sources_rag=sources,
        )

        # Artefact = source de vérité (bucket artefacts)
        if settings.s3_configured:
            uri = storage.put_json(f"{pid}/proposal.json", proposal.model_dump())
            proposal.artefact_uri = uri
            storage.put_json(f"{pid}/proposal.json", proposal.model_dump())

        obs.log_event(trace, name="proposal.created",
                      metadata={"proposal_id": pid, "ecart_global": proposal.ecart_global,
                                "statut": proposal.statut})
        _notify_n8n(proposal, trace)
        return proposal


def get_proposal(pid: str) -> Proposal | None:
    data = storage.get_json(f"{pid}/proposal.json")
    return Proposal(**data) if data else None


def validate_proposal(pid: str, decision: ValidationDecision) -> Proposal:
    """Porte Human-in-the-Loop : applique la décision humaine. SEUL moyen de
    finaliser. approve → validated (+ artefact final) ; reject → rejected."""
    proposal = get_proposal(pid)
    if proposal is None:
        raise KeyError(pid)
    if proposal.statut != "pending_validation":
        raise ValueError(f"Proposition déjà traitée (statut={proposal.statut})")

    decision.decide_le = _now()
    proposal.validation = decision
    proposal.statut = "validated" if decision.decision == "approve" else "rejected"

    with obs.observe(name="reconciliation.validate",
                     input={"proposal_id": pid, "decision": decision.decision,
                            "validateur": decision.validateur},
                     metadata={"proposal_id": pid}) as trace:
        if settings.s3_configured:
            storage.put_json(f"{pid}/proposal.json", proposal.model_dump())
            storage.put_json(f"{pid}/validation.json", decision.model_dump())
            if proposal.statut == "validated":
                storage.put_json(f"{pid}/validated.json", proposal.model_dump())
        obs.log_event(trace, name=f"proposal.{proposal.statut}",
                      metadata={"validateur": decision.validateur})
    return proposal
