# TASK-010-FIX-A

HTTPS transport blocker is fixed. Native acceptance remains open: **NATIVE_RUNTIME = NOT VERIFIED**. No native smoke PASS is claimed from Expo export, Metro bundling, an installed APK or a started activity.

## Baseline

Worktree: `/Users/nuras/Desktop/cashback-one-task-010`.
Required commands ran before editing:

```text
git status: On branch task-010-mobile; nothing to commit, working tree clean
git branch --show-current: task-010-mobile
git rev-parse HEAD: 29a6db9ec5ebaa8630244fb7b250c1e9f27a330a
```

Kept the existing Mobile architecture. No tracked Backend, Agent or Stage0 changes. All work is on the requested branch, above the requested baseline, without amending its commit.

## HTTPS Transport Boundary

Added `mobile/src/api/transport.ts`; the existing API client's single `send` method invokes validation before fetch, request headers, JSON serialization and network I/O. This covers wallet, auth, refresh and logout equally.

Production/release requires `https:`. Runtime policy uses React Native `__DEV__ === true`, not `NODE_ENV`. The insecure env flag is evaluated only inside development. Release with `EXPO_PUBLIC_ALLOW_INSECURE_HTTP=1` still has `allowInsecureHttp=false`. Even an explicit test policy with `development=false, allowInsecureHttp=true` rejects HTTP.

`INSECURE_TRANSPORT` is a safe client machine code, with centralized Russian user-friendly copy. No raw URL/parser exception is retained in the error. There is no protocol/origin fallback and no production-domain hardcoding.

Expo documentation was checked through Context7 for public-variable dot-notation inlining, production constant folding of `__DEV__`, and compatible Expo Go native launch. Installed Expo SDK 55 source also confirms that its Winter runtime installs the WHATWG URL implementation before the app runs; no additional URL library is needed.

## Development HTTP Policy

Both must be true:

```text
__DEV__ === true
EXPO_PUBLIC_ALLOW_INSECURE_HTTP === "1"
```

`.env.example` defaults the flag to `0`. Unset, `0`, `true`, `yes` and whitespace variants do not opt in. `mobile/README.md` explains local Android/iOS/device origins, restart instructions and the warning:

> Never enable insecure HTTP for production/release builds.

The public flag contains no credentials. Development cleartext is limited by explicit build mode and opt-in; use only a controlled test environment/test accounts. Native attempts used opt-in for a local isolated test backend, with no real customer identity submitted.

## URL Validation

One central function validates:

- non-empty trimmed configuration (`CONFIG_MISSING` otherwise);
- explicit absolute URL with authority and hostname;
- syntactically valid URL/port, without whitespace or backslash repair;
- only HTTPS, or HTTP with both development conditions;
- no embedded username/password, query or fragment (including empty delimiters);
- centralized normalization of trailing `/` while preserving a deployment path prefix.

Malformed/configuration URLs produce `INVALID_API_URL`; denied protocols produce `INSECURE_TRANSPORT`. Errors expose codes only, never query/credentials/parser messages. Screens have no transport checks.

## Transport Security Tests

Added 37 regression cases in `mobile/tests/transport.test.ts`, including:

- HTTPS under release/development policies and slash normalization;
- HTTP denied by default and in release even with opt-in;
- HTTP accepted with both development conditions only;
- absent/invalid/relative URLs, invalid port, unsupported schemes;
- userinfo/query/fragment rejection without retaining secrets;
- actual runtime policy with `__DEV__=false` and env flag `1`;
- exact flag semantics, secure default;
- fetch and auth refresh never called for rejected configuration;
- Bearer and auth/refresh JSON bodies never transmitted on rejected transport.

Existing 44 tests remain unchanged and pass. Final total: **81 passed, 5 suites**, exit 0.

## Native Environment

No connected physical Android device was present initially. Xcode/iOS simulator is unavailable. An optional physical-device question received no answer during this run; continued independently with an isolated Android AVD.

Actual native target attempted:

| Field | Actual value |
|---|---|
| Platform | Android emulator |
| Host | macOS 13.7, x86_64, 8 GiB memory; constrained free storage |
| Emulator | Android Emulator 37.1.11.0 |
| AVD | `task010-fix-a`, Pixel 5 profile, compact 720×1280 display |
| System image | Google ATD x86_64, Android 14 / API 34 |
| `ro.product.model` | `Google ATD built for x86_64` |
| OS / boot | `ro.build.version.release=14`; `sys.boot_completed=1` |
| Runtime package | Expo Go 55.0.7, versionCode 419, minSdk 24 / targetSdk 36 |
| App SDK | Expo SDK 55.0.31, React Native 0.83.10 |
| Backend for attempt | Existing Cloud API, isolated APP_ENV=test SQLite schema; `/health` returned 200 |

Native preparation was outside tracked project code. Insufficient disk space required sparse extraction of the official system image and temporary AVD storage. The first custom-userdata boot missed the required metadata partition; supplying the image's `encryptionkey.img` made Android boot and ADB become online.

Official Expo Go was fetched by Expo CLI. Its full universal APK could not install into the small test userdata partition. For the attempted smoke, a local x86_64-only copy removed unused ABI entries and old signatures, was zip-aligned and signed with an ephemeral test key. All retained classes/resources/x86_64 entry contents were verified byte-for-byte against the official APK; Android installation and APK signature verification succeeded. It is a local test-runtime variant, not a production deliverable. Signing keys were deleted; APKs are excluded from the project archive. This runtime detail is disclosed rather than presenting it as an unmodified official binary.

## Native Launch

Emulator command (temporary test resources only):

```bash
emulator -avd task010-fix-a \
  -data /tmp/task010fix-userdata.img \
  -encryption-key <sdk>/system-images/android-34/google_atd/x86_64/encryptionkey.img \
  -no-snapshot -no-audio -no-window \
  -gpu swiftshader_indirect -memory 1536 -cores 2 -show-kernel
```

Actual app launch command from `mobile/`:

```bash
CI=1 ANDROID_HOME=<sdk> \
EXPO_PUBLIC_API_BASE_URL=http://10.0.2.2:18080 \
EXPO_PUBLIC_ALLOW_INSECURE_HTTP=1 \
npx expo start --go --android --localhost --port 8089
```

Additional retry used `adb shell am force-stop host.exp.exponent` followed by `am start -a android.intent.action.VIEW -d exp://127.0.0.1:8089 -p host.exp.exponent`.

Actual results:

- Android booted and Expo Go installed successfully.
- Metro bundled the Android app and ExperienceActivity started on the emulator.
- Window inspection reported `Application Not Responding: system` as the focused window.
- Screen captures stayed black, even after wake/stay-on/keyguard dismissal and activity restart.
- UI Automator could not return a usable UI hierarchy.
- These environment/runtime failures prevented visual and interactive acceptance verification. No claim is made that Login rendered or that absence of a Red Screen proves the app is healthy.

**NATIVE_RUNTIME = NOT VERIFIED.** App-native smoke must still run on a healthy native target. The system ANR is the observed failure; it is not papered over with web/export/test results.

## Login Screen Smoke Test

**NOT VERIFIED.** APK installation, Metro output and activity start are insufficient to claim Login is visible. No screenshot is supplied as a successful Login proof; black captures are not accepted as evidence of the required screen.

## WhatsApp/SMS Navigation Smoke Test

**NOT VERIFIED on native.** The unusable native UI prevented mode switching/input/navigation checks and native challenge creation. No real phone, OTP, token, barcode or WhatsApp secret was entered or recorded in evidence. No messages were sent. Existing automated WhatsApp/SMS flow checks still pass, but they do not replace the native gate.

## Mobile Tests

Required `npm ci`: exit 0, final lockfile installation succeeded.
Required `npm test`: **81 passed, 5 suites**, exit 0, 21.011s. Original 44 plus 37 new transport tests. An earlier concurrent run during system-image extraction hit the existing 5-second timeout in one SMS component flow test (80 passed); the required gate was rerun after extraction and passed without changing that test or its timeout.

## Typecheck

`npm run typecheck`: exit 0; strict TypeScript preserved. No explicit `any` workaround added.

## Lint

`npm run lint`: exit 0, no warnings/errors.

## Expo Dependency Check

`npx expo install --check`: exit 0, dependencies up to date.

## Expo Doctor

Initial `npx expo-doctor` (1.20.4): 19/20 checks passed, failed duplicate native dependencies: `expo-font@55.0.8` nested in Expo and `expo-font@57.0.4` at root.

Compatible fix: `npx expo install expo-font` added the direct SDK-55 version `~55.0.8`, updated lockfile, deduplicated the native module and added its supported config plugin. No SDK migration or app rewrite.

Final `npx expo-doctor`: **20/20 checks passed**, exit 0, no issues detected.

## Expo Export

`EXPO_PUBLIC_ALLOW_INSECURE_HTTP=1 npm run export`: exit 0, iOS and Android Hermes bundles generated. The deliberate flag verifies that a production export still compiles the release-only HTTPS policy; the false `__DEV__`/flag behavior is independently asserted by transport tests. Export is bundling evidence, not native smoke proof. Generated `dist/` is ignored/excluded.

## Backend Regression

No tracked backend change. Initial global `pytest -v -m "not slow"` lacked `aiosqlite`. Recreated isolated `backend/.venv` using existing requirements plus the host-required `greenlet` dependency (Python 3.14); no dependency file change.

Final `.venv/bin/pytest -v -m "not slow"` from `backend/`: **176 passed, 29 skipped**, exit 0, 162.92s. Skips were PostgreSQL tests without a configured test URL. Runtime was longer while system-image extraction competed for host resources.

## PostgreSQL Regression

Local PostgreSQL was available. Created only a dedicated `task010_fix_a_regression` database, and ran the same non-slow suite with `POSTGRES_TEST_URL=postgresql+asyncpg:///task010_fix_a_regression`.

Result: **205 passed**, zero skipped, exit 0, 141.00s. Includes all existing PostgreSQL concurrency checks. No production database or agent data changed.

## Security Regression

Inspected actual app sources and ran:

```bash
rg -n 'console\.|AsyncStorage|OneLoyaltySource|COMConnector|V83|mock|fake|fixture' mobile/src mobile/app
```

No matches. App does not log token/OTP/phone/barcode/payload; tokens remain exclusively in SecureStore; runtime wallet has no mocks/fallback balances; no ONE/COM dependencies were added. Tests alone contain fixtures. New URL errors discard unsafe input/parser messages, and rejected transport does not call fetch. Native attempt evidence contains no customer data, challenges, credentials or signing keys.

## Known Limitations

- HTTPS code/security blocker is resolved; **native acceptance is still open**. TASK-010/FIX-A cannot be called fully accepted until a healthy native target displays Login and completes WhatsApp/SMS/input/navigation smoke.
- The attempted low-resource Android ATD target reached Expo Go activity startup but had a system ANR/black output. No physical target was connected and no iOS target was available.
- No successful native screenshot or native auth action is claimed.
- npm installation still reports the baseline upstream audit findings (15: 11 moderate, 4 high); no incompatible SDK downgrade/forced audit fix was applied.
- Real SMS delivery remains a baseline backend capability limitation; this fix does not add a provider or change backend behavior.

## Git Status

Only these 10 tracked files change:

- `docs/TASK_010_FIX_A_REPORT.md`
- `mobile/src/api/transport.ts`
- `mobile/src/api/client.ts`
- `mobile/src/i18n/ru.ts`
- `mobile/tests/transport.test.ts`
- `mobile/.env.example`
- `mobile/README.md`
- `mobile/package.json`
- `mobile/package-lock.json`
- `mobile/app.json`

Temporary AVD/RAM image, test runtime/signing artifacts and native backend test DB were removed; task-owned servers were stopped. The dedicated PostgreSQL regression database was dropped after successful testing. No Backend/Agent/Stage0 diff. Post-commit status/branch/HEAD are captured in the external delivery record included in the full-project source archive. Temporary native resources and installed dependencies are excluded from the archive.

## Branch

`task-010-mobile`.

## HEAD

Baseline/parent: `29a6db9ec5ebaa8630244fb7b250c1e9f27a330a`.
New commit message: `fix(mobile): enforce transport security and verify native runtime`.
Exact final HEAD is in post-commit `git rev-parse HEAD`, the delivery record and final response. The versioned report cannot embed its own commit hash without changing that hash.
