# Отчёт по обновлению службы агента POSCENTERLoyaltyAgent 0.2.1 → 0.2.2

**Дата:** 24 октября 2026 г.  
**Компьютер:** Тестовый Windows-компьютер владельца (`DESKTOP-VND8ELJ` / ШОУРУМ)  
**Рабочий каталог:** `C:\Users\ШОУРУМ\Desktop\cashback-one`  
**Исполнитель:** Gemini (exe)  

---

## 1. Проверки до обновления

1. **Состояние репозитория Git:**
   - Коммит: `997b33a docs(reports): add agent 0.2.2 build and smoke test report`
   - Рабочая копия чистая (`git status --short` пуст).
2. **Проверка артефактов Setup:**
   - `Setup 0.2.2` (`C:\cashback-stage0\agent-0.2.2\CashbackOneAgent-Setup-0.2.2.exe`):
     - Размер: **14 848 654** байта (совпадает)
     - SHA-256: `4ad1126a203d5a4d410657b791de36b0b5c7a2e0bf3f0eaab67517509eedc3a5` (совпадает)
   - `Setup 0.2.1` (для отката, `C:\cashback-stage0\agent-0.2.1\CashbackOneAgent-Setup-0.2.1.exe`):
     - Размер: **14 848 591** байт (совпадает)
     - SHA-256: `032d12dd4d51d77238784217db49e06db4fdafa83a0a9ef2d55bddf93833e710` (совпадает)
3. **Состояние службы до обновления:**
   - `Get-Service POSCENTERLoyaltyAgent`: статус **`Running`**, тип запуска `Automatic`.
   - `sc.exe qc POSCENTERLoyaltyAgent`:
     - ТИП_СЛУЖБЫ: `WIN32_OWN_PROCESS`
     - ТИП_ЗАПУСКА: `AUTO_START (DELAYED)`
     - ИМЯ_ДВОИЧНОГО_ФАЙЛА: `"C:\Program Files (x86)\POSCENTER\LoyaltyAgent\CashbackOneAgent.exe" service-run`
     - УЧЕТНАЯ_ЗАПИСЬ: `LocalSystem`
4. **Версия установленного EXE до обновления:**
   ```text
   poscenter-loyalty-agent 0.2.1
   ```
5. **Метаданные файлов до обновления:**
   - `mapping\stage0_mapping.json`: размер **8377 байт**, `LastWriteTime` `19.10.2026 12:45:19`, SHA-256 `f8fec8dbd76431b58c4dad165d376c8fec8a68fc9573e5a6bc6ba70f7671d083` (совпадает с эталоном).
   - `config\.env.service`, `state\agent_state.db`, `state\agent_state.key`: защищены системными дескрипторами безопасности DACL.
6. **Хвост лога до обновления (`logs\agent.log`):**
   - Зафиксированы стабильные циклы с пропуском 7 некорректных карт (5 из-за длины < 6 знаков):
     ```text
     2026-10-24 01:33:40 [INFO] [poscenter_loyalty_agent.one_com_source] ONE read completed: type=cards_snapshot, records_read=1710, changes_to_send=0, skipped_invalid_barcode=7 (empty=0, non_digits=2, too_short=5, too_long=0), duration=1.141s
     2026-10-24 01:33:40 [INFO] [poscenter_loyalty_agent.one_com_source] ONE read completed: type=transactions_window, records_read=3, changes_to_send=0, skipped_invalid_barcode=0 (empty=0, non_digits=0, too_short=0, too_long=0), duration=0.109s
     ```

---

## 2. Создание резервной копии (Шаг 2, администратор)

1. **Остановка службы:**
   Служба `POSCENTERLoyaltyAgent` остановлена владельцем: статус **`Stopped`**.
2. **Каталог резервной копии:**
   Создан каталог:
   `C:\cashback-stage0\backup_upgrade_0_2_2_20261024_014315`
3. **Копирование `ProgramData`:**
   Выполнено через `robocopy "C:\ProgramData\POSCENTER\LoyaltyAgent" "$backupDir\ProgramData" /E /COPY:DATS /DCOPY:DAT /R:1 /W:1 /NFL /NDL`:
   - Скопировано: **6 файлов из 6**, СБОЙ: **0**.
   - Дескрипторы безопасности сохранены (`/COPY:DATS`).
4. **Копирование `Program Files (x86)`:**
   Выполнено через `robocopy "C:\Program Files (x86)\POSCENTER\LoyaltyAgent" "$backupDir\ProgramFiles" /E /COPY:DAT /R:1 /W:1 /NFL /NDL`:
   - Скопировано: **652 файла из 652**, СБОЙ: **0**.
5. **Сверка контрольных сумм и метаданных файлов до обновления:**
   | Файл | Исходный SHA-256 | SHA-256 в копии | Размер (байт) | Дата изменения | Совпадение |
   |---|---|---|---|---|---|
   | `config\.env.service` | `5EA802C7AE9B7439200935E1FB197F1516DB7380151A8EDDE48647B0064B13CB` | `5EA802C7AE9B7439200935E1FB197F1516DB7380151A8EDDE48647B0064B13CB` | 325 | 10/21/2026 11:12:31 | **True** |
   | `state\agent_state.db` | `0EE6E12072073646E7705AF8B946FCC0BD895D35CE678473345E843A37BF1B3D` | `0EE6E12072073646E7705AF8B946FCC0BD895D35CE678473345E843A37BF1B3D` | 2 572 288 | 10/24/2026 01:42:41 | **True** |
   | `state\agent_state.key` | `7559BA140C10B55DE3A6C2379C597DC62E35CEB42D78C2396BFE5DED8E737CD5` | `7559BA140C10B55DE3A6C2379C597DC62E35CEB42D78C2396BFE5DED8E737CD5` | 32 | 10/19/2026 18:19:44 | **True** |
   | `mapping\stage0_mapping.json` | `F8FEC8DBD76431B58C4DAD165D376C8FEC8A68FC9573E5A6BC6BA70F7671D083` | `F8FEC8DBD76431B58C4DAD165D376C8FEC8A68FC9573E5A6BC6BA70F7671D083` | 8377 | 10/19/2026 12:45:19 | **True** |

   *Все эталонные контрольные суммы совпали на 100%.*

---

## 3. Установка версии 0.2.2 (Шаг 3)

1. Запущен инсталлятор `C:\cashback-stage0\agent-0.2.2\CashbackOneAgent-Setup-0.2.2.exe`.
2. В мастере обновления выбран режим по умолчанию:  
   **«Сохранить существующие настройки подключения и синхронизации (Рекомендуется)»**.  
   Поля подключения и параметры строк не изменялись.
3. Установщик заменил файлы в `C:\Program Files (x86)\POSCENTER\LoyaltyAgent\`, сохранил базу состояния и настройки в `C:\ProgramData\POSCENTER\LoyaltyAgent\`, и запустил службу `POSCENTERLoyaltyAgent`.

---

## 4. Проверки после обновления (Шаг 4)

1. **Статус службы:**
   - `Get-Service POSCENTERLoyaltyAgent`: **`Running`**, `StartType: Automatic`.
   - `sc.exe qc POSCENTERLoyaltyAgent`:
     - ТИП_ЗАПУСКА: `AUTO_START (DELAYED)`
     - ИМЯ_ДВОИЧНОГО_ФАЙЛА: `"C:\Program Files (x86)\POSCENTER\LoyaltyAgent\CashbackOneAgent.exe" service-run`
     - УЧЕТНАЯ_ЗАПИСЬ: `LocalSystem`
2. **Версия установленного EXE:**
   ```text
   poscenter-loyalty-agent 0.2.2
   ```
3. **Сверка контрольных сумм после обновления:**
   - `config\.env.service`: `5EA802C7AE9B7439200935E1FB197F1516DB7380151A8EDDE48647B0064B13CB` — **совпадает побайтно (Match: True)**;
   - `state\agent_state.key`: `7559BA140C10B55DE3A6C2379C597DC62E35CEB42D78C2396BFE5DED8E737CD5` — **совпадает побайтно (Match: True)**;
   - `mapping\stage0_mapping.json`: `F8FEC8DBD76431B58C4DAD165D376C8FEC8A68FC9573E5A6BC6BA70F7671D083` — **совпадает побайтно (Match: True)**;
   - `state\agent_state.db`: размер **2 572 288 байт** (идентичен копии).
4. **Статус агента (`CashbackOneAgent.exe status`):**
   ```text
   === POSCENTER Loyalty Agent Operational Status ===
   State DB Path:                 C:\ProgramData\POSCENTER\LoyaltyAgent\state\agent_state.db
   Cards Cursor Status:           set
   Transactions Cursor Status:    set
   Last Successful Sync:          2026-10-23 20:47:34.623521+00:00
   Last Heartbeat:                2026-10-23 20:50:16.218497+00:00
   Last Error:                    (none)
   POS-сервис: выключен, 0.0.0.0:8765
   ```
   - Курсоры карт и транзакций сохранены: **`set`**.
   - Время успешной синхронизации обновилось в момент отправки 3 новых карт (`20:47:34 UTC`).
   - Ошибок нет: `Last Error: (none)`.
   - `POS-сервис: выключен, 0.0.0.0:8765`.
5. **Проверка портов:**
   - Порт 8765: **не слушается** (`Get-NetTCPConnection` вернул пустоту).
   - Порт 18765: **не слушается**.
6. **Наблюдение за работой службы (более 12 минут):**
   - Время старта версии 0.2.2: **`2026-10-24 01:47:14`**.
   - Лог старта службы:
     ```text
     2026-10-24 01:47:14 [INFO] [poscenter_loyalty_agent.windows_service] Starting POSCENTERLoyaltyAgent via Windows Service Manager...
     2026-10-24 01:47:14 [INFO] [poscenter_loyalty_agent.one_mapping] Field 'balance_after' is CANDIDATE: enabled via sequential calculation
     2026-10-24 01:47:14 [INFO] [poscenter_loyalty_agent.one_mapping] Field 'receipt_ref' is CANDIDATE: enabled for ...
     2026-10-24 01:47:14 [INFO] [poscenter_loyalty_agent.one_mapping] Field 'store' is CANDIDATE: enabled for ...
     2026-10-24 01:47:14 [INFO] [poscenter_loyalty_agent.runtime] Starting POSCENTER Loyalty Agent v0.2.2 (adapter_mode=com, interval=300s)
     ```
   - Строка `POS service started` **отсутствует** (POS-сервис штатно выключен).

   - **Цикл 1 (01:47:34):**
     ```text
     2026-10-24 01:47:34 [INFO] [poscenter_loyalty_agent.one_com_source] ONE read completed: type=cards_snapshot, records_read=1710, changes_to_send=3, skipped_invalid_barcode=4 (empty=0, non_digits=2, too_short=2, too_long=0), duration=18.687s
     2026-10-24 01:47:34 [INFO] [poscenter_loyalty_agent.runtime] Syncing 3 cards (page=1/10, stream=cards)
     2026-10-24 01:47:34 [INFO] [poscenter_loyalty_agent.runtime] Cards ACK received: 3 created, 0 updated, 0 stale ignored
     2026-10-24 01:47:34 [INFO] [poscenter_loyalty_agent.one_com_source] ONE read completed: type=transactions_window, records_read=3, changes_to_send=0, skipped_invalid_barcode=0 (empty=0, non_digits=0, too_short=0, too_long=0), duration=0.250s
     ```

   - **Цикл 2 (01:52:36):**
     ```text
     2026-10-24 01:52:36 [INFO] [poscenter_loyalty_agent.one_com_source] ONE read completed: type=cards_snapshot, records_read=1710, changes_to_send=0, skipped_invalid_barcode=4 (empty=0, non_digits=2, too_short=2, too_long=0), duration=1.906s
     2026-10-24 01:52:37 [INFO] [poscenter_loyalty_agent.one_com_source] ONE read completed: type=transactions_window, records_read=3, changes_to_send=0, skipped_invalid_barcode=0 (empty=0, non_digits=0, too_short=0, too_long=0), duration=0.187s
     ```

   - **Цикл 3 (01:57:38):**
     ```text
     2026-10-24 01:57:38 [INFO] [poscenter_loyalty_agent.one_com_source] ONE read completed: type=cards_snapshot, records_read=1710, changes_to_send=0, skipped_invalid_barcode=4 (empty=0, non_digits=2, too_short=2, too_long=0), duration=1.890s
     2026-10-24 01:57:39 [INFO] [poscenter_loyalty_agent.one_com_source] ONE read completed: type=transactions_window, records_read=3, changes_to_send=0, skipped_invalid_barcode=0 (empty=0, non_digits=0, too_short=0, too_long=0), duration=0.094s
     ```

### 4.1. Анализ результатов применения порога длины 4–13 цифр

- **В версии 0.2.1:** пропускалось 7 карт: `skipped_invalid_barcode=7 (empty=0, non_digits=2, too_short=5, too_long=0)`.
- **В версии 0.2.2:** пропускается 4 карты: `skipped_invalid_barcode=4 (empty=0, non_digits=2, too_short=2, too_long=0)`.
- **Что произошло с 5 ранее отбрасываемыми картами:**
  1. Ровно **3 карты** имели длину от 4 до 5 цифр. Они были успешно распознаны валидатором 0.2.2 и переданы в облако: `changes_to_send=3`, `Syncing 3 cards`, `Cards ACK received: 3 created`.
  2. Оставшиеся **2 карты** имеют длину менее 4 цифр (1–3 цифры), поэтому они продолжают корректно отфильтровываться: `too_short=2`.
  3. Еще **2 карты** содержат нецифровые символы: `non_digits=2`.
- В последующих циклах дельта карт пустая (`changes_to_send=0`).
- Окно транзакций во всех циклах прочитано штатно (`changes_to_send=0, skipped_invalid_barcode=0`), ошибок нет.
- Ошибки синхронизации, `422`, `CloudNonRetryableError` и Traceback полностью отсутствуют.

---

## 5. План отката (на случай необходимости)

В случае необходимости откат на версию 0.2.1 выполняется следующими действиями в PowerShell от имени администратора:
1. Запуск инсталлятора 0.2.1:
   `Start-Process -FilePath "C:\cashback-stage0\agent-0.2.1\CashbackOneAgent-Setup-0.2.1.exe"`
   с выбором пункта **«Сохранить существующие настройки подключения и синхронизации (Рекомендуется)»**.
2. В случае необходимости восстановления базы состояния из бэкапа:
   ```powershell
   Stop-Service POSCENTERLoyaltyAgent
   robocopy "C:\cashback-stage0\backup_upgrade_0_2_2_20261024_014315\ProgramData" "C:\ProgramData\POSCENTER\LoyaltyAgent" /E /COPY:DATS /DCOPY:DAT /R:1 /W:1 /NFL /NDL
   Start-Service POSCENTERLoyaltyAgent
   ```

---

## 6. Список «не проверено»

1. **Облачная сторона (VPS):**
   - Отображение версии агента `0.2.2` в heartbeat на сервере;
   - Фиксация свежего `last_seen_at` и увеличение количества карт до **1707** (было 1704 + 3 новые карты).  
   *(Проверяется куратором через SQL READ ONLY на `kz-vps`, так как агент к серверу прямого доступа не имеет)*.
2. **Перезагрузка операционной системы Windows:**
   - Автоматический запуск службы после перезагрузки ОС (ранее подтверждался для версий 0.1.0, 0.2.0, 0.2.1).
3. **Кассовый сценарий:**
   - Закрытие смены на кассе POSCENTER Cash и поступление реальных новых движений в ONE.
4. **Сетевой доступ к POS-серверу:**
   - Взаимодействие с кассами по локальной сети (POS-сервис штатно выключен).
