# Отчёт по обновлению службы агента POSCENTERLoyaltyAgent 0.2.0 → 0.2.1

**Дата:** 23 октября 2026 г.  
**Компьютер:** Тестовый Windows-компьютер владельца (`DESKTOP-VND8ELJ` / ШОУРУМ)  
**Рабочий каталог:** `C:\Users\ШОУРУМ\Desktop\cashback-one`  
**Исполнитель:** Gemini (exe)  

---

## 1. Проверки до обновления

1. **Состояние репозитория Git:**
   - Коммит: `fe444a0 docs: Windows agent 0.2.0 -> 0.2.1 upgrade prompt`
   - Рабочая копия чистая (`git status --short` пуст).
2. **Проверка артефактов Setup:**
   - `Setup 0.2.1` (`C:\cashback-stage0\agent-0.2.1\CashbackOneAgent-Setup-0.2.1.exe`):
     - Размер: **14 848 591** байт (совпадает)
     - SHA-256: `032d12dd4d51d77238784217db49e06db4fdafa83a0a9ef2d55bddf93833e710` (совпадает)
   - `Setup 0.2.0` (для отката, `C:\cashback-stage0\agent-0.2.0\CashbackOneAgent-Setup-0.2.0.exe`):
     - Размер: **14 848 085** байт (совпадает)
     - SHA-256: `fe5b799f246250dccf1d731ba3d0efdc9b3e3e03fab7617e70468afffc761ce0` (совпадает)
3. **Состояние службы до обновления:**
   - `Get-Service POSCENTERLoyaltyAgent`: статус **`Running`**, тип запуска `Automatic`.
   - `sc.exe qc POSCENTERLoyaltyAgent`:
     - ТИП_СЛУЖБЫ: `WIN32_OWN_PROCESS`
     - ТИП_ЗАПУСКА: `AUTO_START (DELAYED)`
     - ИМЯ_ДВОИЧНОГО_ФАЙЛА: `"C:\Program Files (x86)\POSCENTER\LoyaltyAgent\CashbackOneAgent.exe" service-run`
     - УЧЕТНАЯ_ЗАПИСЬ: `LocalSystem`
4. **Версия установленного EXE до обновления:**
   ```text
   poscenter-loyalty-agent 0.2.0
   ```
5. **Метаданные файлов до обновления:**
   - `mapping\stage0_mapping.json`: размер **8377 байт**, `LastWriteTime` `19.10.2026 12:45:19`, SHA-256 `f8fec8dbd76431b58c4dad165d376c8fec8a68fc9573e5a6bc6ba70f7671d083` (совпадает с эталоном).
   - `config\.env.service`, `state\agent_state.db`, `state\agent_state.key`: защищены системными DACL LocalSystem/Administrators.
6. **Хвост лога до обновления (`logs\agent.log`):**
   - Зафиксированы стабильные регулярные циклы чтения без ошибок:
     ```text
     2026-10-23 17:43:19 [INFO] [poscenter_loyalty_agent.one_com_source] ONE read completed: type=cards_snapshot, records_read=1710, changes_to_send=0, duration=1.641s
     2026-10-23 17:43:19 [INFO] [poscenter_loyalty_agent.one_com_source] ONE read completed: type=transactions_window, records_read=3, changes_to_send=0, duration=0.266s
     2026-10-23 17:48:20 [INFO] [poscenter_loyalty_agent.one_com_source] ONE read completed: type=cards_snapshot, records_read=1710, changes_to_send=0, duration=1.110s
     2026-10-23 17:48:21 [INFO] [poscenter_loyalty_agent.one_com_source] ONE read completed: type=transactions_window, records_read=3, changes_to_send=0, duration=0.156s
     ```

---

## 2. Создание резервной копии (Шаг 2, администратор)

1. **Остановка службы:**
   Служба `POSCENTERLoyaltyAgent` остановлена владельцем: статус **`Stopped`**.
2. **Каталог резервной копии:**
   Создан каталог:
   `C:\cashback-stage0\backup_upgrade_0_2_1_20261023_175236`
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
   | `state\agent_state.db` | `282EF563C98B0A2A454AF1E588062643504C3C709BA961BC003D6E6CA9B86022` | `282EF563C98B0A2A454AF1E588062643504C3C709BA961BC003D6E6CA9B86022` | 2 572 288 | 10/23/2026 17:52:10 | **True** |
   | `state\agent_state.key` | `7559BA140C10B55DE3A6C2379C597DC62E35CEB42D78C2396BFE5DED8E737CD5` | `7559BA140C10B55DE3A6C2379C597DC62E35CEB42D78C2396BFE5DED8E737CD5` | 32 | 10/19/2026 18:19:44 | **True** |
   | `mapping\stage0_mapping.json` | `F8FEC8DBD76431B58C4DAD165D376C8FEC8A68FC9573E5A6BC6BA70F7671D083` | `F8FEC8DBD76431B58C4DAD165D376C8FEC8A68FC9573E5A6BC6BA70F7671D083` | 8377 | 10/19/2026 12:45:19 | **True** |

   *Все эталонные контрольные суммы совпали на 100%.*

---

## 3. Установка версии 0.2.1 (Шаг 3)

1. Запущен инсталлятор `C:\cashback-stage0\agent-0.2.1\CashbackOneAgent-Setup-0.2.1.exe`.
2. В мастере обновления выбран рекомендованный режим:  
   **«Сохранить существующие настройки подключения и синхронизации (Рекомендуется)»**.  
   Поля подключения и пароли не запрашивались и не менялись.
3. Установщик заменил файлы в `C:\Program Files (x86)\POSCENTER\LoyaltyAgent\`, сохранил конфигурацию и базу данных состояния, и запустил службу `POSCENTERLoyaltyAgent`.

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
   poscenter-loyalty-agent 0.2.1
   ```
3. **Сверка контрольных сумм после обновления:**
   - `config\.env.service`: `5EA802C7AE9B7439200935E1FB197F1516DB7380151A8EDDE48647B0064B13CB` — **совпадает побайтно (Match: True)**;
   - `state\agent_state.key`: `7559BA140C10B55DE3A6C2379C597DC62E35CEB42D78C2396BFE5DED8E737CD5` — **совпадает побайтно (Match: True)**;
   - `mapping\stage0_mapping.json`: `F8FEC8DBD76431B58C4DAD165D376C8FEC8A68FC9573E5A6BC6BA70F7671D083` — **совпадает побайтно (Match: True)**;
   - `state\agent_state.db`: размер **2 572 288 байт** (идентичен копии, файл удерживается блокировкой SQLite запущенной службы).
4. **Статус агента (`CashbackOneAgent.exe status`):**
   ```text
   === POSCENTER Loyalty Agent Operational Status ===
   State DB Path:                 C:\ProgramData\POSCENTER\LoyaltyAgent\state\agent_state.db
   Cards Cursor Status:           set
   Transactions Cursor Status:    set
   Last Successful Sync:          2026-10-19 15:42:09.959806+00:00
   Last Heartbeat:                2026-10-23 12:57:22.592917+00:00
   Last Error:                    (none)
   POS-сервис: выключен, 0.0.0.0:8765
   ```
   - Курсоры карт и транзакций сохранены: **`set`**.
   - Ошибок нет: `Last Error: (none)`.
   - `POS-сервис: выключен, 0.0.0.0:8765`.
5. **Проверка портов:**
   - Порт 8765: **не слушается** (`Get-NetTCPConnection` вернул пустоту).
   - Порт 18765: **не слушается**.
6. **Наблюдение за работой службы (более 12 минут):**
   - Время старта версии 0.2.1: **`2026-10-23 17:56:21`**.
   - Лог старта службы:
     ```text
     2026-10-23 17:56:21 [INFO] [poscenter_loyalty_agent.windows_service] Starting POSCENTERLoyaltyAgent via Windows Service Manager...
     2026-10-23 17:56:21 [INFO] [poscenter_loyalty_agent.one_mapping] Field 'balance_after' is CANDIDATE: enabled via sequential calculation
     2026-10-23 17:56:21 [INFO] [poscenter_loyalty_agent.one_mapping] Field 'receipt_ref' is CANDIDATE: enabled for ...
     2026-10-23 17:56:21 [INFO] [poscenter_loyalty_agent.one_mapping] Field 'store' is CANDIDATE: enabled for ...
     2026-10-23 17:56:21 [INFO] [poscenter_loyalty_agent.runtime] Starting POSCENTER Loyalty Agent v0.2.1 (adapter_mode=com, interval=300s)
     ```
   - Строка `POS service started` **отсутствует** (POS-сервис штатно выключен).
   - **Цикл 1 (17:56:43):**
     - `cards_snapshot`: `ONE read completed: type=cards_snapshot, records_read=1710, changes_to_send=0, skipped_invalid_barcode=7 (empty=0, non_digits=2, too_short=5, too_long=0), duration=20.984s`
     - `transactions_window`: `ONE read completed: type=transactions_window, records_read=3, changes_to_send=0, skipped_invalid_barcode=0 (empty=0, non_digits=0, too_short=0, too_long=0), duration=0.250s`
   - **Цикл 2 (18:01:46):**
     - `cards_snapshot`: `ONE read completed: type=cards_snapshot, records_read=1710, changes_to_send=0, skipped_invalid_barcode=7 (empty=0, non_digits=2, too_short=5, too_long=0), duration=2.421s`
     - `transactions_window`: `ONE read completed: type=transactions_window, records_read=3, changes_to_send=0, skipped_invalid_barcode=0 (empty=0, non_digits=0, too_short=0, too_long=0), duration=0.110s`
   - **Цикл 3 (18:06:47):**
     - `cards_snapshot`: `ONE read completed: type=cards_snapshot, records_read=1710, changes_to_send=0, skipped_invalid_barcode=7 (empty=0, non_digits=2, too_short=5, too_long=0), duration=1.579s`
     - `transactions_window`: `ONE read completed: type=transactions_window, records_read=3, changes_to_send=0, skipped_invalid_barcode=0 (empty=0, non_digits=0, too_short=0, too_long=0), duration=0.110s`
   - **Результаты проверки нововведений 0.2.1 на боевой ONE:**
     - Новый формат агрегатов пропущенных штрихкодов подтверждён: во всех трёх циклах зафиксировано ровно **`skipped_invalid_barcode=7 (empty=0, non_digits=2, too_short=5, too_long=0)`**.
     - Чтение транзакций из реальной базы 1С ONE прошло без ошибок во всех трёх циклах: новая проверка `datetime` типа даты периода успешно пропускает данные. Ошибок `SourceProtocolError` нет.
     - Ошибки и Traceback в логе полностью отсутствуют.

---

## 5. План отката (на случай необходимости)

В случае необходимости откат на версию 0.2.0 выполняется следующими действиями в PowerShell от имени администратора:
1. Запуск инсталлятора 0.2.0:
   `Start-Process -FilePath "C:\cashback-stage0\agent-0.2.0\CashbackOneAgent-Setup-0.2.0.exe"`
   с выбором пункта **«Сохранить существующие настройки подключения и синхронизации (Рекомендуется)»**.
2. В случае необходимости восстановления файлов состояния из бэкапа:
   ```powershell
   Stop-Service POSCENTERLoyaltyAgent
   robocopy "C:\cashback-stage0\backup_upgrade_0_2_1_20261023_175236\ProgramData" "C:\ProgramData\POSCENTER\LoyaltyAgent" /E /COPY:DATS /DCOPY:DAT /R:1 /W:1 /NFL /NDL
   Start-Service POSCENTERLoyaltyAgent
   ```

---

## 6. Список «не проверено»

1. **Облачная сторона (VPS):**
   - Отображение версии агента `0.2.1` в heartbeat на сервере;
   - Фиксация свежего `last_seen_at` и сохранение количества карт/операций (1704/9747).  
   *(Проверяется куратором через SQL READ ONLY на `kz-vps`, так как агент к серверу напрямую доступ не имеет)*.
2. **Перезагрузка операционной системы Windows:**
   - Автоматический запуск службы после перезагрузки ОС (ранее подтверждался для версий 0.1.0 и 0.2.0).
3. **Кассовый сценарий:**
   - Закрытие смены на кассе POSCENTER Cash и поступление реальных новых движений в ONE.
4. **Сетевой доступ к POS-серверу:**
   - Взаимодействие с внешними кассами по локальной сети при включённом POS-сервисе (сервис в данной конфигурации штатно выключен).
