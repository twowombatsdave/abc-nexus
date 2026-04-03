# Touchpoints / Core Interactions (Close.io–style timeline)

This document describes the **next** product slice: a coherent log of touch points across **Google Calendar**, **Gmail** (multiple mailboxes), and **Slack**, grouped by **brand** (e.g. ZYN), with AI-generated summaries and durable storage.

## Goals

1. **Ingest** events from Calendar (meetings/calls), Gmail (threads), Slack (messages that read like notes).
2. **Normalize** into a single `TouchpointEvent` model (kind, time, brand, summary, source ref).
3. **Enrich** with an LLM (classify brand if missing, summarize email body, map Slack thread to “Call” notes).
4. **Persist** to a database and serve a Streamlit (or web) UI: brand → expandable “Core Interactions”.

## Architecture (recommended)

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Connectors │────▶│  Normalizer  │────▶│  LLM worker │
│ Cal/Gmail/  │     │  + idempotency│     │  summarize  │
│ Slack       │     └──────┬───────┘     └──────┬──────┘
└─────────────┘            │                    │
                           ▼                    ▼
                    ┌──────────────┐     ┌─────────────┐
                    │  Postgres    │◀────│  Embeddings │
                    │  (or BQ)     │     │  (optional) │
                    └──────────────┘     └─────────────┘
```

- **Connectors**: read-only polling or webhooks (Slack Events API preferred over polling for scale).
- **Idempotency**: stable external IDs `(source, external_id)` unique constraint.
- **Secrets**: never commit; GitHub Actions uses **OIDC** to cloud where possible; otherwise **repository secrets**.

## Google Workspace (Calendar + Gmail, admin / multi-mailbox)

Two supported patterns:

### A) OAuth 2.0 (user consent) — simplest for 3 mailboxes

- One **Google Cloud** project, **OAuth client** (Desktop or Web).
- Scopes (readonly to start):  
  `https://www.googleapis.com/auth/gmail.readonly`  
  `https://www.googleapis.com/auth/calendar.readonly`
- Run a **one-time** local script per mailbox to obtain **refresh tokens** for:
  - `dave@twowombats.com`
  - `cormac@twowombats.com`
  - `wholesale@twowombats.com`
- Store **refresh tokens** as secrets (one per mailbox); store **client id/secret** once.

**Cons**: three refresh tokens to rotate; consent screen must be published or test users added.

### B) Domain-wide delegation (service account impersonation)

- Service account in GCP with **Workspace admin** enabling DWD for Gmail/Calendar APIs.
- Impersonate each user via `subject=` — **one** JSON key, **no** per-user refresh tokens.
- **Cons**: admin setup in Google Admin Console; tight IAM.

**Recommendation**: start with **A** for speed unless you already use DWD elsewhere.

## Slack

- **Bot token** with scopes (adjust to your retention needs):  
  `channels:history`, `groups:history`, `mpim:history`, `im:history`, `users:read`, `chat:write` (if posting back), `reactions:read` (optional).
- Prefer **Events API** (`events` + `event_subscriptions`) to push messages to your app vs polling all channels.
- Map Slack channels (or keywords) to **brands** via config table or env.

The repo already references `SLACK_BOT_TOKEN` / `SLACK_CHANNEL_ID` in workflows — you may reuse or create a dedicated **Touchpoints** Slack app.

## AI / LLM

- **Summarization + classification**: OpenAI, Anthropic, or Vertex (if already on GCP).
- Store **model name + prompt version** on each row for audit.

## Database

- **Postgres** (RDS, Cloud SQL, Neon, Supabase) is a good default for relational timeline + JSONB raw payload.
- Alternative: **BigQuery** if analytics-first and batch loads are OK (less ideal for interactive UI latency).

## GitHub secrets (suggested names)

| Secret | Purpose |
|--------|---------|
| `GOOGLE_OAUTH_CLIENT_ID` | OAuth client ID (if using refresh-token flow) |
| `GOOGLE_OAUTH_CLIENT_SECRET` | OAuth client secret |
| `GMAIL_REFRESH_TOKEN_DAVE` | Refresh token for dave@twowombats.com |
| `GMAIL_REFRESH_TOKEN_CORMAC` | Refresh token for cormac@twowombats.com |
| `GMAIL_REFRESH_TOKEN_WHOLESALE` | Refresh token for wholesale@twowombats.com |
| **or** `GOOGLE_SERVICE_ACCOUNT_JSON` | SA JSON (if using domain-wide delegation) |
| **or** `GOOGLE_WORKSPACE_IMPERSONATION_*` | Only if using DWD — document subjects per env |
| `SLACK_BOT_TOKEN` | Already used elsewhere; ensure scopes for history |
| `SLACK_SIGNING_SECRET` | Verify Slack Events requests |
| `SLACK_APP_TOKEN` | Only if using Socket Mode |
| `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` | LLM summarization |
| `DATABASE_URL` | Postgres connection string (touchpoints schema) |

**Optional**: `TOUCHPOINTS_ENCRYPTION_KEY` if you encrypt raw payloads at rest.

## Local development

1. Copy `dotenv.template` → `.env` and fill OAuth/Slack/DB placeholders.
2. Run OAuth token helper (to be added) once per mailbox.
3. Run migrations (to be added) then `streamlit run ...` for the touchpoints UI.

## Phased delivery

| Phase | Deliverable |
|-------|-------------|
| **1** | Models + env contract + DB schema (this repo) |
| **2** | Gmail connector (one mailbox) + idempotent insert |
| **3** | Calendar + remaining mailboxes |
| **4** | Slack ingestion (channel allowlist) |
| **5** | LLM pipeline + brand routing |
| **6** | Streamlit “Close.io–style” UI per brand |

## Security & compliance

- Minimize scopes (readonly until you need send).
- PII in Postgres: encrypt at rest (DB + disk), restrict IAM, retention policy.
- Never log full email bodies or tokens — structured logs with `external_id` only.

## Related code in this repo

- `integrations/touchpoints/` — shared models and env keys (scaffolding).
- Existing Google patterns: `dbt/sheet_to_bigquery.py`, `sheet_seed.yml` (service account).
- Slack notification pattern: `.github/workflows/sheet_seed.yml`.
