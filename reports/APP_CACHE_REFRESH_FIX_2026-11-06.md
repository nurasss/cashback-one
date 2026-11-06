# Отчёт: Исправление фонового обновления кеша баннеров, акций и текстов — 2026-11-06

## 1. Что сделано

1. **Фоновое обновление кеша при монтировании (`initialDataUpdatedAt`)**:
   - В `mobile/src/api/app.ts` для хуков `usePromotions` и `useAppContent` добавлена передача `initialDataUpdatedAt`:
     - `usePromotions`: `initialDataUpdatedAt: () => getCachedPromotions(userId)?.cachedAt ?? 0`
     - `useAppContent`: `initialDataUpdatedAt: () => (effectiveBusinessId ? (getCachedAppContent(userId, effectiveBusinessId)?.cachedAt ?? 0) : 0)`
   - Теперь кеш показывается пользователю мгновенно (без пустого экрана и без индикатора ожидания), но поскольку React Query видит `initialDataUpdatedAt` (время реальной записи в кеш, которое больше 30 секунд `staleTime`, либо 0 при первом запуске), запрос в фоне уходит на сервер при открытии экрана и свежий ответ заменяет кеш.
   - Офлайн-режим сохранён: при недоступности сети ошибки перехватываются, кеш остаётся на экране, ошибки не всплывают.
   - ETag/304 сохранён: при неизменных данных сервер отвечает 304, данные кеша остаются активными.
   - В `mobile/src/storage/appCache.ts` в `setCachedAppContent` и `setCachedPromotions` добавлен опциональный параметр `cachedAt?: number = Date.now()`, обеспечивающий 100% обратную совместимость и возможность тестирования устаревания записей.

2. **Обновление потягиванием вниз на главной (`RefreshControl`)**:
   - В `mobile/app/(app)/(tabs)/index.tsx` на `ScrollView` добавлен `RefreshControl`:
     - `refreshing`: флаг `promotions.isRefetching || cards.isRefetching || profile.isRefetching || appContent.isRefetching`
     - `onRefresh`: параллельный вызов `refetch()` для акций (`promotions`), карт (`cards`), профиля (`profile`) и текстов/магазинов (`appContent`)
     - `tintColor: theme.colors.primary` аналогично вкладке «Акции» (`promotions.tsx`).

3. **Анализ возврата приложения из фона (`focusManager`)**:
   - В `mobile/src/auth/provider.tsx` настроена подписка:
     ```ts
     useEffect(() => {
       const subscription = AppState.addEventListener('change', state => focusManager.setFocused(state === 'active'));
       return () => subscription.remove();
     }, []);
     ```
   - Проверка показала:
     - При переходе приложения в фон (`state === 'background'`) `focusManager.setFocused(false)` переводит менеджер фокуса в неактивное состояние.
     - При возврате приложения на передний план (`state === 'active'`) `focusManager.setFocused(true)` оповещает `QueryClient` (`this.#queryCache.onFocus()`).
     - Для всех активных запросов, у которых данные устарели (`now - dataUpdatedAt > staleTime (30s)`), TanStack React Query автоматически запускает фоновый повторный запрос (`refetch`).
     - До добавления `initialDataUpdatedAt` данные из кеша при запуске считались полученными «прямо сейчас» (`Date.now()`), поэтому если приложение сворачивалось и разворачивалось вскоре после старта, `focusManager` не считал их устаревшими. Теперь же, когда `initialDataUpdatedAt` отражает реальный возраст кеша (`cachedAt`), `focusManager` корректно определяет устаревание и перезапрашивает свежие акции и тексты. Поведение подтверждено тестом в `cacheRefresh.test.tsx`.

4. **Тесты (`mobile/tests/cacheRefresh.test.tsx`)**:
   - Кеш с баннерами есть: при монтировании `Home` запрос `/me/promotions` уходит в фоне, и свежий ответ сервера заменяет кешированные данные;
   - Сервер недоступен: показывается кеш, ошибки на экране нет (`ErrorNotice` не отображается);
   - Ответ 304 Not Modified: данные кеша сохраняются и остаются на экране;
   - `app-content`: фоновое обновление устаревшего кеша текстов и магазинов, сохранение при ошибках сети и на 304;
   - Потягивание вниз на главной (`RefreshControl`): параллельно отправляет повторные запросы для `/me/promotions`, `/me/cards`, `/me/profile` и `/me/app-content`;
   - Общий клиент (`cashbackone`): запросы уходят без `business_id`, кеш изолирован;
   - Клиент `keremet`: запросы уходят с `business_id=f3a0cf2d-4a1d-4c0e-af27-b363054394f0`, кеш изолирован по бизнесу, при наличии старого пустого кеша баннеры заменяются новыми серверными баннерами Keremet;
   - Возврат из фона (`focusManager`): при переходе в `focused=true` устаревший запрос акций автоматически перезапрашивается.

---

## 2. Сырой вывод проверок ДО правок

### 2.1. `npx jest --runInBand` (baseline)

```
PASS tests/appUpdate.test.tsx
PASS tests/push.test.tsx
PASS tests/profileSave.test.tsx
PASS tests/clientConfig.test.tsx
PASS tests/historyPeriod.test.tsx
PASS tests/flows.test.tsx
PASS tests/qrScreen.test.tsx
PASS tests/core.test.ts
PASS tests/serverContentAndCache.test.tsx
PASS tests/cardScanner.test.tsx
PASS tests/homeArtwork.test.tsx
PASS tests/cityCustom.test.tsx
PASS tests/components.test.tsx
PASS tests/wallet.test.tsx
PASS tests/avatar.test.tsx
PASS tests/promotionsArtwork.test.tsx
PASS tests/session.test.ts
PASS tests/loginScreen.test.tsx
PASS tests/levels.test.tsx
PASS tests/demo.test.ts
PASS tests/transport.test.ts
PASS tests/keyboardLift.test.ts

Test Suites: 22 passed, 22 total
Tests:       301 passed, 301 total
Snapshots:   0 total
Time:        22.678 s, estimated 40 s
Ran all test suites.
```

### 2.2. `npx tsc --noEmit && npx eslint .` (baseline)

```
/Users/nuras/Desktop/cashback-one/mobile/src/components/useKeyboardLift.ts
  62:20  warning  The ref value 'generation.current' will likely have changed by the time this effect cleanup function runs. If this ref points to a node rendered by React, copy 'generation.current' to a variable inside the effect, and use that variable in the cleanup function  react-hooks/exhaustive-deps

✖ 1 problem (0 errors, 1 warning)
```

---

## 3. Сырой вывод проверок ПОСЛЕ правок

### 3.1. `npx jest --runInBand`

```
PASS tests/appUpdate.test.tsx (5.225 s)
PASS tests/profileSave.test.tsx
PASS tests/clientConfig.test.tsx
PASS tests/qrScreen.test.tsx
PASS tests/flows.test.tsx
PASS tests/cacheRefresh.test.tsx
PASS tests/cardScanner.test.tsx
PASS tests/homeArtwork.test.tsx
PASS tests/cityCustom.test.tsx
PASS tests/historyPeriod.test.tsx
PASS tests/avatar.test.tsx
PASS tests/wallet.test.tsx
PASS tests/serverContentAndCache.test.tsx
PASS tests/components.test.tsx
PASS tests/push.test.tsx
PASS tests/core.test.ts
PASS tests/loginScreen.test.tsx
PASS tests/promotionsArtwork.test.tsx
PASS tests/levels.test.tsx
PASS tests/session.test.ts
PASS tests/demo.test.ts
PASS tests/transport.test.ts
PASS tests/keyboardLift.test.ts

Test Suites: 23 passed, 23 total
Tests:       311 passed, 311 total
Snapshots:   0 total
Time:        24.394 s
Ran all test suites.
```

### 3.2. `npx tsc --noEmit && npx eslint .`

```
/Users/nuras/Desktop/cashback-one/mobile/src/components/useKeyboardLift.ts
  62:20  warning  The ref value 'generation.current' will likely have changed by the time this effect cleanup function runs. If this ref points to a node rendered by React, copy 'generation.current' to a variable inside the effect, and use that variable in the cleanup function  react-hooks/exhaustive-deps

✖ 1 problem (0 errors, 1 warning)
```

---

## 4. `git diff`

```diff
diff --git a/mobile/app/(app)/(tabs)/index.tsx b/mobile/app/(app)/(tabs)/index.tsx
index c290c98..488a9be 100644
--- a/mobile/app/(app)/(tabs)/index.tsx
+++ b/mobile/app/(app)/(tabs)/index.tsx
@@ -1,6 +1,6 @@
 import { TAB_BAR_HEIGHT } from '../../../src/components/TabBar';
 import { router } from 'expo-router';
-import { Alert, Linking, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
+import { Alert, Linking, Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
 import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
 import { useAppContent, useProfile, usePromotions } from '../../../src/api/app';
 import { getClientConfig } from '../../../src/config/client';
@@ -30,6 +30,16 @@ export default function Home() {
     });
   };
 
+  const isRefreshing = promotions.isRefetching || cards.isRefetching || profile.isRefetching || appContent.isRefetching;
+  const onRefresh = () => {
+    void Promise.all([
+      promotions.refetch(),
+      cards.refetch(),
+      profile.refetch(),
+      appContent.refetch(),
+    ]);
+  };
+
   const banners = promotions.data?.banners ?? [];
   const offers = promotions.data?.offers ?? [];
 
@@ -38,6 +48,13 @@ export default function Home() {
       style={local.scrollView}
       contentContainerStyle={[local.pageContent, { paddingBottom: TAB_BAR_HEIGHT + insets.bottom + 16 }]}
       showsVerticalScrollIndicator={false}
+      refreshControl={
+        <RefreshControl
+          refreshing={isRefreshing}
+          onRefresh={onRefresh}
+          tintColor={theme.colors.primary}
+        />
+      }
     >
       <FadeIn style={local.topSheet}>
         <BalanceHeader phone={phoneText(profile.data?.phone)} balance={card?.balance ?? '0'} />
diff --git a/mobile/src/api/app.ts b/mobile/src/api/app.ts
index b3b0378..71501d3 100644
--- a/mobile/src/api/app.ts
+++ b/mobile/src/api/app.ts
@@ -122,6 +122,7 @@ export function usePromotions() {
   return useQuery({
     queryKey: keys.promotions,
     initialData: () => getCachedPromotions(userId)?.data,
+    initialDataUpdatedAt: () => getCachedPromotions(userId)?.cachedAt ?? 0,
     queryFn: ({ signal }) => fetchPromotionsWithCache(api, userId, signal),
   });
 }
@@ -134,6 +135,7 @@ export function useAppContent(businessId: string | undefined) {
     queryKey: keys.appContent(effectiveBusinessId),
     enabled: !!effectiveBusinessId,
     initialData: () => (effectiveBusinessId ? getCachedAppContent(userId, effectiveBusinessId)?.data : undefined),
+    initialDataUpdatedAt: () => (effectiveBusinessId ? (getCachedAppContent(userId, effectiveBusinessId)?.cachedAt ?? 0) : 0),
     queryFn: ({ signal }) => (effectiveBusinessId ? fetchAppContentWithCache(api, userId, effectiveBusinessId, signal) : null),
   });
 }
diff --git a/mobile/src/storage/appCache.ts b/mobile/src/storage/appCache.ts
index 18a37b7..84877fc 100644
--- a/mobile/src/storage/appCache.ts
+++ b/mobile/src/storage/appCache.ts
@@ -105,9 +105,10 @@ export function setCachedAppContent(
   businessId: string,
   data: AppContent,
   etag: string | null,
+  cachedAt: number = Date.now(),
 ): void {
   const key = getAppContentCacheKey(userId, businessId);
-  const entry: CachedEntry<AppContent> = { data, etag, cachedAt: Date.now() };
+  const entry: CachedEntry<AppContent> = { data, etag, cachedAt };
   memoryCache.set(key, entry as CachedEntry<unknown>);
   void AsyncStorage.setItem(key, JSON.stringify(entry)).catch(() => {});
 }
@@ -117,9 +118,14 @@ export function getCachedPromotions(userId: string): CachedEntry<Promotions> | n
   return (memoryCache.get(key) as CachedEntry<Promotions> | undefined) ?? null;
 }
 
-export function setCachedPromotions(userId: string, data: Promotions, etag: string | null): void {
+export function setCachedPromotions(
+  userId: string,
+  data: Promotions,
+  etag: string | null,
+  cachedAt: number = Date.now(),
+): void {
   const key = getPromotionsCacheKey(userId);
-  const entry: CachedEntry<Promotions> = { data, etag, cachedAt: Date.now() };
+  const entry: CachedEntry<Promotions> = { data, etag, cachedAt };
   memoryCache.set(key, entry as CachedEntry<unknown>);
   void AsyncStorage.setItem(key, JSON.stringify(entry)).catch(() => {});
 }
```

---

## 5. Ограничения соблюдены

- Сборка APK не запускалась.
- Версии и номер сборки приложения не менялись.
- Папки `android/`, серверная часть и админка не затрагивались.
- Коммитов и push в репозиторий не выполнялось.
