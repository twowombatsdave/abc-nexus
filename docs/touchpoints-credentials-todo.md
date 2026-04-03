# Touchpoints — credentials todo checklist

Use this when wiring **Gmail**, **Calendar**, **Slack**, **Gemini** summaries, and **storage** (BigQuery and/or Postgres). Check items as you complete them. **Do not commit real values** — use `.env` locally and **GitHub Actions → Secrets** for CI.

---

## Google Cloud (shared)

- [ ] **GCP project** chosen (same project as BigQuery if you want one bill/IAM story).
- [ ] **APIs enabled**: Gmail API, Google Calendar API (and later Vertex AI if not using AI Studio key).
- [ ] **OAuth consent screen** configured (External or Internal); test users added if app is in Testing.
- [ ] **OAuth 2.0 Client** created (Desktop or Web). Note **Client ID** + **Client secret**.

**GitHub secrets (OAuth path, three mailboxes)**

- [ ] `GOOGLE_OAUTH_CLIENT_ID`
- [ ] `GOOGLE_OAUTH_CLIENT_SECRET`
- [ ] `GMAIL_REFRESH_TOKEN_DAVE` — after authorizing `dave@twowombats.com` (one-time script).
- [ ] `GMAIL_REFRESH_TOKEN_CORMAC` — `cormac@twowombats.com`
- [ ] `GMAIL_REFRESH_TOKEN_WHOLESALE` — `wholesale@twowombats.com`

**Alternative: domain-wide delegation (optional)**

- [ ] Service account + Admin Console DWD for Gmail/Calendar scopes.
- [ ] `GOOGLE_SERVICE_ACCOUNT_JSON` (full JSON as a **single** secret, or file path in CI only).
- [ ] Document impersonation subjects (same three emails) in runbook — not always separate secrets.

---

## BigQuery (you already use this)

- [ ] **Dataset** for touchpoints (e.g. `touchpoints` or inside existing reporting dataset).
- [ ] **Table** design agreed (partition on `occurred_at`, cluster on `brand_slug` + `source`).
- [ ] **Service account** (or user) has `bigquery.dataEditor` + `jobUser` on that dataset.
- [ ] **GitHub / runtime**: same pattern as existing jobs — e.g. `GOOGLE_APPLICATION_CREDENTIALS` or `GOOGLE_SERVICE_ACCOUNT` secret (match what `dbt` / `sheet_seed` already use).

---

## Slack

- [ ] **Slack app** created (or existing app reused) with **Bot User**.
- [ ] **OAuth scopes** for read history: `channels:history`, `groups:history`, `mpim:history`, `im:history`, `users:read` (add `chat:write` only if you post back).
- [ ] **Events API** (recommended): set **Request URL** when app is deployed; subscribe to `message.channels` (etc.).
- [ ] `SLACK_BOT_TOKEN` — **xoxb-…**
- [ ] `SLACK_SIGNING_SECRET` — verify HTTP callbacks from Slack.
- [ ] (Optional) `SLACK_APP_TOKEN` — only if you use **Socket Mode** instead of public HTTPS.

---

## Gemini (summaries & classification)

**Option A — Google AI Studio (simplest)**

- [ ] Create an API key in [Google AI Studio](https://aistudio.google.com/apikey).
- [ ] `GEMINI_API_KEY` (or `GOOGLE_API_KEY` — pick one name and stick to it in code).

**Option B — Vertex AI Gemini (same GCP as BigQuery)**

- [ ] Vertex AI API enabled; **Gemini** model access in your region.
- [ ] Runtime uses **Application Default Credentials** (`GOOGLE_APPLICATION_CREDENTIALS` or workload identity).
- [ ] `GOOGLE_CLOUD_PROJECT` and `GEMINI_VERTEX_LOCATION` (e.g. `us-central1`) — names TBD when we add code.

---

## Database (if you use Postgres for hot path)

- [ ] Instance / connection string ready.
- [ ] `DATABASE_URL` in secrets (use a **password** secret separate from URL if your org prefers).

---

## Optional / hygiene

- [ ] `TOUCHPOINTS_ENCRYPTION_KEY` — only if encrypting raw payloads at rest.
- [ ] Rotate **refresh tokens** if a mailbox is compromised.
- [ ] **Least privilege**: separate Slack app for “prod touchpoints” vs “CI notifications” if needed.

---

## Quick copy — suggested GitHub secret names

| Secret | Required for |
|--------|----------------|
| `GOOGLE_OAUTH_CLIENT_ID` | Gmail + Calendar (OAuth) |
| `GOOGLE_OAUTH_CLIENT_SECRET` | Gmail + Calendar (OAuth) |
| `GMAIL_REFRESH_TOKEN_DAVE` | Dave mailbox |
| `GMAIL_REFRESH_TOKEN_CORMAC` | Cormac mailbox |
| `GMAIL_REFRESH_TOKEN_WHOLESALE` | Wholesale mailbox |
| `GEMINI_API_KEY` | Summaries (AI Studio) |
| `SLACK_BOT_TOKEN` | Slack read / post |
| `SLACK_SIGNING_SECRET` | Slack Events verification |
| `GOOGLE_SERVICE_ACCOUNT` or existing SA secret | BigQuery + optional Vertex |

*(Adjust names to match what you already store — e.g. reuse `GOOGLE_SERVICE_ACCOUNT` from `sheet_seed.yml`.)*
