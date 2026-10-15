# Cashback One Mobile

## Экраны

Вкладки: **Главная** (телефон, баланс, баннеры, статус, «Горячие предложения»), **Акции**, центральная кнопка **Мой QR-код** (динамический QR, обновляется каждые 30 с), **Уведомления**, **Профиль** (Каз/Рус, данные клиента, «История начислений», «Мои карты», выход). Отдельно: «Мой статус» (уровень и прогресс), «История начислений», карточка акции, привязка карты. Красная точка на «Акциях» и «Уведомлениях» — новые акции или непрочитанные уведомления (`GET /me/badges`).

Шрифт Montserrat (`@expo-google-fonts/montserrat`), иконки — единый контурный набор в `src/components/icons.tsx`. Вход — одноразовый код в WhatsApp, сессия 14 дней.

Для локального просмотра без телефона можно запустить веб-версию: `npx expo start --web`. В вебе сессия хранится только в памяти (`src/storage/secure.web.ts`) и сбрасывается при перезагрузке страницы. Для веба нужно добавить его адрес (например `http://localhost:8081`) в `ADMIN_ALLOWED_ORIGINS` сервера; чтобы получать коды без Wappi, на сервере разработки включите `WHATSAPP_PROVIDER_MODE=log`.


Customer app: Expo SDK 55 / React Native 0.83 / React 19.2 / TypeScript strict.
Works exclusively through the Cloud Backend. No generated loyalty data or alternate API.

## Requirements / install

- Node.js 22 LTS or newer, npm (lockfile committed).
- Expo Go compatible with SDK 55 on a device, or an Android emulator / iOS simulator.
- iOS simulator requires macOS + Xcode; Android requires Android Studio + SDK and a valid AVD.
- Reachable backend, PostgreSQL and Redis, configured WhatsApp login profile/webhook for real delivery. The current backend has no production SMS adapter.

```bash
cd mobile
npm ci
cp .env.example .env
# Set EXPO_PUBLIC_API_BASE_URL before starting Metro.
npm start
```

`EXPO_PUBLIC_API_BASE_URL` is the Cloud Backend origin (with optional deployment prefix), without a trailing `/auth` or `/me`. It is public configuration, never a secret. There is no fallback origin. Missing configuration shows an actionable error when an API request is made. Restart Expo after changing `.env`.

## Backend connection setup

HTTPS is required by the API client for every production/release request, including auth, refresh and logout. `EXPO_PUBLIC_ALLOW_INSECURE_HTTP` cannot override this in release: it is considered only when React Native `__DEV__ === true` (not from `NODE_ENV`). There is no origin/protocol fallback.

Never enable insecure HTTP for production/release builds.

For local development only, explicitly set both in `mobile/.env`:

```env
EXPO_PUBLIC_API_BASE_URL=http://<reachable-dev-host>:8000
EXPO_PUBLIC_ALLOW_INSECURE_HTTP=1
```

Unset/`0`/any value other than exactly `1` keeps HTTPS mandatory even in development. Development HTTP sends credentials in cleartext; use only a controlled local test environment with test accounts. Validation rejects empty/invalid/relative URLs, other protocols, userinfo, query and fragment; it normalizes trailing slashes centrally. Errors use safe codes (`CONFIG_MISSING`, `INVALID_API_URL`, `INSECURE_TRANSPORT`) and user-friendly copy without retaining a URL or parser message.

For local development, bind uvicorn to `0.0.0.0` and permit the port through the firewall. Set the URL only in `.env`:

- Android standard emulator: `http://10.0.2.2:8000` reaches the host.
- iOS simulator: `http://localhost:8000` reaches the Mac.
- Physical device: use the computer's reachable LAN address, e.g. `http://<host-lan-ip>:8000`; both devices must be on the same network.

See repository `README.md`, `docs/AUTH.md`, `docs/CUSTOMER_API.md` and backend configuration for deployment. Mobile never receives database or messaging-provider credentials. The current backend implements only `disabled` and test-only `fake` SMS provider modes. Production SMS requests return `SMS_PROVIDER_NOT_CONFIGURED`; the app displays a safe unavailable message. Adding a real vendor adapter is a separate backend task.

## Run iOS / Android

```bash
npm run ios
npm run android
```

Alternatively scan the Expo terminal QR using Expo Go on a real device. Native SecureStore is required. Web authentication is not supported; tokens are never placed in browser localStorage. Expo export verifies iOS and Android JS/Hermes bundles; it is not an App Store / Play Store binary build.

## Quality gates

```bash
npm test
npm run typecheck
npm run lint
npm run export
npx expo install --check
```

Tests cover session bootstrap, native storage adapter, headers, refresh single-flight/retry/failure, stale-session response protection, logout, normalized errors/privacy, barcode/QR, empty/populated wallet, SMS/challenge requests, ambiguous binding, cursor pagination and confirmed hiding. Mock loyalty data lives only in `tests/`.

## Authentication and session

- WhatsApp: `POST /auth/challenge` sends **only `device_id`**. Display the returned code, TTL and instruction, and open the returned `https://wa.me` link. The user sends the message; the backend webhook identifies their phone. No client confirmation endpoint exists.
- Poll `GET /auth/challenge/{id}` with `X-Device-Id`, sequentially about every two seconds while foregrounded. `pending` waits; `confirmed` yields the tokens; `expired` requires a new challenge. Polling stops on network/server error and offers manual retry; it does not spin forever.
- SMS fallback: send entered phone text (trimmed only) to `/auth/sms/request`, then send the same phone/device and six-digit string code to `/auth/sms/verify`. Backend normalization is authoritative. TTL comes from `expires_in`. UI resend cooldown is 30 seconds; actual rate limits and attempt counts remain server enforced. A new request invalidates the previous OTP.
- A random installation ID persists in SecureStore across logout. There are no hardware/device PII identifiers.
- Tokens are one JSON item in Expo SecureStore, with `WHEN_UNLOCKED_THIS_DEVICE_ONLY`. A single item avoids half-written token pairs. Android backup exclusion is enabled by the plugin. Corrupt records are deleted.
- Startup remains in a loading state while reading and rotating tokens, persisting the rotated pair, and validating identity through `/me/cards`. This last request is needed because the current backend `/auth/refresh` does not check `users.deleted_at`. Transient bootstrap failure shows retry/logout instead of flashing Login or silently deleting usable credentials.
- Protected Expo Router groups follow session state. 401 triggers one shared rotation and one retry. Irrecoverable 401 or inability to persist rotation clears credentials/cache. Network/503 refresh errors retain credentials and show a retryable error.

## Wallet / QR / mutations

- Wallet uses `GET /me/cards`, detail uses `GET /me/cards/{id}`. Empty list is a normal state with a bind CTA. Balance is formatted directly from the Decimal string without floating-point conversion.
- QR encodes the exact validated 13-digit barcode string. Leading zeros remain. No URL, prefix, or JSON wrapper. There is a white quiet margin and readable number below; content scrolls with large text.
- History requests `limit=20`, then only the backend `next_cursor` when `has_more` is true. “Load more” offers deliberate pagination. Refresh rebuilds pages through TanStack Query. Documented `accrual` and `redemption` have distinct text and color; unknown types display their raw type with neutral styling.
- Bind validates 13 ASCII digits, sends `barcode`, and optionally sends the selected `business_id` from `BUSINESS_SELECTION_REQUIRED.error.businesses`. Already-visible own card is a successful idempotent response, not an invented error. Rebinding an own hidden card restores it.
- Hide asks for confirmation and sends DELETE. Only after 204 do cached cards change and detail/history queries disappear. Bind similarly updates existing list cache only after server success. Queries are invalidated after mutations. No optimistic success or offline mutation queue.

## Logout and offline behaviour

Logout blocks protected UI, waits for an ongoing refresh rotation, calls `/auth/logout` with the latest refresh token, clears the entire authenticated query/mutation cache and deletes the secure token item regardless of network result. Requests have a 15-second timeout. A failed network revoke displays a notice that this device has signed out but server revocation was not confirmed. Server tokens may remain valid until expiry; there is no offline revoke queue.

SecureStore deletion failure leaves the protected UI locked on an error screen; retry performs local cleanup. Reopen/reinstall behaviour is governed by native secure storage. iOS Keychain can persist across reinstall; Android uninstall usually removes data. No promise of remote logout is made without a successful response.

Only session-lifetime query snapshots are retained in memory. After a failed refresh, cached wallet/detail/history is explicitly marked stale with the last successful fetch time; `updated_at` shows the separate backend card snapshot time. There is no persistent wallet cache and no offline startup bypass. On app foreground TanStack Query checks stale queries again. Mutations always contact the backend and cannot succeed offline.

## Structure / dependencies

- `app/`: Expo Router root, login and protected wallet routes.
- `src/api/`: typed HTTP client, safe errors, wallet query hooks.
- `src/auth/`: session lifecycle, token validation, React provider.
- `src/storage/`: secure token pair and installation ID.
- `src/features/`: reusable card, QR and bind UI.
- `src/components/`: accessible buttons, labelled inputs, loading/error views.
- `src/theme/`, `src/i18n/`: small centralized tokens and Russian copy (ready for a later kk catalogue).
- `src/types/`, `src/utils/`: backend DTOs and string-safe formatting.
- `tests/`: isolated fixtures and automated logic/component/flow checks.

Expo Router provides session-based navigation; SecureStore stores credentials; Crypto generates the installation ID; TanStack Query handles in-memory server state/pagination; QRCode SVG + react-native-svg renders QR; safe-area-context/screens and Expo linking/constants/status-bar support native routes/UI. React DOM is pinned to the matching React version to satisfy router web peer dependencies, not to implement web auth. Jest Expo + React Native Testing Library + matching React test renderer are test-only. ESLint/TypeScript are quality tools. No validation/architecture framework is added.

## Known limitations / deferred

A real SMS adapter is absent in this baseline backend; the mobile fallback is connected to the existing request/verify API and tested with isolated fixtures. Real WhatsApp provider delivery, physical cashier scanner checks, device accessibility audits and signed store builds require deployment/devices. No full offline mode or persisted loyalty snapshots. History type is an open backend string: only documented types receive semantic labels. Generic `VALIDATION_ERROR` is shown safely without retaining backend validation messages (which may contain PII). Logo/colors exist in DTOs; the MVP uses a consistent accessible palette and actual business name.

A successful single-use challenge/OTP exchange whose response is lost in transit cannot be recovered by this backend contract; obtain a new code. Likewise a refresh whose rotation succeeded but response was lost may require login on the next refresh. The app does not invent recovery endpoints.

Native minimum OS versions follow SDK 55, not the old provisional Android 8 / iOS 15 statement in the original specification. No backend or integration implementation changes. Camera scanning, passes, pushes, marketing, virtual cards, biometrics, admin and store release are deferred.
