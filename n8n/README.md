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

Le workflow envoie le lien de revue par **email (Brevo)** puis attend la décision humaine.

## Import (après création du compte propriétaire n8n)
1. Ouvre **https://n8n.nexerp.fr** → crée ton compte propriétaire si pas déjà fait.
2. **Crée la credential Brevo** : *Credentials → New → Header Auth* →
   **Name** `Brevo api-key`, **Header Name** `api-key`, **Value** = ta clé Brevo `xkeysib-…`
   (la même que le site nexerp.fr ; ne la colle jamais en chat).
3. **Workflows → ⋯ → Import from File** → `reconciliation-hitl.workflow.json`
   (ou *Import from URL* avec le « raw » GitHub).
4. Sur le nœud **Email Brevo (lien de revue)**, sélectionne la credential `Brevo api-key`
   créée à l'étape 2. Ajuste si besoin l'expéditeur (`contact@nexerp.fr`, domaine authentifié Brevo)
   et le destinataire (`richard@geovtc.com`).
5. **Active** le workflow (toggle). Le webhook de production devient :
   `https://n8n.nexerp.fr/webhook/reconciliation-validation`
   (déjà pré-câblé dans l'agent via `N8N_VALIDATION_WEBHOOK`).

## Fonctionnement
- Quand l'agent crée une proposition (`POST /reconcile`), il **notifie** ce webhook.
- Le nœud **Email Brevo** envoie au réviseur un mail contenant la synthèse + le **lien direct
  du formulaire de revue** (`{{ $execution.resumeFormUrl }}`).
- L'exécution se met **en attente** sur le nœud *Revue humaine* (formulaire n8n).
- Le réviseur clique le lien, choisit `approve`/`reject` + son email + un commentaire.
  (À défaut de mail, le formulaire reste accessible via n8n → **Executions** → exécution en attente.)
- À la soumission, n8n appelle `POST http://reconciliation:8000/proposal/<id>/validate`
  → l'agent finalise (`validated` / `rejected`) et écrit l'artefact correspondant dans MinIO.

## Améliorations possibles
- Remplacer le mail par un **Slack/Teams** « Send & Wait » si tu préfères ce canal.
- Restreindre l'accès au formulaire (n8n → Settings → form auth) si besoin.
