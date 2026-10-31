# Отчёт: новая иконка и оформление акций — 2026-10-31

## Первая попытка: остановка на baseline

Работа остановлена на обязательном baseline до любых изменений: `npx jest` завершился с кодом 1 — 2 таймаута, 201 passed из 203. По инструкции промпта дальнейшие проверки и правки не выполнялись.

## Baseline

- Команда: `npx jest`
- Рабочая папка: `mobile/`
- Перед тестом `uptime`: `12:59 up 15 mins, 1 user, load averages: 5.56 18.29 25.50`; load average за 1 минуту ниже порога 12.
- Результат: **2 failed, 12 passed; 2 failed, 201 passed, 203 total; exit code 1**.
- `npx tsc --noEmit`, lint и тесты после изменений не запускались.

### Сырой вывод `npx jest`

```text
PASS tests/homeArtwork.test.tsx (32.8 s)
PASS tests/session.test.ts
FAIL tests/profileSave.test.tsx (34.37 s)
  ● Done saves only the edited field with a PATCH, closes the sheet and shows the new value

    thrown: "Exceeded timeout of 5000 ms for a test.
    Add a timeout value to this test to increase the timeout. See https://jestjs.io/docs/api#testname-fn-timeout."

      31 | beforeEach(() => { jest.clearAllMocks(); mockRequest.mockReset(); });
      32 |
    > 33 | it('Done saves only the edited field with a PATCH, closes the sheet and shows the new value', async () => {
         | ^
      34 |   const screen = await open();
      35 |   fireEvent.press(screen.getByLabelText(ru.email));
      36 |   expect(inputs(screen)).toBe(3);

      at Object.it (tests/profileSave.test.tsx:33:1)

PASS tests/cardBarcode.test.tsx
PASS tests/wallet.test.tsx
FAIL tests/flows.test.tsx (38.29 s)
  ● home shows phone, balance, status, max cashback and hot offers

    thrown: "Exceeded timeout of 5000 ms for a test.
    Add a timeout value to this test to increase the timeout. See https://jestjs.io/docs/api#testname-fn-timeout."

      105 | });
      106 |
    > 107 | it('home shows phone, balance, status, max cashback and hot offers', async () => {
          | ^
      108 |   serve({ '/me/cards': [card], '/me/profile': profile, '/me/promotions': { banners: [banner], offers: [offer], has_new: true } });
      109 |   const { screen } = mountWith(<Home />);
      110 |   await waitFor(() => expect(screen.getByText('+7 705 834 43 26')).toBeTruthy());

      at Object.it (tests/flows.test.tsx:107:1)

PASS tests/code128.test.ts
PASS tests/transport.test.ts
PASS tests/core.test.ts
PASS tests/demo.test.ts
PASS tests/levels.test.tsx
PASS tests/keyboardLift.test.ts
PASS tests/components.test.tsx (33.644 s)
PASS tests/cardScanner.test.tsx (39.274 s)
A worker process has failed to exit gracefully and has been force exited. This is likely caused by tests leaking due to improper teardown. Try running with --detectOpenHandles to find leaks. Active timers can also cause this, ensure that .unref() was called on them.

Test Suites: 2 failed, 12 passed, 14 total
Tests:       2 failed, 201 passed, 203 total
Snapshots:   0 total
Time:        77.22 s
Ran all test suites.
```

## Состояние на момент первой остановки

- В `mobile/` ничего не менялось; исходные изображения не тронуты.
- Нативные файлы в `mobile/android/` не менялись; резервная копия для них не создавалась, поскольку до правок дело не дошло.
- APK и скриншоты не создавались.
- Отчёт — единственный файл, созданный этой задачей.

## Состояние Git при первой остановке

После baseline `git status --short`:

```text
?? C:/
?? docs/PROMPT_APP_ART_ICON_2026-10-31.md
?? mobile/assets/source-2026-10-31/
?? video/
```

Это присутствовало до изменений и сохранено без вмешательства. `git diff --stat` не вывел строк.

## Не проверено на момент первой остановки

На тот момент не проверялись функциональность баннеров и карточек акций, навигация и описания, переводы RU/KK, корректность иконки/безопасной зоны, отображение при 360/412 px, lint/typecheck и нативный лаунчер. Этот раздел сохранён как исторический.

## Продолжение после СТОП по решению куратора

В обновлённом промпте куратор сообщил, что отдельно повторил baseline (`npx jest`: 203 passed, код 0; `profileSave` и `flows`: 26 passed) и разрешил продолжить без повторения baseline. Это результат, переданный в промпте; здесь он повторно не запускался.

### Выполнено до итоговой остановки

- Новые PNG из оригиналов, конвертированные Pillow без изменения размеров: `mobile/assets/promotions/banner-coffee-machine.png` (2000×862), `banner-stickers.png` (2000×860), `promo-hits-discount.png`, `promo-card-bonus.png`, `promo-weekly.png`, `promo-fresh-products.png` (каждый 2000×1085). Альфа-канал сохранён. Оригиналы из `source-2026-10-31/` не изменялись.
- Иконки: `mobile/assets/icon.png` (1024×1024) и прозрачный foreground `mobile/assets/icon-foreground.png` (1024×1024). В `mobile/app.json` указаны `icon`, `android.adaptiveIcon.foregroundImage` и `backgroundColor: #FD6156`; версия и versionCode оставлены прежними.
- Цвет `#FD6156` получен медианой пикселей четырёх угловых областей исходной иконки и добавлен в `res/values/colors.xml`.
- Foreground: альфа-границы монеты на холсте 1024×1024 — `(221, 206)–(817, 819)` px (правая/нижняя граница exclusive). Центральная безопасная область 66% — `[174.08, 849.92]` px по обеим осям. Весь силуэт, включая надпись ONE, внутри неё; максимально видимый размер около 596×613 px против 675.84 px допустимого размера. Foreground уменьшен пропорционально, не растянут. Стандартная круглая маска не обрезает силуэт.
- Локальное превью трёх масок: `reports/screenshots/app-art-icon/icon-mask-preview.png` (круг, скруглённый квадрат, квадрат). Оно просмотрено локально.
- До правок нативных ресурсов сохранены 11 исходных файлов во временный каталог: `/private/var/folders/ws/2yz96w190q34htgtvflq4bm00000gn/T/opencode/app-art-icon-native-backup-rn69eib5`.

### Нативные файлы `mobile/android/` (не входят в Git)

Заменены:

```text
mobile/android/app/src/main/res/mipmap-mdpi/ic_launcher.webp
mobile/android/app/src/main/res/mipmap-mdpi/ic_launcher_round.webp
mobile/android/app/src/main/res/mipmap-hdpi/ic_launcher.webp
mobile/android/app/src/main/res/mipmap-hdpi/ic_launcher_round.webp
mobile/android/app/src/main/res/mipmap-xhdpi/ic_launcher.webp
mobile/android/app/src/main/res/mipmap-xhdpi/ic_launcher_round.webp
mobile/android/app/src/main/res/mipmap-xxhdpi/ic_launcher.webp
mobile/android/app/src/main/res/mipmap-xxhdpi/ic_launcher_round.webp
mobile/android/app/src/main/res/mipmap-xxxhdpi/ic_launcher.webp
mobile/android/app/src/main/res/mipmap-xxxhdpi/ic_launcher_round.webp
mobile/android/app/src/main/res/values/colors.xml
```

Добавлены:

```text
mobile/android/app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml
mobile/android/app/src/main/res/mipmap-anydpi-v26/ic_launcher_round.xml
mobile/android/app/src/main/res/mipmap-mdpi/ic_launcher_foreground.webp       # 108×108
mobile/android/app/src/main/res/mipmap-hdpi/ic_launcher_foreground.webp       # 162×162
mobile/android/app/src/main/res/mipmap-xhdpi/ic_launcher_foreground.webp      # 216×216
mobile/android/app/src/main/res/mipmap-xxhdpi/ic_launcher_foreground.webp     # 324×324
mobile/android/app/src/main/res/mipmap-xxxhdpi/ic_launcher_foreground.webp    # 432×432
```

### Изменения приложения и тесты

- `mobile/src/features/promotionsArtwork.ts`: список трёх локальных баннеров и отдельный `PROMOTION_CARDS`; `PERMANENT_OFFERS` не менялся.
- `mobile/src/features/home.tsx`: локальные баннеры идут перед серверными; изображения `contain` с исходными пропорциями; обобщены функции клонирования, перехода и автопрокрутки карусели.
- `mobile/app/(app)/(tabs)/promotions.tsx`: четыре собственные карточки всегда сверху, затем серверные акции; загрузка и ошибка не скрывают собственные карточки, пустое состояние серверных акций удалено.
- `mobile/app/(app)/promotion/[id].tsx`: локальные ID открывают описание без вызова `usePromotion`; серверный маршрут сохранён; для отсутствующего ID есть пустое состояние.
- `mobile/src/i18n/ru.ts`, `mobile/src/i18n/kz.ts`: подписи баннеров, отдельные ключи описаний и ключ неизвестной акции.
- Тесты обновлены в `mobile/tests/homeArtwork.test.tsx`; добавлен `mobile/tests/promotionsArtwork.test.tsx`.

### Итоговый прогон и СТОП

- Перед тестом `uptime`: `13:17  up 32 mins, 1 user, load averages: 3.44 5.19 12.32`; минутная нагрузка ниже порога.
- Команда: `npx jest` в `mobile/`, вывод перенаправлен в `/private/var/folders/ws/2yz96w190q34htgtvflq4bm00000gn/T/opencode/app-art-icon-final-jest.log`.
- Результат: **211 passed, 1 failed, 212 total**, exit code 1. Единственная ошибка — утверждение о порядке контейнера серверных карточек в новом тесте; это не таймаут. Поэтому повтор по правилу о таймаутах не выполнялся, исправлений после падения нет, дальнейшие проверки остановлены.
- `npx tsc --noEmit` и lint не запускались. Скриншоты реальных экранов на 360/412 px для RU/KK не созданы. Не запускались `expo prebuild`, сборка APK, публикация, commit или push.

#### Сырой вывод итогового `npx jest`

```text
FAIL tests/promotionsArtwork.test.tsx (6.226 s)
  ● promotions artwork › places server offers below own cards when the API returns offers

    expect(received).toEqual(expected) // deep equality

    - Expected  - 1
    + Received  + 0

      Array [
        "promotion-artwork-cards",
    -   "server-promotion-cards",
      ]

       96 |     mount(<PromotionsScreen />);
       97 |
    >  98 |     expect(screen.getAllByTestId(/^promotion-.*-cards$/).map(node => node.props.testID)).toEqual([
          |                                                                                          ^
       99 |       'promotion-artwork-cards',
      100 |       'server-promotion-cards',
      101 |     ]);

      at Object.toEqual (tests/promotionsArtwork.test.tsx:98:90)

PASS tests/cardScanner.test.tsx (7.556 s)
PASS tests/profileSave.test.tsx (9.546 s)
PASS tests/components.test.tsx
PASS tests/flows.test.tsx
PASS tests/cardBarcode.test.tsx
PASS tests/homeArtwork.test.tsx
PASS tests/core.test.ts
PASS tests/demo.test.ts
PASS tests/levels.test.tsx
PASS tests/wallet.test.tsx
PASS tests/transport.test.ts
PASS tests/session.test.ts
PASS tests/code128.test.ts
PASS tests/keyboardLift.test.ts

Test Suites: 1 failed, 14 passed, 15 total
Tests:       1 failed, 211 passed, 212 total
Snapshots:   0 total
Time:        15.177 s
Ran all test suites.
```

### Состояние Git после продолжения

`git diff --stat`:

```text
mobile/app.json                          |  5 ++
mobile/app/(app)/(tabs)/promotions.tsx   | 26 +++++++--
mobile/app/(app)/promotion/[id].tsx      | 41 +++++++++++++-
mobile/src/features/home.tsx             | 42 ++++++++++----
mobile/src/features/promotionsArtwork.ts | 66 ++++++++++++++++++++--
mobile/src/i18n/kz.ts                    |  8 ++-
mobile/src/i18n/ru.ts                    |  8 ++-
mobile/tests/homeArtwork.test.tsx        | 96 +++++++++++++++++++-------------
8 files changed, 228 insertions(+), 64 deletions(-)
```

Новый `mobile/tests/promotionsArtwork.test.tsx`, PNG-ассеты, иконки и этот отчёт не попадают в `git diff --stat`, так как они untracked. Нативные файлы `mobile/android/` игнорируются Git; их список приведён отдельно. До первой остановки уже существовали `C:/`, промпт, переданные оригиналы и `video/`; они сохранены без вмешательства.

## Осталось проверить

Сначала требуется отдельное решение куратора по падению не-таймаутного теста; самостоятельно исправлять и повторно запускать нельзя. После разрешённого продолжения остаются typecheck, lint, реальные экраны на 360/412 px в RU/KK и проверка, что ошибка/загрузка API показывают собственные карточки, а серверные карточки идут следом. На реальном Android-лаунчере и телефоне иконка не проверена. APK не собирался.

## Приёмка куратора — 2026-10-31

Падение теста разобрано и закрыто. Куратор сам внёс мелкие правки и повторил проверки. Этот раздел отменяет раздел «Осталось проверить» и замеры foreground выше.

### Что найдено и исправлено

1. **Тест:** регулярка `^promotion-.*-cards$` не могла совпасть с `server-promotion-cards`. Ошибка в тесте, не в экране. Регулярка исправлена.
2. **Высота карточек «Акций» и картинки описания (тесты этого не ловили):** у `Image` из `require` RN подставляет высоту файла, поэтому `aspectRatio` на самой картинке не работает. В demo-превью высота была 1085 px вместо 173,6, над первой карточкой — пустой экран. Исправлено как у баннеров: пропорция на контейнере, картинка `width/height: 100%` (`promotions.tsx`, `promotion/[id].tsx`). Тест теперь проверяет именно это.
3. **Адаптивная иконка:** прежний слой был вырезанной монетой на плоском `#FD6156`. Превью исполнителя показывало другое (исходник с свечением), а реальная сборка слоёв давала плоский фон, монету почти во всю иконку и белый край от вырезания. Причина — указание куратора взять цвет с края. `mobile/assets/icon-foreground.png` и пять `ic_launcher_foreground.webp` пересобраны из целой картинки: она занимает 76 из 108 dp по центру, вокруг продолжение её же краёв. `icon-mask-preview.png` теперь построен из настоящего слоя. Монета — около 47 dp в поперечнике при безопасной зоне 66 dp (оценка по превью). Прежний слой сохранён в scratchpad куратора, он очищается.
4. Удалён неиспользуемый импорт `Dictionary` в `promotionsArtwork.ts`.
5. Замечание к промпту: «центральные 66%» неточно. Безопасная зона Android — круг 66 dp из 108 (61%).

### Проверки куратора

- `npx jest`: **15 suites, 212 passed, 0 failed**, код 0.
- `npx tsc --noEmit`: код 0. `eslint .`: 0 ошибок, 1 давнее предупреждение (`useKeyboardLift.ts:62`).
- `git diff --check`: чисто.
- Demo-превью (встроенный браузер, `EXPO_PUBLIC_DEMO=1`, API подменён demo-режимом):
  - карусель: авто, кофемашина, стикеры, затем 3 demo-баннера, 6 точек, 288×125,4 px, автопрокрутка дошла до серверных;
  - «Акции» на 360 px: 4 карточки 320×173,6 px в порядке хиты, карта, неделя, свежие;
  - нажатие открывает `/promotion/art-card-bonus`, ошибок в консоли нет;
  - `/promotion/no-such-id` показывает «Акция не найдена»;
  - 412 px: без искажений.
- Кадры: `home-360-ru-coffee.jpg`, `promotions-360-ru.jpg`, `detail-360-ru.jpg`, `promotions-412-ru.jpg`.

### Не проверено

- KK на живых экранах: в вебе `LanguageSync` сбрасывает язык из demo-профиля. Тексты и паритет ключей покрыты тестом, вид не снят.
- Главная на 412 px и описание на 412 px не снимались.
- Вид на телефоне и на настоящем лаунчере, включая рамку Android для адаптивной иконки.
- Вывод о том, что ошибка высоты есть и на Android, сделан по логике `Image`; на устройстве старая версия не запускалась.
- Подарки и условия акций: тексты описаний — временная общая фраза.

### Версия

Куратор поднял `mobile/app.json` до **1.0.7 / versionCode 8**. Нативный `build.gradle` меняется при сборке. Промпт: `docs/PROMPT_APK_1_0_7_2026-10-31.md`.
