# TASK-010 Summary

Implemented an Expo / React Native / strict TypeScript customer app in `mobile/`: native secure sessions, reverse WhatsApp login, SMS fallback API, actual wallet/card balances, exact barcode QR, cursor history, manual binding with business disambiguation, confirmed hiding, and logout. Production code has no loyalty fixtures, token/PII logging or integration internals. Backend, agent and integration behaviour were not changed.

## Baseline

Requested base: `main`, `4a2a1e938ce94d22cd5daba5a97a9bf093120d05`.
Initial required commands ran in `/Users/nuras/Desktop/cashback-one`:

- `git status`: detached HEAD at `4a2a1e9`, many pre-existing modified/deleted files.
- `git branch --show-current`: empty (detached).
- `git rev-parse HEAD`: exactly the requested base.

Preserved that directory unchanged. Created clean isolated worktree `/Users/nuras/Desktop/cashback-one-task-010`, branch `task-010-mobile`, directly from the supplied commit. Its initial `git status --short` was empty. `main` also resolves to the supplied baseline. All TASK-010 edits are in the isolated worktree.

Read original `TZ_loyalty_app_v1.1.docx`, repository README, AUTH/CUSTOMER_API documentation, auth/wallet API and schemas, errors, dependencies, security/phone utilities, wallet/SMS/provider services and relevant tests. Actual backend code governed implementation. Context7 checked Expo protected routes/SecureStore/testing and TanStack pagination/cache behaviour; the QR package's installed upstream README verified its `value` string API.

### Actual contract used

Responses below are the actual backend DTOs, not a separate speculative API.

| Endpoint | Method / body | Response | Auth | Relevant errors |
|---|---|---|---|---|
| `/auth/challenge` | POST `{device_id}` | `challenge_id, code, login_url, expires_in, expires_at` | none | `VALIDATION_ERROR`, `RATE_LIMIT_EXCEEDED`, `AUTH_RATE_LIMIT_UNAVAILABLE`, `CHALLENGE_GENERATION_FAILED` |
| `/auth/challenge/{id}` | GET, `X-Device-Id` | `status`; on confirmed also access/refresh/token_type/expires_in | device ownership | `DEVICE_HEADER_MISSING`, `DEVICE_MISMATCH`, `CHALLENGE_NOT_FOUND`, `CHALLENGE_ALREADY_CONSUMED`, `CHALLENGE_PHONE_MISSING`; expiry is **200 status expired** |
| `/auth/sms/request` | POST `{phone, device_id}` | `status: sent, expires_in` | none | `VALIDATION_ERROR`, `RATE_LIMIT_EXCEEDED`, `AUTH_RATE_LIMIT_UNAVAILABLE`, `SMS_PROVIDER_NOT_CONFIGURED`, `SMS_DELIVERY_UNAVAILABLE` |
| `/auth/sms/verify` | POST `{phone, device_id, code}` | token DTO | none | `VALIDATION_ERROR`, `OTP_NOT_FOUND`, `OTP_EXPIRED`, `INVALID_CODE`, `OTP_MAX_ATTEMPTS_EXCEEDED` |
| `/auth/refresh` | POST `{refresh_token}` | `access_token, refresh_token, token_type, expires_in` | refresh token | `INVALID_REFRESH_TOKEN`, `REFRESH_TOKEN_EXPIRED`, `VALIDATION_ERROR` |
| `/auth/logout` | POST `{refresh_token}` | `{status: ok}` | refresh token; missing/revoked token is idempotent | `VALIDATION_ERROR` |
| `/me/cards` | GET | array of card DTOs | Bearer | common auth errors |
| `/me/cards/{id}` | GET | card DTO | Bearer | common auth errors, `CARD_NOT_FOUND`, `VALIDATION_ERROR` |
| `/me/cards/{id}/transactions` | GET `limit=20`, optional opaque `cursor` (backend also accepts exact `type`) | `items, next_cursor, has_more` | Bearer | common auth errors, `CARD_NOT_FOUND`, `INVALID_CURSOR`, `VALIDATION_ERROR` |
| `/me/cards/bind` | POST `{barcode, business_id?}` | card DTO (200, also for existing own binding) | Bearer | `CARD_NOT_FOUND`, `CARD_BIND_NOT_ALLOWED`, `CARD_ACTIVATION_REQUIRED`, `BUSINESS_SELECTION_REQUIRED` with safe businesses, `VALIDATION_ERROR` |
| `/me/cards/{id}` | DELETE | 204, no body | Bearer | common auth errors, `CARD_NOT_FOUND`, `VALIDATION_ERROR` |

Card DTO: `id, barcode: string, balance: Decimal-string, is_blocked, updated_at, bound_at, bind_method, business: {id,name,branding}`. Branding has nullable `logo_url, primary_color, accent_color`.
Transaction DTO: `id, external_id, type: string, amount: Decimal-string, balance_after: Decimal-string, occurred_at, receipt_ref?, store?`. Nullable fields are retained. Amounts are never converted to floating point.
Common auth errors: `UNAUTHORIZED`, `INVALID_AUTHORIZATION_HEADER`, `TOKEN_EXPIRED`, `INVALID_TOKEN`, `SESSION_NOT_FOUND`, `SESSION_REVOKED`, `SESSION_EXPIRED`, `USER_NOT_FOUND`.

### Documentation / capability differences

- The AUTH flow diagram abbreviates polling as `GET /auth/challenge`; actual route requires `/{challenge_id}`. Mobile uses the actual route.
- WhatsApp challenge has **no phone request field**. Backend confirms the sender's phone. Mobile asks for a phone only in SMS fallback, consistent with code and reverse authentication.
- Already-bound own card is idempotent success, not a new `already bound` error. Hidden own card may be explicitly rebound. Foreign ownership is the same safe `CARD_BIND_NOT_ALLOWED` code as phone mismatch.
- SMS endpoints exist, but `sms_provider.py` and config provide only `disabled` and **test-only** `fake`. There is no production vendor adapter at this baseline. Mobile connects request/verify and shows safe 503 messaging; real SMS delivery cannot be enabled by mobile configuration. Backend was not expanded.
- `/auth/refresh` does not validate deleted users itself. Bootstrap validates with `/me/cards` after refresh; an unrecoverable auth response logs out.
- `type` is an open transaction string. Only documented `accrual` / `redemption` receive semantic labels; unknown values remain neutral.
- The original specification's iOS 15+ target was provisional; SDK 55 native requirements apply. No legacy native compatibility workaround was added.
- The repository README still describes mobile as future work; `mobile/README.md` is the current implementation/run guide.

## Mobile Architecture

Expo SDK 55.0.31, React Native 0.83.10, React 19.2, TypeScript 5.9 strict + unchecked-index checking. Files are organized into routes, typed API/session/storage, query hooks, reusable UI/features, theme, Russian catalogue, and utilities. No empty abstraction layers. All fetch calls are centralized in one client. Only Cloud customer contracts reach the app.

## Dependencies

`package-lock.json` is committed; `npm ci` succeeded. Expo installs aligned native packages. Expo Router/screens/linking/constants supply routing; safe-area-context and status-bar supply native layout; SecureStore stores tokens; Crypto creates installation UUIDs; TanStack Query manages in-memory server state/pagination; QRCode SVG + SVG render QR. React DOM and test renderer are pinned to matching React 19.2 to avoid npm peer-version drift. TypeScript/ESLint/Jest Expo/React Native Testing Library are quality dependencies. No validation framework or general state architecture framework was added.

`npx expo install --check`: dependencies up to date. `npm audit` at dependency installation reported 15 upstream findings (11 moderate, 4 high), including Expo CLI/code-signing tooling and router transitive packages. Automatic recommendations include incompatible SDK downgrades/major changes; no forced audit downgrade was applied. This is a remaining dependency-review limitation, not a failed app quality command.

## Navigation

Expo Router protected stacks depend on actual anonymous/authenticated state. Root loading/error/sign-out states block the protected UI. Logout/session invalidation removes protected navigation history. Wallet, bind and card-detail routes are within the authenticated group; login is unauthenticated.

## Session Bootstrap

Single-flight startup reads SecureStore, rotates/persists refresh pair, validates customer session via `/me/cards`, then reveals wallet. No saved tokens means login. An offline/503 bootstrap failure keeps credentials and exposes retry/logout without a login flash. Corrupt storage is cleared. Concurrent bootstrap/refresh and stale responses after logout are covered by tests.

## Secure Token Storage

Access+refresh tokens are stored together in one secure JSON item. Writes and deletion are serialized. `WHEN_UNLOCKED_THIS_DEVICE_ONLY` is used; Android backup excludes encrypted storage via plugin. Stable random installation ID is another secure item and survives logout. No AsyncStorage or browser token storage. A storage cleanup failure locks authenticated UI and permits another cleanup attempt.

## API Client

Environment-only `EXPO_PUBLIC_API_BASE_URL`, typed DTOs, JSON/Bearer/device headers, normalized machine-code errors, 15-second timeout and request cancellation. Concurrent 401s share rotation; other delayed 401s observe rotated access token and avoid replaying old refresh. One retry only; second 401 invalidates. Network refresh failures retain credentials. Invalid rotated response or secure persistence failure invalidates unusable credentials. Query/cache invalidation follows refresh. Generation checks prevent prior-session responses entering a new session.

## WhatsApp Auth

Display backend-generated code/instruction and remaining TTL; open only returned HTTPS `wa.me` links. Foreground sequential polling uses device header and pauses after error. Pending, expired, invalid/consumed and confirmed outcomes are handled; token confirmation is single-use. No provider webhook calls or new confirmation endpoint are implemented in mobile.

## SMS Fallback

Entered Kazakhstan-friendly `+7` phone is trimmed only; normalization stays server-owned. Request TTL drives countdown, verify requires exactly six digits, and resend has a client debounce (30 seconds) in addition to actual server limits. Invalid/expired/missing/exhausted code, rate limits and provider unavailability have safe messages. Existing backend's missing production provider is explicitly documented above.

## Wallet

Real card array, business name, balance, exact barcode, blocked/active flag. Loading, pull-to-refresh, empty, error and success states. Empty array presents a bind CTA. Existing successful query data remains visible after refresh failure with an explicit stale note and successful fetch timestamp.

## Card Detail

Real business/card identity, balance, state, backend `updated_at`, last successful fetch, QR and history. Refresh reloads both card and history. Content scrolls and supports enlarged text. No invented program/balance fields.

## QR

Validated 13 ASCII-digit string passes unchanged to QR encoder; zero prefixes survive. No metadata, URL or JSON. Human-readable number below QR, white quiet margin, black modules. Malformed server barcode displays safe failure without rendering an invalid encoder.

## Transactions

Opaque cursor pages of 20; explicit load-more button, no unbounded initial fetch. Next-page/refetch controls prevent overlapping pagination. Display actual type, amount, occurred time, balance-after, available store/receipt. Accrual and redemption have distinct labels/colors; unknown types have no invented interpretation. Initial/next-page errors are retryable; prior data is marked stale on failure.

## Card Binding

Client requires exactly 13 digits, preserves string, server remains authoritative. Backend business choices appear when ambiguity requires `business_id`. Safe ownership/activation/not-found/validation errors; no owner PII. Successful response updates existing cached list and detail before invalidating queries. No optimistic success.

## Card Hiding

Native confirmation dialog before DELETE. Cached list removes the card only after 204. Detail/history queries are removed and wallet refreshed. Failed request leaves state unchanged and displays an error. No offline simulated mutation.

## Logout

Block protected UI, await active refresh to revoke its latest token, POST `/auth/logout`, clear query+mutation cache and secure pair even if revoke request fails. Network revoke failure shows that local logout succeeded but remote revocation is unconfirmed. No unbounded request; 15-second timeout. No persistent revoke queue. SecureStore delete failure keeps UI locked with cleanup retry, rather than claiming credentials were deleted.

## Offline Behaviour

Only in-memory last-success snapshots during an authenticated app session, explicitly stale after failed retrieval with fetch time; no persistent loyalty cache or offline bootstrap bypass. Mutations always contact backend and never fake success. Foregrounding triggers stale-query checks. Lost single-use confirmation or refresh rotation responses may require fresh login because backend offers no recovery endpoint.

## Error Handling

Map machine codes to centralized Russian copy, never compare backend messages. Unknown/server/network/timeout/config/storage errors have safe fallback. Raw server messages/bodies are discarded since validation errors can contain PII. Safe business choices are the only additional error data retained.

## Privacy

No app console logging, tokens/OTP/challenge/phone/barcode logging, analytics, PII persistence outside native credential storage, or production fixtures. QR and entered numbers appear only where the customer must use them. Auth query/mutation cache clears on logout. No backend/agent/internal integration imports or endpoints.

## Accessibility

Buttons have role/label and at least 48-point targets; inputs are labelled with phone/OTP keyboard/autofill; error notices are alerts/live regions. Status/transaction meanings are text plus color. QR/card screens scroll at large font sizes. Russian strings and theme tokens are centralized for later kk localization. A physical screen-reader audit is still deferred.

## Tests

`npm test`: 4 suites / 44 tests passed, exit 0. Logic/component/flow coverage includes all requested critical session/storage/header/401/logout/error/barcode/QR/wallet/bind cases, plus SMS/challenge requests, safe business disambiguation, cursor encoding and confirmed hiding. No snapshots or tautological tests.

An optional `--detectOpenHandles` run during heavy SDK image extraction hit the 5-second timeout in two component flow tests (42 passed). The ordinary required gate was rerun after that load and all 44 passed. Earlier React peer dependency drift and Jest dynamic import test setup errors were corrected; final lockfile uses matching versions. Mutation GC in test clients is disabled so test cleanup leaves no 5-minute timer.

## Typecheck

`npm run typecheck`: strict `tsc --noEmit`, exit 0. Explicit DTOs; no `any` escapes in app or tests.

## Lint

`npm run lint`: ESLint Expo flat configuration, exit 0, zero warnings/errors. Explicit-any and console rules enforced. A test mock display-name/config scoping issue was fixed before final gate.

## Expo Build Validation

`npm run export` (`expo export --platform ios --platform android`): exit 0; iOS and Android Hermes bundles generated in ignored `mobile/dist/`. Initial native dependency alignment/React renderer peer conflicts were resolved with the SDK installer and pinned matching versions. This proves Metro/Hermes bundling, not signed store binaries.

Native device smoke result: **NOT VERIFIED**, no app-runtime PASS claimed. Xcode/iOS simulator is unavailable. The pre-existing Android AVD has an invalid ARM configuration on this x86 host. A separate test AVD was attempted: host storage blocked normal image installation; an isolated Android 28 image with the installed emulator 37 repeatedly failed to mount its required vendor partition and never reached an online ADB device. Expo Metro started, but Expo Go could not open on an offline device. Temporary images/AVD/userdata were removed. A real compatible device/emulator run remains an acceptance verification gap, despite passing bundle and component checks.

## Backend Regression

Initial global `pytest -v -m "not slow"` failed to import missing `aiosqlite`; fresh isolated `backend/.venv` installed existing requirements plus `greenlet` required by SQLAlchemy asyncio on this host's Python 3.14. No backend dependency files or behaviour changed.

Final `backend/.venv/bin/pytest -v -m "not slow"` from `backend/`: **176 passed, 29 skipped**, exit 0, 12.47s. Skips were PostgreSQL-specific checks without `POSTGRES_TEST_URL`.

## PostgreSQL Regression

Created a dedicated local `task010_regression` PostgreSQL test database (never used application databases). Ran existing full non-slow suite with `POSTGRES_TEST_URL=postgresql+asyncpg:///task010_regression`: **205 passed**, zero skipped, exit 0, 21.28s. Includes all 29 real PostgreSQL concurrency tests. No production DB migrations or fixtures were touched.

## Files Changed

Only mobile implementation and this report (35 files):

- `docs/TASK_010_REPORT.md`
- `mobile/.env.example`
- `mobile/README.md`
- `mobile/app.json`
- `mobile/app/(wallet)/_layout.tsx`
- `mobile/app/(wallet)/bind.tsx`
- `mobile/app/(wallet)/cards/[id].tsx`
- `mobile/app/(wallet)/index.tsx`
- `mobile/app/_layout.tsx`
- `mobile/app/login.tsx`
- `mobile/eslint.config.js`
- `mobile/jest.config.js`
- `mobile/package-lock.json`
- `mobile/package.json`
- `mobile/src/api/client.ts`
- `mobile/src/api/errors.ts`
- `mobile/src/api/wallet.ts`
- `mobile/src/auth/provider.tsx`
- `mobile/src/auth/session.ts`
- `mobile/src/auth/tokens.ts`
- `mobile/src/components/ui.tsx`
- `mobile/src/features/BindForm.tsx`
- `mobile/src/features/CardQr.tsx`
- `mobile/src/features/WalletList.tsx`
- `mobile/src/i18n/ru.ts`
- `mobile/src/storage/secure.ts`
- `mobile/src/theme/index.ts`
- `mobile/src/types/api.ts`
- `mobile/src/utils/format.ts`
- `mobile/tests/components.test.tsx`
- `mobile/tests/core.test.ts`
- `mobile/tests/flows.test.tsx`
- `mobile/tests/session.test.ts`
- `mobile/tests/setup.ts`
- `mobile/tsconfig.json`

## Known Limitations

- Production SMS vendor adapter absent in baseline backend; existing mobile fallback API supported/tested, real delivery not claimed.
- Real Wappi profile delivery and cashier scanner hardware not available for verification.
- Native iOS runtime requires Xcode, unavailable on this host. Android native app launch also remains unverified (test emulator never completed boot). Full TASK-010 acceptance must therefore include an independent native runtime check.
- No persistent wallet cache/offline-first mode; bootstrap needs server session validation.
- External single-use exchange/rotation response loss has no backend recovery contract.
- SDK/CLI transitive npm audit findings remain for separate compatible dependency review.
- Actual branding fields are typed but MVP uses one accessible palette and actual business identity.
- SecureStore uninstall/reinstall behaviour follows OS; iOS Keychain may survive reinstall.

## Deferred Work

No Admin, camera scanner, Wallet passes, push, marketing/news, white-label, virtual card creation, biometrics, signed store release or integration implementation. TASK-010 stops after delivery.

## Git Status

Implementation is isolated from the original dirty checkout. Commit and post-commit `git status`, branch and final HEAD are recorded in the external delivery record bundled with the source archive. This report belongs to that implementation commit; generated bundles, dependencies, virtualenvs and local `.env` files are ignored and excluded from the source archive.

## Branch

`task-010-mobile`.

## HEAD

Baseline/parent: `4a2a1e938ce94d22cd5daba5a97a9bf093120d05`.
Final HEAD is the new commit containing this report; its exact hash is provided by the post-commit `git rev-parse HEAD` in the delivery record and final response. A commit cannot embed its own hash in a versioned report without changing that hash.
