"""Modèles de données de la réconciliation Retail↔Compta."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class RetailLine(BaseModel):
    """Ligne issue du Retail (caisse / ventes / règlements CEGID Retail)."""
    id: str
    date: str                          # ISO (YYYY-MM-DD)
    libelle: str = ""
    montant: float                     # TTC, en euros (signé)
    mode_reglement: Optional[str] = None   # CB, espèces, chèque, virement...
    reference: Optional[str] = None        # n° ticket / Z / bordereau
    magasin: Optional[str] = None


class ComptaLine(BaseModel):
    """Écriture comptable (journal de caisse / banque / ventes)."""
    id: str
    date: str
    libelle: str = ""
    montant: float                     # en euros (signé)
    compte: Optional[str] = None       # n° de compte (ex. 5112, 707...)
    piece: Optional[str] = None        # n° de pièce
    journal: Optional[str] = None


class ReconcileRequest(BaseModel):
    periode: str = Field(..., description="Libellé de la période, ex. '2026-05' ou 'Semaine 21'")
    magasin: Optional[str] = None
    retail_lines: list[RetailLine] = []
    compta_lines: list[ComptaLine] = []
    tolerance_euros: float = 0.01      # écart toléré pour un appariement exact
    tolerance_jours: int = 2           # décalage de date toléré
    note: Optional[str] = None


class MatchPair(BaseModel):
    retail_id: Optional[str] = None
    compta_id: Optional[str] = None
    statut: Literal["apparie", "ecart_montant", "ecart_date", "retail_seul", "compta_seul", "anomalie"]
    ecart_montant: float = 0.0
    ecart_jours: int = 0
    explication: str = ""
    confiance: float = 0.0             # 0..1
    action_recommandee: str = ""


class Proposal(BaseModel):
    proposal_id: str
    periode: str
    magasin: Optional[str] = None
    statut: Literal["pending_validation", "validated", "rejected"] = "pending_validation"
    cree_le: str                       # ISO datetime
    total_retail: float = 0.0
    total_compta: float = 0.0
    ecart_global: float = 0.0
    nb_apparies: int = 0
    nb_ecarts: int = 0
    nb_non_apparies: int = 0
    matches: list[MatchPair] = []
    synthese: str = ""                 # rédigée par le LLM
    sources_rag: list[dict] = []       # citations Hermes
    artefact_uri: Optional[str] = None # s3://artefacts/reconciliations/<id>/proposal.json
    # Rempli à la validation (HITL) :
    validation: Optional["ValidationDecision"] = None


class ValidationDecision(BaseModel):
    decision: Literal["approve", "reject"]
    validateur: str                    # email / identifiant humain
    commentaire: str = ""
    decide_le: Optional[str] = None    # ISO datetime (posé côté serveur)


Proposal.model_rebuild()
