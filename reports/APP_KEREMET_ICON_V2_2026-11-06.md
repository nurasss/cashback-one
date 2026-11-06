# Отчёт: новая иконка Keremet Bonus и круглый значок в шапке — 2026-11-06

## 1. Сверка исходных файлов

Хеши проверены до начала работы, оригиналы не изменялись:

| Файл | Ожидаемый SHA-256 | Фактический SHA-256 | Статус |
|---|---|---|---|
| `docs/clients/keremet/app_icon_v2_2000.jpg` | `95ae0a15419d98bed21163efe00193d63c8c4e2a5d76abfa3c32f4dafc527dfd` | `95ae0a15419d98bed21163efe00193d63c8c4e2a5d76abfa3c32f4dafc527dfd` | СОВПАДАЕТ |
| `docs/clients/keremet/header_badge_k.png` | `f41876cb6290d1783bc5c8753dd05916b5b2a25c0186868730fa0afdf15b545a` | `f41876cb6290d1783bc5c8753dd05916b5b2a25c0186868730fa0afdf15b545a` | СОВПАДАЕТ |

Прежние `app_icon_1024.png` и `keremet_logo.svg` сохранены без изменений.

---

## 2. Значок справа вверху на главной (Выполнено полностью)

1. **Изображение значка**:
   - `mobile/clients/keremet/header_badge.png`: 120×120 px (3× от 38–40 pt), PNG с прозрачным фоном, круглая белая буква «k» на орнаменте.
2. **Конфигурация клиента (`mobile/src/config/client.ts`)**:
   - В интерфейс `ClientConfig` добавлено опциональное поле `headerBadge?: ImageSourcePropType`.
   - Для клиента `keremet` подключен значок: `headerBadge: require('../../clients/keremet/header_badge.png')`.
   - У `cashbackone` и `example` поле отсутствует (используется стандартное отображение).
3. **Компонент значка (`mobile/src/components/BrandBadge.tsx`)**:
   - Реализован компонент `HeaderBadge({ size = 38 })`.
   - Если у клиента есть `headerBadge`, рендерится круглый значок (размер 38 pt, `borderRadius: 19`, `accessibilityRole="image"`, `accessibilityLabel` — название приложения).
   - Если `headerBadge` нет (для `cashbackone` и `example`) — рендерится стандартный `BrandBadge` высотой 24 pt (плашка «ONE»).
4. **Шапка главной (`mobile/src/features/home.tsx`)**:
   - В строке баланса `BalanceHeader` (`styles.balanceGroup`) вызов `BrandBadge` заменен на `HeaderBadge`. Значок расположен справа от баланса, выровнен вертикально по центру строки (`alignItems: 'center'`).
5. **Экран входа (`mobile/app/login.tsx`)**:
   - Оставлен прежний `BrandBadge` (логотип «keremet» в SVG).
6. **Снимок экрана**:
   - `reports/keremet-icon-v2-2026-11-06/home-header.png` (390 px, web-preview на demo-данных): значок отображается справа от баланса в шапке главной.

---

## 3. Иконка приложения (Решение владельца: Вариант C — нарезка выполнена)

По решению владельца принят **Вариант C** (scale 0.66, вся композиция в безопасном круге 72 dp, фон-орнамент продлён до границ слоя 108 dp).

1. **Генерация master-слоёв**:
   - Мастер 2160×2160 px (соответствует 108 dp при 20 px/dp).
   - Композиция из `app_icon_v2_2000.jpg` (буква «k», три подарка, центральный орнамент) отмасштабирована в коэффициент 0.66 (1425 px, строго внутри безопасной зоны 72 dp / 1440 px).
   - Фоновый орнамент продлён до 108 dp с бесшовным градиентным переходом.
   - Выделена центральная зона 72 dp для legacy square-иконки `ic_launcher.png` и круглой маски `ic_launcher_round.png`.
   - В `mobile/clients/keremet/android/res/values/colors.xml` цвет `ic_launcher_background` обновлён на `#F15173` в тон фону иконки.

2. **Список нарезанных финальных ресурсов клиента `keremet` (все плотности)**:

| Ресурс | Разрешение | Формат | Размер | SHA-256 |
|---|---|---|---|---|
| `mobile/clients/keremet/android/res/mipmap-mdpi/ic_launcher_foreground.png` | 108×108 | RGBA | 20 830 байт | `e3e9e29477495ca4580ad77887e13666b9f7398a754bef383c7371df4f8dfabf` |
| `mobile/clients/keremet/android/res/mipmap-mdpi/ic_launcher.png` | 48×48 | RGBA | 5 812 байт | `c1d30b0d907da5f056354d680af979d20c165943571a77fa489570b222686c3f` |
| `mobile/clients/keremet/android/res/mipmap-mdpi/ic_launcher_round.png` | 48×48 | RGBA | 5 738 байт | `885c893872fa123a07fe3d60b7d12abee2d8aa59854c810c105601bb16ef87ae` |
| `mobile/clients/keremet/android/res/mipmap-hdpi/ic_launcher_foreground.png` | 162×162 | RGBA | 38 363 байт | `12333d2390ab082b9d06b384d5d9a1c647cad1bbd0b46dba427f5841ada146e3` |
| `mobile/clients/keremet/android/res/mipmap-hdpi/ic_launcher.png` | 72×72 | RGBA | 10 999 байт | `96834f6be82cc7a860071dbff78639567d5f850b8893590c8d69310406515c99` |
| `mobile/clients/keremet/android/res/mipmap-hdpi/ic_launcher_round.png` | 72×72 | RGBA | 10 861 байт | `2a4189a644601188997e48ad10f084535eacc78c3e5265deca863be82655bea0` |
| `mobile/clients/keremet/android/res/mipmap-xhdpi/ic_launcher_foreground.png` | 216×216 | RGBA | 59 842 байт | `a01312f902fcd6e95e4f7cc0f7213ca707acb03e076d32fc21bb40a460e15454` |
| `mobile/clients/keremet/android/res/mipmap-xhdpi/ic_launcher.png` | 96×96 | RGBA | 17 327 байт | `bd0fb5e6f1759e371a8027fdbcf1b9a689c55296e3eba6a4a35846e2bcf1a2f2` |
| `mobile/clients/keremet/android/res/mipmap-xhdpi/ic_launcher_round.png` | 96×96 | RGBA | 17 115 байт | `a3d821fd357c9b59ff6d952772ec0d57e7c53adb8341c00565b33a52fce12f77` |
| `mobile/clients/keremet/android/res/mipmap-xxhdpi/ic_launcher_foreground.png` | 324×324 | RGBA | 111 535 байт | `c712403e5aadee912de80892d571b53eef44ecc5502568d795e088ff2ff8196a` |
| `mobile/clients/keremet/android/res/mipmap-xxhdpi/ic_launcher.png` | 144×144 | RGBA | 33 003 байт | `a304f5485aac1fde6df91a52bc67092fe4e4d5607e39d4a146116b1e5241c36f` |
| `mobile/clients/keremet/android/res/mipmap-xxhdpi/ic_launcher_round.png` | 144×144 | RGBA | 32 171 байт | `12a5deb111be6123f59f1421d85524d3903569754f3f1d48b15f99bc313e0058` |
| `mobile/clients/keremet/android/res/mipmap-xxxhdpi/ic_launcher_foreground.png` | 432×432 | RGBA | 171 945 байт | `17965b64750b1343fb6883e89568670e66aa6cac1d17603e4819ec625be74360` |
| `mobile/clients/keremet/android/res/mipmap-xxxhdpi/ic_launcher.png` | 192×192 | RGBA | 52 256 байт | `e1eb01a1a5385c8ce66eaf699aaf4cb78545e6519374b104edd05cd1de8877ab` |
| `mobile/clients/keremet/android/res/mipmap-xxxhdpi/ic_launcher_round.png` | 192×192 | RGBA | 50 746 байт | `124ed7d03f9568685930e0ef9e243cd6d4734911371bb732e7e323aacbe10fb8` |

3. Иконка уведомлений (белая монохромная) не изменялась.
4. Другие клиенты (`cashbackone`, `example`) не затрагивались.

---

## 4. Сводка файлов превью (Только Вариант C)

Превью перегенерированы строго по финальным нарезанным файлам Варианта C:

| Файл | Разрешение | Формат | Размер | SHA-256 | Описание |
|---|---|---|---|---|---|
| `reports/keremet-icon-v2-2026-11-06/home-header.png` | 1000×1304 | RGB | 212 690 байт | `841cf42d36be0a04d20952ecd4f9917000f2749953c6ebedc073f36e62e8a170` | Снимок шапки главной Keremet (390 px): баланс и круглый значок |
| `reports/keremet-icon-v2-2026-11-06/round.png` | 616×656 | RGB | 256 325 байт | `7ba75f039eded3a06ac7550d38bd0d36365766527e72536e5f70b3d1e7bfcb6a` | Превью финальной иконки (Вариант C) под круглой маской лаунчера |
| `reports/keremet-icon-v2-2026-11-06/squircle.png` | 616×656 | RGB | 281 254 байт | `4ee018fcc225f6bdf35b8f3273e5438cd3d067c5aa155719bb86e8c580be3b88` | Превью финальной иконки (Вариант C) под сквиркл-маской лаунчера |
| `reports/keremet-icon-v2-2026-11-06/legacy.png` | 340×340 | RGB | 94 560 байт | `375cab42434fd3dd49f3a25079a19bf204f7cffefa22cd438587b05d1ddaa59d` | Превью финальной legacy-иконки `ic_launcher.png` (Вариант C) |

---

## 5. Сырой вывод проверок

### `npx jest --runInBand`
```
PASS tests/clientConfig.test.tsx (10.025 s)
PASS tests/profileSave.test.tsx (7.224 s)
PASS tests/flows.test.tsx
PASS tests/qrScreen.test.tsx
PASS tests/noCardNotice.test.tsx
PASS tests/appUpdate.test.tsx
PASS tests/cacheRefresh.test.tsx
PASS tests/homeArtwork.test.tsx
PASS tests/components.test.tsx
PASS tests/cityCustom.test.tsx
PASS tests/serverContentAndCache.test.tsx
PASS tests/wallet.test.tsx
PASS tests/historyPeriod.test.tsx
PASS tests/avatar.test.tsx
PASS tests/core.test.ts
PASS tests/push.test.tsx
PASS tests/loginScreen.test.tsx
PASS tests/promotionsArtwork.test.tsx
PASS tests/levels.test.tsx
PASS tests/demo.test.ts
PASS tests/session.test.ts
PASS tests/transport.test.ts
PASS tests/keyboardLift.test.ts

Test Suites: 23 passed, 23 total
Tests:       315 passed, 315 total
Snapshots:   0 total
Time:        36.658 s
Ran all test suites.
Exit code: 0
```

### Проверка ресурсов клиента (все плотности) из Jest `clientConfig.test.tsx`:
```
    1. Schema & Validation of client.json files
      ✓ validates cashbackone client.json and required resources (7 ms)
      ✓ validates example client.json and required resources (15 ms)
      ✓ validates keremet client.json and required resources (17 ms)
      ✓ verifies keremet mipmap resources and dimensions across all densities (117 ms)
```

### `npx tsc --noEmit`
```
Exit code: 0
No errors.
```

### `npx eslint .`
```
/Users/nuras/Desktop/cashback-one/mobile/src/components/useKeyboardLift.ts
  62:20  warning  The ref value 'generation.current' will likely have changed by the time this effect cleanup function runs. If this ref points to a node rendered by React, copy 'generation.current' to a variable inside the effect, and use that variable in the cleanup function  react-hooks/exhaustive-deps

✖ 1 problem (0 errors, 1 warning)
Exit code: 0
```
*(Предупреждение в `useKeyboardLift.ts` существовало до начала задачи)*

---

## 6. Git diff --stat

```
 mobile/clients/keremet/android/res/mipmap-hdpi/ic_launcher.png        | Bin 9245 -> 10999 bytes
 mobile/clients/keremet/android/res/mipmap-hdpi/ic_launcher_foreground.png     | Bin 19749 -> 38363 bytes
 mobile/clients/keremet/android/res/mipmap-hdpi/ic_launcher_round.png  | Bin 8499 -> 10861 bytes
 mobile/clients/keremet/android/res/mipmap-mdpi/ic_launcher.png        | Bin 4825 -> 5812 bytes
 mobile/clients/keremet/android/res/mipmap-mdpi/ic_launcher_foreground.png     | Bin 10079 -> 20830 bytes
 mobile/clients/keremet/android/res/mipmap-mdpi/ic_launcher_round.png  | Bin 4312 -> 5738 bytes
 mobile/clients/keremet/android/res/mipmap-xhdpi/ic_launcher.png       | Bin 14973 -> 17327 bytes
 mobile/clients/keremet/android/res/mipmap-xhdpi/ic_launcher_foreground.png    | Bin 31585 -> 59842 bytes
 mobile/clients/keremet/android/res/mipmap-xhdpi/ic_launcher_round.png | Bin 13844 -> 17115 bytes
 mobile/clients/keremet/android/res/mipmap-xxhdpi/ic_launcher.png      | Bin 28408 -> 33003 bytes
 mobile/clients/keremet/android/res/mipmap-xxhdpi/ic_launcher_foreground.png   | Bin 59823 -> 111535 bytes
 mobile/clients/keremet/android/res/mipmap-xxhdpi/ic_launcher_round.png        | Bin 26698 -> 32171 bytes
 mobile/clients/keremet/android/res/mipmap-xxxhdpi/ic_launcher.png     | Bin 44391 -> 52256 bytes
 mobile/clients/keremet/android/res/mipmap-xxxhdpi/ic_launcher_foreground.png  | Bin 94049 -> 171945 bytes
 mobile/clients/keremet/android/res/mipmap-xxxhdpi/ic_launcher_round.png       | Bin 42293 -> 50746 bytes
 mobile/clients/keremet/android/res/values/colors.xml                  |   2 +-
 mobile/src/components/BrandBadge.tsx                                  |  20 +++++-
 mobile/src/config/client.ts                                           |   4 ++
 mobile/src/features/home.tsx                                          |   4 +-
 mobile/tests/clientConfig.test.tsx                                    |  68 ++++++++++++++++++++-
 20 files changed, 93 insertions(+), 5 deletions(-)
```
