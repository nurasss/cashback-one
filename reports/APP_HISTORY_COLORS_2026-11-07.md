# Отчёт: цвета операций и скрытие склада в истории — 2026-11-07

**Дата:** 2026-11-07  
**Куратор проекта:** Antigravity  
**Статус:** Выполнено успешно, проверки пройдены (jest: 23 suites, 317 passed; tsc: 0 errors; eslint: clean)

---

## 1. Резюме изменений

В соответствии с `docs/PROMPT_APP_HISTORY_COLORS_2026-11-07.md`:

1. **Цвета в истории операций (`mobile/app/(app)/history.tsx`):**
   - **Начисление (`accrual`):**
     - сумма `+…` окрашена в зелёный цвет `theme.colors.success` (`#1F8A4C`);
     - кружок с иконкой плюса (`plus`) получил светло-зелёный фон `theme.colors.softSuccess` (`#E8F5EC`) и зелёную иконку `theme.colors.success` (`#1F8A4C`).
   - **Списание (`redemption`):**
     - сумма `−…` окрашена в красный цвет `theme.colors.error` (`#C8102E`);
     - кружок с иконкой минуса (`minus`) получил светло-красный фон `theme.colors.softError` (`#FFF1F0`) и красную иконку `theme.colors.error` (`#C8102E`).
   - Строка «Баланс …» и дата оставлены прежними (серый цвет `styles.muted` / `theme.colors.muted`).
   - Цвета одинаковы для всех клиентов (`keremet`, `cashbackone`, `example`) и не зависят от `primary_color` (у KeremEt основной цвет `#FA2247`, но начисления теперь строго зелёные, а списания — красные).

2. **Склад убран из истории:**
   - Строка `{item.store && <Text style={styles.muted} numberOfLines={1}>{item.store}</Text>}` полностью удалена из `mobile/app/(app)/history.tsx`.
   - Поле `store` в типах API (`mobile/src/types/api.ts`) и в ответах сервера/демо-моков оставлено без изменений, сервер не затрагивался.

3. **Проверка других экранов на операции/цвета:**
   - **Главная (`mobile/app/(app)/(tabs)/index.tsx`, `mobile/src/features/home.tsx`):** операции не отображаются; блок `BalanceHeader` показывает суммарный баланс и переход на `/history`.
   - **Уведомления (`mobile/app/(app)/(tabs)/notifications.tsx`):** отображаются пуш-уведомления типов `accrual` (иконка `plus`) и `redemption` (иконка `minus`). Для единообразия иконки и фоны кружков приведены к тем же цветам:
     - `accrual`: фон `softSuccess` (`#E8F5EC`), иконка `success` (`#1F8A4C`);
     - `redemption`: фон `softError` (`#FFF1F0`), иконка `error` (`#C8102E`);
     - другие типы (колокольчик `bell`): фон `softPrimary`, иконка `primary`.
   - **Экраны «Мой статус», «Мои карты», «QR-код»:** операции не отображаются.

4. **Тема (`mobile/src/theme/index.ts`):**
   - Добавлен цвет `softSuccess: '#E8F5EC'` в палитру `theme.colors`.

5. **Тесты:**
   - В `mobile/tests/historyPeriod.test.tsx` добавлен блок тестов `HistoryScreen transaction colors and store exclusion`:
     - проверка зелёного цвета суммы (`#1F8A4C`) и иконки начисления;
     - проверка красного цвета суммы (`#C8102E`) и иконки списания;
     - проверка независимости от цвета брендинга клиента (`branding.primary_color`);
     - проверка отсутствия названия склада в DOM при наличии поля `store` в ответе API;
   - В `mobile/tests/flows.test.tsx` добавлена проверка `expect(screen.queryByText('Shop 1')).toBeNull()` в тесте истории.

---

## 2. `git diff --stat mobile/`

```text
 mobile/app/(app)/(tabs)/notifications.tsx | 24 +++++----
 mobile/app/(app)/history.tsx              |  7 ++-
 mobile/src/theme/index.ts                 |  2 +-
 mobile/tests/flows.test.tsx               |  1 +
 mobile/tests/historyPeriod.test.tsx       | 85 +++++++++++++++++++++++++++++++
 5 files changed, 105 insertions(+), 14 deletions(-)
```

---

## 3. Детали изменений по файлам

### `mobile/src/theme/index.ts`
Добавлен `softSuccess: '#E8F5EC'`:
```diff
@@ -21,7 +21,7 @@ export const theme = {
   colors: {
     background: '#F4F4F6', surface: '#FFFFFF', text: '#111111', muted: '#6E6E76', placeholder: '#6C6C74', subtle: '#B4B4BA',
     primary: clientPrimary, primaryPressed: '#D0102F', onPrimary: '#FFFFFF', softPrimary: '#FDE9EC', tint: '#F8EEF0',
-    status: '#F8BEB2', border: '#E7E7EB', input: '#F2F2F4', error: '#C8102E', success: '#1F8A4C', softError: '#FFF1F0',
+    status: '#F8BEB2', border: '#E7E7EB', input: '#F2F2F4', error: '#C8102E', success: '#1F8A4C', softSuccess: '#E8F5EC', softError: '#FFF1F0',
     qr: '#FFFFFF', shadow: '#1B1B1F',
   },
```

### `mobile/app/(app)/history.tsx`
Начисления окрашены в `theme.colors.success`/`softSuccess`, списания — в `theme.colors.error`/`softError`, строка склада удалена:
```diff
@@ -47,16 +47,15 @@ export default function HistoryScreen() {
       renderItem={({ item, index }) => {
         const incoming = item.type === 'accrual';
         return <FadeIn index={Math.min(index, 6)} style={local.row}>
-          <View style={[local.icon, { backgroundColor: incoming ? theme.colors.softPrimary : '#EFEFF2' }]}>
-            <Icon name={incoming ? 'plus' : 'minus'} size={18} color={incoming ? theme.colors.primary : theme.colors.muted} />
+          <View style={[local.icon, { backgroundColor: incoming ? theme.colors.softSuccess : theme.colors.softError }]}>
+            <Icon name={incoming ? 'plus' : 'minus'} size={18} color={incoming ? theme.colors.success : theme.colors.error} />
           </View>
           <View style={{ flex: 1, gap: 2 }}>
             <Text style={local.title}>{transactionLabel(item.type, language)}</Text>
-            {item.store && <Text style={styles.muted} numberOfLines={1}>{item.store}</Text>}
             <Text style={styles.muted}>{dateText(item.occurred_at, language)}</Text>
           </View>
           <View style={{ alignItems: 'flex-end', gap: 2 }}>
-            <Text style={[local.amount, { color: incoming ? theme.colors.primary : theme.colors.text }]}>{incoming ? '+' : '−'}{pointsText(item.amount.replace('-', ''))}</Text>
+            <Text style={[local.amount, { color: incoming ? theme.colors.success : theme.colors.error }]}>{incoming ? '+' : '−'}{pointsText(item.amount.replace('-', ''))}</Text>
             <Text style={styles.muted}>{t('balanceAfter')} {pointsText(item.balance_after)}</Text>
           </View>
         </FadeIn>;
```

### `mobile/app/(app)/(tabs)/notifications.tsx`
Иконки уведомлений начисления и списания приведены к аналогичным цветам:
```diff
@@ -25,15 +25,21 @@ export default function NotificationsScreen() {
         {notifications.isPending ? <Loading /> : notifications.isError ? <ErrorNotice error={notifications.error} retry={() => { void notifications.refetch(); }} /> : null}
       </>}
       ListEmptyComponent={notifications.isSuccess ? <EmptyState icon="bell" title={t('noNotifications')} /> : null}
-      renderItem={({ item, index }) => <FadeIn index={Math.min(index, 6)}><View style={local.item} accessible accessibilityLabel={`${item.is_unread ? t('newBadge') + '. ' : ''}${item.title}. ${item.body}`}>
-        <View style={local.icon}><Icon name={item.kind === 'accrual' ? 'plus' : item.kind === 'redemption' ? 'minus' : 'bell'} size={18} color={theme.colors.primary} /></View>
-        <View style={{ flex: 1, gap: 4 }}>
-          <Text style={local.title}>{item.title}</Text>
-          <Text style={local.body}>{item.body}</Text>
-          <Text style={styles.muted}>{dateText(item.created_at, language)}</Text>
-        </View>
-        {item.is_unread && <NewDot />}
-      </View></FadeIn>} />
+      renderItem={({ item, index }) => {
+        const isAccrual = item.kind === 'accrual';
+        const isRedemption = item.kind === 'redemption';
+        const iconBg = isAccrual ? theme.colors.softSuccess : isRedemption ? theme.colors.softError : theme.colors.softPrimary;
+        const iconColor = isAccrual ? theme.colors.success : isRedemption ? theme.colors.error : theme.colors.primary;
+        return <FadeIn index={Math.min(index, 6)}><View style={local.item} accessible accessibilityLabel={`${item.is_unread ? t('newBadge') + '. ' : ''}${item.title}. ${item.body}`}>
+          <View style={[local.icon, { backgroundColor: iconBg }]}><Icon name={isAccrual ? 'plus' : isRedemption ? 'minus' : 'bell'} size={18} color={iconColor} /></View>
+          <View style={{ flex: 1, gap: 4 }}>
+            <Text style={local.title}>{item.title}</Text>
+            <Text style={local.body}>{item.body}</Text>
+            <Text style={styles.muted}>{dateText(item.created_at, language)}</Text>
+          </View>
+          {item.is_unread && <NewDot />}
+        </View></FadeIn>;
+      }} />
   </SafeAreaView>;
```

---

## 4. Сырой вывод проверок

### 4.1. Baseline (до правок)

#### `npx jest --runInBand`
```text
PASS tests/clientConfig.test.tsx
PASS tests/profileSave.test.tsx
PASS tests/qrScreen.test.tsx
PASS tests/flows.test.tsx
PASS tests/appUpdate.test.tsx
PASS tests/cacheRefresh.test.tsx
PASS tests/core.test.ts
PASS tests/push.test.tsx
PASS tests/noCardNotice.test.tsx
PASS tests/promotionsArtwork.test.tsx
PASS tests/homeArtwork.test.tsx
PASS tests/historyPeriod.test.tsx
PASS tests/cityCustom.test.tsx
PASS tests/wallet.test.tsx
PASS tests/components.test.tsx
PASS tests/avatar.test.tsx
PASS tests/loginScreen.test.tsx
PASS tests/serverContentAndCache.test.tsx
PASS tests/demo.test.ts
PASS tests/levels.test.tsx
PASS tests/keyboardLift.test.ts
PASS tests/session.test.ts
PASS tests/transport.test.ts

Test Suites: 23 passed, 23 total
Tests:       315 passed, 315 total
Snapshots:   0 total
Time:        19.54 s
Ran all test suites.
```

#### `npx tsc --noEmit`
```text
Exit code: 0
No errors.
```

#### `npx eslint .`
```text
/Users/nuras/Desktop/cashback-one/mobile/src/components/useKeyboardLift.ts
  62:20  warning  The ref value 'generation.current' will likely have changed by the time this effect cleanup function runs. If this ref points to a node rendered by React, copy 'generation.current' to a variable inside the effect, and use that variable in the cleanup function  react-hooks/exhaustive-deps

✖ 1 problem (0 errors, 1 warning)
Exit code: 0
```
*(Предупреждение существовало до начала задачи)*

---

### 4.2. Контрольный прогон (после правок)

#### `npx jest --runInBand --forceExit`
```text
PASS tests/flows.test.tsx
PASS tests/clientConfig.test.tsx
PASS tests/profileSave.test.tsx
PASS tests/historyPeriod.test.tsx
PASS tests/components.test.tsx
PASS tests/appUpdate.test.tsx
PASS tests/noCardNotice.test.tsx
PASS tests/loginScreen.test.tsx
PASS tests/cityCustom.test.tsx
PASS tests/qrScreen.test.tsx
PASS tests/avatar.test.tsx
PASS tests/serverContentAndCache.test.tsx
PASS tests/core.test.ts
PASS tests/cacheRefresh.test.tsx
PASS tests/push.test.tsx
PASS tests/homeArtwork.test.tsx
PASS tests/wallet.test.tsx
PASS tests/promotionsArtwork.test.tsx
PASS tests/demo.test.ts
PASS tests/levels.test.tsx
PASS tests/transport.test.ts
PASS tests/session.test.ts
PASS tests/keyboardLift.test.ts

Test Suites: 23 passed, 23 total
Tests:       317 passed, 317 total
Snapshots:   0 total
Time:        22.253 s
Ran all test suites.
Exit code: 0
```

#### `npx tsc --noEmit`
```text
Exit code: 0
No errors.
```

#### `npx eslint .`
```text
/Users/nuras/Desktop/cashback-one/mobile/src/components/useKeyboardLift.ts
  62:20  warning  The ref value 'generation.current' will likely have changed by the time this effect cleanup function runs. If this ref points to a node rendered by React, copy 'generation.current' to a variable inside the effect, and use that variable in the cleanup function  react-hooks/exhaustive-deps

✖ 1 problem (0 errors, 1 warning)
Exit code: 0
```

---

## 5. Снимок экрана (web-preview, 390 px, demo, клиент `keremet`)

Снимок сохранён по пути: `reports/app-history-colors-2026-11-07/history.png`

| Файл | Разрешение | Размер | SHA-256 | Описание |
|---|---|---|---|---|
| [`history.png`](file:///Users/nuras/Desktop/cashback-one/reports/app-history-colors-2026-11-07/history.png) | 1000×1304 px (эмуляция 390 px) | 163 806 байт | `1214c16b77731a1a08dc5a02616510f5cde16b8da20b6eaf240ac4960405a6a3` | Экран истории начислений Keremet Bonus: начисления с зелёной суммой `+2 450,00` и зелёной иконкой плюса, списание с красной суммой `−1 500,00` и красной иконкой минуса. Фильтр «Все» выбран. Название склада полностью отсутствует. |

---

## 6. Ограничения

- APK не собирался.
- Версии (`package.json`, `app.json`) не изменялись.
- Папка `android/` не затрагивалась.
- Сервер, БД и панель администрирования не затрагивались.
- `git commit` и `git push` не выполнялись.
