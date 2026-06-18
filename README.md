# Agent Réconciliation Retail↔Compta (NEXERP IA Factory)

Agent qui rapproche les flux **Retail** (caisse / ventes / règlements CEGID Retail) des
**écritures comptables** (journaux caisse/banque/ventes), avec **porte de validation
Human-in-the-Loop** : aucune réconciliation n'est finalisée sans décision humaine.

## Branchements (réseau interne `recette`)
- **RAG** : Hermes — règles de rapprochement CEGID via `HERMES_URL` (hostname stable `http://hermes:8000`).
- **LLM** : Claude (`claude-opus-4-8`) en sortie structurée (tool use).
- **Stockage** : MinIO bucket **`artefacts`**, préfixe `reconciliations/` — source de vérité des propositions.
- **Observabilité** : Langfuse (coût/latence/usage par run).
- **Orchestration / HITL** : n8n — webhook notifié à chaque proposition en attente (`N8N_VALIDATION_WEBHOOK`).

## Endpoints
| Méthode | Route | Rôle |
|---|---|---|
| GET | `/health`, `/ready` | liveness / readiness (DB objet, RAG, Langfuse) |
| POST | `/reconcile` | lance une réconciliation → **proposition** `pending_validation` |
| GET | `/proposals` | liste des propositions |
| GET | `/proposal/{id}` | détail d'une proposition |
| POST | `/proposal/{id}/validate` | **PORTE HITL** — décision humaine `approve`/`reject` |

### Cycle de vie (porte HITL)
```
POST /reconcile ──> Proposal(statut = pending_validation)   ← RAG + Claude + artefact + trace + notif n8n
                          │
                          ▼   (décision humaine OBLIGATOIRE)
POST /proposal/{id}/validate {decision: approve|reject, validateur, commentaire}
                          │
            approve ──> validated (+ artefact validated.json)
            reject  ──> rejected
```
Tant que `hitl_required=true`, **rien n'est finalisé** sans cet appel explicite.

## Exemple
```bash
curl -X POST http://hermes-... /reconcile -H 'Content-Type: application/json' -d '{
  "periode": "2026-05",
  "magasin": "Paris-Champs",
  "retail_lines": [{"id":"R1","date":"2026-05-02","montant":1250.00,"mode_reglement":"CB","reference":"Z0502"}],
  "compta_lines": [{"id":"C1","date":"2026-05-02","montant":1250.00,"compte":"5112","piece":"BQ0502"}]
}'
```

## Configuration (variables d'environnement / secrets montés)
`HERMES_URL`, `ANTHROPIC_API_KEY`, `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`,
`S3_BUCKET=artefacts`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`,
`N8N_VALIDATION_WEBHOOK`, `HITL_REQUIRED=true`.

Les secrets sont chargés au démarrage depuis `/app/secrets/agent.env` (monté par Coolify,
jamais dans l'image ni dans Git).
