# Промпт исполнителю (Mac): четыре правки приложения — 2026-11-02

Репозиторий `/Users/nuras/Desktop/cashback-one`, папки `mobile/` и `backend/`. Общайся и пиши отчёт по-русски. Прочитай `AGENTS.md` (раздел о проверках и ограничениях).

**Упало или неожиданно — СТОП и сырой вывод; без самостоятельных исправлений и повторных мутаций; секреты и персональные данные скрыть.**

Команды, которых нет в окружении, сразу заменяй (`rg` → `grep`). Сбой твоего вспомогательного скрипта тоже не повод для СТОП. Backend запускай через `backend/.venv/bin/python`.

**Без APK, без смены версии, без деплоя, без миграций, без commit/push.** Сборку по `docs/PROMPT_APK_1_0_10_2026-11-02.md` не запускай.

В рабочем дереве лежат принятые правки окна обновления (`UpdateNotice.tsx`, `appUpdate.ts`, `_layout.tsx`, i18n). Их не откатывать и не менять.

Владелец проверил 1.0.9 на телефоне и прислал четыре замечания.

## 1. Высота карточек на экране «Акции»

Четыре постоянные карточки (`PROMOTION_CARDS`, `app/(app)/(tabs)/promotions.tsx`) сейчас картинки 2000×1085 и в два раза выше карточек из кабинета (`OfferCard wide`, `minHeight: 112`). Нужна **та же высота и тот же вид**, что у `OfferCard wide`.

Просто уменьшить нельзя: текст вшит в картинку и станет нечитаемым. Поэтому слева настоящий текст, справа иллюстрация.

**Ассеты.** Одноразовым скриптом на Pillow во временной папке вне репозитория создай `mobile/assets/promotions/promo-*-side.png`. Исходные `promo-*.png` не менять и не удалять: они нужны экрану описания `/promotion/[id]`.

| Новый файл | Источник | Область (left, top, right, bottom) | Фон карточки |
|---|---|---|---|
| `promo-hits-discount-side.png` | `promo-hits-discount.png` | 950, 325, 1990, 1085 | `#FEE4E8` |
| `promo-card-bonus-side.png` | `promo-card-bonus.png` | 825, 325, 1990, 1085 | `#ECEEF0` |
| `promo-weekly-side.png` | `promo-weekly.png` | 1025, 260, 1950, 1085 | `#EEEDF0` |
| `promo-fresh-products-side.png` | `promo-fresh-products.png` | 940, 260, 1990, 1085 | `#FEE4E8` |

Обработка: уменьшить до высоты 360 px с LANCZOS, RGBA. Левые 15 % ширины и верхние 10 % высоты плавно увести в прозрачность, чтобы не было видно границы с фоном карточки. Текста и стрелки из исходной картинки в области быть не должно: открой каждый результат и проверь.

**Компонент.** В `mobile/src/features/home.tsx` рядом с `OfferCard` добавь `ArtworkOfferCard`, на тех же стилях `styles.offer`, `styles.offerWide`, `styles.offerBadge`, `styles.offerBadgeText`, `styles.offerTitle`, `styles.offerTitleWide`. Отличия:

- фон карточки из таблицы;
- иллюстрация: `position: 'absolute', right: 0, top: 0, bottom: 0`, ширина задаётся `aspectRatio` по размеру файла, `resizeMode: 'contain'`, прижата к правому нижнему углу;
- значок в плашке: `percent`, `card`, `gift`, `cart` соответственно.

В `PromotionCard` добавь `sideImage`, `sideAspectRatio`, `background`, `badgeKey`, `titleTextKey`, `icon`. `titleKey` и `bodyKey` оставь: они нужны экрану описания и подписи для чтения с экрана.

На экране «Акции» используй `ArtworkOfferCard`. Сохрани `testID` `promotion-card-<id>` и `promotion-image-<id>` и `accessibilityLabel`. Обнови тесты в `mobile/tests/promotionsArtwork.test.tsx`, которые проверяют прежнюю пропорцию. Экран `/promotion/[id]` и главная не меняются.

i18n:

| Ключ | RU | KK |
|---|---|---|
| `promoHitsBadge` | Скидка на хиты | Хит тауарларға жеңілдік |
| `promoHitsTitle` | Покупайте выгодно | Тиімді сатып алыңыз |
| `promoWeeklyBadge` | Акция недели | Апта акциясы |
| `promoWeeklyTitle` | Товары по лучшим ценам | Ең тиімді бағадағы тауарлар |
| `promoCardBadge` | Выгодно с картой | Картамен тиімді |
| `promoCardTitle` | Больше бонусов | Көбірек бонустар |
| `promoFreshBadge` | Суперцена | Супер баға |
| `promoFreshTitle` | Свежие продукты | Балғын өнімдер |

## 2. «Другой город»: ручной ввод

Сейчас выбор строки сохраняет сам текст «Другой город». Нужно поле для названия. **Карта в эту задачу не входит.**

`FieldSheet` в `mobile/src/features/profile.tsx`: необязательный проп `customOption?: { value: string; placeholder: string; maxLength: number; validate: (value: string) => string | null }`.

- Нажатие на строку с `value === customOption.value` ничего не сохраняет. Шторка переходит к полю ввода с тем же заголовком и кнопкой «Готово», поле пустое, клавиатура открыта.
- «Готово» сохраняет обрезанный текст через обычный `onDone`, с той же защитой от повторного нажатия и показом ошибки.
- Остальные строки сохраняются сразу, как раньше. Другие шторки не меняются.

`profile.tsx`: для `city` передай `customOption` со значением `ru.cityOption22`, `maxLength: 100` (предел backend), проверкой «после обрезки не меньше 2 символов», иначе `invalidCity`. Backend не меняется.

Уже сохранённое своё название `cityOptions` показывает первой строкой: так и остаётся. Если у покупателя сохранён сам текст «Другой город», строка отмечена, нажатие открывает поле.

i18n: `cityCustomPh` «Название города» / «Қала атауы», `invalidCity` «Введите название города» / «Қала атауын енгізіңіз».

## 3. Выбор периода в истории

Сейчас API не умеет фильтровать по датам, а история постраничная, поэтому фильтр только на телефоне не подходит.

**Backend.** `backend/app/api/customer_wallet.py`, `list_card_transactions`, и `get_customer_card_transactions` в `backend/app/services/wallet_service.py`:

- необязательные `date_from: datetime` и `date_to: datetime` в Query. Без них ответ как раньше;
- без часового пояса: 422 `INVALID_PERIOD`. `date_from >= date_to`: 422 `INVALID_PERIOD`;
- условие: `occurred_at >= date_from` и `occurred_at < date_to`, граница `date_to` не включается;
- фильтр работает вместе с `type` и `cursor`: страницы не теряют и не повторяют строк;
- проверка владельца картой остаётся первой. Индекс `ix_transactions_card_id_occurred_at` уже есть, миграция не нужна.

**Приложение.**

1. Новый файл `mobile/src/features/historyPeriod.ts`: тип `HistoryPeriod` (`'all' | '7d' | '30d' | '90d' | { from: string; to: string }`, даты в виде `YYYY-MM-DD`) и чистая `historyRange(period, now)`, возвращающая `{ from?: string; to?: string }` в виде ISO UTC.
   - Границы — полночь **местного** дня телефона, затем `toISOString()`.
   - `'7d'`: начало дня 6 дней назад, сегодняшний день входит. `'30d'`: 29 дней назад. `'90d'`: 89 дней назад. Верхней границы нет.
   - Свой период: `to` — полночь дня **после** выбранного, выбранный день входит целиком.
2. `useHistory(id, filter, period)` в `mobile/src/api/wallet.ts`: период входит в `queryKey`, `date_from` и `date_to` проходят через `encodeURIComponent`. Границы считаются внутри `queryFn`, а не при рендере.
3. `app/(app)/history.tsx`: под фильтрами второй ряд `Chip` в горизонтальном `ScrollView`: «Всё время», «7 дней», «30 дней», «3 месяца», «Свой период». По умолчанию «Всё время». Смена периода показывает `Loading`, как при первой загрузке.
4. Новая шторка `PeriodSheet` в `mobile/src/features/`, оформление как у `FieldSheet`, с `useKeyboardLift`. Два поля с маской `birthDateInputText`, проверка через `birthDateToApi`. Кнопка «Показать».
   - неверная дата или дата позже сегодняшней: `invalidDate`;
   - начало позже конца: `invalidPeriod`;
   - отмена не меняет выбранный период.
   - После выбора подпись чипа: `01.10.2026 – 15.10.2026`.
5. Пустой результат при выбранном периоде: `noHistoryPeriod`. Без периода — прежний `noHistory`.
6. `mobile/src/demo/mockApi.ts`: учитывай `date_from` и `date_to`, без обращения к настоящему API.

i18n:

| Ключ | RU | KK |
|---|---|---|
| `periodAll` | Всё время | Барлық уақыт |
| `period7` | 7 дней | 7 күн |
| `period30` | 30 дней | 30 күн |
| `period90` | 3 месяца | 3 ай |
| `periodCustom` | Свой период | Өз кезеңі |
| `periodFrom` | Начало периода | Кезең басы |
| `periodTo` | Конец периода | Кезең соңы |
| `periodApply` | Показать | Көрсету |
| `invalidPeriod` | Дата начала позже даты окончания | Басталу күні аяқталу күнінен кеш |
| `noHistoryPeriod` | За этот период операций нет | Бұл кезеңде операциялар жоқ |

## 4. Артефакт под кнопкой QR

`mobile/src/components/TabBar.tsx`, `styles.qrButton`. На Android под нижним краем круга виден светлый серп: это тень от `elevation` с цветным `shadowColor`. Убери из `qrButton` `shadowColor`, `shadowOpacity`, `shadowRadius`, `shadowOffset`, `elevation`. Круг станет плоским. Размер, цвет, положение и `qrButtonSelected` не менять. Тень панели `styles.bar` не трогать.

## Не трогать

`admin/`, `agent/`, лендинг, `mobile/android/`, `app.json`, `package.json`, lock-файлы, `backend/app/core/phone.py`, миграции, `C:/`, `video/`. Новые зависимости не добавлять.

## Ограничения

- Не запускать `expo prebuild`, `mobile/scripts/build-apk.sh`, `scripts/upload_admin.py`, `upload_apk.py`.
- Не подключаться к VPS и хостингу. Не печатать `.env*`, телефоны и коды.
- **Не использовать внешние сервисы анализа и генерации изображений и не загружать никуда файлы и снимки.** Не делать снимков всего экрана.
- Тесты — перенаправлением в файл, таймаут инструмента не меньше 600 с. Перед запуском `uptime`: при load average за 1 минуту выше 12 подожди до 5 минут. Если упали только таймаутом `Exceeded timeout`, один раз повтори упавшие файлы и приложи оба вывода. Упал повтор или ошибка другая — СТОП.
- В вебе экраны с `useKeyboardLift` падают (`Keyboard.metrics`). Это известно, не чини.

## Проверки

1. **Baseline до правок:** `npx jest` → 227 passed, `npx tsc --noEmit` чисто, `npx eslint .` 0 ошибок, `backend/.venv/bin/python -m pytest backend/tests -q -ra` → 373 passed, 36 skipped. Иное — СТОП.
2. **Новые тесты в `mobile`:**
   - акции: четыре карточки с текстом и иллюстрацией, `minHeight` как у `OfferCard wide`, RU и KK, нажатие открывает описание;
   - город: «Другой город» не вызывает сохранение и показывает поле, текст сохраняется обрезанным, один символ даёт `invalidCity`, обычный город сохраняется сразу;
   - `historyRange`: все предустановки, свой период, включение крайних дней, смена месяца и года;
   - история: смена периода даёт новый запрос с параметрами, «Всё время» запрос без них, вместе с `filter`, «Ещё» передаёт те же границы, `noHistoryPeriod`, неверная дата, начало позже конца, будущая дата, отмена;
   - `TabBar`: в стиле `qrButton` нет `elevation`.
3. **Новые тесты в `backend/tests/test_customer_wallet.py`:** без параметров как раньше; только `date_from`; только `date_to`; граница `date_to` не включена; вместе с `type`; постраничный обход с периодом без потерь и повторов; дата без пояса и `date_from >= date_to` дают 422; чужая карта 404.
4. **После правок:** `npx jest`, `npx tsc --noEmit`, `npx eslint .`, pytest, `ruff check backend/app backend/tests/test_customer_wallet.py`. 0 failed.
5. `git status`, `git diff --stat`: только `mobile/`, `backend/` и отчёт.

## Отчёт

`reports/APP_POLISH_2026-11-02.md`: изменения по файлам, размеры четырёх новых PNG, сырые выводы проверок. Укажи, сколько тестов добавлено и изменено.

**Не проверено на этом этапе:** вид карточек, шторки периода и кнопки QR на телефоне, деплой backend.

Не пиши «полностью готово» без доказательств.
