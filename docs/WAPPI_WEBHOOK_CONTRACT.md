# Wappi Webhook Specification & Integration Contract

## 1. Document Overview & Source Evidence

* **Source Documentation:** Wappi Official API Documentation (`https://wappi.pro/docs/`)
* **Verification Date:** 2026-09-29
* **Integration Purpose:** Reverse WhatsApp authentication flow for POSCENTER Loyalty customer mobile application (TASK-004 / TASK-004-FIX).

---

## 2. Webhook Authentication (`auth`) & Header Verification Status

Wappi webhook profile settings provide an `auth` configuration parameter described as:
> *"Секретная фраза в заголовке Webhook. Передается в запросе от сервиса к вашему URL."*

### Status of Header Name:
```text
WAPPI_AUTH_HEADER_NAME = NOT VERIFIED
```

* **Rationale:** Current public documentation confirms that a secret string is transmitted in an HTTP header, but does not definitively standardize a single immutable header name.
* **Architecture Solution:** The header name has NO production default in application code and is strictly required via runtime deployment configuration:
  * `WAPPI_WEBHOOK_AUTH_HEADER` (must be explicitly provided in development/production)
  * `WAPPI_WEBHOOK_AUTH_SECRET` (min 32 characters, verified using constant-time `hmac.compare_digest`)
* Once a real Wappi profile is connected and the live header observed, production configuration is set without code changes.

---

## 3. Webhook Event Types & Filtering

Wappi broadcasts multiple webhook event categories (`wh_type`):
* `incoming_message` — **ONLY event processed for authentication**
* `delivery_status` — Ignored (200 OK)
* `authorization_status` — Ignored (200 OK)
* `application_status` — Ignored (200 OK)
* `incoming_call` — Ignored (200 OK)
* `outgoing_message_api` — Ignored (200 OK)
* `outgoing_message_phone` — Ignored (200 OK)

Any unknown or newly added `wh_type` is safely acknowledged with HTTP 200 without triggering server errors or database updates.

---

## 4. Incoming Message Schema (`wh_type = "incoming_message"`)

Wappi delivers incoming messages in a batch payload container `messages` (or as a single message object):

```json
{
  "messages": [
    {
      "wh_type": "incoming_message",
      "profile_id": "c1f7a8b9-...",
      "id": "wamid.HBgLM...",
      "body": "AB7K2M9Q",
      "type": "chat",
      "from": "77017778899@c.us",
      "to": "77001234567@c.us",
      "senderName": "Customer Name",
      "chatId": "77017778899@c.us",
      "timestamp": "1729499277",
      "time": 1729499277,
      "chat_type": "dialog"
    }
  ]
}
```

### Field Definitions:

| Field | Type | Required for Login | Validation / Filter Rule |
|---|---|---|---|
| `wh_type` | string | Yes | Must equal `"incoming_message"`. |
| `profile_id` | string | Yes | Must strictly match `WAPPI_LOGIN_PROFILE_ID`. Other profiles ignored. |
| `id` | string | Yes | Unique provider message ID. Used for database idempotency `(profile_id, message_id)`. |
| `body` | string | Yes | Text message content. Stripped and uppercased: must be exactly 8 chars from `CHALLENGE_CODE_ALPHABET`. |
| `type` | string | Yes | Message media type. Must strictly equal `"chat"`. Images, audio, reactions, etc. are ignored. |
| `from` | string | Yes | Sender JID. Must match `^(\d{10,15})@c\.us$`. Group JIDs (`@g.us`) and `@lid` are rejected. |
| `chatId` | string | Optional | If ends with `@g.us`, message is rejected as group message. |
| `chat_type` | string | Optional | If present, must equal `"dialog"`. Any other value rejected as group/broadcast. |
| `to` | string | Optional | Recipient WhatsApp business address. |
| `time` / `timestamp` | int/str | Optional | Event timestamp. |

---

## 5. Security & Invariants

1. **Profile Isolation:** Webhook requests for profiles other than `WAPPI_LOGIN_PROFILE_ID` are rejected from authentication processing to prevent cross-profile privilege escalation.
2. **Payload Size Guard:** Webhooks exceeding `WAPPI_WEBHOOK_MAX_BODY_BYTES` (default 64 KB) are rejected prior to processing (`413 Payload Too Large`).
3. **No Outbound Response:** POSCENTER Loyalty backend never sends outbound WhatsApp messages in response to webhook events. Challenge state is fetched by the customer app via polling `GET /auth/challenge/{id}`.
4. **Zero PII Storage:** Raw webhook payloads, full customer phone numbers, and challenge codes are never stored in the `wappi_webhook_events` audit table.

---

## 6. Webhook Retry & Error Semantics

* **2xx Outcomes (Definitive Acceptance):**
  - Expected domain/provider outcomes (`confirmed`, `already_confirmed_same_phone`, `already_confirmed_other_phone`, `expired`, `consumed`, `not_found`, `duplicate`, ignored filters) are durably committed and return HTTP 200.
* **Non-2xx Outcomes (Transient Failure):**
  - Operational failures (database connection drop, transaction error, lock timeout) trigger an immediate `ROLLBACK` of the uncommitted reservation and return HTTP 503 (`WEBHOOK_PROCESSING_UNAVAILABLE`).
  - No durable error record is saved. Rollback preserves our ability to safely process a repeated delivery when the provider retries.
* **Batch Failure Semantics:**
  - Messages in a batch are processed transactionally. If message $N$ fails due to an infrastructure outage, prior messages $1..N-1$ remain durably committed, message $N$ rolls back, and 503 is returned.
  - When the provider retries the batch, messages $1..N-1$ are acknowledged as duplicates, and message $N$ is processed without data loss.
* **Information Leak Prevention:**
  - Technical error messages (`str(exc)`), SQL statements, and database credentials are strictly prohibited in API responses and sanitized to controlled error envelopes.
