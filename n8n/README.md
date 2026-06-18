# Workflow n8n — Revue humaine (HITL) de la réconciliation

`reconciliation-hitl.workflow.json` implémente la porte Human-in-the-Loop :

```
Agent (proposition pending_validation)
   │  POST  N8N_VALIDATION_WEBHOOK
   ▼
[Webhook] ──► [Revue humaine (formulaire)] ──► [Appel agent /validate]
                      (decision/validateur/commentaire)        │
                                                               ▼
                                         agent: statut → validated / rejected
```

## Import (après création du compte propriétaire n8n)
1. Ouvre **https://n8n.nexerp.fr** → crée ton compte propriétaire si pas déjà fait.
2. **Workflows → ⋯ → Import from File** → choisis `reconciliation-hitl.workflow.json`
   (ou *Import from URL* avec le « raw » GitHub du fichier).
3. **Active** le workflow (toggle en haut à droite). Le webhook de production devient :
   `https://n8n.nexerp.fr/webhook/reconciliation-validation`
   (déjà pré-câblé dans l'agent via `N8N_VALIDATION_WEBHOOK`).

## Fonctionnement
- Quand l'agent crée une proposition (`POST /reconcile`), il **notifie** ce webhook.
- L'exécution se met **en attente** sur le nœud *Revue humaine* (formulaire n8n).
- Le réviseur ouvre le **formulaire d'attente** (visible dans n8n → **Executions** →
  l'exécution en attente → lien du formulaire) et choisit `approve`/`reject` + son email + un commentaire.
- À la soumission, n8n appelle `POST http://reconciliation:8000/proposal/<id>/validate`
  → l'agent finalise (`validated` / `rejected`) et écrit l'artefact correspondant dans MinIO.

## Améliorations possibles (1 nœud)
- Insérer un nœud **Email/Slack** entre *Webhook* et *Revue humaine* pour **envoyer le lien
  du formulaire** au réviseur (au lieu de le chercher dans Executions). Le lien est dispo via
  `{{ $execution.resumeUrl }}`.
- Restreindre l'accès au formulaire (n8n → Settings → form auth) si besoin.
