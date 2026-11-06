# Отчёт по восстановлению данных бизнеса `test` в состояние до 04.11

**Дата:** 6 ноября 2026 г.  
**Инструкция:** `docs/PROMPT_TEST_BUSINESS_RESTORE_2026-11-05.md` (+ Дополнение 1)  
**Сервер:** `ssh kz-vps`, проект `/opt/cashback-one`  
**Исполнитель:** Gemini (VPS)  

---

## 1. Свежая резервная копия базы (Шаг 1)

- **Путь:** `/opt/cashback-one/backups/test-restore-20261106T074533Z/pg.sql.gz`
- **Размер:** 722 787 байт
- **Проверка целостности (`gzip -t`):** Успешно (код возврата 0).
- **Команда создания:**
  ```bash
  docker exec cashback-postgres sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > /opt/cashback-one/backups/test-restore-20261106T074533Z/pg.sql.gz
  ```

---

## 2. Извлечение данных из копии от 02.11 (Шаг 2)

- **Исходный дамп:** `/opt/cashback-one/backups/cors-delete-20261102T063701Z/pg.sql.gz` (620 513 байт, `gzip -t` пройден).
- **Контейнер:** временный изолированный `postgres:16` с флагом `--network none` (без монтирования томов хоста).
- **Ожидание готовности:** цикл проверки `psql -c "SELECT 1"` каждые 2 секунды (контейнер готов через 8 секунд).
- **Выгрузка CSV:** 1710 строк карт бизнеса `test` (1 строка заголовка + 1710 строк данных = 1711 строк). Файл сохранён с правами `600`.
- **Очистка контейнера:** временный контейнер `pg-temp-restore` немедленно удалён (`docker rm -f`).

---

## 3. Проверка состояния до изменений (Шаг 3, Read Only)

Все проверки выполнены без изменений production.

### 3.1. Операции бизнеса `test` в диапазоне `[2026-11-04 08:00, 09:00)` UTC
```text
 count_tx_in_range | count_occurred_20261030 | count_occurred_other 
-------------------+-------------------------+----------------------
              1661 |                    1661 |                    0
```
- Ровно **1661** операция, у всех `occurred_at::date = 2026-10-30`.

### 3.2. Внешние ключи на `transactions`
```text
 referencing_fk_count 
----------------------
                    0
```
- Ссылок на данные операции нет (0).

### 3.3. Карты бизнеса `test` с `updated_at` в `[2026-11-04 07:00, 08:00)` UTC
```text
 count_target_cards | count_found_in_backup | count_missing_in_backup 
--------------------+-----------------------+-------------------------
               1703 |                  1703 |                       0
```
- Ровно **1703** карты, все 1703 присутствуют в CSV копии от 02.11 по `id`.

### 3.4. Расхождения по столбцам у 1703 карт
```text
 diff_balance | diff_spend_total | diff_phone | diff_full_name | diff_is_blocked | diff_barcode 
--------------+------------------+------------+----------------+-----------------+--------------
         1676 |                0 |          0 |              0 |               0 |            0
```
- У 1676 карт изменился `balance`. Поля `spend_total`, `phone`, `full_name`, `is_blocked`, `barcode` не изменялись.

### 3.5. Карта с `updated_at` 2026-11-04 11:00 UTC
```text
 exists_in_prod | exists_in_backup |        prod_updated_at        
----------------+------------------+-------------------------------
 t              | f                | 2026-11-04 11:08:00.527907+00
```
- В копии отсутствует (новая карта, созданная 04.11). Не изменялась.

### 3.6. Общие количества
```text
 test_cards_prod | test_cards_backup | test_tx_prod | test_tx_backup (расчёт)
-----------------+-------------------+--------------+------------------------
            1711 |              1710 |        11411 |                   9750
```
- Разница по картам: ровно 1 карта (созданная 04.11 в 11:08).
- Разница по операциям: ровно 1661 (`11411 - 1661 = 9750`).

### 3.7. Суммы баланса 1703 карт до изменения
```text
 prod_target_balance_sum | backup_target_balance_sum 
-------------------------+---------------------------
             414859.0000 |                -6281.0000
```

---

## 4. Изменение одной транзакцией (Шаг 4)

### 4.1. SQL-скрипт изменения (без вывода персональных данных)
```sql
BEGIN;

CREATE TEMP TABLE cards_0211 (LIKE cards INCLUDING ALL) ON COMMIT DROP;
COPY cards_0211 FROM '/tmp/test_cards_0211.csv' WITH CSV HEADER;

CREATE TEMP TABLE target_card_ids (id uuid PRIMARY KEY) ON COMMIT DROP;
INSERT INTO target_card_ids (id)
SELECT c.id
FROM cards c
JOIN businesses b ON c.business_id = b.id
WHERE b.name = 'test'
  AND c.updated_at >= '2026-11-04 07:00:00+00'
  AND c.updated_at < '2026-11-04 08:00:00+00';

-- 1. Удаление 1661 ошибочной операции
WITH deleted_tx AS (
    DELETE FROM transactions t
    USING cards c, businesses b
    WHERE t.card_id = c.id
      AND c.business_id = b.id
      AND b.name = 'test'
      AND t.created_at >= '2026-11-04 08:00:00+00'
      AND t.created_at < '2026-11-04 09:00:00+00'
    RETURNING t.id
)
SELECT count(*) AS deleted_tx_count FROM deleted_tx \gset

-- 2. Восстановление всех полей (кроме id) для 1703 карт из копии
WITH updated_cards AS (
    UPDATE cards c
    SET 
        business_id = bk.business_id,
        barcode = bk.barcode,
        phone = bk.phone,
        full_name = bk.full_name,
        balance = bk.balance,
        is_blocked = bk.is_blocked,
        updated_at = bk.updated_at,
        spend_total = bk.spend_total
    FROM cards_0211 bk
    JOIN target_card_ids t ON bk.id = t.id
    WHERE c.id = bk.id
    RETURNING c.id
)
SELECT count(*) AS updated_cards_count FROM updated_cards \gset

-- 3. Проверки перед фиксацией
SELECT 
    :deleted_tx_count AS deleted_tx_count,
    :updated_cards_count AS updated_cards_count,
    (SELECT count(*) FROM transactions t JOIN cards c ON t.card_id = c.id JOIN businesses b ON c.business_id = b.id WHERE b.name = 'test') AS test_tx_count,
    (SELECT count(*) FROM cards c JOIN businesses b ON c.business_id = b.id WHERE b.name = 'test') AS test_cards_count,
    (SELECT sum(c.balance) FROM cards c JOIN target_card_ids t ON c.id = t.id) AS target_balance_sum_in_prod,
    (SELECT sum(bk.balance) FROM cards_0211 bk JOIN target_card_ids t ON bk.id = t.id) AS target_balance_sum_in_backup,
    (SELECT max(c.updated_at) FROM cards c JOIN businesses b ON c.business_id = b.id WHERE b.name = 'test') AS max_cards_updated_at,
    (SELECT max(t.created_at) FROM transactions t JOIN cards c ON t.card_id = c.id JOIN businesses b ON c.business_id = b.id WHERE b.name = 'test') AS max_tx_created_at;

SELECT b.name AS business, count(a.id) AS agent_count
FROM businesses b
LEFT JOIN agents a ON a.business_id = b.id
GROUP BY b.name
ORDER BY b.name;

SELECT 
    (SELECT count(*) FROM cards c JOIN businesses b ON c.business_id = b.id WHERE b.name = 'keremet') AS keremet_cards,
    (SELECT count(*) FROM transactions t JOIN cards c ON t.card_id = c.id JOIN businesses b ON c.business_id = b.id WHERE b.name = 'keremet') AS keremet_tx;

COMMIT;
```

### 4.2. Результаты проверок внутри транзакции (предварительный ROLLBACK и итоговый COMMIT)
```text
 deleted_tx_count | updated_cards_count | test_tx_count | test_cards_count | target_balance_sum_in_prod | target_balance_sum_in_backup |     max_cards_updated_at      |       max_tx_created_at       
------------------+---------------------+---------------+------------------+----------------------------+------------------------------+-------------------------------+-------------------------------
             1661 |                1703 |          9750 |             1711 |                 -6281.0000 |                   -6281.0000 | 2026-11-04 11:08:00.527907+00 | 2026-10-24 06:14:59.675301+00
```
- Агенты: `keremet` — 1, `test` — 1.
- Бизнес `keremet`: 3 карты, 0 операций (без изменений).
- Транзакция успешно зафиксирована (`COMMIT`).

---

## 5. Проверка после изменений (Шаг 5, Read Only)

### 5.1. Операции бизнеса `test` в диапазоне 08:00–09:00 UTC
```text
 count_tx_in_range: 0
```

### 5.2. Карты бизнеса `test` в диапазоне 07:00–08:00 UTC
```text
 count_cards_in_0700_range: 0
```

### 5.3. Сверка всех 1710 карт с копией от 02.11
```text
 diff_balance | diff_spend_total | diff_phone | diff_full_name | diff_is_blocked | diff_barcode | diff_updated_at 
--------------+------------------+------------+----------------+-----------------+--------------+-----------------
            0 |                0 |          0 |              0 |               0 |            0 |               0
```
- Полное совпадение (0 расхождений) по всем столбцам для всех 1710 карт из бэкапа.

### 5.4. Карта от 11:08 UTC
```text
 count_1100_card: 1
 max_1100_updated_at: 2026-11-04 11:08:00.527907+00
```

### 5.5. Итоговые счётчики
```text
 test_cards | test_tx | keremet_cards | keremet_tx 
------------+---------+---------------+------------
       1711 |    9750 |             3 |          0
```

---

## 6. Проверка кеша Redis (Шаг 6)

- Анализ кодовой базы (`backend/app`): Redis используется исключительно для:
  1. Rate limiter (`app.services.rate_limiter.RedisRateLimiter`) по IP и маршрутам.
  2. Health check (`app.api.health.check_redis_readiness`).
- Маршруты `GET /customer/profile`, `GET /customer/cards/*` и балансы покупателей **не кешируются** в Redis и запрашиваются напрямую из PostgreSQL при каждом обращении.
- Сброс Redis не требуется.

---

## 7. Удаление временных файлов (Шаг 7)

- Файлы CSV удалены безвозвратно:
  - внутри контейнера `cashback-postgres`: `/tmp/test_cards_0211.csv` удалён;
  - на хосте: `/opt/cashback-one/backups/test-restore-20261106T074533Z/test_cards_0211.csv` удалён через `shred -u`.
- В каталоге остался только дамп:
  `/opt/cashback-one/backups/test-restore-20261106T074533Z/pg.sql.gz` (722 787 байт).

---

## 8. Процедура отката (Rollback)

В случае необходимости отката изменений:
```bash
zcat /opt/cashback-one/backups/test-restore-20261106T074533Z/pg.sql.gz | docker exec -i cashback-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```
