# Промпт исполнителю (Mac): исправления после приёмки правок приложения — 2026-11-02

Репозиторий `/Users/nuras/Desktop/cashback-one`, папки `mobile/` и `backend/`. Общайся и пиши отчёт по-русски. Прочитай `AGENTS.md` (раздел о проверках и ограничениях), `docs/PROMPT_APP_POLISH_2026-11-02.md` и `reports/APP_POLISH_ACCEPTANCE_2026-11-02.md`.

**Упало или неожиданно — СТОП и сырой вывод; без самостоятельных исправлений и повторных мутаций; секреты и персональные данные скрыть.**

Команды, которых нет в окружении, сразу заменяй (`rg` → `grep`). Сбой твоего вспомогательного скрипта тоже не повод для СТОП. Backend запускай через `backend/.venv/bin/python`.

**Без APK, без смены версии, без деплоя, без миграций, без commit/push.** Сборку по `docs/PROMPT_APK_1_0_10_2026-11-02.md` не запускай.

Правки из рабочего дерева не откатывать: чинить только перечисленное ниже. Окно обновления (`UpdateNotice.tsx`, `appUpdate.ts`, `_layout.tsx`) не трогать.

## 1. Размер иллюстрации в `ArtworkOfferCard` (главный дефект)

`mobile/src/features/home.tsx`. На телефоне `Image` с `require` получает `width` и `height` из файла (`react-native/Libraries/Image/Image.android.js:379-381`, `Image.ios.js:133-135`). В `styles.artworkSideImage` их нет, поэтому картинка рисуется 493×360 dp и обрезается карточкой, а `top`, `bottom` и `aspectRatio` не работают. Jest и веб этого не показывают.

Позиция и пропорция переходят на обёртку:

```tsx
<View style={[styles.artworkSide, { aspectRatio: card.sideAspectRatio }]}>
  <Image testID={`promotion-image-${card.id}`} source={card.sideImage} style={styles.artworkSideImage} resizeMode="contain" accessibilityIgnoresInvertColors />
</View>
```

```ts
artworkSide: { position: 'absolute', right: 0, top: 0, bottom: 0, zIndex: 0 },
artworkSideImage: { width: '100%', height: '100%' },
```

Тест в `mobile/tests/promotionsArtwork.test.tsx`: у `promotion-image-*` стиль `{ width: '100%', height: '100%' }`, `aspectRatio` и `position: 'absolute'` у родителя (`.parent` по дереву до `View`). Проверка `aspectRatio` на самом `Image` исключена.

## 2. Чистка четырёх `promo-*-side.png`

В текущих файлах остались куски исходной красной плашки (на `promo-card-bonus-side.png` с обрывками текста) и тонкая светлая кайма справа и снизу.

Одноразовый скрипт на Pillow во временной папке вне репозитория. Запустить **один раз**, на текущие файлы:

1. `crop((0, 0, w - 10, h - 10))`.
2. Маска: прямоугольник `(0, 0, rw, rh)` равен 0, остальное 255, затем `ImageFilter.GaussianBlur(4)`. Новая альфа: `Image.composite(alpha, Image.new('L', size, 0), mask)`.

| Файл | rw | rh | Итоговый размер | `sideAspectRatio` |
|---|---|---|---|---|
| `promo-hits-discount-side.png` | 70 | 44 | 483×350 | `483 / 350` |
| `promo-card-bonus-side.png` | 190 | 44 | 542×350 | `542 / 350` |
| `promo-weekly-side.png` | 26 | 54 | 394×350 | `394 / 350` |
| `promo-fresh-products-side.png` | 100 | 54 | 448×350 | `448 / 350` |

Куратор проверил эти числа на копиях: остатков и каймы нет. Обнови `sideAspectRatio` в `mobile/src/features/promotionsArtwork.ts`. Исходные `promo-*.png` не менять.

Проверка: наложи каждый файл на фон карточки на поле 984×336 и открой результат. Лучи и товары не должны быть задеты. Файлы проверки держи вне репозитория.

## 3. «Другой город»: поле должно быть пустым

`mobile/src/features/profile.tsx`, `FieldSheet`. Сейчас `setValue(initial && initial !== customOption.value ? initial : '')` подставляет уже сохранённый город. Нужно `setValue('')`.

Тесты в `mobile/tests/cityCustom.test.tsx`: при сохранённом «Алматы» поле пустое; при сохранённом «Другой город» строка отмечена, нажатие открывает пустое поле и не вызывает сохранение.

## 4. Предустановки периода: без верхней границы

`mobile/src/features/historyPeriod.ts`. Для `7d`, `30d`, `90d` верхней границы нет: вернуть только `{ from }`. Параметр `date_to` в запрос не идёт. Свой период не менять.

Тесты в `mobile/tests/historyPeriod.test.tsx`:

- `historyRange`: `to` равен `undefined` у всех предустановок;
- смена года: `now = new Date(2027, 0, 3)`, `'7d'` даёт начало `new Date(2026, 11, 28)`;
- смена месяца: `now = new Date(2026, 2, 1)`, `'7d'` даёт начало `new Date(2026, 1, 23)`;
- свой период `2026-12-31`–`2026-12-31`: конец `new Date(2027, 0, 1)`.

## 5. Подсказка дат в `PeriodSheet`

`mobile/src/features/PeriodSheet.tsx`. Вместо зашитого `ДД.ММ.ГГГГ` оба поля используют `t('birthDatePh')`. Тест: в KK виден `kz.birthDatePh`.

## 6. Экстремальная дата даёт 500

`backend/app/services/wallet_service.py`. `as_utc` на `0001-01-01T00:00:00+14:00` бросает `OverflowError`. Перед фильтрами приведи `date_from` и `date_to` к UTC в `try/except OverflowError`, при ошибке `AppError` `INVALID_PERIOD`, 422, сообщение без значения даты. Проверка владельца остаётся первой. В запросе и сравнении используй уже приведённые значения.

Тесты в `backend/tests/test_customer_wallet.py`: `date_from=0001-01-01T00:00:00%2B14:00` и `date_to=9999-12-31T23:59:59-14:00` дают 422 `INVALID_PERIOD`.

## 7. Тесты, которых нет из прежнего задания

Добавь в `mobile/tests/historyPeriod.test.tsx` проверки на настоящем `HistoryScreen`:

- «Всё время» после выбранного периода: запрос без `date_from` и `date_to`;
- период вместе с фильтром: в URL есть и `type=redemption`, и `date_from`;
- «Ещё»: ответ с `has_more: true` и `next_cursor`, нажатие `ru.more`, второй запрос содержит `cursor` и те же `date_from` и `date_to`;
- отмена шторки: нажатие на подложку с подписью `ru.cancel` не меняет выбранный период и не создаёт запрос.

## Не трогать

`admin/`, `agent/`, лендинг, `mobile/android/`, `app.json`, `package.json`, lock-файлы, `backend/app/core/phone.py`, миграции, `C:/`, `video/`. Новые зависимости не добавлять.

## Ограничения

- Не запускать `expo prebuild`, `mobile/scripts/build-apk.sh`, `scripts/upload_admin.py`, `upload_apk.py`.
- Не подключаться к VPS и хостингу. Не печатать `.env*`, телефоны и коды.
- Не использовать внешние сервисы анализа и генерации изображений, никуда не загружать файлы и снимки. Не делать снимков всего экрана.
- Тесты — перенаправлением в файл, таймаут инструмента не меньше 600 с. Перед запуском `uptime`: при load average за 1 минуту выше 12 подожди до 5 минут. Если упали только таймаутом `Exceeded timeout`, один раз повтори упавшие файлы и приложи оба вывода. Упал повтор или ошибка другая — СТОП.

## Проверки

1. **Baseline до правок:** `git rev-parse --short HEAD` → `339e208`; `npx jest` → 240 passed; `npx tsc --noEmit` чисто; `npx eslint .` 0 ошибок; pytest → 377 passed, 36 skipped. Иное — СТОП.
2. **После правок:** `npx jest`, `npx tsc --noEmit`, `npx eslint .`, `backend/.venv/bin/python -m pytest backend/tests -q -ra`, `backend/.venv/bin/python -m ruff check backend/app backend/tests/test_customer_wallet.py`. 0 failed.
3. `git status`, `git diff --stat`: только `mobile/`, `backend/` и отчёт.

## Отчёт

`reports/APP_POLISH_FIXES_2026-11-02.md`:

- изменения по файлам, размеры четырёх PNG, сколько тестов добавлено и изменено;
- **сырые выводы** всех проверок, baseline и итог, включая последние строки jest и pytest;
- настоящий HEAD; значения фонов и значков описывай только по коду;
- раздел **«Не проверено»**: вид карточек, шторки периода и кнопки QR на телефоне, запись на PostgreSQL, деплой backend.

Не пиши «полностью готово» без доказательств.
